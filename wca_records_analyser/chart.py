"""Shaping of personal-record data into a series for client-side charting."""

from wca_records_analyser.formatting import format_time

DATE_KEY = "x"
VALUE_KEY = "y"
DISPLAY_KEY = "display"


def to_record_series(progression):
    """Turn record points into chart points carrying date, centiseconds, and formatted time."""
    return [
        {
            DATE_KEY: record.date,
            VALUE_KEY: record.value,
            DISPLAY_KEY: format_time(record.value),
        }
        for record in progression
    ]
