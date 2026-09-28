"""/healthz: the container's liveness check, which must not depend on the database.

The Docker HEALTHCHECK and the pull deploy's keep-or-roll-back decision use it. If it read
the database, a new image with a newer schema would fail against the old database and be
rolled back for good, and CI's smoke run (no database) would fail on every branch.
"""

import pytest
from fastapi.testclient import TestClient

from wca_records_analyser import web
from wca_records_analyser.web import app

HEALTH_PATH = "/healthz"


@pytest.fixture
def client_without_a_database(monkeypatch, tmp_path):
    monkeypatch.setenv("WCA_DATA_DB_PATH", str(tmp_path / "missing.sqlite"))

    def no_database():
        raise AssertionError("the health check read the database")

    app.dependency_overrides[web.get_export_date_function] = lambda: no_database
    yield TestClient(app)
    app.dependency_overrides.pop(web.get_export_date_function, None)


def test_the_health_check_answers_without_a_database(client_without_a_database):
    response = client_without_a_database.get(HEALTH_PATH)
    assert response.status_code == 200
    assert response.text == "ok"


def test_the_health_check_answers_itself_while_the_holding_page_is_on(client_without_a_database, monkeypatch):
    monkeypatch.setattr(web, "HOLDING_PAGE_ENABLED", True)
    response = client_without_a_database.get(HEALTH_PATH)
    assert response.status_code == 200
    assert response.text == "ok"
