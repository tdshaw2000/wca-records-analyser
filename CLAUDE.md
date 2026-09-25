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
- **HTTP:** httpx (against the WCA public API at `https://www.worldcubeassociation.org/api/v0`)
- **Charting:** Chart.js (vendored under `static/vendor/`, no CDN) with the date-fns adapter for time axes.
- **CI/CD:** GitHub Actions (hosted runners; `.github/workflows/ci.yml`)

## project structure

Each module owns one concern; keep HTTP, analysis, presentation, and web wiring separate.

- `wca_client.py` — WCA API access only. `search_persons`, `get_results`, `get_competition_dates`, `get_competed_events`; dataclasses `Person`, `Result`. Functions take an optional `client` for test injection.
- `records.py` — PR analysis (no HTTP). `personal_record_flags`, `single_record_progression`; dataclass `RecordPoint`. Singles are centiseconds; non-positive values are DNF/DNS and are skipped.
- `events.py` — event id → display name table (`EVENT_NAMES`) and `named_events`; dataclass `Event`.
- `formatting.py` — `format_single` renders centiseconds as a cubing time string.
- `chart.py` — shapes `RecordPoint` progressions into JSON-serialisable chart series (no HTTP); rendered client-side by `static/records-chart.js`.
- `web.py` — FastAPI routes (`/`, `/search`, `/records`) with injectable `Depends` seams (`get_search_function`, `get_events_function`, `get_progression_function`) so web tests never hit the network. Templates in `templates/`.
  - **Holding page:** since the WCA API access change of 24 September 2026, `HOLDING_PAGE_ENABLED = True` makes a middleware answer every non-static request with `templates/holding.html` (status 200, so Render's `/` health check still passes). Set it to `False` to restore the app. `tests/conftest.py` disables it for the normal suite; `tests/test_holding_page.py` re-enables it.

## running and testing

- **Tests:** `.venv/bin/python -m pytest`
- **Run the app:** `.venv/bin/python -m uvicorn wca_records_analyser.web:app`. TLS to the live API works without any extra environment: `wca_client` calls `truststore.inject_into_ssl()` at import, so httpx verifies against the OS trust store (which holds the host's Zscaler proxy CA) instead of certifi's bundle.
