from types import SimpleNamespace

from fastapi.testclient import TestClient

from wca_records_analyser.events import Event
from wca_records_analyser.records import ConsistencyPoint, RecordPoint
from wca_records_analyser.web import (
    RecordProgressions,
    app,
    get_profile_function,
    get_progression_function,
    get_search_function,
)
from wca_records_analyser.wca_client import Person, Profile

SEARCH_ROUTE = "/search"
RECORDS_ROUTE = "/records"
SEARCH_NAME_PARAMETER = "name"
SEARCHED_NAME = "Mats Valk"
EVENT_ID = "333"
EVENT_NAME = "3x3x3 Cube"
DEFAULT_EVENT_ID = "333"
STYLESHEET_PATH = "/static/styles.css"

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
PROGRESSIONS_WITH_ALL_RESULTS = SimpleNamespace(
    singles=SINGLE_PROGRESSION,
    averages=AVERAGE_PROGRESSION,
    all_singles=ALL_SINGLES,
    all_averages=ALL_AVERAGES,
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
MATS_VALK_EVENTS = [
    Event(event_id="222", name="2x2x2 Cube"),
    Event(event_id="333", name="3x3x3 Cube"),
]
MATS_VALK_EVENT_IDS = [event.event_id for event in MATS_VALK_EVENTS]
MATS_VALK_PROFILE = Profile(person=MATS_VALK, event_ids=MATS_VALK_EVENT_IDS)
WCA_PROFILE_URL = "https://www.worldcubeassociation.org/persons/2007VALK01"

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


def test_index_page_links_the_stylesheet():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert STYLESHEET_PATH in response.text


def test_records_page_links_the_stylesheet():
    response = _get_records_page()

    assert response.status_code == 200
    assert STYLESHEET_PATH in response.text


def test_stylesheet_is_served():
    client = TestClient(app)

    response = client.get(STYLESHEET_PATH)

    assert response.status_code == 200


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


def _get_records_page(
    event_id=EVENT_ID, progressions=PROGRESSIONS, profile=MATS_VALK_PROFILE
):
    app.dependency_overrides[get_progression_function] = (
        lambda: _progression_returning(progressions)
    )
    app.dependency_overrides[get_profile_function] = lambda: _profile_returning(
        profile
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


def test_records_embeds_the_single_average_midpoint_as_chart_data():
    response = _get_records_page()

    assert response.status_code == 200
    assert 'id="midpoint-chart-data"' in response.text
    assert '"display": "19.77"' in response.text
    assert '"display": "16.93"' in response.text


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
    assert 'id="midpoint-chart-data"' not in response.text
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


def test_records_embeds_the_consistency_series_as_chart_data():
    response = _get_records_page(progressions=PROGRESSIONS_WITH_CONSISTENCY)

    assert response.status_code == 200
    assert 'id="consistency-chart-data"' in response.text
    assert 'id="consistency-progression"' in response.text
    assert f'"y": {EXPECTED_CONSISTENCY_RATIO}' in response.text
