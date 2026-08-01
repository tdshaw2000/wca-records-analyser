from types import SimpleNamespace

from fastapi.testclient import TestClient

from wca_records_analyser.events import Event
from wca_records_analyser.overview import EventAges
from wca_records_analyser.records import (
    ConsistencyPoint,
    DailySolveRange,
    RecordPoint,
)
from wca_records_analyser.web import (
    STATIC_DIRECTORY,
    Overview,
    RecordProgressions,
    app,
    get_map_function,
    get_overview_function,
    get_profile_function,
    get_progression_function,
    get_search_function,
    static_asset_version,
)
from wca_records_analyser.wca_client import Person, Profile

SEARCH_ROUTE = "/search"
API_SEARCH_ROUTE = "/api/search"
RECORDS_ROUTE = "/records"
OVERVIEW_ROUTE = "/overview"
OVERVIEW_ROWS_ROUTE = "/overview/rows"
SEARCH_NAME_PARAMETER = "name"
SEARCH_QUERY_PARAMETER = "q"
MAX_SEARCH_SUGGESTIONS = 10
SEARCHED_NAME = "Mats Valk"
EVENT_ID = "333"
EVENT_NAME = "3x3x3 Cube"
STYLESHEET_PATH = "/static/styles.css"
STYLESHEET_FILENAME = "styles.css"

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

CONSISTENCY_POINTS = [
    ConsistencyPoint(date="2023-11-18", single=1777, average=2177),
    ConsistencyPoint(date="2024-11-01", single=1498, average=1888),
]
PROGRESSIONS_WITH_CONSISTENCY = SimpleNamespace(
    singles=SINGLE_PROGRESSION,
    averages=AVERAGE_PROGRESSION,
    all_singles=[],
    all_averages=[],
    daily_ranges=[],
    consistency=CONSISTENCY_POINTS,
)
EXPECTED_CONSISTENCY_RATIO = 1.26

NON_RECORD_SINGLE = 2050
NON_RECORD_AVERAGE = 2400
ALL_SINGLES = [
    RecordPoint(date="2023-11-18", value=1777),
    RecordPoint(date="2024-06-01", value=NON_RECORD_SINGLE),
    RecordPoint(date="2024-11-01", value=1498),
]
ALL_AVERAGES = [
    RecordPoint(date="2023-11-18", value=2177),
    RecordPoint(date="2024-06-01", value=NON_RECORD_AVERAGE),
    RecordPoint(date="2024-11-01", value=1888),
]
SLOWEST_SOLVE_OF_DAY = 2300
DAILY_RANGES = [
    DailySolveRange(date="2023-11-18", fastest=1777, slowest=SLOWEST_SOLVE_OF_DAY),
    DailySolveRange(date="2024-11-01", fastest=1498, slowest=1900),
]
PROGRESSIONS_WITH_ALL_RESULTS = SimpleNamespace(
    singles=SINGLE_PROGRESSION,
    averages=AVERAGE_PROGRESSION,
    all_singles=ALL_SINGLES,
    all_averages=ALL_AVERAGES,
    daily_ranges=DAILY_RANGES,
    consistency=[],
)

MATS_VALK_AVATAR_THUMB_URL = (
    "https://avatars.worldcubeassociation.org/2007VALK01_thumb.jpg"
)
MATS_VALK = Person(
    name="Mats Valk",
    wca_id="2007VALK01",
    profile_url="https://www.worldcubeassociation.org/persons/2007VALK01",
    avatar_thumb_url=MATS_VALK_AVATAR_THUMB_URL,
)
FELIKS_ZEMDEGS = Person(
    name="Feliks Zemdegs",
    wca_id="2009ZEMD01",
    profile_url="https://www.worldcubeassociation.org/persons/2009ZEMD01",
    avatar_thumb_url=(
        "https://avatars.worldcubeassociation.org/2009ZEMD01_thumb.jpg"
    ),
)
MANY_COMPETITORS = [
    Person(
        name=f"Test Competitor {index}",
        wca_id=f"2020TEST{index:02d}",
        profile_url=f"https://www.worldcubeassociation.org/persons/2020TEST{index:02d}",
        avatar_thumb_url="",
    )
    for index in range(MAX_SEARCH_SUGGESTIONS + 2)
]
MATS_VALK_EVENTS = [
    Event(event_id="222", name="2x2x2 Cube"),
    Event(event_id="333", name="3x3x3 Cube"),
]
MATS_VALK_EVENT_IDS = [event.event_id for event in MATS_VALK_EVENTS]
MATS_VALK_PROFILE = Profile(person=MATS_VALK, event_ids=MATS_VALK_EVENT_IDS)
WCA_PROFILE_URL = "https://www.worldcubeassociation.org/persons/2007VALK01"

