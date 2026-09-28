"""The review gate hook (.claude/hooks/review_gate.py).

It has two jobs:
- `record` runs when the reviewer subagent stops, and saves its verdict against the commit it
  reviewed.
- `gate` runs before a pull request is opened or marked ready for review, and blocks that until
  the current commit has passed review.

Each test drives the real script the way Claude Code does: JSON on stdin, a blocking message on
stderr with exit code 2.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".claude/hooks/review_gate.py"
BLOCKED = 2


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A feature branch with one commit, pushed to a remote."""
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    git(tmp_path, "init", "-b", "main", str(work))
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.com")
    git(work, "remote", "add", "origin", str(remote))
    # Fetch from GitHub, as a real clone would, but push to the local bare repo.
    git(work, "config", "remote.origin.pushurl", str(remote))
    git(work, "remote", "set-url", "origin", "https://github.com/o/r.git")
    (work / "a.py").write_text("x = 1\n")
    git(work, "add", ".")
    git(work, "commit", "-m", "first")
    git(work, "push", "-u", "origin", "main")
    git(work, "checkout", "-b", "feature")
    new_commit(work)
    return work


def new_commit(repo, push=True):
    path = repo / "a.py"
    path.write_text(path.read_text() + "y = 2\n")
    git(repo, "commit", "-am", "change")
    if push:
        git(repo, "push", "-u", "origin", "HEAD")
    return head(repo)


def head(repo):
    return git(repo, "rev-parse", "HEAD")


