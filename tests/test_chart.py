from wca_records_analyser.chart import to_record_series
from wca_records_analyser.records import RecordPoint

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
