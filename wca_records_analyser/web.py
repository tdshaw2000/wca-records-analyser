"""Web page for searching World Cube Association competitors by name."""

from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from wca_records_analyser.chart import to_record_series
from wca_records_analyser.events import EVENT_NAMES, named_events
from wca_records_analyser.formatting import format_time
from wca_records_analyser.records import single_record_progression
from wca_records_analyser.wca_client import (
    Person,
    get_competed_events,
    get_competition_dates,
    get_results,
    search_persons,
)

INDEX_ROUTE = "/"
SEARCH_ROUTE = "/search"
RECORDS_ROUTE = "/records"
SEARCH_NAME_PARAMETER = "name"
INDEX_TEMPLATE = "index.html"
RECORDS_TEMPLATE = "records.html"
TEMPLATES_DIRECTORY = Path(__file__).parent / "templates"
STATIC_ROUTE = "/static"
STATIC_NAME = "static"
STATIC_DIRECTORY = Path(__file__).parent / "static"
RESULTS_CONTEXT_KEY = "results"
SEARCHED_NAME_CONTEXT_KEY = "searched_name"
EVENT_NAME_CONTEXT_KEY = "event_name"
PROGRESSION_CONTEXT_KEY = "progression"
CHART_SERIES_CONTEXT_KEY = "chart_series"
TIME_FILTER = "time"

app = FastAPI()
app.mount(
    STATIC_ROUTE,
    StaticFiles(directory=STATIC_DIRECTORY),
    name=STATIC_NAME,
)
templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)
templates.env.filters[TIME_FILTER] = format_time


@dataclass(frozen=True)
class CompetitorResult:
    """A matching competitor together with the events they can be graphed on."""

    person: Person
    events: list


def get_search_function():
    """Provide the function used to search for competitors (overridable in tests)."""
    return search_persons


def get_events_function():
    """Provide the function used to look up a competitor's events (overridable in tests)."""

    def competitor_events(wca_id):
        return named_events(get_competed_events(wca_id))

    return competitor_events


def get_progression_function():
    """Provide the function used to build a record progression (overridable in tests)."""

    def record_progression(wca_id, event_id):
        results = get_results(wca_id, event_id)
        competition_dates = get_competition_dates(wca_id)
        return single_record_progression(results, competition_dates)

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
    events_function=Depends(get_events_function),
):
    results = [
        CompetitorResult(person=person, events=events_function(person.wca_id))
        for person in search_function(name)
    ]
    return _render_index(request, searched_name=name, results=results)


@app.get(RECORDS_ROUTE, response_class=HTMLResponse)
def records(
    request: Request,
    wca_id: str,
    event_id: str,
    progression_function=Depends(get_progression_function),
):
    progression = progression_function(wca_id, event_id)
    return templates.TemplateResponse(
        request=request,
        name=RECORDS_TEMPLATE,
        context={
            EVENT_NAME_CONTEXT_KEY: EVENT_NAMES[event_id],
            PROGRESSION_CONTEXT_KEY: progression,
            CHART_SERIES_CONTEXT_KEY: to_record_series(progression),
        },
    )