class FakeGitHub(BaseHTTPRequestHandler):
    """Answers the check-runs request the gate makes before a merge."""

    check_runs = []
    requests = []

    def do_GET(self):
        FakeGitHub.requests.append(self.path)
        body = json.dumps(
            {"total_count": len(self.check_runs), "check_runs": self.check_runs}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def check_run(name="test", status="completed", conclusion="success"):
    return {"name": name, "status": status, "conclusion": conclusion}


@pytest.fixture(scope="session")
def github_api():
    server = HTTPServer(("127.0.0.1", 0), FakeGitHub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def ci(github_api, monkeypatch):
    """CI is green unless a test says otherwise."""
    monkeypatch.setenv("REVIEW_GATE_GITHUB_API", github_api)
    FakeGitHub.check_runs = [check_run(), check_run("deploy_render", conclusion="skipped")]
    FakeGitHub.requests = []
    return FakeGitHub


def run(mode, payload):
    return subprocess.run(
        [sys.executable, str(SCRIPT), mode],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def verdict(commit, blocking=0, suggestions=0, judgment_calls=0):
    finding = {"file": "a.py", "line": 1, "summary": "s", "detail": "d"}
    body = {
        "commit": commit,
        "blocking": [finding] * blocking,
        "suggestions": [finding] * suggestions,
        "judgment_calls": [{"question": "q", "options": ["a", "b"]}] * judgment_calls,
    }
    return f"Review notes.\n\n```json\n{json.dumps(body, indent=2)}\n```\n"


def record(repo, message, agent_type="reviewer", stop_hook_active=False):
    return run(
        "record",
        {
            "hook_event_name": "SubagentStop",
            "cwd": str(repo),
            "agent_type": agent_type,
            "agent_id": "a1",
            "stop_hook_active": stop_hook_active,
            "last_assistant_message": message,
        },
    )


def review(repo, blocking=0, agent_type="reviewer", **counts):
    result = record(repo, verdict(head(repo), blocking=blocking, **counts), agent_type)
    assert result.returncode == 0, result.stderr


def data_review(repo, blocking=0, **counts):
    review(repo, blocking=blocking, agent_type="data-reviewer", **counts)


def touch(repo, path, push=True):
    """Commit a change to path, which may be in a new directory."""
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text((file.read_text() if file.exists() else "") + "z = 3\n")
    git(repo, "add", path)
    git(repo, "commit", "-m", f"change {path}")
    if push:
        git(repo, "push", "-u", "origin", "HEAD")
    return head(repo)


def mark_ready(repo):
    return run(
        "gate",
        {
            "hook_event_name": "PreToolUse",
            "cwd": str(repo),
            "tool_name": "mcp__github__update_pull_request",
            "tool_input": {"owner": "o", "repo": "r", "pullNumber": 1, "draft": False},
        },
    )


def bash(repo, command):
    return run(
        "gate",
        {
            "hook_event_name": "PreToolUse",
            "cwd": str(repo),
            "tool_name": "Bash",
            "tool_input": {"command": command},
        },
    )


# --- The gate: marking a PR ready for review ---


def test_marking_ready_is_blocked_until_the_commit_has_been_reviewed(repo):
    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "reviewer" in result.stderr


def test_marking_ready_is_allowed_once_the_commit_passes_review(repo):
    review(repo)

    assert mark_ready(repo).returncode == 0


def test_suggestions_and_judgment_calls_do_not_block(repo):
    review(repo, suggestions=2, judgment_calls=1)

    assert mark_ready(repo).returncode == 0


def test_blocking_findings_block_and_say_which_round_this_is(repo):
    review(repo, blocking=2)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "round 1 of 3" in result.stderr


def test_a_new_commit_needs_a_new_review(repo):
    review(repo)
    new_commit(repo)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "reviewer" in result.stderr


def test_a_fix_that_passes_re_review_is_allowed(repo):
    review(repo, blocking=1)
    new_commit(repo)
    review(repo)

    assert mark_ready(repo).returncode == 0


def test_after_three_rounds_with_blocking_findings_it_stops_and_hands_over(repo):
    for _ in range(3):
        review(repo, blocking=1)
        new_commit(repo)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "Stop" in result.stderr
    assert "draft" in result.stderr


def test_a_third_round_that_passes_is_still_allowed(repo):
    for _ in range(2):
        review(repo, blocking=1)
        new_commit(repo)
    review(repo)

    assert mark_ready(repo).returncode == 0


def test_rounds_are_counted_per_branch(repo):
    for _ in range(3):
        review(repo, blocking=1)
        new_commit(repo)
    git(repo, "checkout", "-b", "other-feature")
    new_commit(repo)
    review(repo)

    assert mark_ready(repo).returncode == 0


def test_uncommitted_changes_block_marking_ready(repo):
    review(repo)
    (repo / "a.py").write_text("changed but not committed\n")

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "uncommitted" in result.stderr


def test_untracked_files_block_marking_ready(repo):
    review(repo)
    (repo / "new.py").write_text("unreviewed\n")

    assert mark_ready(repo).returncode == BLOCKED


def test_an_unpushed_commit_blocks_marking_ready(repo):
    new_commit(repo, push=False)
    review(repo)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "push" in result.stderr


def test_gh_pr_ready_is_gated_too(repo):
    assert bash(repo, "gh pr ready 12").returncode == BLOCKED
    review(repo)
    assert bash(repo, "gh pr ready 12").returncode == 0


def test_gh_pr_ready_undo_is_not_gated(repo):
    assert bash(repo, "gh pr ready 12 --undo").returncode == 0


def test_gh_pr_ready_undo_on_a_continuation_line_is_not_gated(repo):
    assert bash(repo, "gh pr ready 12 \\\n  --undo").returncode == 0


# --- The gate: opening a PR ---


def test_opening_a_pr_that_is_not_a_draft_is_blocked(repo):
    result = run(
        "gate",
        {
            "cwd": str(repo),
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"title": "t", "head": "feature", "base": "main"},
        },
    )

    assert result.returncode == BLOCKED
    assert "draft" in result.stderr


def test_opening_a_draft_pr_is_allowed_without_a_review(repo):
    result = run(
        "gate",
        {
            "cwd": str(repo),
            "tool_name": "mcp__github__create_pull_request",
            "tool_input": {"title": "t", "head": "feature", "base": "main", "draft": True},
        },
    )

    assert result.returncode == 0


def test_gh_pr_create_needs_the_draft_flag(repo):
    assert bash(repo, "gh pr create --title t --body b").returncode == BLOCKED
    assert bash(repo, "gh pr create --draft --title t --body b").returncode == 0


# --- The gate leaves everything else alone ---


@pytest.mark.parametrize(
    "tool_name, tool_input",
    [
        ("Bash", {"command": "uv run pytest"}),
        ("mcp__github__update_pull_request", {"title": "new title"}),
        ("mcp__github__update_pull_request", {"draft": True}),
        ("Read", {"file_path": "/x"}),
    ],
)
def test_other_tool_calls_pass_through(repo, tool_name, tool_input):
    result = run("gate", {"cwd": str(repo), "tool_name": tool_name, "tool_input": tool_input})

    assert result.returncode == 0, result.stderr


# --- Recording the reviewer's verdict ---


def test_a_verdict_without_the_json_block_sends_the_reviewer_back(repo):
    result = record(repo, "Looks good to me!")

    assert result.returncode == BLOCKED
    assert "```json" in result.stderr


def test_a_verdict_for_an_older_commit_is_kept_for_that_commit_only(repo):
    reviewed = head(repo)
    new_commit(repo)

    assert record(repo, verdict(reviewed)).returncode == 0
    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "reviewer" in result.stderr


def test_a_verdict_for_a_commit_that_does_not_exist_sends_the_reviewer_back(repo):
    result = record(repo, verdict("0" * 40))

    assert result.returncode == BLOCKED
    assert "0" * 40 in result.stderr


def test_a_second_bad_verdict_is_let_go_but_not_recorded(repo):
    result = record(repo, "still no block", stop_hook_active=True)

    assert result.returncode == 0
    assert mark_ready(repo).returncode == BLOCKED


def test_other_subagents_are_not_recorded(repo):
    result = record(repo, verdict(head(repo)), agent_type="Explore")

    assert result.returncode == 0
    assert mark_ready(repo).returncode == BLOCKED


def test_the_last_json_block_is_the_verdict(repo):
    message = 'Example:\n```json\n{"blocking": []}\n```\n' + verdict(head(repo))

    assert record(repo, message).returncode == 0
    assert mark_ready(repo).returncode == 0


def test_review_state_lives_inside_git_so_it_is_never_committed(repo):
    review(repo)

    assert git(repo, "status", "--porcelain") == ""


def test_marking_ready_outside_a_git_repo_is_blocked_not_crashed(tmp_path):
    result = run(
        "gate",
        {
            "cwd": str(tmp_path),
            "tool_name": "mcp__github__update_pull_request",
            "tool_input": {"draft": False},
        },
    )

    assert result.returncode == BLOCKED
    assert "git" in result.stderr


# --- Round 1 review fixes ---


def test_a_pass_after_three_failed_rounds_is_still_blocked(repo):
    for _ in range(3):
        review(repo, blocking=1)
        new_commit(repo)
    review(repo)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "Stop" in result.stderr


def test_re_reviewing_the_same_commit_counts_as_one_round(repo):
    review(repo, blocking=1)
    review(repo, blocking=1)
    review(repo, blocking=1)
    new_commit(repo)
    review(repo)

    assert mark_ready(repo).returncode == 0


@pytest.mark.parametrize(
    "command",
    [
        "(gh pr ready 12)",
        "echo 1; $(gh pr ready 12)",
        "GH_REPO=o/r gh pr ready 12",
        "command gh pr ready 12",
        'bash -c "gh pr ready 12"',
        "gh api graphql -f query='mutation { markPullRequestReadyForReview(input: {}) { x } }'",
        "echo 'gh pr ready' is how you mark it",
    ],
)
def test_every_shell_form_of_marking_ready_is_gated(repo, command):
    assert bash(repo, command).returncode == BLOCKED


@pytest.mark.parametrize(
    "command",
    [
        'gh pr create --title "fix; tidy" --draft --body b',
        "gh pr create --title t --body \"$(cat <<'EOF'\nSummary\n\nMore | detail\nEOF\n)\" --draft",
        "gh pr create -d --title t",
        "gh pr create \\\n  --draft \\\n  --fill",
    ],
)
def test_draft_creates_are_allowed_however_the_body_is_written(repo, command):
    result = bash(repo, command)

    assert result.returncode == 0, result.stderr


def test_the_github_server_may_have_another_name(repo):
    result = run(
        "gate",
        {
            "cwd": str(repo),
            "tool_name": "mcp__plugin_gh_github__update_pull_request",
            "tool_input": {"draft": False},
        },
    )

    assert result.returncode == BLOCKED


def test_a_corrupt_state_file_blocks_instead_of_failing_open(repo):
    review(repo)
    state = next((repo / ".git/claude-review").iterdir())
    state.write_text("{bad")

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "review gate" in result.stderr


def test_a_pushed_branch_without_an_upstream_is_told_to_set_one(repo):
    git(repo, "checkout", "-b", "no-upstream")
    new_commit(repo, push=False)
    git(repo, "push", "origin", "HEAD")
    review(repo)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "push -u" in result.stderr


# --- Round 2 review fixes ---


@pytest.mark.parametrize(
    "command",
    [
        'gh pr create --title t --body "Run docker compose up -d first"',
        "git branch -d old && gh pr create --title t --body b",
        "gh pr create --draft=false --title t --body b",
        "gh pr create --title t --body b; gh pr create --draft --title u",
        "gh pr create --title t\necho --draft",
        'gh pr create --title "unbalanced',
        'bash -c "gh pr create --title t --draft"',
    ],
)
def test_a_draft_flag_only_counts_on_its_own_gh_pr_create(repo, command):
    result = bash(repo, command)

    assert result.returncode == BLOCKED
    assert "draft" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "gh pr ready 13 && gh pr ready 12 --undo",
        "gh pr ready 13  # no --undo",
        "gh pr \\\n  ready 13",
        "gh \\\n pr ready 13",
    ],
)
def test_undo_and_line_continuations_do_not_hide_marking_ready(repo, command):
    assert bash(repo, command).returncode == BLOCKED