# The 3x3x3 row deliberately has no average PR, so the page must show a placeholder
# rather than a blank cell.
NO_AVERAGE_PLACEHOLDER = "—"
MATS_VALK_OVERVIEW_ROWS = [
    EventAges(
        event_id="222",
        event_name="2x2x2 Cube",
        single_age="3 months ago",
        average_age="3 months ago",
    ),
    EventAges(
        event_id="333",
        event_name="3x3x3 Cube",
        single_age="1 week ago",
        average_age=None,
    ),
]
MATS_VALK_OVERVIEW = Overview(person=MATS_VALK, rows=MATS_VALK_OVERVIEW_ROWS)

SINGLE_MAP_CITY = "Chippenham, Wiltshire"
SINGLE_MAP_DISPLAY = "14.98"
SINGLE_MAP_DATE = "2024-02-03"
SINGLE_MAP_SERIES = [
    {
        "city": SINGLE_MAP_CITY,
        "lat": 51.461317,
        "lng": -2.113757,
        "prs": [{"date": SINGLE_MAP_DATE, "display": SINGLE_MAP_DISPLAY}],
    }
]
AVERAGE_MAP_CITY = "Weston-super-Mare, Somerset"
AVERAGE_MAP_DISPLAY = "21.77"
AVERAGE_MAP_DATE = "2023-11-18"
AVERAGE_MAP_SERIES = [
    {
        "city": AVERAGE_MAP_CITY,
        "lat": 51.347823,
        "lng": -2.986306,
        "prs": [{"date": AVERAGE_MAP_DATE, "display": AVERAGE_MAP_DISPLAY}],
    }
]

FEWEST_MOVES_EVENT_ID = "333fm"
FEWEST_MOVES_SINGLE_MOVES = 24
FEWEST_MOVES_AVERAGE_CENTI_MOVES = 2733
FEWEST_MOVES_PROGRESSIONS = RecordProgressions(
    singles=[RecordPoint(date="2024-01-06", value=FEWEST_MOVES_SINGLE_MOVES)],
    averages=[
        RecordPoint(date="2024-01-06", value=FEWEST_MOVES_AVERAGE_CENTI_MOVES)
    ],
)
FEWEST_MOVES_PROFILE = Profile(
    person=MATS_VALK, event_ids=[FEWEST_MOVES_EVENT_ID]
)


MULTI_BLIND_EVENT_ID = "333mbf"
MULTI_BLIND_SINGLE = 930206102  # 8/10 in 34:21 (6 pts)
MULTI_BLIND_PROGRESSIONS = RecordProgressions(
    singles=[RecordPoint(date="2024-01-06", value=MULTI_BLIND_SINGLE)],
    averages=[],
    all_singles=[RecordPoint(date="2024-01-06", value=MULTI_BLIND_SINGLE)],
    all_averages=[],
    daily_ranges=[
        DailySolveRange(
            date="2024-01-06",
            fastest=MULTI_BLIND_SINGLE,
            slowest=MULTI_BLIND_SINGLE,
        )
    ],
)
MULTI_BLIND_PROFILE = Profile(person=MATS_VALK, event_ids=[MULTI_BLIND_EVENT_ID])


def _search_returning(persons):
    def _search(name):
        return persons

    return _search


def _progression_returning(progressions):
    def _progression(wca_id, event_id):
        return progressions

    return _progression


def _profile_returning(profile):
    def _profile(wca_id):
        return profile

    return _profile


def _overview_returning(overview):
    def _overview(wca_id):
        return overview

    return _overview


def _map_returning(single_series, average_series):
    def _map(wca_id, event_id):
        return {"singles": single_series, "averages": average_series}

    return _map


def _get_overview_page(profile=MATS_VALK_PROFILE):
    # The shell fetches only the profile; overriding the overview function too
    # keeps these tests off the network no matter how the rows are wired.
    app.dependency_overrides[get_profile_function] = lambda: _profile_returning(
        profile
    )
    app.dependency_overrides[get_overview_function] = lambda: _overview_returning(
        MATS_VALK_OVERVIEW
    )
    try:
        client = TestClient(app)
        return client.get(
            OVERVIEW_ROUTE, params={"wca_id": profile.person.wca_id}
        )
    finally:
        app.dependency_overrides.clear()


