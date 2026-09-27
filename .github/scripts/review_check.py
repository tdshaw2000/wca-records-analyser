"""The Review gate check: does this PR carry a passing review summary for its head commit?

Run by .github/workflows/review-gate.yml. It passes only when someone with write access has
posted a PR review containing, on a line of its own,

    <!-- review-gate: passed <head sha> -->

In Claude Code sessions the review gate hook (.claude/hooks/review_gate.py) lets Claude post
that line only once every reviewer the PR needs has passed that exact commit. main's ruleset
requires this check, so a merge from outside such a session needs the same summary.

Settings come from the environment: GITHUB_TOKEN, REPO (owner/name), PR, HEAD_SHA, and
REVIEW_CHECK_GITHUB_API for tests. Standard library only. Exit 0 passes; anything else fails.
"""

import json
import os
import sys
import urllib.request

GITHUB_API = "https://api.github.com"
WRITE_ACCESS = {"OWNER", "MEMBER", "COLLABORATOR"}
PAGE_SIZE = 100


def reviews(api, repo, pr, token):
    page = 1
    while True:
        url = f"{api}/repos/{repo}/pulls/{pr}/reviews?per_page={PAGE_SIZE}&page={page}"
        request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=30) as response:
            batch = json.load(response)
        yield from batch
        if len(batch) < PAGE_SIZE:
            return
        page += 1


def passes(review, head):
    return (
        review.get("author_association") in WRITE_ACCESS
        and review.get("state") != "DISMISSED"
        and f"<!-- review-gate: passed {head} -->"
        in (line.strip() for line in (review.get("body") or "").splitlines())
    )


def main():
    env = os.environ
    api = env.get("REVIEW_CHECK_GITHUB_API", GITHUB_API)
    head = env["HEAD_SHA"]
    found = [
        r for r in reviews(api, env["REPO"], env["PR"], env["GITHUB_TOKEN"]) if passes(r, head)
    ]
    if found:
        print(f"Review summary for {head} posted by {found[-1]['user']['login']}.")
        return 0
    print(
        f"No review summary for {head}. The reviewers must pass this commit, then post a PR "
        f"review containing <!-- review-gate: passed {head} -->. See 'Review loop' in CLAUDE.md."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
