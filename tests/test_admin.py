"""The /admin route: who's used the app, behind HTTP Basic auth."""

import pytest
from fastapi.testclient import TestClient

from wca_records_analyser.web import ADMIN_ROUTE, app, get_admin_log_text_function

PASSWORD_ENVIRONMENT_VARIABLE = "ADMIN_PASSWORD"
PASSWORD = "s3cret"

OVERVIEW_LINE = (
    'web-1  | 2026-10-02T06:46:50.123456789Z INFO:     1.2.3.4:5 - '
    '"GET /overview?wca_id=2015DOEJ01 HTTP/1.1" 200 OK'
)
RECORDS_LINE = (
    'web-1  | 2026-10-02T06:47:01.987654321Z INFO:     1.2.3.4:5 - '
    '"GET /records?wca_id=2015DOEJ01&event_id=333 HTTP/1.1" 200 OK'
)


def _get(auth=(("admin", PASSWORD))):
    app.dependency_overrides[get_admin_log_text_function] = lambda: (
        lambda: "\n".join([OVERVIEW_LINE, RECORDS_LINE])
    )
    try:
        client = TestClient(app)
        return client.get(ADMIN_ROUTE, auth=auth)
    finally:
        app.dependency_overrides.clear()


def test_admin_is_a_404_when_no_password_is_configured(monkeypatch):
    monkeypatch.delenv(PASSWORD_ENVIRONMENT_VARIABLE, raising=False)
    response = _get(auth=None)
    assert response.status_code == 404


def test_admin_requires_credentials_once_a_password_is_configured(monkeypatch):
    monkeypatch.setenv(PASSWORD_ENVIRONMENT_VARIABLE, PASSWORD)
    response = _get(auth=None)
    assert response.status_code == 401


def test_admin_rejects_the_wrong_password(monkeypatch):
    monkeypatch.setenv(PASSWORD_ENVIRONMENT_VARIABLE, PASSWORD)
    response = _get(auth=("admin", "wrong"))
    assert response.status_code == 401


def test_admin_lists_the_competitor_and_their_other_pages_once_authenticated(monkeypatch):
    monkeypatch.setenv(PASSWORD_ENVIRONMENT_VARIABLE, PASSWORD)
    response = _get()
    assert response.status_code == 200
    assert "2015DOEJ01" in response.text
    assert "/records?wca_id=2015DOEJ01&amp;event_id=333" in response.text


@pytest.fixture(autouse=True)
def _clean_up_overrides():
    yield
    app.dependency_overrides.clear()
