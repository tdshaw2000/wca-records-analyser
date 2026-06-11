"""Web page for searching World Cube Association competitors by name."""

from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from wca_records_analyser.events import named_events
from wca_records_analyser.wca_client import (
    Person,
    get_competed_events,
    search_persons,
)

INDEX_ROUTE = "/"
SEARCH_ROUTE = "/search"
SEARCH_NAME_PARAMETER = "name"
INDEX_TEMPLATE = "index.html"
TEMPLATES_DIRECTORY = Path(__file__).parent / "templates"
RESULTS_CONTEXT_KEY = "results"
SEARCHED_NAME_CONTEXT_KEY = "searched_name"

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIRECTORY)


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
