"""Each visitor can pick their own skin from the gear menu; it is remembered in a cookie,
the same mechanism Scramble Challenge uses (gear menu, cookie, per-skin stylesheet)."""

import re

import pytest
from fastapi.testclient import TestClient

from wca_records_analyser.wca_client import Person, Profile
from wca_records_analyser.web import (
    DEFAULT_THEME,
    STATIC_DIRECTORY,
    THEME_COOKIE_NAME,
    THEMES,
    RecordProgressions,
    app,
    get_map_function,
    get_profile_function,
    get_progression_function,
)

STATIC_THEMES_DIRECTORY = STATIC_DIRECTORY / "themes"


def skin_cookie(client):
    found = client.cookies.get(THEME_COOKIE_NAME)
    return found


def skin_options(html: str) -> list[tuple[str, str, bool]]:
    """(value, label, is_current) for each button in the skin menu."""
    return [
        (value, label.strip(), bool(current))
        for value, current, label in re.findall(
            r'<button[^>]*name="skin" value="([^"]+)"( aria-current="true")?[^>]*>([^<]+)</button>',
            html,
        )
    ]


ALL_THEME_KEYS = ["plain", "dark", "dos", "mario64", "monkeyisland2", "neon80s"]
ALL_THEME_OPTIONS = [
    ("plain", "Minimal"),
    ("dark", "Dark"),
    ("dos", "DOS"),
    ("mario64", "Mario"),
    ("monkeyisland2", "Monkey"),
    ("neon80s", "VHS"),
]


def test_every_listed_theme_has_a_stylesheet():
    assert list(THEMES) == ALL_THEME_KEYS
    for theme in THEMES:
        assert (STATIC_THEMES_DIRECTORY / theme / "theme.css").is_file()


def test_the_default_theme_is_one_of_the_listed_themes():
    assert DEFAULT_THEME in THEMES


def test_the_index_page_offers_each_skin_and_ticks_the_default_one():
    client = TestClient(app)

    response = client.get("/")

    assert skin_options(response.text) == [
        (value, label, value == DEFAULT_THEME) for value, label in ALL_THEME_OPTIONS
    ]


@pytest.mark.parametrize("chosen", ALL_THEME_KEYS)
def test_a_chosen_skin_cookie_ticks_that_skin(chosen):
    client = TestClient(app)
    client.cookies.set(THEME_COOKIE_NAME, chosen)

    response = client.get("/")

    assert skin_options(response.text) == [
        (value, label, value == chosen) for value, label in ALL_THEME_OPTIONS
    ]


@pytest.mark.parametrize("chosen", ALL_THEME_KEYS)
def test_a_chosen_skin_cookie_links_that_skins_stylesheet(chosen):
    client = TestClient(app)
    client.cookies.set(THEME_COOKIE_NAME, chosen)

    response = client.get("/")

    assert f"/static/themes/{chosen}/theme.css" in response.text


@pytest.mark.parametrize("theme", ALL_THEME_KEYS)
def test_every_theme_styles_the_skin_picker(theme):
    css = (STATIC_THEMES_DIRECTORY / theme / "theme.css").read_text()

    for variable in (
        "--page-background",
        "--surface",
        "--text",
        "--muted-text",
        "--border",
        "--accent",
        "--accent-hover",
        "--accent-soft",
        "--table-head-background",
        "--overlay-background",
    ):
        assert variable in css, variable


def test_an_unknown_skin_in_the_cookie_falls_back_to_the_default():
    client = TestClient(app)
    client.cookies.set(THEME_COOKIE_NAME, "../../secrets")

    response = client.get("/")

    assert f"/static/themes/{DEFAULT_THEME}/theme.css" in response.text


def test_choosing_a_skin_remembers_it_and_goes_back():
    client = TestClient(app)

    response = client.post(
        "/skin", data={"skin": "dark", "next": "/records?wca_id=abc&event_id=333"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/records?wca_id=abc&event_id=333"
    assert skin_cookie(client) == "dark"


def test_skin_cookie_is_long_lived_and_hidden_from_scripts():
    client = TestClient(app)

    response = client.post(
        "/skin", data={"skin": "dark", "next": "/"}, follow_redirects=False
    )

    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie or "SameSite=Lax" in set_cookie
    assert "Max-Age=" in set_cookie


def test_an_unknown_skin_is_refused():
    client = TestClient(app)

    response = client.post(
        "/skin", data={"skin": "neon", "next": "/"}, follow_redirects=False
    )

    assert response.status_code == 400
    assert skin_cookie(client) is None


@pytest.mark.parametrize(
    "next_url",
    [
        "",
        "https://evil.example/",
        "//evil.example/",
        "/\\evil.example",
        "c/abc",
        # Browsers and Werkzeug/Starlette drop tabs and newlines, which would leave //evil.example.
        "/\t/evil.example",
        "/\n/evil.example",
        "/\r/evil.example",
        "/ /evil.example",
    ],
)
def test_choosing_a_skin_only_goes_back_to_a_page_on_this_site(next_url):
    client = TestClient(app)

    response = client.post(
        "/skin",
        data={"skin": "dark", "next": next_url},
        follow_redirects=False,
    )

    assert response.headers["location"] == "/"


def test_the_gear_menu_is_on_the_records_page_too():
    person = Person(
        wca_id="2007VALK01", name="Mats Valk", country_id="Netherlands", profile_url=""
    )
    profile = Profile(person=person, event_ids=["333"])

    def _map_returning(singles, averages):
        def build(wca_id, event_id):
            return {"singles": singles, "averages": averages}

        return build

    app.dependency_overrides[get_profile_function] = lambda: (lambda wca_id: profile)
    app.dependency_overrides[get_progression_function] = lambda: (
        lambda wca_id, event_id: RecordProgressions(singles=[], averages=[])
    )
    app.dependency_overrides[get_map_function] = lambda: _map_returning([], [])
    try:
        client = TestClient(app)
        response = client.get(
            "/records", params={"wca_id": person.wca_id, "event_id": "333"}
        )
    finally:
        app.dependency_overrides.clear()

    assert len(skin_options(response.text)) == len(ALL_THEME_KEYS)
