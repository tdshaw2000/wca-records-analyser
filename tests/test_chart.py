from wca_records_analyser.chart import to_single_record_series
from wca_records_analyser.records import RecordPoint

EARLIEST_DATE = "2023-11-18"
LATEST_DATE = "2024-11-01"

EARLIEST_SINGLE = 1807
LATEST_SINGLE = 1498

EARLIEST_DISPLAY = "18.07"
LATEST_DISPLAY = "14.98"

PROGRESSION = [
    RecordPoint(date=EARLIEST_DATE, single=EARLIEST_SINGLE),
    RecordPoint(date=LATEST_DATE, single=LATEST_SINGLE),
]
EXPECTED_SERIES = [
    {"x": EARLIEST_DATE, "y": EARLIEST_SINGLE, "display": EARLIEST_DISPLAY},
    {"x": LATEST_DATE, "y": LATEST_SINGLE, "display": LATEST_DISPLAY},
]


def test_to_single_record_series_carries_date_centiseconds_and_formatted_time():
    assert to_single_record_series(PROGRESSION) == EXPECTED_SERIES


def test_to_single_record_series_of_empty_progression_is_empty():
    assert to_single_record_series([]) == []
