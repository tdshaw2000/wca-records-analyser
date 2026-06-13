# CLAUDE.md — WCA Records Analyser

> This file defines the working standards for this project.
> Claude must follow all rules below at all times, without exception.

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
- **HTTP:** httpx (against the WCA public API at `https://www.worldcubeassociation.org/api/v0`)
- **Charting:** Chart.js (vendored under `static/vendor/`, no CDN) with the date-fns adapter for time axes.
- **CI/CD:** gitlab

## project structure

Each module owns one concern; keep HTTP, analysis, presentation, and web wiring separate.

- `wca_client.py` — WCA API access only. `search_persons`, `get_results`, `get_competition_dates`, `get_competed_events`; dataclasses `Person`, `Result`. Functions take an optional `client` for test injection.
- `records.py` — PR analysis (no HTTP). `personal_record_flags`, `single_record_progression`; dataclass `RecordPoint`. Singles are centiseconds; non-positive values are DNF/DNS and are skipped.
- `events.py` — event id → display name table (`EVENT_NAMES`) and `named_events`; dataclass `Event`.
- `formatting.py` — `format_single` renders centiseconds as a cubing time string.
- `chart.py` — shapes `RecordPoint` progressions into JSON-serialisable chart series (no HTTP); rendered client-side by `static/records-chart.js`.
- `web.py` — FastAPI routes (`/`, `/search`, `/records`) with injectable `Depends` seams (`get_search_function`, `get_events_function`, `get_progression_function`) so web tests never hit the network. Templates in `templates/`.

## running and testing

- **Tests:** `.venv/bin/python -m pytest`
- **Run the app:** `.venv/bin/python -m uvicorn wca_records_analyser.web:app`. TLS to the live API works without any extra environment: `wca_client` calls `truststore.inject_into_ssl()` at import, so httpx verifies against the OS trust store (which holds the host's Zscaler proxy CA) instead of certifi's bundle.

## test-driven development

- **Tests first.** Write a failing test before writing any production code. No exceptions.
- The red-green-refactor cycle is mandatory: red → green → refactor.
- **Never mix test changes and business logic changes in the same commit.** Each commit must touch either tests or production code, not both.
- **Never modify an existing test to make failing code pass.** If a test is wrong, raise it explicitly and wait for direction. Fix the implementation, not the contract.

## commit discipline

- Commit frequently. Do not accumulate large diffs. Every logical unit of work is a candidate for a commit.
- Each commit must represent exactly one logical change. If you find yourself writing "and" in a commit message, split the commit.
- Commit messages follow **Conventional Commits (feat/fix/chore/test)** format.

## code style

- **Constants over literals.** All magic numbers and string literals must be extracted into named constants. Inline literals (other than 0, 1, empty string, true/false) are not permitted in business logic.
- **Meaningful, unabbreviated names.** Identifiers must be self-documenting. Avoid abbreviations unless they are universally understood domain terms.
- **Single responsibility.** Methods do one thing. Classes own one concept. If you need "and" to describe what a method does, split it.
- **No dead code.** Remove unused methods, variables, imports, and classes. Do not comment out code — delete it. Version control is the history.

## working style

- Explain your reasoning before making changes, especially when multiple approaches exist.
- If a requirement is ambiguous, ask a clarifying question before proceeding.
- After each commit-worthy change, pause and confirm before moving to the next step.
- Do not refactor and add functionality in the same step.
