"""Claude Code hook: no pull request is marked ready for review until the reviewers pass it.

    review_gate.py record   SubagentStop, for the reviewer and data-reviewer subagents. Saves
                            the verdict against the commit it reviewed.
    review_gate.py gate     PreToolUse. Blocks opening a PR that isn't a draft, and blocks
                            marking a PR ready or merging it until the current commit has
                            passed review: by the reviewer always, and by the data-reviewer too
                            when the branch touches the data layer or server config. Merges
                            must be merge commits of that exact commit, with green CI on it.
                            Also blocks posting the review-gate marker (the review summary the
                            GitHub check looks for) until the same review has passed.

Claude Code sends the event as JSON on stdin. Exit code 2 blocks, and stderr tells Claude why.
Any other failure would let the tool call through, so the gate turns its own errors into blocks.
Verdicts are kept in .git/claude-review/, so they are never committed. Standard library only,
so the hook runs with any python3.
"""

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path

MAX_ROUNDS = 3
BLOCK = 2
REVIEWER = "reviewer"
DATA_REVIEWER = "data-reviewer"
REVIEWERS = (REVIEWER, DATA_REVIEWER)
# Changes to any of these need the data-reviewer as well. fnmatch's * also matches /.
DATA_PATHS = (
    "wca_data/*",
    "tests/wca_data/*",
    "deploy/*",
    "*.sql",
    "Dockerfile",
    "*compose*.y*ml",
    "Caddyfile*",
    "*.service",
    "*.timer",
)
GITHUB_API = "https://api.github.com"
CI_PASSES = {"success", "skipped", "neutral"}
LOOP = "See 'Review loop' in CLAUDE.md."

# Fail closed: anything that looks like marking ready is gated, even a quoted mention.
# A false block only costs a retry; a missed one skips the review.
# Each "pr ready" is exempt only if its own part of the command (up to ; & | or #) says --undo.
# gh accepts -R/--repo between "pr" and the subcommand.
PR = r"\bpr\s+(?:(?:-R|--repo)(?:=|\s+)\S+\s+)*"
GH_READY = re.compile(PR + r"ready\b([^;&|#\n]*)")
GRAPHQL_READY = "markPullRequestReadyForReview"
GH_MERGE = re.compile(PR + r"merge\b([^;&|#\n]*)")
# Merges the gate can't check for method and pinned head, so they are always blocked.
API_MERGE = re.compile(
    r"mergePullRequest|mergeBranch|pulls/[^/\s]+/merge\b|repos/[^/\s]+/[^/\s]+/merges\b"
)
API_AUTO_MERGE = "enablePullRequestAutoMerge"
GH_CREATE = re.compile(r"\bgh\b.*\bpr\s+create\b", re.DOTALL)
SEPARATORS = {";", "&", "&&", "|", "||", "\n", "(", ")"}
DRAFT_FLAGS = {"--draft", "-d", "--draft=true"}
VERDICT = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
# The line the Review gate workflow (.github/scripts/review_check.py) looks for in a PR review.
# Matched loosely, so a marker the gate can't read (such as a sha from $(git rev-parse HEAD))
# is caught and blocked rather than let through.
MARKER = re.compile(r"review-gate\W*passed\s*([^\s<>-]*)", re.IGNORECASE)
SHA = re.compile(r"[0-9a-f]{40}")
# A review posted from the shell may take its body from a file the gate can't see. So gh pr
# review, and every gh api call that can write, count as posting a review. gh api writes when
# it is sent graphql, a field or an input file (in any spelling), or a writing method.
GH_REVIEW = re.compile(PR + r"review\b")
GH_API = re.compile(r"\bapi\b")
API_WRITE = re.compile(
    r"\bgraphql\b"
    r"|(?:^|\s)(?:-[fF]|--field|--raw-field|--input)"
    r"|(?:^|\s)(?:-X|--method)[\s=]*['\"]?(?:POST|PUT|PATCH|DELETE)",
    re.IGNORECASE,
)
# The MCP tools that post text the Review gate workflow could read as a marker.
POSTS_TEXT = ("__pull_request_review_write", "__add_issue_comment")


def git(cwd, *args):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def block(message):
    print(message, file=sys.stderr)
    sys.exit(BLOCK)


def state_file(cwd):
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    folder = Path(git(cwd, "rev-parse", "--absolute-git-dir")) / "claude-review"
    return folder / (branch.replace("/", "__") + ".json")


def load_rounds(cwd):
    path = state_file(cwd)
    return json.loads(path.read_text())["rounds"] if path.exists() else []


def save_round(cwd, round_):
    path = state_file(cwd)
    rounds = load_rounds(cwd) + [round_]
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"rounds": rounds}, indent=2))


