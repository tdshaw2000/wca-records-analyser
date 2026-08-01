import pytest

from wca_records_analyser.map import to_map_series, to_overview_map_series
from wca_records_analyser.wca_client import Competition, Result

THREE_BY_THREE_EVENT_ID = "333"
TWO_BY_TWO_EVENT_ID = "222"
FEWEST_MOVES_EVENT_ID = "333fm"
MULTI_BLIND_EVENT_ID = "333mbf"

CITY_A = "Chippenham, Wiltshire"
CITY_B = "Weston-super-Mare, Somerset"

COMP_A1_ID = "ChippenhamWinter2024"
COMP_A2_ID = "ChippenhamSummer2024"
COMP_B1_ID = "WestonAutumn2023"

COMP_A1_DATE = "2024-02-03"
COMP_A2_DATE = "2024-06-15"
COMP_B1_DATE = "2023-11-18"

COMP_A1_LAT = 51.461317
COMP_A1_LNG = -2.113757
COMP_A2_LAT = 51.462000
COMP_A2_LNG = -2.114000
COMP_B1_LAT = 51.347823
COMP_B1_LNG = -2.986306

COMPETITIONS = {
    COMP_A1_ID: Competition(
        id=COMP_A1_ID,
        start_date=COMP_A1_DATE,
        latitude=COMP_A1_LAT,
        longitude=COMP_A1_LNG,
        city=CITY_A,
    ),
    COMP_A2_ID: Competition(
        id=COMP_A2_ID,
        start_date=COMP_A2_DATE,
        latitude=COMP_A2_LAT,
        longitude=COMP_A2_LNG,
        city=CITY_A,
    ),
    COMP_B1_ID: Competition(
        id=COMP_B1_ID,
        start_date=COMP_B1_DATE,
        latitude=COMP_B1_LAT,
        longitude=COMP_B1_LNG,
        city=CITY_B,
    ),
}

# Single PRs: 18.07 at Weston, then 14.98 at Chippenham #1, then 13.55 at Chippenham #2.
FIRST_SINGLE = 1807
SECOND_SINGLE = 1498
THIRD_SINGLE = 1355

# Averages: 21.77 at Weston, then 16.46 at Chippenham #2.
FIRST_AVERAGE = 2177
SECOND_AVERAGE = 1646

RESULTS = [
    Result(
        single=FIRST_SINGLE,
        average=FIRST_AVERAGE,
        competition_id=COMP_B1_ID,
        solves=(FIRST_SINGLE, 2100, 1950, 2200, 2050),
    ),
    Result(
        single=SECOND_SINGLE,
        average=2300,
        competition_id=COMP_A1_ID,
        solves=(SECOND_SINGLE, 1600, 1700, 1550, 1650),
    ),
    Result(
        single=THIRD_SINGLE,
        average=SECOND_AVERAGE,
        competition_id=COMP_A2_ID,
        solves=(THIRD_SINGLE, 1400, 1450, 1380, 1390),
    ),
]


def test_to_map_series_singles_groups_prs_by_city():
    series = to_map_series(RESULTS, COMPETITIONS, THREE_BY_THREE_EVENT_ID, is_average=False)

    cities = [group["city"] for group in series]
    assert CITY_B in cities
    assert CITY_A in cities


def test_to_map_series_singles_places_one_group_per_city():
    series = to_map_series(RESULTS, COMPETITIONS, THREE_BY_THREE_EVENT_ID, is_average=False)

    assert len(series) == 2


def test_to_map_series_singles_collects_all_prs_set_in_a_city():
    series = to_map_series(RESULTS, COMPETITIONS, THREE_BY_THREE_EVENT_ID, is_average=False)

    city_a_group = next(g for g in series if g["city"] == CITY_A)
    assert len(city_a_group["prs"]) == 2


def test_to_map_series_singles_carries_date_and_formatted_display():
    series = to_map_series(RESULTS, COMPETITIONS, THREE_BY_THREE_EVENT_ID, is_average=False)

    city_b_group = next(g for g in series if g["city"] == CITY_B)
    assert city_b_group["prs"] == [{"date": COMP_B1_DATE, "display": "18.07"}]


def test_to_map_series_singles_averages_lat_lng_across_competitions_in_city():
    series = to_map_series(RESULTS, COMPETITIONS, THREE_BY_THREE_EVENT_ID, is_average=False)

    city_a_group = next(g for g in series if g["city"] == CITY_A)
    expected_lat = (COMP_A1_LAT + COMP_A2_LAT) / 2
    expected_lng = (COMP_A1_LNG + COMP_A2_LNG) / 2
    assert city_a_group["lat"] == pytest.approx(expected_lat)
    assert city_a_group["lng"] == pytest.approx(expected_lng)


