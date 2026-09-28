from datetime import date

import pytest

from wca_records_analyser import web


@pytest.fixture(autouse=True)
def holding_page_disabled(monkeypatch):
    """Serve the real app in tests; holding-page tests opt back in explicitly."""
    monkeypatch.setattr(web, "HOLDING_PAGE_ENABLED", False)


@pytest.fixture(autouse=True)
def default_export_date():
    """Give every page a WCA export date without needing a real database.

    Tests that care about the licence notice itself override this dependency
    with their own date; this default just keeps unrelated tests off the network.
    """
    web.app.dependency_overrides[web.get_export_date_function] = lambda: (
        lambda: date(2026, 9, 23)
    )
    yield
    web.app.dependency_overrides.pop(web.get_export_date_function, None)