def test_a_null_command_is_not_a_crash(repo):
    result = run("gate", {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": None}})

    assert result.returncode == 0, result.stderr


def test_a_verdict_commit_that_is_not_a_sha_is_never_passed_to_git(repo):
    result = record(repo, verdict("--output=/tmp/x"))

    assert result.returncode == BLOCKED
    assert "full sha" in result.stderr


# --- Merging: Claude merges once review passes (owner's decision, 2026-09-25) ---


def merge(work, **overrides):
    tool_input = {
        "owner": "o",
        "repo": "r",
        "pullNumber": 1,
        "merge_method": "merge",
        "expectedHeadSha": head(work),
    }
    tool_input.update(overrides)
    return run(
        "gate",
        {
            "cwd": str(work),
            "tool_name": "mcp__github__merge_pull_request",
            "tool_input": tool_input,
        },
    )


def test_merging_is_blocked_until_the_commit_passes_review(repo):
    result = merge(repo)

    assert result.returncode == BLOCKED
    assert "reviewer" in result.stderr


def test_merging_is_allowed_once_the_commit_passes_review(repo):
    review(repo)

    assert merge(repo).returncode == 0


def test_merging_after_three_failed_rounds_is_blocked(repo):
    for _ in range(3):
        review(repo, blocking=1)
        new_commit(repo)
    review(repo)

    result = merge(repo)

    assert result.returncode == BLOCKED
    assert "Stop" in result.stderr


@pytest.mark.parametrize("method", ["squash", "rebase", None])
def test_merging_must_use_a_merge_commit(repo, method):
    review(repo)

    result = merge(repo, merge_method=method)

    assert result.returncode == BLOCKED
    assert "merge commit" in result.stderr


@pytest.mark.parametrize("sha", ["0" * 40, None])
def test_merging_must_name_the_reviewed_head(repo, sha):
    review(repo)

    result = merge(repo, expectedHeadSha=sha)

    assert result.returncode == BLOCKED
    assert "expectedHeadSha" in result.stderr


def test_gh_pr_merge_is_gated_and_needs_a_merge_commit_and_the_head(repo):
    ok = f"gh pr merge 13 --merge --match-head-commit {head(repo)}"
    assert bash(repo, ok).returncode == BLOCKED
    review(repo)
    assert bash(repo, ok).returncode == 0
    assert bash(repo, f"gh pr merge 13 --squash --match-head-commit {head(repo)}").returncode == 2
    assert bash(repo, "gh pr merge 13 --merge").returncode == BLOCKED


@pytest.mark.parametrize(
    "tool_name, tool_input",
    [
        ("mcp__github__enable_pr_auto_merge", {"pullNumber": 1}),
        ("Bash", {"command": "gh pr merge 13 --auto --merge"}),
    ],
)
def test_auto_merge_is_blocked(repo, tool_name, tool_input):
    review(repo)
    if tool_name == "Bash":
        tool_input["command"] += f" --match-head-commit {head(repo)}"

    result = run("gate", {"cwd": str(repo), "tool_name": tool_name, "tool_input": tool_input})

    assert result.returncode == BLOCKED
    assert "auto-merge" in result.stderr


# --- Merge gating, review round 1 fixes ---


@pytest.mark.parametrize(
    "command",
    [
        "gh api -X PUT repos/o/r/pulls/13/merge -f merge_method=merge",
        "gh api graphql -f query='mutation{mergePullRequest(input:{pullRequestId:\"X\"}){x}}'",
    ],
)
def test_merging_through_gh_api_is_blocked_even_after_review(repo, command):
    review(repo)

    result = bash(repo, command)

    assert result.returncode == BLOCKED
    assert "gh pr merge --merge" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "gh api graphql -f query='mutation{enablePullRequestAutoMerge(input:{}){x}}'",
        "gh pr merge 13 --merge --auto=true --match-head-commit HEADSHA",
    ],
)
def test_every_form_of_auto_merge_is_blocked(repo, command):
    review(repo)

    result = bash(repo, command.replace("HEADSHA", head(repo)))

    assert result.returncode == BLOCKED
    assert "auto-merge" in result.stderr


