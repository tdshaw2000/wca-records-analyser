import pytest

from wca_records_analyser import web


@pytest.fixture(autouse=True)
def holding_page_disabled(monkeypatch):
    """Serve the real app in tests; holding-page tests opt back in explicitly."""
    monkeypatch.setattr(web, "HOLDING_PAGE_ENABLED", False)
