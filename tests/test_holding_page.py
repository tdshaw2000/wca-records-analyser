import pytest
from fastapi.testclient import TestClient

from wca_records_analyser import web
from wca_records_analyser.web import app, get_search_function

HOLDING_MESSAGE = (
    "As of 24th September 2026, this app is no longer working due to a change "
    "in WCA API access, which it relied on. Until a new solution is found, this "
    "unfortunately cannot be rectified."
)
STYLESHEET_PATH = "/static/styles.css"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(web, "HOLDING_PAGE_ENABLED", True)
    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/search?name=Mats",
        "/api/search?q=Mats",
        "/overview?wca_id=2007VALK01",
        "/records?wca_id=2007VALK01&event_id=333",
    ],
)
def test_every_page_shows_the_holding_message(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert HOLDING_MESSAGE in response.text


def test_holding_page_never_calls_the_wca_api(client):
    def failing_search(name):
        raise AssertionError("the holding page must not reach the WCA API")

    app.dependency_overrides[get_search_function] = lambda: failing_search
    try:
        response = client.get("/search?name=Mats")
    finally:
        app.dependency_overrides.clear()

    assert HOLDING_MESSAGE in response.text


def test_holding_page_still_serves_static_assets(client):
    response = client.get(STYLESHEET_PATH)

    assert response.status_code == 200
    assert HOLDING_MESSAGE not in response.text
