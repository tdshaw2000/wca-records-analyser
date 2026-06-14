from wca_records_analyser.chart import (
    to_consistency_series,
    to_midpoint_series,
    to_record_series,
)
from wca_records_analyser.records import ConsistencyPoint, RecordPoint

THREE_BY_THREE_EVENT_ID = "333"
FEWEST_MOVES_EVENT_ID = "333fm"
MULTI_BLIND_EVENT_ID = "333mbf"

EARLIEST_DATE = "2023-11-18"
LATEST_DATE = "2024-11-01"

EARLIEST_SINGLE = 1807
LATEST_SINGLE = 1498

EARLIEST_DISPLAY = "18.07"
LATEST_DISPLAY = "14.98"

PROGRESSION = [
    RecordPoint(date=EARLIEST_DATE, value=EARLIEST_SINGLE),
    RecordPoint(date=LATEST_DATE, value=LATEST_SINGLE),
]
EXPECTED_SERIES = [
    {"x": EARLIEST_DATE, "y": EARLIEST_SINGLE, "display": EARLIEST_DISPLAY},
    {"x": LATEST_DATE, "y": LATEST_SINGLE, "display": LATEST_DISPLAY},
]

FEWEST_MOVES_DATE = "2024-01-06"
FEWEST_MOVES_SINGLE = 24
FEWEST_MOVES_AVERAGE_CENTI_MOVES = 2733
FEWEST_MOVES_AVERAGE_MOVES = 27.33


def test_to_record_series_carries_date_centiseconds_and_formatted_time():
    assert (
        to_record_series(PROGRESSION, THREE_BY_THREE_EVENT_ID, is_average=False)
        == EXPECTED_SERIES
    )


def test_to_record_series_of_empty_progression_is_empty():
    assert to_record_series([], THREE_BY_THREE_EVENT_ID, is_average=False) == []


def test_to_record_series_renders_fewest_moves_single_as_a_move_count():
    progression = [RecordPoint(date=FEWEST_MOVES_DATE, value=FEWEST_MOVES_SINGLE)]

    assert to_record_series(
        progression, FEWEST_MOVES_EVENT_ID, is_average=False
    ) == [{"x": FEWEST_MOVES_DATE, "y": FEWEST_MOVES_SINGLE, "display": "24"}]


def test_to_record_series_scales_fewest_moves_average_to_moves():
    progression = [
        RecordPoint(date=FEWEST_MOVES_DATE, value=FEWEST_MOVES_AVERAGE_CENTI_MOVES)
    ]

    assert to_record_series(
        progression, FEWEST_MOVES_EVENT_ID, is_average=True
    ) == [
        {
            "x": FEWEST_MOVES_DATE,
            "y": FEWEST_MOVES_AVERAGE_MOVES,
            "display": "27.33",
        }
    ]


# Encoded Multi-Blind singles (see test_formatting for the encoding).
MULTI_BLIND_EIGHT_OF_TEN = 930206102  # 8/10 in 34:21 (6 pts)
MULTI_BLIND_TEN_OF_TEN = 890300000  # 10/10 in 50:00 (10 pts)
MULTI_BLIND_ONE_OF_THREE = 1000060002  # 1/3, -1 pts: a DNF

MULTI_BLIND_PROGRESSION = [
    RecordPoint(date=EARLIEST_DATE, value=MULTI_BLIND_EIGHT_OF_TEN),
    RecordPoint(date=LATEST_DATE, value=MULTI_BLIND_TEN_OF_TEN),
]
EXPECTED_MULTI_BLIND_SERIES = [
    {"x": EARLIEST_DATE, "y": 6, "display": "8/10 in 34:21 (6 pts)"},
    {"x": LATEST_DATE, "y": 10, "display": "10/10 in 50:00 (10 pts)"},
]


def test_to_record_series_plots_multi_blind_points_with_full_display():
    assert (
        to_record_series(
            MULTI_BLIND_PROGRESSION, MULTI_BLIND_EVENT_ID, is_average=False
        )
        == EXPECTED_MULTI_BLIND_SERIES
    )


MULTI_BLIND_PROGRESSION_WITH_DNF = [
    RecordPoint(date=EARLIEST_DATE, value=MULTI_BLIND_ONE_OF_THREE),
    RecordPoint(date=LATEST_DATE, value=MULTI_BLIND_EIGHT_OF_TEN),
]
EXPECTED_MULTI_BLIND_SERIES_WITHOUT_DNF = [
    {"x": LATEST_DATE, "y": 6, "display": "8/10 in 34:21 (6 pts)"},
]


def test_to_record_series_excludes_multi_blind_dnf_results():
    assert (
        to_record_series(
            MULTI_BLIND_PROGRESSION_WITH_DNF, MULTI_BLIND_EVENT_ID, is_average=False
        )
        == EXPECTED_MULTI_BLIND_SERIES_WITHOUT_DNF
    )


