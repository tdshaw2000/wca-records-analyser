"""The GitHub side of the review gate (.github/scripts/review_check.py and the Review gate
workflow).

The hook only runs inside Claude Code sessions. This check runs on GitHub for every PR, so a
merge from anywhere else also needs the review summary that the hook lets Claude post only once
the reviewers have passed the PR's head commit. main's ruleset makes the check required.
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
SCRIPT = ROOT / ".github/scripts/review_check.py"
WORKFLOW = ROOT / ".github/workflows/review-gate.yml"
HEAD = "a" * 40
OLD = "b" * 40


def marker(sha):
    return f"<!-- review-gate: passed {sha} -->"


def a_review(body, association="OWNER", state="COMMENTED", review_id=1):
    return {
        "id": review_id,
        "body": body,
        "state": state,
        "author_association": association,
        "user": {"login": "someone"},
    }


class FakeGitHub(BaseHTTPRequestHandler):
    """Serves a PR's reviews, 100 to a page, as GitHub does."""

    reviews = []
    requests = []

    def do_GET(self):
        FakeGitHub.requests.append(self.path)
        page = int(self.path.split("page=")[-1]) if "&page=" in self.path else 1
        body = json.dumps(self.reviews[(page - 1) * 100 : page * 100]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def github_api():
    server = HTTPServer(("127.0.0.1", 0), FakeGitHub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def github(github_api):
    FakeGitHub.reviews = []
    FakeGitHub.requests = []
    FakeGitHub.api = github_api
    return FakeGitHub


def check(github, head=HEAD):
    env = os.environ | {
        "REVIEW_CHECK_GITHUB_API": github.api,
        "GITHUB_TOKEN": "t",
        "REPO": "o/r",
        "PR": "7",
        "HEAD_SHA": head,
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env
    )


def test_a_pr_with_no_review_summary_fails(github):
    result = check(github)

    assert result.returncode == 1
    assert HEAD in result.stdout
    assert github.requests == ["/repos/o/r/pulls/7/reviews?per_page=100&page=1"]


def test_a_review_summary_for_the_head_commit_passes(github):
    github.reviews = [a_review(f"Both reviewers passed.\n\n{marker(HEAD)}")]

    result = check(github)

    assert result.returncode == 0, result.stdout


def test_a_summary_for_an_older_commit_does_not_count(github):
    github.reviews = [a_review(marker(OLD))]

    result = check(github)

    assert result.returncode == 1


@pytest.mark.parametrize("association", ["CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "NONE"])
def test_a_summary_from_someone_without_write_access_does_not_count(github, association):
    github.reviews = [a_review(marker(HEAD), association=association)]

    assert check(github).returncode == 1


@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_summaries_from_people_with_write_access_count(github, association):
    github.reviews = [a_review(marker(HEAD), association=association)]

    assert check(github).returncode == 0


def test_a_dismissed_summary_does_not_count(github):
    github.reviews = [a_review(marker(HEAD), state="DISMISSED")]

    assert check(github).returncode == 1


def test_a_summary_on_a_later_page_is_found(github):
    github.reviews = [a_review("nit", review_id=i) for i in range(100)] + [
        a_review(marker(HEAD), review_id=100)
    ]

    result = check(github)

    assert result.returncode == 0, result.stdout
    assert len(github.requests) == 2


def test_the_marker_only_counts_on_a_line_of_its_own(github):
    github.reviews = [a_review(f"The line `{marker(HEAD)}` is what we look for.")]

    assert check(github).returncode == 1


def test_an_unreachable_github_fails_the_check(github):
    github.api = "http://127.0.0.1:9"

    result = check(github)

    assert result.returncode == 1
    assert "Couldn't read the reviews" in result.stdout


def test_a_summary_from_a_deleted_account_still_passes(github):
    github.reviews = [a_review(marker(HEAD)) | {"user": None}]

    result = check(github)

    assert result.returncode == 0, result.stdout + result.stderr


# --- The workflow ---


@pytest.fixture(scope="module")
def workflow():
    return WORKFLOW.read_text() if WORKFLOW.exists() else ""


def test_the_check_reruns_when_the_pr_changes_or_a_review_is_posted(workflow):
    for trigger in (
        "pull_request:",
        "pull_request_review:",
        "synchronize",
        "submitted",
        "edited",
        "dismissed",
    ):
        assert trigger in workflow


def test_the_check_never_runs_with_the_base_repos_secrets(workflow):
    assert "pull_request_target" not in workflow
    assert "secrets." not in workflow


def test_the_check_only_reads(workflow):
    assert "permissions:\n  pull-requests: read\n" in workflow
    assert "write" not in workflow


def test_the_check_job_has_the_name_the_ruleset_requires(workflow):
    assert "\n  review-gate:\n" in workflow
    assert "python3 .github/scripts/review_check.py" in workflow


def test_the_check_is_given_the_prs_head_commit(workflow):
    assert "HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in workflow


def test_claude_md_says_how_to_post_the_marker():
    text = (ROOT / "CLAUDE.md").read_text()

    assert "<!-- review-gate: passed <sha> -->" in text
    assert "review-gate" in text
