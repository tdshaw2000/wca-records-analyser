from fastapi.testclient import TestClient

from wca_records_analyser.records import RecordPoint
from wca_records_analyser.web import (
    RecordProgressions,
    app,
    get_progression_function,
    get_search_function,
)
from wca_records_analyser.wca_client import Person

SEARCH_ROUTE = "/search"
RECORDS_ROUTE = "/records"
SEARCH_NAME_PARAMETER = "name"
SEARCHED_NAME = "Mats Valk"
EVENT_ID = "333"
EVENT_NAME = "3x3x3 Cube"
DEFAULT_EVENT_ID = "333"

SINGLE_PROGRESSION = [
    RecordPoint(date="2023-11-18", value=1777),
    RecordPoint(date="2024-11-01", value=1498),
]
AVERAGE_PROGRESSION = [
    RecordPoint(date="2023-11-18", value=2177),
    RecordPoint(date="2024-11-01", value=1888),
]
PROGRESSIONS = RecordProgressions(
    singles=SINGLE_PROGRESSION, averages=AVERAGE_PROGRESSION
)

MATS_VALK = Person(
    name="Mats Valk",
    wca_id="2007VALK01",
    profile_url="https://www.worldcubeassociation.org/persons/2007VALK01",
)


def _search_returning(persons):
    def _search(name):
        return persons

    return _search


def _progression_returning(progressions):
    def _progression(wca_id, event_id):
        return progressions

    return _progression


def test_index_page_shows_a_name_search_form():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert f'name="{SEARCH_NAME_PARAMETER}"' in response.text


def test_search_links_each_competitor_to_their_default_event_records():
    app.dependency_overrides[get_search_function] = lambda: _search_returning(
        [MATS_VALK]
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
    assert RECORDS_ROUTE in response.text
    assert f"wca_id={MATS_VALK.wca_id}" in response.text
    assert f"event_id={DEFAULT_EVENT_ID}" in response.text


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


def _get_records_page():
    app.dependency_overrides[get_progression_function] = (
        lambda: _progression_returning(PROGRESSIONS)
    )
    try:
        client = TestClient(app)
        return client.get(
            RECORDS_ROUTE,
            params={"wca_id": MATS_VALK.wca_id, "event_id": EVENT_ID},
        )
    finally:
        app.dependency_overrides.clear()


def test_records_embeds_both_single_and_average_progressions_as_chart_data():
    response = _get_records_page()

    assert response.status_code == 200
    assert "<canvas" in response.text
    assert 'id="single-chart-data"' in response.text
    assert '"y": 1498' in response.text
    assert '"display": "14.98"' in response.text
    assert 'id="average-chart-data"' in response.text
    assert '"y": 1888' in response.text
    assert '"display": "18.88"' in response.text


def test_records_shows_a_table_of_the_single_record_progression():
    response = _get_records_page()

    assert response.status_code == 200
    assert EVENT_NAME in response.text
    assert "single record progression" in response.text
    assert "2023-11-18" in response.text
    assert "17.77" in response.text
    assert "2024-11-01" in response.text
    assert "14.98" in response.text


def test_records_shows_a_table_of_the_average_record_progression():
    response = _get_records_page()

    assert response.status_code == 200
    assert "average record progression" in response.text
    assert "21.77" in response.text
    assert "18.88" in response.text
