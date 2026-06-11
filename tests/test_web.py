from fastapi.testclient import TestClient

from wca_records_analyser.events import Event
from wca_records_analyser.web import app, get_events_function, get_search_function
from wca_records_analyser.wca_client import Person

SEARCH_ROUTE = "/search"
SEARCH_NAME_PARAMETER = "name"
SEARCHED_NAME = "Mats Valk"

MATS_VALK = Person(
    name="Mats Valk",
    wca_id="2007VALK01",
    profile_url="https://www.worldcubeassociation.org/persons/2007VALK01",
)
MATS_VALK_EVENTS = [
    Event(event_id="222", name="2x2x2 Cube"),
    Event(event_id="333", name="3x3x3 Cube"),
]


def _search_returning(persons):
    def _search(name):
        return persons

    return _search


def _events_returning(events_by_wca_id):
    def _events(wca_id):
        return events_by_wca_id.get(wca_id, [])

    return _events


def test_index_page_shows_a_name_search_form():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert f'name="{SEARCH_NAME_PARAMETER}"' in response.text


def test_search_lists_a_link_to_each_matching_competitor():
    app.dependency_overrides[get_search_function] = lambda: _search_returning(
        [MATS_VALK]
    )
    app.dependency_overrides[get_events_function] = lambda: _events_returning(
        {MATS_VALK.wca_id: MATS_VALK_EVENTS}
    )
    try:
        client = TestClient(app)
        response = client.get(
            SEARCH_ROUTE, params={SEARCH_NAME_PARAMETER: SEARCHED_NAME}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert MATS_VALK.name in response.text
    assert MATS_VALK.profile_url in response.text


def test_search_shows_an_event_dropdown_of_each_competitors_events():
    app.dependency_overrides[get_search_function] = lambda: _search_returning(
        [MATS_VALK]
    )
    app.dependency_overrides[get_events_function] = lambda: _events_returning(
        {MATS_VALK.wca_id: MATS_VALK_EVENTS}
    )
    try:
        client = TestClient(app)
        response = client.get(
            SEARCH_ROUTE, params={SEARCH_NAME_PARAMETER: SEARCHED_NAME}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert 'name="event_id"' in response.text
    for event in MATS_VALK_EVENTS:
        assert f'value="{event.event_id}"' in response.text
        assert event.name in response.text


def test_search_with_no_matches_shows_a_friendly_message():
    app.dependency_overrides[get_search_function] = lambda: _search_returning([])
    try:
        client = TestClient(app)
        response = client.get(
            SEARCH_ROUTE, params={SEARCH_NAME_PARAMETER: "no such competitor"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "No competitors found" in response.text