def _get_overview_rows(overview=MATS_VALK_OVERVIEW):
    app.dependency_overrides[get_overview_function] = lambda: _overview_returning(
        overview
    )
    try:
        client = TestClient(app)
        return client.get(
            OVERVIEW_ROWS_ROUTE, params={"wca_id": overview.person.wca_id}
        )
    finally:
        app.dependency_overrides.clear()


def test_index_page_shows_a_name_search_form():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert f'name="{SEARCH_NAME_PARAMETER}"' in response.text


def test_index_page_labels_the_search_field_as_name_or_wca_id():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Competitor (name or WCA ID)" in response.text


def test_index_page_has_no_search_submit_button():
    # Live search replaces the button; Enter still submits the form.
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'type="submit"' not in response.text


def test_index_page_includes_the_live_search_script():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    version = static_asset_version("search-live.js")
    assert f"/static/search-live.js?v={version}" in response.text


def test_index_page_has_a_suggestions_container():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="search-suggestions"' in response.text


def test_index_page_links_the_stylesheet():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert STYLESHEET_PATH in response.text


def test_records_page_links_the_stylesheet():
    response = _get_records_page()

    assert response.status_code == 200
    assert STYLESHEET_PATH in response.text


def test_index_stylesheet_link_is_cache_busted():
    client = TestClient(app)

    response = client.get("/")

    version = static_asset_version(STYLESHEET_FILENAME)
    assert f"{STYLESHEET_PATH}?v={version}" in response.text


def test_records_stylesheet_link_is_cache_busted():
    response = _get_records_page()

    version = static_asset_version(STYLESHEET_FILENAME)
    assert f"{STYLESHEET_PATH}?v={version}" in response.text


def test_records_scripts_are_cache_busted():
    response = _get_records_page(progressions=PROGRESSIONS_WITH_ALL_RESULTS)

    assert response.status_code == 200
    for filename in (
        "records-loading.js",
        "records-chart.js",
        "scatter-chart.js",
        "gap-chart.js",
    ):
        version = static_asset_version(filename)
        assert f"/static/{filename}?v={version}" in response.text


def test_static_asset_version_changes_with_file_contents():
    assert static_asset_version("styles.css") != static_asset_version(
        "records-chart.js"
    )


def test_records_chart_datasets_have_clip_disabled():
    chart_js = (STATIC_DIRECTORY / "records-chart.js").read_text()
    assert "clip: false" in chart_js


def test_stylesheet_is_served():
    client = TestClient(app)

    response = client.get(STYLESHEET_PATH)

    assert response.status_code == 200