def test_admin_merges_are_blocked(repo):
    review(repo)

    result = bash(repo, f"gh pr merge 13 --merge --admin --match-head-commit {head(repo)}")

    assert result.returncode == BLOCKED
    assert "--admin" in result.stderr


@pytest.mark.parametrize(
    "form",
    [
        '--match-head-commit "SHA"',
        "--match-head-commit 'SHA'",
        '--match-head-commit="SHA"',
        "--match-head-commit=SHA",
    ],
)
def test_a_quoted_head_sha_is_accepted(repo, form):
    review(repo)

    result = bash(repo, "gh pr merge 13 --merge " + form.replace("SHA", head(repo)))

    assert result.returncode == 0, result.stderr


# --- Merge gating, review round 2 fixes ---


@pytest.mark.parametrize(
    "command",
    [
        "gh pr -R o/r merge 13 --squash",
        "gh pr --repo=o/r merge 13 --squash --admin",
        "gh pr --repo o/r ready 13",
        "gh -R o/r pr merge 13 --squash",
    ],
)
def test_repo_flags_before_the_subcommand_are_still_gated(repo, command):
    assert bash(repo, command).returncode == BLOCKED


@pytest.mark.parametrize(
    "command",
    [
        "gh api repos/o/r/merges -f base=main -f head=feat",
        "gh api graphql -f query='mutation{mergeBranch(input:{}){x}}'",
    ],
)
def test_branch_merges_through_gh_api_are_blocked(repo, command):
    review(repo)

    assert bash(repo, command).returncode == BLOCKED