def test_to_map_series_averages_only_flags_average_prs():
    series = to_map_series(RESULTS, COMPETITIONS, THREE_BY_THREE_EVENT_ID, is_average=True)

    # Only two average PRs: 21.77 at Weston, 16.46 at Chippenham #2.
    assert len(series) == 2
    city_b_group = next(g for g in series if g["city"] == CITY_B)
    assert city_b_group["prs"] == [{"date": COMP_B1_DATE, "display": "21.77"}]


def test_to_map_series_singles_is_empty_when_there_are_no_results():
    assert to_map_series([], COMPETITIONS, THREE_BY_THREE_EVENT_ID, is_average=False) == []


def test_to_map_series_averages_is_empty_for_multi_blind():
    mbf_result = Result(
        single=930206102,
        average=0,
        competition_id=COMP_B1_ID,
        solves=(930206102,),
    )
    series = to_map_series([mbf_result], COMPETITIONS, MULTI_BLIND_EVENT_ID, is_average=True)

    assert series == []


def test_to_map_series_multi_blind_singles_use_full_display():
    mbf_result = Result(
        single=930206102,
        average=0,
        competition_id=COMP_B1_ID,
        solves=(930206102,),
    )
    series = to_map_series([mbf_result], COMPETITIONS, MULTI_BLIND_EVENT_ID, is_average=False)

    assert series[0]["prs"] == [{"date": COMP_B1_DATE, "display": "8/10 in 34:21 (6 pts)"}]


# --- to_overview_map_series ---

THREE_BY_THREE_DISPLAY_NAME = "3x3x3 Cube"
TWO_BY_TWO_DISPLAY_NAME = "2x2x2 Cube"

OVERVIEW_EVENT_NAMES = {
    THREE_BY_THREE_EVENT_ID: THREE_BY_THREE_DISPLAY_NAME,
    TWO_BY_TWO_EVENT_ID: TWO_BY_TWO_DISPLAY_NAME,
}

TWO_BY_TWO_SINGLE = 400
TWO_BY_TWO_AVERAGE = 500

# One 222 result at Chippenham A1 — both a single PR and average PR.
RESULTS_222 = [
    Result(
        single=TWO_BY_TWO_SINGLE,
        average=TWO_BY_TWO_AVERAGE,
        competition_id=COMP_A1_ID,
        solves=(TWO_BY_TWO_SINGLE, 500, 450, 520, 490),
    ),
]

RESULTS_BY_EVENT = {
    THREE_BY_THREE_EVENT_ID: RESULTS,
    TWO_BY_TWO_EVENT_ID: RESULTS_222,
}


def test_to_overview_map_series_groups_prs_by_city():
    series = to_overview_map_series(RESULTS_BY_EVENT, COMPETITIONS, OVERVIEW_EVENT_NAMES)

    cities = [group["city"] for group in series]
    assert CITY_A in cities
    assert CITY_B in cities


def test_to_overview_map_series_places_one_entry_per_city():
    series = to_overview_map_series(RESULTS_BY_EVENT, COMPETITIONS, OVERVIEW_EVENT_NAMES)

    assert len(series) == 2


def test_to_overview_map_series_total_sums_singles_and_averages_across_events():
    series = to_overview_map_series(RESULTS_BY_EVENT, COMPETITIONS, OVERVIEW_EVENT_NAMES)

    city_a_group = next(g for g in series if g["city"] == CITY_A)
    # Chippenham: 333 singles=2, 333 averages=1, 222 singles=1, 222 averages=1 → total=5
    assert city_a_group["total"] == 5


def test_to_overview_map_series_events_lists_singles_and_averages_per_event():
    series = to_overview_map_series(RESULTS_BY_EVENT, COMPETITIONS, OVERVIEW_EVENT_NAMES)

    city_a_group = next(g for g in series if g["city"] == CITY_A)
    events_by_name = {e["name"]: e for e in city_a_group["events"]}
    assert events_by_name[THREE_BY_THREE_DISPLAY_NAME]["singles"] == 2
    assert events_by_name[THREE_BY_THREE_DISPLAY_NAME]["averages"] == 1
    assert events_by_name[TWO_BY_TWO_DISPLAY_NAME]["singles"] == 1
    assert events_by_name[TWO_BY_TWO_DISPLAY_NAME]["averages"] == 1


def test_to_overview_map_series_averages_lat_lng_across_unique_contributing_competitions():
    series = to_overview_map_series(RESULTS_BY_EVENT, COMPETITIONS, OVERVIEW_EVENT_NAMES)

    city_a_group = next(g for g in series if g["city"] == CITY_A)
    # Unique competitions in Chippenham that contributed PRs: COMP_A1, COMP_A2
    expected_lat = (COMP_A1_LAT + COMP_A2_LAT) / 2
    expected_lng = (COMP_A1_LNG + COMP_A2_LNG) / 2
    assert city_a_group["lat"] == pytest.approx(expected_lat)
    assert city_a_group["lng"] == pytest.approx(expected_lng)


def test_to_overview_map_series_is_empty_when_results_by_event_is_empty():
    series = to_overview_map_series({}, COMPETITIONS, OVERVIEW_EVENT_NAMES)

    assert series == []
