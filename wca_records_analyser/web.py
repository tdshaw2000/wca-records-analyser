"""Web page for searching World Cube Association competitors by name."""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_303_SEE_OTHER

from wca_records_analyser.cache import ttl_cached
from wca_records_analyser.concurrency import run_concurrently
from wca_records_analyser.chart import (
    to_consistency_series,
    to_daily_range_series,
    to_gap_series,
    to_record_series,
)
from wca_records_analyser.events import EVENT_NAMES, named_events
from wca_records_analyser.formatting import (
    MULTI_BLIND_EVENT_ID,
    event_has_average,
    format_average,
    format_single,
    result_unit,
)
from wca_records_analyser.overview import overview_rows
from wca_records_analyser.records import (
    all_solves_over_time,
    average_record_progression,
    average_results_over_time,
    consistency_over_time,
    daily_solve_range_over_time,
    single_record_progression,
)
from wca_records_analyser.wca_client import (
    get_competition_dates,
    get_profile,
    get_results,
    search_persons,
)

INDEX_ROUTE = "/"
SEARCH_ROUTE = "/search"
API_SEARCH_ROUTE = "/api/search"
RECORDS_ROUTE = "/records"
OVERVIEW_ROUTE = "/overview"
OVERVIEW_ROWS_ROUTE = "/overview/rows"
SEARCH_NAME_PARAMETER = "name"
SEARCH_QUERY_PARAMETER = "q"
WCA_ID_QUERY_PARAMETER = "wca_id"
SINGLE_MATCH_COUNT = 1
MINIMUM_SEARCH_LENGTH = 3
MAX_SEARCH_SUGGESTIONS = 10
SUGGESTION_WCA_ID_KEY = "wca_id"
SUGGESTION_NAME_KEY = "name"
INDEX_TEMPLATE = "index.html"
RECORDS_TEMPLATE = "records.html"
OVERVIEW_TEMPLATE = "overview.html"
OVERVIEW_ROWS_TEMPLATE = "overview_rows.html"
TEMPLATES_DIRECTORY = Path(__file__).parent / "templates"
STATIC_ROUTE = "/static"
STATIC_NAME = "static"
STATIC_DIRECTORY = Path(__file__).parent / "static"
RESULTS_CONTEXT_KEY = "results"
SEARCHED_NAME_CONTEXT_KEY = "searched_name"
WCA_ID_CONTEXT_KEY = "wca_id"
NAME_CONTEXT_KEY = "name"
AVATAR_THUMB_URL_CONTEXT_KEY = "avatar_thumb_url"
EVENT_ID_CONTEXT_KEY = "event_id"
EVENTS_CONTEXT_KEY = "events"
PROFILE_URL_CONTEXT_KEY = "profile_url"
EVENT_NAME_CONTEXT_KEY = "event_name"
SINGLE_PROGRESSION_CONTEXT_KEY = "single_progression"
AVERAGE_PROGRESSION_CONTEXT_KEY = "average_progression"
SINGLE_CHART_SERIES_CONTEXT_KEY = "single_chart_series"
AVERAGE_CHART_SERIES_CONTEXT_KEY = "average_chart_series"
GAP_CHART_SERIES_CONTEXT_KEY = "gap_chart_series"
ALL_SINGLES_CHART_SERIES_CONTEXT_KEY = "all_singles_chart_series"
ALL_AVERAGES_CHART_SERIES_CONTEXT_KEY = "all_averages_chart_series"
DAILY_RANGE_SERIES_CONTEXT_KEY = "daily_range_series"
CONSISTENCY_SERIES_CONTEXT_KEY = "consistency_series"
RESULT_UNIT_CONTEXT_KEY = "result_unit"
EVENT_HAS_AVERAGE_CONTEXT_KEY = "event_has_average"
OVERVIEW_ROWS_CONTEXT_KEY = "overview_rows"
SKELETON_ROW_COUNT_CONTEXT_KEY = "skeleton_row_count"
OVERVIEW_ROWS_URL_CONTEXT_KEY = "overview_rows_url"
SINGLE_FILTER = "single"
AVERAGE_FILTER = "average"
STATIC_VERSION_GLOBAL = "static_version"
VERSION_HASH_LENGTH = 8

app = FastAPI()
app.mount(
    STATIC_ROUTE,
    StaticFiles(directory=STATIC_DIRECTORY),
    name=STATIC_NAME,
)
def static_asset_version(filename):
    """Return a short content hash of a static file, for cache-busting its URL."""
    contents = (STATIC_DIRECTORY / filename).read_bytes()
    return hashlib.sha256(contents).hexdigest()[:VERSION_HASH_LENGTH]


templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)
templates.env.filters[SINGLE_FILTER] = format_single
templates.env.filters[AVERAGE_FILTER] = format_average
templates.env.globals[STATIC_VERSION_GLOBAL] = static_asset_version


@dataclass(frozen=True)
class RecordProgressions:
    """A competitor's single and average PR progressions, plus per-sitting consistency."""

    singles: list
    averages: list
    all_singles: list = field(default_factory=list)
    all_averages: list = field(default_factory=list)
    daily_ranges: list = field(default_factory=list)
    consistency: list = field(default_factory=list)


@dataclass(frozen=True)
class Overview:
    """A competitor's identity and their per-event latest-PR age rows."""

    person: object
    rows: list


# A competitor's WCA data changes at most once per competition, so caching each
# fetch for an hour spares the overview its burst of per-event calls on revisits
# (and speeds the records pages, which share the same lookups).
CACHE_TTL_SECONDS = 60 * 60
# Cap on simultaneous per-event fetches when building an overview: enough to
# collapse the sequential wait for a many-event competitor, while staying a
# considerate caller against an API that publishes no rate limit of its own.
MAX_CONCURRENT_FETCHES = 8
cached_profile = ttl_cached(CACHE_TTL_SECONDS, time.monotonic)(get_profile)
cached_competition_dates = ttl_cached(CACHE_TTL_SECONDS, time.monotonic)(
    get_competition_dates
)
cached_results = ttl_cached(CACHE_TTL_SECONDS, time.monotonic)(get_results)


def get_search_function():
    """Provide the function used to search for competitors (overridable in tests)."""
    return search_persons


def get_overview_function():
    """Provide the function used to build a competitor's overview (overridable in tests)."""

    def build_overview(wca_id):
        profile = cached_profile(wca_id)
        competition_dates = cached_competition_dates(wca_id)
        # The per-event result fetches are independent, so fan them out rather
        # than paying one sequential round-trip per event.
        results_per_event = run_concurrently(
            [
                lambda event_id=event_id: cached_results(wca_id, event_id)
                for event_id in profile.event_ids
            ],
            MAX_CONCURRENT_FETCHES,
        )
        results_by_event = dict(zip(profile.event_ids, results_per_event))
        rows = overview_rows(
            profile.event_ids,
            results_by_event,
            competition_dates,
            date.today().isoformat(),
        )
        return Overview(person=profile.person, rows=rows)

    return build_overview


def get_profile_function():
    """Provide the function used to look up a competitor's profile (overridable in tests)."""
    return cached_profile


def get_progression_function():
    """Provide the function used to build a record progression (overridable in tests)."""

    def record_progression(wca_id, event_id):
        results = cached_results(wca_id, event_id)
        competition_dates = cached_competition_dates(wca_id)
        return RecordProgressions(
            singles=single_record_progression(results, competition_dates),
            averages=average_record_progression(results, competition_dates),
            all_singles=all_solves_over_time(results, competition_dates),
            all_averages=average_results_over_time(results, competition_dates),
            daily_ranges=daily_solve_range_over_time(results, competition_dates),
            consistency=consistency_over_time(results, competition_dates),
        )

    return record_progression


def _render_index(request, searched_name, results):
    return templates.TemplateResponse(
        request=request,
        name=INDEX_TEMPLATE,
        context={
            SEARCHED_NAME_CONTEXT_KEY: searched_name,
            RESULTS_CONTEXT_KEY: results,
        },
    )


@app.get(INDEX_ROUTE, response_class=HTMLResponse)
def index(request: Request):
    return _render_index(request, searched_name=None, results=None)


@app.get(SEARCH_ROUTE, response_class=HTMLResponse)
def search(
    request: Request,
    name: str,
    search_function=Depends(get_search_function),
):
    results = search_function(name)
    # A search that pins down exactly one competitor may as well skip the
    # single-item results list and take them straight to that overview.
    if len(results) == SINGLE_MATCH_COUNT:
        overview_url = (
            f"{OVERVIEW_ROUTE}?{WCA_ID_QUERY_PARAMETER}={results[0].wca_id}"
        )
        return RedirectResponse(overview_url, status_code=HTTP_303_SEE_OTHER)
    return _render_index(request, searched_name=name, results=results)


@app.get(API_SEARCH_ROUTE)
def api_search(
    q: str,
    search_function=Depends(get_search_function),
):
    # Guard the unindexed LIKE scan server-side too, not just in the browser: a
    # 1-2 character query would make WCA scan its whole persons table.
    if len(q.strip()) < MINIMUM_SEARCH_LENGTH:
        return []
    results = search_function(q)
    return [
        {
            SUGGESTION_WCA_ID_KEY: person.wca_id,
            SUGGESTION_NAME_KEY: person.name,
        }
        for person in results[:MAX_SEARCH_SUGGESTIONS]
    ]


