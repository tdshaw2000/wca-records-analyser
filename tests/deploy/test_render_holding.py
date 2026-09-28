"""The static page Render serves at the old URL: a link to the new site, no auto-redirect."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "deploy" / "render-holding" / "index.html"
NEW_SITE_URL = "https://wca-records-analyser.duckdns.org"


def test_the_page_links_to_the_new_site():
    html = PAGE.read_text()
    assert f'href="{NEW_SITE_URL}"' in html


def test_the_page_does_not_auto_redirect():
    html = PAGE.read_text().lower()
    assert "http-equiv=\"refresh\"" not in html
    assert "window.location" not in html
    assert "<meta http-equiv=refresh" not in html
