# WCA Records Analyser

Search for a [World Cube Association](https://www.worldcubeassociation.org) (WCA)
competitor by name and explore their speedcubing personal records.

The WCA is the official body for competitive speedcubing and publishes all
competition data. This project builds a small web application on top of that
data. The first feature lets you search for a competitor by name and follow a
link to their official WCA profile; graphing a competitor's personal records for
a chosen puzzle is planned next.

## Features

- Search competitors by name via the WCA public API.
- View a link to each matching competitor's official WCA profile.
- Clear message when a search returns no matches.

## Tech stack

- **Language:** Python 3.12+
- **Web framework:** FastAPI (served with Uvicorn)
- **HTTP client:** httpx
- **Templates:** Jinja2
- **Tests:** pytest
- **CI/CD:** GitHub Actions

## Requirements

- Python 3.12 or newer

## Installation

Create a virtual environment and install the project with its development
dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Running the app

```bash
.venv/bin/uvicorn wca_records_analyser.web:app --reload
```

Then open <http://127.0.0.1:8000> and search for a competitor by name.

> **Note:** if you see `CERTIFICATE_VERIFY_FAILED` when the app calls the WCA
> API, point Python at your system CA bundle:
>
> ```bash
> SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
>   .venv/bin/uvicorn wca_records_analyser.web:app --reload
> ```

## Running the tests

The test suite mocks all HTTP calls, so it runs offline and never contacts the
WCA:

```bash
.venv/bin/pytest
```

## Project structure

```
wca_records_analyser/
├── wca_client.py          # Searches competitors via the WCA persons API
├── web.py                 # FastAPI app: search form and results page
└── templates/
    └── index.html         # Search form and competitor links
tests/                     # pytest suite (HTTP mocked)
```

## Development

This project follows test-driven development: a failing test is written before
any production code, and test changes are committed separately from production
code. See [CLAUDE.md](CLAUDE.md) for the full working standards.

## Roadmap

- Graph a competitor's personal records for a selected puzzle.
- Graceful handling of WCA API errors and timeouts on the page.