@pytest.mark.parametrize(
    "command",
    [
        "git push -u origin review-loop",
        "git push origin main-fix",
        "git push",
        "git pull origin main",
    ],
)
def test_ordinary_pushes_are_not_gated(repo, command):
    assert bash(repo, command).returncode == 0


# --- The data reviewer: required when a PR touches the data layer or the server ---


@pytest.mark.parametrize(
    "path",
    [
        "wca_data/build.py",
        "wca_data/schema/tables.sql",
        "tests/wca_data/test_build.py",
        "deploy/wca-data-build.timer",
        "deploy/Caddyfile",
        "Dockerfile",
        "migrations/001.sql",
    ],
)
def test_data_layer_changes_need_the_data_reviewer_too(repo, path):
    touch(repo, path)
    review(repo)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "data-reviewer" in result.stderr


@pytest.mark.parametrize("path", ["wca_data/build.py", "deploy/Caddyfile"])
def test_data_layer_changes_pass_once_both_reviewers_pass(repo, path):
    touch(repo, path)
    review(repo)
    data_review(repo)

    assert mark_ready(repo).returncode == 0


def test_app_only_changes_do_not_need_the_data_reviewer(repo):
    touch(repo, "wca_records_analyser/web.py")
    review(repo)

    assert mark_ready(repo).returncode == 0