def test_search_links_each_competitor_to_their_overview():
    app.dependency_overrides[get_search_function] = lambda: _search_returning(
        [MATS_VALK, FELIKS_ZEMDEGS]
    )
    try:
        client = TestClient(app)
        response = client.get(
            SEARCH_ROUTE, params={SEARCH_NAME_PARAMETER: SEARCHED_NAME}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    for competitor in (MATS_VALK, FELIKS_ZEMDEGS):
        assert competitor.name in response.text
        assert f'{OVERVIEW_ROUTE}?wca_id={competitor.wca_id}' in response.text


def test_search_with_a_single_match_redirects_straight_to_their_overview():
    app.dependency_overrides[get_search_function] = lambda: _search_returning(
        [MATS_VALK]
    )
    try:
        client = TestClient(app)
        response = client.get(
            SEARCH_ROUTE,
            params={SEARCH_NAME_PARAMETER: SEARCHED_NAME},
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"{OVERVIEW_ROUTE}?wca_id={MATS_VALK.wca_id}"
    )


def test_api_search_returns_matching_competitors_as_json():
    app.dependency_overrides[get_search_function] = lambda: _search_returning(
        [MATS_VALK, FELIKS_ZEMDEGS]
    )
    try:
        client = TestClient(app)
        response = client.get(
            API_SEARCH_ROUTE, params={SEARCH_QUERY_PARAMETER: "valk"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {"wca_id": MATS_VALK.wca_id, "name": MATS_VALK.name},
        {"wca_id": FELIKS_ZEMDEGS.wca_id, "name": FELIKS_ZEMDEGS.name},
    ]


def test_api_search_caps_the_number_of_suggestions():
    app.dependency_overrides[get_search_function] = lambda: _search_returning(
        MANY_COMPETITORS
    )
    try:
        client = TestClient(app)
        response = client.get(
            API_SEARCH_ROUTE, params={SEARCH_QUERY_PARAMETER: "test"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == MAX_SEARCH_SUGGESTIONS


def test_api_search_ignores_queries_below_the_minimum_length():
    calls = []

    def _spy_search(name):
        calls.append(name)
        return [MATS_VALK]

    app.dependency_overrides[get_search_function] = lambda: _spy_search
    try:
        client = TestClient(app)
        response = client.get(
            API_SEARCH_ROUTE, params={SEARCH_QUERY_PARAMETER: "va"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []
    assert calls == []


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


def _get_records_page(
    event_id=EVENT_ID,
    progressions=PROGRESSIONS,
    profile=MATS_VALK_PROFILE,
    single_map_series=None,
    average_map_series=None,
):
    app.dependency_overrides[get_progression_function] = (
        lambda: _progression_returning(progressions)
    )
    app.dependency_overrides[get_profile_function] = lambda: _profile_returning(
        profile
    )
    app.dependency_overrides[get_map_function] = lambda: _map_returning(
        single_map_series or [], average_map_series or []
    )
    try:
        client = TestClient(app)
        return client.get(
            RECORDS_ROUTE,
            params={"wca_id": profile.person.wca_id, "event_id": event_id},
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


def test_records_pr_chart_has_reset_zoom_button():
    response = _get_records_page()

    assert response.status_code == 200
    assert 'id="record-reset-zoom"' in response.text


def test_records_pr_chart_loads_zoom_plugin():
    response = _get_records_page()

    assert response.status_code == 200
    assert "/static/vendor/hammer.min.js" in response.text
    assert "/static/vendor/chartjs-plugin-zoom.min.js" in response.text


def test_records_consistency_chart_has_reset_zoom_button():
    response = _get_records_page(progressions=PROGRESSIONS_WITH_CONSISTENCY)

    assert response.status_code == 200
    assert 'id="consistency-reset-zoom"' in response.text


def test_records_gap_chart_has_reset_zoom_button():
    response = _get_records_page()

    assert response.status_code == 200
    assert 'id="gap-reset-zoom"' in response.text


def test_records_shows_an_average_single_gap_chart():
    response = _get_records_page()

    assert response.status_code == 200
    assert "Average/Single Gap" in response.text
    assert 'id="gap-progression"' in response.text
    assert 'id="gap-chart-data"' in response.text
    assert '"y": 390' in response.text
    assert '"display": "3.90"' in response.text
    assert 'id="midpoint-chart-data"' not in response.text


def test_records_formats_fewest_moves_as_move_counts():
    response = _get_records_page(
        event_id=FEWEST_MOVES_EVENT_ID,
        progressions=FEWEST_MOVES_PROGRESSIONS,
        profile=FEWEST_MOVES_PROFILE,
    )

    assert response.status_code == 200
    assert "<td>24</td>" in response.text
    assert "<td>27.33</td>" in response.text
    assert 'data-result-unit="moves"' in response.text
    assert '"y": 27.33' in response.text
    assert '"display": "24"' in response.text


def test_records_renders_multi_blind_as_points_and_solved_over_attempted():
    response = _get_records_page(
        event_id=MULTI_BLIND_EVENT_ID,
        progressions=MULTI_BLIND_PROGRESSIONS,
        profile=MULTI_BLIND_PROFILE,
    )

    assert response.status_code == 200
    assert 'data-result-unit="points"' in response.text
    assert '"y": 6' in response.text
    assert "8/10 in 34:21 (6 pts)" in response.text
    assert "<td>8/10 34:21</td>" in response.text


def test_records_omits_every_mention_of_average_for_multi_blind():
    response = _get_records_page(
        event_id=MULTI_BLIND_EVENT_ID,
        progressions=MULTI_BLIND_PROGRESSIONS,
        profile=MULTI_BLIND_PROFILE,
    )

    assert response.status_code == 200
    assert "<h2>Average</h2>" not in response.text
    assert "No average personal records found" not in response.text
    assert 'id="average-chart-data"' not in response.text
    assert 'id="all-averages-scatter-data"' not in response.text
    assert 'id="gap-chart-data"' not in response.text
    assert "Average/Single Gap" not in response.text
    assert "average" not in response.text
    assert 'id="all-singles-scatter-data"' in response.text


def test_records_titles_the_chart_with_the_event_name():
    response = _get_records_page()

    assert response.status_code == 200
    assert f'<h2 class="chart-title">{EVENT_NAME}</h2>' in response.text


def test_records_shows_a_table_of_the_single_record_progression():
    response = _get_records_page()

    assert response.status_code == 200
    assert "<h2>Single</h2>" in response.text
    assert "2023-11-18" in response.text
    assert "17.77" in response.text
    assert "2024-11-01" in response.text
    assert "14.98" in response.text


def test_records_shows_a_table_of_the_average_record_progression():
    response = _get_records_page()

    assert response.status_code == 200
    assert "<h2>Average</h2>" in response.text
    assert "21.77" in response.text
    assert "18.88" in response.text


def test_records_shows_an_event_dropdown_posting_back_to_the_records_route():
    response = _get_records_page()

    assert response.status_code == 200
    assert f'action="{RECORDS_ROUTE}"' in response.text
    assert 'name="wca_id"' in response.text
    assert f'value="{MATS_VALK.wca_id}"' in response.text
    assert 'name="event_id"' in response.text
    for event in MATS_VALK_EVENTS:
        assert f'value="{event.event_id}"' in response.text
        assert event.name in response.text


def test_records_dropdown_preselects_the_current_event():
    response = _get_records_page()

    assert response.status_code == 200
    assert f'value="{EVENT_ID}" selected' in response.text


def test_records_dropdown_auto_submits_when_the_event_changes():
    response = _get_records_page()

    assert response.status_code == 200
    assert "this.form.submit()" in response.text


def test_records_links_to_the_competitors_wca_profile():
    response = _get_records_page()

    assert response.status_code == 200
    assert WCA_PROFILE_URL in response.text


def test_records_links_the_competitor_identity_back_to_the_overview():
    response = _get_records_page()

    assert response.status_code == 200
    assert f"{OVERVIEW_ROUTE}?wca_id={MATS_VALK.wca_id}" in response.text


def test_records_shows_the_competitor_identity():
    response = _get_records_page()

    assert response.status_code == 200
    assert MATS_VALK.name in response.text
    assert MATS_VALK.wca_id in response.text


def test_records_shows_the_competitor_avatar():
    response = _get_records_page()

    assert response.status_code == 200
    assert f'src="{MATS_VALK_AVATAR_THUMB_URL}"' in response.text


def test_records_opens_the_wca_profile_in_a_new_tab_safely():
    response = _get_records_page()

    assert response.status_code == 200
    assert 'target="_blank"' in response.text
    assert 'rel="noopener noreferrer"' in response.text


def test_records_embeds_all_results_as_scatter_chart_data():
    response = _get_records_page(progressions=PROGRESSIONS_WITH_ALL_RESULTS)

    assert response.status_code == 200
    assert 'id="all-results-scatter"' in response.text
    assert 'id="all-singles-scatter-data"' in response.text
    assert 'id="all-averages-scatter-data"' in response.text
    assert f'"y": {NON_RECORD_SINGLE}' in response.text
    assert f'"y": {NON_RECORD_AVERAGE}' in response.text


def test_records_embeds_the_daily_solve_range_band_as_chart_data():
    response = _get_records_page(progressions=PROGRESSIONS_WITH_ALL_RESULTS)

    assert response.status_code == 200
    assert 'id="daily-range-data"' in response.text
    assert f'"y": {SLOWEST_SOLVE_OF_DAY}' in response.text


def test_records_omits_the_daily_range_band_for_multi_blind():
    response = _get_records_page(
        event_id=MULTI_BLIND_EVENT_ID,
        progressions=MULTI_BLIND_PROGRESSIONS,
        profile=MULTI_BLIND_PROFILE,
    )

    assert response.status_code == 200
    assert 'id="daily-range-data"' not in response.text


def test_records_embeds_the_consistency_series_as_chart_data():
    response = _get_records_page(progressions=PROGRESSIONS_WITH_CONSISTENCY)

    assert response.status_code == 200
    assert 'id="consistency-chart-data"' in response.text
    assert 'id="consistency-progression"' in response.text
    assert f'"y": {EXPECTED_CONSISTENCY_RATIO}' in response.text


def test_overview_shows_the_competitor_identity():
    response = _get_overview_page()

    assert response.status_code == 200
    assert MATS_VALK.name in response.text
    assert MATS_VALK.wca_id in response.text
    assert f'src="{MATS_VALK_AVATAR_THUMB_URL}"' in response.text
    assert WCA_PROFILE_URL in response.text


def test_overview_heads_the_table_with_event_single_and_average():
    response = _get_overview_page()

    assert response.status_code == 200
    assert "Event" in response.text
    assert "Latest Single" in response.text
    assert "Latest Average" in response.text


def test_overview_shows_a_skeleton_row_per_event_while_loading():
    response = _get_overview_page()

    assert response.status_code == 200
    assert response.text.count('class="skeleton-row"') == len(
        MATS_VALK_EVENT_IDS
    )


def test_overview_loads_its_rows_from_the_fragment_endpoint():
    response = _get_overview_page()

    assert response.status_code == 200
    assert (
        f'data-rows-url="{OVERVIEW_ROWS_ROUTE}?wca_id={MATS_VALK.wca_id}"'
        in response.text
    )


def test_overview_includes_the_rows_loading_script():
    response = _get_overview_page()

    assert response.status_code == 200
    version = static_asset_version("overview-rows.js")
    assert f"/static/overview-rows.js?v={version}" in response.text


def test_overview_rows_list_each_event_with_its_latest_pr_ages():
    response = _get_overview_rows()

    assert response.status_code == 200
    assert "2x2x2 Cube" in response.text
    assert "3x3x3 Cube" in response.text
    assert "1 week ago" in response.text
    assert "3 months ago" in response.text


def test_overview_rows_link_each_event_to_its_records_page():
    response = _get_overview_rows()

    assert response.status_code == 200
    for event in MATS_VALK_EVENTS:
        assert (
            f"{RECORDS_ROUTE}?wca_id={MATS_VALK.wca_id}&event_id={event.event_id}"
            in response.text
        )


def test_overview_rows_show_a_placeholder_when_an_event_has_no_average_pr():
    response = _get_overview_rows()

    assert response.status_code == 200
    assert NO_AVERAGE_PLACEHOLDER in response.text


RECORDS_MAP_JS = (STATIC_DIRECTORY / "records-map.js").read_text()


def test_records_map_js_initialises_a_leaflet_map():
    assert "L.map(" in RECORDS_MAP_JS


def test_records_map_js_reads_single_map_data_from_the_page():
    assert "single-map-data" in RECORDS_MAP_JS


def test_records_map_js_reads_average_map_data_from_the_page():
    assert "average-map-data" in RECORDS_MAP_JS


def test_records_map_js_sizes_circles_by_pr_count():
    assert ".prs.length" in RECORDS_MAP_JS


def test_records_map_js_uses_single_pr_colour():
    assert "#2563eb" in RECORDS_MAP_JS


def test_records_map_js_uses_average_pr_colour():
    assert "#449964" in RECORDS_MAP_JS


def test_records_map_js_has_legend_toggle():
    assert "legend" in RECORDS_MAP_JS


def test_records_map_js_legend_labels_single_and_average_without_prs_suffix():
    assert '{ label: "Single"' in RECORDS_MAP_JS
    assert '{ label: "Average"' in RECORDS_MAP_JS


def test_records_page_has_a_map_container():
    response = _get_records_page()

    assert response.status_code == 200
    assert 'id="pr-map"' in response.text


def test_records_page_embeds_single_map_series_as_json():
    response = _get_records_page(single_map_series=SINGLE_MAP_SERIES)

    assert response.status_code == 200
    assert 'id="single-map-data"' in response.text
    assert SINGLE_MAP_CITY in response.text
    assert SINGLE_MAP_DISPLAY in response.text


def test_records_page_embeds_average_map_series_as_json():
    response = _get_records_page(average_map_series=AVERAGE_MAP_SERIES)

    assert response.status_code == 200
    assert 'id="average-map-data"' in response.text
    assert AVERAGE_MAP_CITY in response.text
    assert AVERAGE_MAP_DISPLAY in response.text


def test_records_page_loads_leaflet():
    response = _get_records_page()

    assert response.status_code == 200
    assert "/static/vendor/leaflet.js" in response.text
    assert "/static/vendor/leaflet.css" in response.text


def test_records_page_loads_records_map_script_cache_busted():
    response = _get_records_page()

    assert response.status_code == 200
    version = static_asset_version("records-map.js")
    assert f"/static/records-map.js?v={version}" in response.text