# --- record ---


def parse_verdict(message):
    blocks = VERDICT.findall(message or "")
    if not blocks:
        return None
    try:
        verdict = json.loads(blocks[-1])
    except json.JSONDecodeError:
        return None
    keys = ("blocking", "suggestions", "judgment_calls")
    if not isinstance(verdict, dict) or not all(isinstance(verdict.get(k), list) for k in keys):
        return None
    return verdict


def transcript_report(path):
    """The reviewer's final report, read from its own transcript. Cloud sessions' SubagentStop
    event carries no last_assistant_message; the reviewer hands its report back through a
    SubagentHandback tool call instead of a closing text message, so that is read here as the
    message of last resort, in transcript order so the latest one wins."""
    if not path:
        return None
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        return None
    message = None
    for line in lines:
        try:
            content = json.loads(line).get("message", {}).get("content")
        except json.JSONDecodeError:
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                message = block["text"]
            elif block.get("type") == "tool_use" and block.get("name") == "SubagentHandback":
                text = (block.get("input") or {}).get("message")
                if isinstance(text, str):
                    message = text
    return message


def record(event):
    reviewer = event.get("agent_type")
    if reviewer not in REVIEWERS:
        return
    cwd = event.get("cwd")
    message = event.get("last_assistant_message") or transcript_report(
        event.get("agent_transcript_path")
    )
    verdict = parse_verdict(message)
    problem = None
    if verdict is None:
        problem = (
            "Your review must end with a ```json block holding commit, blocking, "
            "suggestions and judgment_calls (see your instructions)."
        )
    else:
        # The verdict counts for the commit it names. If HEAD has moved on since, the gate
        # simply won't find a review for HEAD; the reviewer must never relabel its verdict.
        named = verdict.get("commit")
        commit = None
        if isinstance(named, str) and re.fullmatch(r"[0-9a-f]{40}", named):
            commit = git(cwd, "rev-parse", "--verify", "--quiet", f"{named}^{{commit}}")
        if commit is None:
            problem = (
                f"The verdict names commit {verdict.get('commit')}, which isn't a full sha of a "
                f"commit here. Name the commit you actually reviewed (HEAD is "
                f"{git(cwd, 'rev-parse', 'HEAD')} now; if that isn't what you reviewed, say so "
                "and review it from scratch)."
            )
    if problem:
        if event.get("stop_hook_active"):
            return  # Already sent back once; don't loop. Nothing is recorded, so the gate holds.
        block(problem)
    save_round(
        cwd,
        {
            "commit": commit,
            "reviewer": reviewer,
            "blocking": len(verdict["blocking"]),
            "suggestions": len(verdict["suggestions"]),
            "judgment_calls": len(verdict["judgment_calls"]),
        },
    )


# --- gate ---


def marks_ready(command):
    if GRAPHQL_READY in command:
        return True
    # gh may be named anywhere in the command, such as G=gh on one line and $G on the next.
    if not re.search(r"\bgh\b", command):
        return False
    return any(
        "--undo" not in match.group(1).split()
        for line in command.split("\n")
        for match in GH_READY.finditer(line)
    )


def creates_without_draft(command):
    """True if any gh pr create in the command lacks its own --draft. Unsure means True."""
    if not GH_CREATE.search(command):
        return False
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        words = list(lexer)
    except ValueError:
        return True  # unbalanced quotes
    segments, current = [], []
    for word in words + [";"]:
        if word in SEPARATORS or set(word) <= set(";&|()\n"):
            segments.append(current)
            current = []
        else:
            current.append(word)
    creates = [
        seg
        for seg in segments
        if any(seg[i : i + 2] == ["pr", "create"] and "gh" in seg[:i] for i in range(len(seg)))
    ]
    if not creates:
        return True  # gh pr create is in there somewhere we can't read, such as bash -c "..."
    return any(not DRAFT_FLAGS & set(seg) for seg in creates)


def gh_merges(command):
    """(method, head sha) for each gh pr merge in the command, or 'auto' or 'admin' if any
    uses those flags."""
    merges = []
    if not re.search(r"\bgh\b", command):
        return merges
    for line in command.split("\n"):
        for match in GH_MERGE.finditer(line):
            flags = match.group(1).split()
            if any(f == "--auto" or f.startswith("--auto=") for f in flags):
                return "auto"
            if any(f == "--admin" or f.startswith("--admin=") for f in flags):
                return "admin"
            method = next(
                (
                    m
                    for m in ("merge", "squash", "rebase")
                    if f"--{m}" in flags or f"-{m[0]}" in flags
                ),
                None,
            )
            sha = None
            for i, flag in enumerate(flags):
                if flag == "--match-head-commit" and i + 1 < len(flags):
                    sha = flags[i + 1].strip("'\"")
                elif flag.startswith("--match-head-commit="):
                    sha = flag.split("=", 1)[1].strip("'\"")
            merges.append((method, sha))
    return merges