def test_a_data_change_earlier_on_the_branch_still_needs_the_data_reviewer(repo):
    touch(repo, "wca_data/build.py")
    touch(repo, "wca_records_analyser/web.py")
    review(repo)

    assert mark_ready(repo).returncode == BLOCKED


def test_the_data_reviewer_alone_is_not_enough(repo):
    touch(repo, "wca_data/build.py")
    data_review(repo)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "`reviewer`" in result.stderr


def test_blocking_findings_from_the_data_reviewer_block(repo):
    touch(repo, "wca_data/build.py")
    review(repo)
    data_review(repo, blocking=1)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "round 1 of 3" in result.stderr
    assert "data-reviewer" in result.stderr


def test_both_reviewers_blocking_the_same_commit_is_one_round(repo):
    touch(repo, "wca_data/build.py")
    review(repo, blocking=1)
    data_review(repo, blocking=1)

    result = mark_ready(repo)

    assert "round 1 of 3" in result.stderr


def test_rounds_blocked_by_either_reviewer_add_up_to_the_cap(repo):
    touch(repo, "wca_data/build.py")
    review(repo, blocking=1)
    touch(repo, "wca_data/build.py")
    data_review(repo, blocking=1)
    touch(repo, "wca_data/build.py")
    review(repo)
    data_review(repo, blocking=1)
    touch(repo, "wca_data/build.py")
    review(repo)
    data_review(repo)

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "Stop" in result.stderr


def test_the_data_reviewers_verdict_is_recorded(repo):
    result = record(repo, "no verdict here", agent_type="data-reviewer")

    assert result.returncode == BLOCKED
    assert "json" in result.stderr


def test_the_changed_files_cannot_be_worked_out_without_main(repo):
    review(repo)
    git(repo, "update-ref", "-d", "refs/remotes/origin/main")

    result = mark_ready(repo)

    assert result.returncode == BLOCKED
    assert "git fetch" in result.stderr


# --- CI: a merge waits for green checks on the reviewed commit ---


def test_merging_checks_ci_on_the_reviewed_commit_of_the_named_repo(repo, ci):
    review(repo)

    assert merge(repo, owner="tdshaw2000", repo="wca").returncode == 0
    assert ci.requests == [f"/repos/tdshaw2000/wca/commits/{head(repo)}/check-runs?per_page=100"]


def test_gh_pr_merge_checks_ci_on_the_origin_repo(repo, ci):
    review(repo)

    assert bash(repo, f"gh pr merge 13 --merge --match-head-commit {head(repo)}").returncode == 0
    assert ci.requests == [f"/repos/o/r/commits/{head(repo)}/check-runs?per_page=100"]


@pytest.mark.parametrize(
    "runs, reason",
    [
        ([check_run(conclusion="failure")], "failed"),
        ([check_run(status="in_progress", conclusion=None)], "not finished"),
        ([check_run(), check_run("lint", conclusion="cancelled")], "failed"),
        ([], "no CI"),
        ([check_run(conclusion="skipped")], "no CI"),
    ],
)
def test_merging_is_blocked_until_ci_is_green(repo, ci, runs, reason):
    review(repo)
    ci.check_runs = runs

    result = merge(repo)

    assert result.returncode == BLOCKED
    assert reason in result.stderr


