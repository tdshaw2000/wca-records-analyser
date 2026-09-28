# CLAUDE.md — WCA Records Analyser

> This file describes the shape of this project: what it is, the domain
> terminology, and how it is laid out, built and run.
>
> General working standards — TDD, commit discipline, code style, working
> style — are not repeated here. They live in the personal global
> `~/.claude/CLAUDE.md` and apply to this repo in full.

---

## project summary

- **Name:** WCA Records Analyser
- **Purpose:** This project will use data available at https://www.worldcubeassociation.org, which is the official website for speedcubing and contains all competition data for competitive speedcubers. The idea is that you can search for a member, select a puzzle that they have competed in, and produce a graph of their personal records.

## terminology

- **PR** means **Personal Record** (the speedcubing term), never "pull request". A result is a PR when it beats all of that competitor's prior results for the same event. Use "PR" consistently in code, tests, and discussion.
- The WCA API does **not** flag PRs; we compute them ourselves as the running minimum of results ordered by competition date. (The API's `regional_single_record` / `regional_average_record` fields are for regional records — NR/CR/WR — not PRs.)

## tech stack

- **Language:** Python
- **Web:** FastAPI + Jinja2 templates, served with uvicorn
- **Data access:** `wca_data` (see below) reads a SQLite database built from the WCA public results export; the app no longer calls the WCA API directly.
- **Charting:** Chart.js (vendored under `static/vendor/`, no CDN) with the date-fns adapter for time axes.
- **CI/CD:** GitHub Actions (hosted runners; `.github/workflows/ci.yml`)

## project structure

Each module owns one concern; keep HTTP, analysis, presentation, and web wiring separate.

- `wca_client.py` — reads a competitor's data via `wca_data.read.WcaData`, in the shapes the rest of the app expects: `search_persons`, `get_results`, `get_competitions`, `get_competition_dates`, `get_profile`, `get_export_date`; dataclasses `Person`, `Competition`, `Profile`, `Result`. `PersonNotFound` for an unknown WCA ID (a 404 in `web.py`). Functions take an optional `data` (an open `WcaData`) for test injection; without one they open the database `WCA_DATA_DB_PATH` names.
- `records.py` — PR analysis (no HTTP). `personal_record_flags`, `single_record_progression`; dataclass `RecordPoint`. Singles are centiseconds; non-positive values are DNF/DNS and are skipped.
- `events.py` — event id → display name table (`EVENT_NAMES`) and `named_events`; dataclass `Event`.
- `formatting.py` — `format_single` renders centiseconds as a cubing time string.
- `chart.py` — shapes `RecordPoint` progressions into JSON-serialisable chart series (no HTTP); rendered client-side by `static/records-chart.js`.
- `web.py` — FastAPI routes (`/`, `/search`, `/records`) with injectable `Depends` seams (`get_search_function`, `get_events_function`, `get_progression_function`) so web tests never hit the network. Templates in `templates/`.
  - **Holding page:** since the WCA API access change of 24 September 2026, `HOLDING_PAGE_ENABLED = True` makes a middleware answer every non-static request with `templates/holding.html` (status 200, so Render's `/` health check still passes; `/healthz`, the image's database-free health check, is let through). Set it to `False` to restore the app. `tests/conftest.py` disables it for the normal suite; `tests/test_holding_page.py` re-enables it.

The data layer is a separate package, `wca_data/`, being built to replace the WCA API (plan:
`docs/plans/own-data-backend.md`). It must never import `wca_records_analyser` or anything
web; `tests/wca_data/test_isolation.py` enforces that. App-specific analysis stays in the app.

- `wca_data/export.py` — streams tables from the WCA export zip by header name (`read_table`, `read_metadata`), undoing MySQL batch escapes.
- `wca_data/schema.py` — the database's tables and `SCHEMA_VERSION`; documented for other apps in `wca_data/SCHEMA.md` (a test keeps them in sync).
- `wca_data/build.py` — `build_database` (export zip → SQLite) and the nightly job, `python -m wca_data.build`: skips an unchanged export, checks the version, sanity-checks against the live database, swaps atomically keeping `.prev`. Settings: `WCA_DATA_DB_PATH`, `WCA_DATA_PING_URL`.
- `wca_data/read.py` — the read library: `WcaData.open()` (read-only, per request, checks the schema version) with `metadata`, `person`, `search_persons`, `events`, `competed_events`, `competitions`, `results`; plain dataclasses. Search is word-prefix FTS plus `persons_cjk` for any run of CJK characters.
- Tests in `tests/wca_data/`, against the hand-made export in `tests/wca_data/fixtures/export/`. No network.

Deployment (phase 4): the VM shared with the scramble app pulls the image; nothing in Actions
connects to it. How to set up and operate it: `docs/runbook.md`.

- `Dockerfile` — one image for the web app and the build; uid 10001, a health check on `/healthz` (never reads the database), and a copy of `deploy/` at `/opt/wca-records-analyser/deploy`.
- `.github/workflows/ci.yml` — `test`; `image` (build, start, wait for healthy) on every branch; `publish` to `ghcr.io/tdshaw2000/wca-records-analyser` (amd64+arm64) on `main` only.
- `deploy/compose.yaml` — services `web` (read-only `/srv/wca-data`, no ports, alias `wca-records-analyser` on the scramble stack's network) and `build` (profile only, nice 19 / idle IO in the container, capped CPU and memory). Both run `${WCA_IMAGE}`.
- `deploy/pull_deploy.py` — stdlib script for the host, every 5 minutes: pins the new digest in `.env`, `compose up --wait web`, rolls back and records an unhealthy image in `bad-images`.
- `deploy/systemd/` — `wca-data-build` (03:30 UTC nightly) and `wca-deploy` services and timers.
- `deploy/caddy/` — reference copy of the site block that lives in the scramble repo's Caddyfile.
- Tests in `tests/deploy/`.

## repo rules (the repo is to become public)

- No self-hosted runners and no `pull_request_target` workflows.
- No secrets in the repo; the only token Actions uses is `GITHUB_TOKEN`.
- The data build runs on the VM, never in Actions.
- Server config is committed as templates under `deploy/`; IPs, OCIDs and SSH details stay in a gitignored file on the VM.

## running and testing

- **Tests:** `.venv/bin/python -m pytest`
- **Run the app:** `WCA_DATA_DB_PATH=<path to a built database> .venv/bin/python -m uvicorn wca_records_analyser.web:app`.

## Review loop

The owner does not review or merge PRs. Claude opens every PR as a draft, gets it through
review and CI, then marks it ready and merges it with a merge commit (never squash or rebase).
The owner is told what shipped, and is only asked when a decision is theirs (see step 6 and
the three-round cap). Merging to main deploys: CI publishes the image and the VM pulls it.

Work is strict TDD: every change in behaviour is a red commit (failing tests) then a green
commit (the code that passes them). Both reviewers check this and block on a break.

Two read-only reviewer subagents:

- `reviewer` (.claude/agents/reviewer.md) reviews every PR: the web app, tests, TDD history.
- `data-reviewer` (.claude/agents/data-reviewer.md) also reviews any PR that touches the data
  layer or the server: `wca_data/`, `tests/wca_data/`, `deploy/`, `*.sql`, the Dockerfile,
  Compose or Caddy files, systemd units and timers. New server config goes under `deploy/`.

A hook (.claude/hooks/review_gate.py) enforces this. It blocks opening a PR that isn't a draft.
It blocks marking ready or merging until the pushed HEAD commit has passed every reviewer it
needs (it works out from the diff against origin/main whether that includes `data-reviewer`).
It blocks merges that aren't merge commits of that exact commit, merges while any CI check run
on that commit is unfinished or failed, auto-merge, --admin merges, and merges through gh api.
It blocks posting the review-gate marker (below) until the same review has passed, and a
marker that doesn't name HEAD as a written-out sha. It also holds gh pr review and every
gh api call that can write (graphql, a field or input flag, or a writing method) until then,
since the body may come from a file. Plain gh api reads, grep and commit messages that
mention the marker are not held. Any error in the hook, even bad input, blocks.
It does not stop direct pushes to main.

GitHub enforces the same thing outside Claude sessions. The `review-gate` check
(.github/workflows/review-gate.yml, .github/scripts/review_check.py) passes only when someone
with write access has posted a PR review holding the marker for the PR's head commit. Every
new push fails it again until the new head is reviewed. main's ruleset requires it and `test`,
and allows only merge commits.

1. Finish the work (red then green), push, and open the PR as a draft.
2. Run `reviewer`, and `data-reviewer` too if the PR touches the paths above. Run them in
   parallel. Give each the PR number and one line on what the change is for. Don't tell them
   what to conclude. Each verdict is recorded automatically when it stops.
3. **Blocking findings** from either reviewer: fix each one test-first, push, and run the
   reviewers again (both, if both are needed). Every commit that either reviewer blocks counts
   as one round, and the hook allows 3. After the third, stop: leave the PR open and unmerged
   and tell the owner in the thread what is still blocking and why. If you think a blocking
   finding is wrong, give that reviewer your evidence on the next round; it still counts.
4. **Once both pass**, post the suggestions as one PR review with event COMMENT and one inline
   comment per suggestion (pull_request_review_write create, add_comment_to_pending_review,
   then submit_pending). Don't act on suggestions unless they are trivial. The review body
   always ends with the marker line `<!-- review-gate: passed <sha> -->`, with `<sha>` the full
   reviewed commit; post the review even when there are no suggestions.
5. **Judgment calls** take the reviewer's recommendation (the owner chose this). List each one,
   with the choice made, in the PR review body and in the message to the owner.
6. **If the reviewers disagree** (they recommend different answers to the same judgment call,
   or one blocks what the other recommends), don't pick a side. Stop, leave the PR as a draft,
   and ask the owner in the thread, with each reviewer's position in a line.
7. Wait for CI, including the rerun of `review-gate`, to be green on the reviewed commit
   (pull_request_read get_check_runs; a re-run check counts by its latest run). Then mark
   the PR ready and merge it: merge_pull_request with merge_method "merge" and
   expectedHeadSha set to the reviewed commit.
8. Tell the owner in the thread, in plain words, what shipped and any judgment calls taken.

Limits, on purpose: the hook only runs inside Claude Code sessions; outside them only the
`review-gate` check stands, and it trusts any marker from someone with write access. The check
runs the PR's own copy of its workflow and script, so a PR could edit it to pass; that is
accepted, since only someone with write access can merge. The hook can't see into
curl calls or ad-hoc scripts, so post reviews with the GitHub MCP tools. The hook checks the branch
you are on, so mark ready and merge from the PR's own branch (expectedHeadSha makes GitHub
refuse a merge of any other head). It guards against mistakes, not against an agent that
edits its state.

Verdicts live in .git/claude-review/, one file per branch, and are never committed. In cloud
sessions a reviewer hands its report back before it stops, so the hook sends it back once for
the JSON verdict and records it a few seconds after the report arrives; check for the file
after the reviewer's task has finished. Rounds are
counted per commit reviewed. To start a branch's count again (only when the owner says so):
`rm .git/claude-review/<branch>.json`, with any / in the branch name written as __.