def wants(event):
    """What the tool call does, as (action, detail). action is 'ready', 'merge', 'auto-merge',
    'admin-merge', 'api-merge', 'create-not-draft', 'post-review' (a review or other write
    posted from the shell, whose body the gate may not see), or None for anything else.
    A merge's detail is [(method, head sha)]."""
    tool, args = event.get("tool_name") or "", event.get("tool_input") or {}
    if tool.startswith("mcp__") and tool.endswith("__update_pull_request"):
        return ("ready" if args.get("draft") is False else None), None
    if tool.startswith("mcp__") and tool.endswith("__create_pull_request"):
        return (None if args.get("draft") is True else "create-not-draft"), None
    if tool.startswith("mcp__") and tool.endswith("__merge_pull_request"):
        return "merge", [(args.get("merge_method"), args.get("expectedHeadSha"))]
    if tool.startswith("mcp__") and tool.endswith("__enable_pr_auto_merge"):
        return "auto-merge", None
    if tool == "Bash":
        command = str(args.get("command") or "").replace("\\\n", " ")  # join continuations
        if API_AUTO_MERGE in command:
            return "auto-merge", None
        if API_MERGE.search(command):
            return "api-merge", None
        merges = gh_merges(command)
        if merges in ("auto", "admin"):
            return f"{merges}-merge", None
        if merges:
            return "merge", merges
        if marks_ready(command):
            return "ready", None
        if posts_from_the_shell(command):
            return "post-review", None
        if creates_without_draft(command):
            return "create-not-draft", None
    return None, None


def posts_from_the_shell(command):
    """True if the command runs gh pr review, or a gh api call that can write. As elsewhere,
    gh may be named anywhere in the command, such as G=gh on one line and $G on the next."""
    if not re.search(r"\bgh\b", command):
        return False
    if GH_REVIEW.search(command):
        return True
    return any(
        GH_API.search(part) and API_WRITE.search(part) for part in re.split(r"[;&|\n]", command)
    )


def check_merge(cwd, merges):
    head = git(cwd, "rev-parse", "HEAD")
    for method, sha in merges:
        if method != "merge":
            block(
                "Merge with a merge commit (merge_method: merge, or gh pr merge --merge) so the "
                "red/green history survives. " + LOOP
            )
        if sha != head:
            block(
                f"Pin the merge to the reviewed commit: expectedHeadSha (or gh pr merge "
                f"--match-head-commit) must be HEAD, {head}. " + LOOP
            )


def needs_data_review(cwd):
    base = git(cwd, "merge-base", "origin/main", "HEAD")
    if base is None:
        block(
            "Can't find where this branch left main, so the gate can't tell which reviewers it "
            "needs. git fetch origin main (add --depth=500 in a shallow clone), then try again. "
            + LOOP
        )
    changed = (git(cwd, "diff", "--name-only", base, "HEAD") or "").splitlines()
    return any(fnmatch.fnmatch(path, pattern) for path in changed for pattern in DATA_PATHS)


def check_ready(cwd):
    if git(cwd, "rev-parse", "--abbrev-ref", "HEAD") in (None, "HEAD"):
        block("Not on a git branch here, so the review state can't be checked. " + LOOP)
    if git(cwd, "status", "--porcelain"):
        block("There are uncommitted changes. Commit and push them, then review. " + LOOP)
    commit = git(cwd, "rev-parse", "HEAD")
    upstream = git(cwd, "rev-parse", "@{upstream}")
    if upstream is None:
        block("This branch has no upstream. git push -u origin HEAD, then try again. " + LOOP)
    if upstream != commit:
        block("HEAD isn't pushed. git push, then review that commit. " + LOOP)

    rounds = load_rounds(cwd)
    failed = len({r["commit"] for r in rounds if r["blocking"] > 0})
    if failed >= MAX_ROUNDS:
        block(
            f"Stop: {failed} review rounds found blocking issues. Leave the PR as a draft and "
            "tell the user what is still blocking. " + LOOP
        )
    needed = [REVIEWER, DATA_REVIEWER] if needs_data_review(cwd) else [REVIEWER]
    latest = {}
    for r in rounds:
        if r["commit"] == commit:
            latest[r.get("reviewer", REVIEWER)] = r
    blocked = [name for name in needed if name in latest and latest[name]["blocking"] > 0]
    if blocked:
        found = ", ".join(f"{latest[name]['blocking']} from the {name}" for name in blocked)
        block(
            f"Review round {failed} of {MAX_ROUNDS} found blocking issues ({found}). Fix them "
            "(red/green), push, and run the reviewers again. " + LOOP
        )
    missing = [name for name in needed if name not in latest]
    if missing:
        names = " and ".join(f"`{name}`" for name in missing)
        block(f"Commit {commit[:7]} hasn't been reviewed by {names}. Run it first. " + LOOP)