def test_marking_ready_does_not_wait_for_ci(repo, ci):
    review(repo)
    ci.check_runs = [check_run(status="queued", conclusion=None)]

    assert mark_ready(repo).returncode == 0
    assert ci.requests == []


def test_ci_is_not_checked_before_review_passes(repo, ci):
    result = merge(repo)

    assert result.returncode == BLOCKED
    assert ci.requests == []


def test_an_unreachable_github_blocks_the_merge(repo, monkeypatch):
    review(repo)
    monkeypatch.setenv("REVIEW_GATE_GITHUB_API", "http://127.0.0.1:9")

    result = merge(repo)

    assert result.returncode == BLOCKED
    assert "CI" in result.stderr


# --- Fail-closed edge cases from the PR #4 review ---


@pytest.mark.parametrize(
    "stdin",
    [
        "not json",
        "[1, 2]",
        json.dumps({"tool_name": "Bash", "tool_input": "gh pr ready 12"}),
    ],
)
def test_a_malformed_event_blocks_instead_of_failing_open(repo, stdin):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "gate"],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=repo,
    )

    assert result.returncode == BLOCKED
    assert "review gate" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "G=gh\n$G pr ready 4",
        "G=gh\n$G pr merge 4 --squash",
    ],
)
def test_gh_named_on_another_line_is_still_gated(repo, command):
    assert bash(repo, command).returncode == BLOCKED


# --- The review-gate marker: the review summary the GitHub check looks for ---


def marker(sha):
    return f"<!-- review-gate: passed {sha} -->"


def post_review(repo, body, tool_name="mcp__github__pull_request_review_write"):
    return run(
        "gate",
        {
            "cwd": str(repo),
            "tool_name": tool_name,
            "tool_input": {
                "owner": "o",
                "repo": "r",
                "pullNumber": 1,
                "method": "create",
                "event": "COMMENT",
                "body": f"Both reviewers passed.\n\n{body}",
            },
        },
    )


def test_the_marker_cannot_be_posted_before_the_commit_passes_review(repo):
    result = post_review(repo, marker(head(repo)))

    assert result.returncode == BLOCKED
    assert "reviewer" in result.stderr


def test_the_marker_can_be_posted_once_the_commit_passes_review(repo):
    review(repo)

    result = post_review(repo, marker(head(repo)))

    assert result.returncode == 0, result.stderr


def test_the_marker_needs_the_data_reviewer_when_the_data_layer_changed(repo):
    touch(repo, "wca_data/build.py")
    review(repo)

    assert post_review(repo, marker(head(repo))).returncode == BLOCKED


def test_the_marker_must_name_the_reviewed_head(repo):
    old = head(repo)
    review(repo)
    new_commit(repo)
    review(repo)

    result = post_review(repo, marker(old))

    assert result.returncode == BLOCKED
    assert head(repo) in result.stderr


def test_the_marker_is_gated_when_posted_as_a_comment_or_through_bash(repo):
    body = marker(head(repo))

    assert post_review(repo, body, "mcp__github__add_issue_comment").returncode == BLOCKED
    assert bash(repo, f"gh pr review 1 --comment --body '{body}'").returncode == BLOCKED


def test_reviews_without_the_marker_are_not_gated(repo):
    result = post_review(repo, "Suggestion: rename x.")

    assert result.returncode == 0, result.stderr


# --- CI: only the latest run of each check counts ---


def test_a_failed_check_that_was_rerun_green_does_not_block_the_merge(repo, ci):
    review(repo)
    ci.check_runs = [
        check_run("review-gate", conclusion="success") | {"id": 20},
        check_run() | {"id": 5},
        check_run("review-gate", conclusion="failure") | {"id": 10},
    ]

    result = merge(repo)

    assert result.returncode == 0, result.stderr


def test_a_check_that_failed_after_passing_still_blocks_the_merge(repo, ci):
    review(repo)
    ci.check_runs = [
        check_run("review-gate", conclusion="success") | {"id": 10},
        check_run() | {"id": 5},
        check_run("review-gate", conclusion="failure") | {"id": 20},
    ]

    result = merge(repo)

    assert result.returncode == BLOCKED
    assert "review-gate" in result.stderr