@app.get(OVERVIEW_ROUTE, response_class=HTMLResponse)
def overview(
    request: Request,
    wca_id: str,
    profile_function=Depends(get_profile_function),
):
    # Only the profile (one fetch) is needed to render the shell instantly; the
    # slow per-event rows arrive afterwards from the fragment endpoint. One
    # skeleton row per competed event keeps the table from jumping once they land.
    profile = profile_function(wca_id)
    person = profile.person
    return templates.TemplateResponse(
        request=request,
        name=OVERVIEW_TEMPLATE,
        context={
            WCA_ID_CONTEXT_KEY: wca_id,
            NAME_CONTEXT_KEY: person.name,
            AVATAR_THUMB_URL_CONTEXT_KEY: person.avatar_thumb_url,
            PROFILE_URL_CONTEXT_KEY: person.profile_url,
            SKELETON_ROW_COUNT_CONTEXT_KEY: len(profile.event_ids),
            OVERVIEW_ROWS_URL_CONTEXT_KEY: (
                f"{OVERVIEW_ROWS_ROUTE}?{WCA_ID_QUERY_PARAMETER}={wca_id}"
            ),
        },
    )


@app.get(OVERVIEW_ROWS_ROUTE, response_class=HTMLResponse)
def overview_rows_fragment(
    request: Request,
    wca_id: str,
    overview_function=Depends(get_overview_function),
):
    competitor_overview = overview_function(wca_id)
    return templates.TemplateResponse(
        request=request,
        name=OVERVIEW_ROWS_TEMPLATE,
        context={
            WCA_ID_CONTEXT_KEY: wca_id,
            OVERVIEW_ROWS_CONTEXT_KEY: competitor_overview.rows,
        },
    )


@app.get(RECORDS_ROUTE, response_class=HTMLResponse)
def records(
    request: Request,
    wca_id: str,
    event_id: str,
    progression_function=Depends(get_progression_function),
    profile_function=Depends(get_profile_function),
):
    progressions = progression_function(wca_id, event_id)
    profile = profile_function(wca_id)
    person = profile.person
    single_chart_series = to_record_series(
        progressions.singles, event_id, is_average=False
    )
    average_chart_series = to_record_series(
        progressions.averages, event_id, is_average=True
    )
    # Multi-Blind solves are encoded scores, not times, so a fastest-to-slowest
    # band over them would be meaningless; it is shown for every other event.
    daily_range_series = None
    if event_id != MULTI_BLIND_EVENT_ID and progressions.daily_ranges:
        daily_range_series = to_daily_range_series(
            progressions.daily_ranges, event_id
        )
    return templates.TemplateResponse(
        request=request,
        name=RECORDS_TEMPLATE,
        context={
            WCA_ID_CONTEXT_KEY: wca_id,
            NAME_CONTEXT_KEY: person.name,
            AVATAR_THUMB_URL_CONTEXT_KEY: person.avatar_thumb_url,
            EVENT_ID_CONTEXT_KEY: event_id,
            EVENTS_CONTEXT_KEY: named_events(profile.event_ids),
            PROFILE_URL_CONTEXT_KEY: person.profile_url,
            EVENT_NAME_CONTEXT_KEY: EVENT_NAMES[event_id],
            SINGLE_PROGRESSION_CONTEXT_KEY: progressions.singles,
            AVERAGE_PROGRESSION_CONTEXT_KEY: progressions.averages,
            SINGLE_CHART_SERIES_CONTEXT_KEY: single_chart_series,
            AVERAGE_CHART_SERIES_CONTEXT_KEY: average_chart_series,
            GAP_CHART_SERIES_CONTEXT_KEY: to_gap_series(
                single_chart_series, average_chart_series, event_id
            ),
            ALL_SINGLES_CHART_SERIES_CONTEXT_KEY: to_record_series(
                progressions.all_singles, event_id, is_average=False
            ),
            ALL_AVERAGES_CHART_SERIES_CONTEXT_KEY: to_record_series(
                progressions.all_averages, event_id, is_average=True
            ),
            DAILY_RANGE_SERIES_CONTEXT_KEY: daily_range_series,
            CONSISTENCY_SERIES_CONTEXT_KEY: to_consistency_series(
                progressions.consistency, event_id
            ),
            RESULT_UNIT_CONTEXT_KEY: result_unit(event_id),
            EVENT_HAS_AVERAGE_CONTEXT_KEY: event_has_average(event_id),
        },
    )