def github_repo(cwd, tool_input):
    """owner/repo for the merge: named by the MCP tool, or else the origin remote."""
    owner, repo = tool_input.get("owner"), tool_input.get("repo")
    if owner and repo:
        return f"{owner}/{repo}"
    url = git(cwd, "remote", "get-url", "origin") or ""
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    if not match:
        block(f"Can't tell which GitHub repo origin ({url}) is, to check its CI. " + LOOP)
    return f"{match.group(1)}/{match.group(2)}"


def check_ci(cwd, tool_input):
    commit = git(cwd, "rev-parse", "HEAD")
    api = os.environ.get("REVIEW_GATE_GITHUB_API", GITHUB_API)
    url = f"{api}/repos/{github_repo(cwd, tool_input)}/commits/{commit}/check-runs?per_page=100"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and api == GITHUB_API:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            runs = json.load(response)["check_runs"]
    except Exception as error:  # noqa: BLE001 - any failure to read CI must block the merge
        block(f"Couldn't read CI for {commit[:7]} ({error!r}). Try again shortly. " + LOOP)
    # A check that was re-run counts by its latest run, as GitHub counts required checks.
    latest = {}
    for r in sorted(runs, key=lambda r: r.get("id") or 0):
        latest[((r.get("app") or {}).get("id"), r["name"])] = r
    runs = list(latest.values())
    unfinished = [r["name"] for r in runs if r.get("status") != "completed"]
    if unfinished:
        block(f"CI has not finished on {commit[:7]}: {', '.join(unfinished)}. Wait. " + LOOP)
    failing = [r["name"] for r in runs if r.get("conclusion") not in CI_PASSES]
    if failing:
        block(f"CI failed on {commit[:7]}: {', '.join(failing)}. Fix it first. " + LOOP)
    if not any(r.get("conclusion") == "success" for r in runs):
        block(f"There is no CI result for {commit[:7]} yet. Wait for it to run. " + LOOP)


def strings(value):
    """Every string inside a tool call's input."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def check_markers(cwd, shas):
    head = git(cwd, "rev-parse", "HEAD")
    if any(not SHA.fullmatch(sha) or sha != head for sha in shas):
        block(
            f"The review-gate marker must name the reviewed commit, HEAD, written out: "
            f"<!-- review-gate: passed {head} -->. " + LOOP
        )


def gate(event):
    action, detail = wants(event)
    # Only calls that post text are read for a marker, so grep or a commit message naming it
    # is not blocked.
    tool = event.get("tool_name") or ""
    posts = action == "post-review" or (tool.startswith("mcp__") and tool.endswith(POSTS_TEXT))
    texts = strings(event.get("tool_input")) if posts else []
    markers = [sha for text in texts for sha in MARKER.findall(text)]
    if action is None and not markers:
        return
    if action == "create-not-draft":
        block("Open the pull request as a draft. It is marked ready only after review. " + LOOP)
    if action == "auto-merge":
        block("No auto-merge: merge directly once review and CI have passed. " + LOOP)
    if action == "admin-merge":
        block("No --admin merges: they skip GitHub's own checks. " + LOOP)
    if action == "api-merge":
        block(
            "Merge with gh pr merge --merge --match-head-commit <HEAD sha>, or the MCP "
            "merge_pull_request tool, so the review gate can check it. " + LOOP
        )
    if action == "merge":
        check_merge(event.get("cwd"), detail)
    check_ready(event.get("cwd"))
    if markers:
        check_markers(event.get("cwd"), markers)
    if action == "merge":
        check_ci(event.get("cwd"), event.get("tool_input") or {})


def safe_gate(stdin):
    """The gate, failing closed: any error, even in reading the event, blocks the tool call."""
    try:
        event = json.load(stdin)
        if not isinstance(event, dict) or not isinstance(event.get("tool_input") or {}, dict):
            raise TypeError(f"not a tool call event: {str(event)[:80]}")
        gate(event)
    except Exception as error:  # noqa: BLE001 - exit 1 would let the tool call through
        block(f"The review gate failed ({error!r}), so it is blocking to be safe. " + LOOP)


def main():
    if sys.argv[1] == "gate":
        safe_gate(sys.stdin)
    else:
        record(json.load(sys.stdin))


if __name__ == "__main__":
    main()