CONSISTENCY_EARLIEST_SINGLE = 1807
CONSISTENCY_EARLIEST_AVERAGE = 2456
CONSISTENCY_LATEST_SINGLE = 1498
CONSISTENCY_LATEST_AVERAGE = 2012

CONSISTENCY_POINTS = [
    ConsistencyPoint(
        date=EARLIEST_DATE,
        single=CONSISTENCY_EARLIEST_SINGLE,
        average=CONSISTENCY_EARLIEST_AVERAGE,
    ),
    ConsistencyPoint(
        date=LATEST_DATE,
        single=CONSISTENCY_LATEST_SINGLE,
        average=CONSISTENCY_LATEST_AVERAGE,
    ),
]
EXPECTED_CONSISTENCY_SERIES = [
    {"x": EARLIEST_DATE, "y": 1.359, "display": "1.36×"},
    {"x": LATEST_DATE, "y": 1.343, "display": "1.34×"},
]


def test_to_consistency_series_plots_the_average_to_single_ratio():
    assert (
        to_consistency_series(CONSISTENCY_POINTS, THREE_BY_THREE_EVENT_ID)
        == EXPECTED_CONSISTENCY_SERIES
    )


def test_to_consistency_series_of_no_points_is_empty():
    assert to_consistency_series([], THREE_BY_THREE_EVENT_ID) == []


MIDPOINT_SINGLE_SERIES = [
    {"x": EARLIEST_DATE, "y": 1800, "display": "18.00"},
    {"x": LATEST_DATE, "y": 1500, "display": "15.00"},
]
MIDPOINT_AVERAGE_SERIES = [
    {"x": EARLIEST_DATE, "y": 2400, "display": "24.00"},
    {"x": LATEST_DATE, "y": 2000, "display": "20.00"},
]
EXPECTED_MIDPOINT_SERIES = [
    {"x": EARLIEST_DATE, "y": 2100.0, "display": "21.00"},
    {"x": LATEST_DATE, "y": 1750.0, "display": "17.50"},
]


def test_to_midpoint_series_averages_the_best_single_and_best_average():
    assert (
        to_midpoint_series(
            MIDPOINT_SINGLE_SERIES, MIDPOINT_AVERAGE_SERIES, THREE_BY_THREE_EVENT_ID
        )
        == EXPECTED_MIDPOINT_SERIES
    )


# A single PR on its own date, then an average PR, then another single PR: the
# midpoint only appears once both exist, and carries the unchanged record forward.
MIDPOINT_FIRST_SINGLE_DATE = "2023-01-01"
MIDPOINT_AVERAGE_DATE = "2023-02-01"
MIDPOINT_SECOND_SINGLE_DATE = "2023-03-01"
STAGGERED_SINGLE_SERIES = [
    {"x": MIDPOINT_FIRST_SINGLE_DATE, "y": 2000, "display": "20.00"},
    {"x": MIDPOINT_SECOND_SINGLE_DATE, "y": 1500, "display": "15.00"},
]
STAGGERED_AVERAGE_SERIES = [
    {"x": MIDPOINT_AVERAGE_DATE, "y": 2600, "display": "26.00"},
]
EXPECTED_STAGGERED_MIDPOINT_SERIES = [
    {"x": MIDPOINT_AVERAGE_DATE, "y": 2300.0, "display": "23.00"},
    {"x": MIDPOINT_SECOND_SINGLE_DATE, "y": 2050.0, "display": "20.50"},
]


def test_to_midpoint_series_starts_once_both_records_exist_and_carries_forward():
    assert (
        to_midpoint_series(
            STAGGERED_SINGLE_SERIES,
            STAGGERED_AVERAGE_SERIES,
            THREE_BY_THREE_EVENT_ID,
        )
        == EXPECTED_STAGGERED_MIDPOINT_SERIES
    )


def test_to_midpoint_series_is_empty_when_there_is_no_average():
    assert (
        to_midpoint_series(MIDPOINT_SINGLE_SERIES, [], THREE_BY_THREE_EVENT_ID) == []
    )


FEWEST_MOVES_CONSISTENCY_SINGLE_MOVES = 24
FEWEST_MOVES_CONSISTENCY_AVERAGE_CENTI_MOVES = 2733


def test_to_consistency_series_scales_fewest_moves_average_before_the_ratio():
    points = [
        ConsistencyPoint(
            date=FEWEST_MOVES_DATE,
            single=FEWEST_MOVES_CONSISTENCY_SINGLE_MOVES,
            average=FEWEST_MOVES_CONSISTENCY_AVERAGE_CENTI_MOVES,
        )
    ]

    assert to_consistency_series(points, FEWEST_MOVES_EVENT_ID) == [
        {"x": FEWEST_MOVES_DATE, "y": 1.139, "display": "1.14×"}
    ]
