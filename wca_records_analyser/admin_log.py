"""Who's used the app, parsed from the web container's access log (no HTTP, no docker).

The log text this reads is already filtered to lines naming a wca_id, by
deploy/collect_admin_log.py on the VM — that script has docker access and this doesn't.
Uvicorn's own access log already includes the query string, so every request for a
competitor's page is in it with no extra logging needed.
"""

import re
from dataclasses import dataclass

OVERVIEW_PATH = "/overview"
WCA_ID_PARAMETER = "wca_id"

# A docker-compose "logs -t" line carrying a uvicorn access log entry, e.g.:
#   web-1  | 2026-10-02T06:46:50.123456789Z INFO:     1.2.3.4:5 - "GET /overview?wca_id=X HTTP/1.1" 200 OK
_LOG_LINE = re.compile(
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z).*"
    r'"[A-Z]+ (?P<path>\S+) HTTP/\d\.\d"'
)


@dataclass(frozen=True)
class PageVisit:
    """One logged request for a page that named a competitor."""

    wca_id: str
    path: str
    timestamp: str


@dataclass(frozen=True)
class CompetitorUsage:
    """A competitor's overview-page visits, and every other page they viewed."""

    wca_id: str
    overview_visits: list
    other_visits: list


def parse_visits(log_text):
    """Return a PageVisit for each logged request whose query string names a wca_id."""
    visits = []
    for line in log_text.splitlines():
        match = _LOG_LINE.search(line)
        if not match:
            continue
        path = match.group("path")
        wca_id = _wca_id_from_path(path)
        if wca_id is None:
            continue
        visits.append(
            PageVisit(wca_id=wca_id, path=path, timestamp=match.group("timestamp"))
        )
    return visits


def usage_by_wca_id(visits):
    """Group visits by competitor, keeping only those who visited the overview page.

    Each competitor's overview visits are the top-level entry; every other page they
    visited nests under it. Ordered by their most recent overview visit, newest first.
    """
    overview_visits_by_id = {}
    other_visits_by_id = {}
    for visit in visits:
        path = visit.path.split("?", 1)[0]
        bucket = overview_visits_by_id if path == OVERVIEW_PATH else other_visits_by_id
        bucket.setdefault(visit.wca_id, []).append(visit)

    usage = [
        CompetitorUsage(
            wca_id=wca_id,
            overview_visits=overview_visits,
            other_visits=other_visits_by_id.get(wca_id, []),
        )
        for wca_id, overview_visits in overview_visits_by_id.items()
    ]
    usage.sort(key=lambda entry: entry.overview_visits[-1].timestamp, reverse=True)
    return usage


def _wca_id_from_path(path):
    query = path.split("?", 1)[1] if "?" in path else ""
    for pair in query.split("&"):
        key, _, value = pair.partition("=")
        if key == WCA_ID_PARAMETER and value:
            return value
    return None
