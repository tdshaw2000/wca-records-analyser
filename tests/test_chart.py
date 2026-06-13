from wca_records_analyser.chart import to_consistency_series, to_record_series
from wca_records_analyser.records import ConsistencyPoint, RecordPoint

THREE_BY_THREE_EVENT_ID = "333"
FEWEST_MOVES_EVENT_ID = "333fm"

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
