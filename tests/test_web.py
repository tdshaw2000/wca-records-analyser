from fastapi.testclient import TestClient

from wca_records_analyser.web import app, get_search_function
from wca_records_analyser.wca_client import Person

SEARCH_ROUTE = "/search"
SEARCH_NAME_PARAMETER = "name"
SEARCHED_NAME = "Mats Valk"

MATS_VALK = Person(
    name="Mats Valk",
    profile_url="https://www.worldcubeassociation.org/persons/2007VALK01",
)


def _search_returning(persons):
    def _search(name):
        return persons

    return _search


def test_index_page_shows_a_name_search_form():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert f'name="{SEARCH_NAME_PARAMETER}"' in response.text


def test_search_lists_a_link_to_each_matching_competitor():
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
    assert MATS_VALK.profile_url in response.text


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