# --- Review round 1: the marker gate fails closed ---


@pytest.mark.parametrize(
    "command",
    [
        'gh pr review 8 --comment --body "<!-- review-gate: passed $(git rev-parse HEAD) -->"',
        'gh pr review 8 --comment --body "<!-- review-gate: passed ${SHA} -->"',
        "gh pr review 8 --comment --body 'review-gate:passed HEAD'",
    ],
)
def test_a_marker_whose_sha_is_not_written_out_is_blocked_even_after_review(repo, command):
    review(repo)

    result = bash(repo, command)

    assert result.returncode == BLOCKED
    assert head(repo) in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "gh pr review 8 --comment --body-file /tmp/summary.md",
        "gh pr review 8 -c -F /tmp/summary.md",
        'gh pr review 8 --comment --body "$(cat /tmp/summary.md)"',
        "gh api repos/o/r/pulls/8/reviews -F body=@/tmp/summary.md -f event=COMMENT",
    ],
)
def test_posting_a_review_through_bash_waits_for_review_whatever_the_body(repo, command):
    assert bash(repo, command).returncode == BLOCKED
    review(repo)
    assert bash(repo, command).returncode == 0


def test_a_loosely_written_marker_for_another_commit_is_blocked(repo):
    review(repo)

    result = post_review(repo, f"review-gate:passed {'0' * 40}")

    assert result.returncode == BLOCKED
    assert head(repo) in result.stderr


def test_checks_from_different_apps_with_the_same_name_are_counted_apart(repo, ci):
    review(repo)
    ci.check_runs = [
        check_run(conclusion="failure") | {"id": 10, "app": {"id": 1}},
        check_run() | {"id": 20, "app": {"id": 2}},
    ]

    result = merge(repo)

    assert result.returncode == BLOCKED
    assert "test" in result.stderr


# --- Review round 2 judgment call: GraphQL reviews wait for review too ---


@pytest.mark.parametrize(
    "command",
    [
        "gh api graphql -f query='mutation{addPullRequestReview(input:{}){x}}'",
        "gh api graphql -f query='mutation{submitPullRequestReview(input:{}){x}}'",
        "gh api graphql -f query='mutation{updatePullRequestReview(input:{}){x}}'",
        "gh api graphql -F query=@/tmp/q.graphql",
        "gh api graphql --field query=@/tmp/q.graphql",
    ],
)
def test_reviews_posted_through_graphql_wait_for_review(repo, command):
    assert bash(repo, command).returncode == BLOCKED
    review(repo)
    assert bash(repo, command).returncode == 0


# --- Review round 3: every write through gh api waits for review ---


@pytest.mark.parametrize(
    "command",
    [
        "gh api graphql --input /tmp/q.json",
        "gh api graphql -Fquery=@/tmp/q.graphql",
        "gh api graphql -f query='query { viewer { login } }'",
        "gh api --input /tmp/review.json repos/o/r/pulls/8/reviews",
        "gh api -X POST $URL -f body=x",
        "gh api --method=PUT $URL",
        "echo start; gh api $URL -fbody=x && echo done",
        "G=gh\n$G api graphql --input /tmp/q.json",
        "echo '{}' | gh api graphql --input -",
        "gh api -XPOST $URL",
    ],
)
def test_every_write_through_gh_api_waits_for_review(repo, command):
    assert bash(repo, command).returncode == BLOCKED
    review(repo)
    assert bash(repo, command).returncode == 0


@pytest.mark.parametrize(
    "command",
    [
        "gh api repos/o/r/pulls/8/reviews --jq '.[].body'",
        "gh api repos/o/r/pulls/8/reviews && rm -f /tmp/x",
        'grep -rn "review-gate: passed" .github',
        'git commit -m "docs: explain the review-gate: passed marker"',
    ],
)
def test_reads_and_mentions_of_the_marker_are_not_gated(repo, command):
    result = bash(repo, command)

    assert result.returncode == 0, result.stderr
