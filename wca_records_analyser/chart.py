"""Shaping of personal-record data into a series for client-side charting."""

from wca_records_analyser.formatting import (
    CENTI_MOVES_PER_MOVE,
    FEWEST_MOVES_EVENT_ID,
    format_average,
    format_consistency,
    format_single,
)

DATE_KEY = "x"
VALUE_KEY = "y"
DISPLAY_KEY = "display"
CONSISTENCY_RATIO_DECIMAL_PLACES = 3


def to_record_series(progression, event_id, is_average):
    """Turn record points into chart points carrying date, plotted value, and display."""
    formatter = format_average if is_average else format_single
    return [
        {
            DATE_KEY: record.date,
            VALUE_KEY: _plot_value(record.value, event_id, is_average),
            DISPLAY_KEY: formatter(record.value, event_id),
        }
        for record in progression
    ]


def to_consistency_series(points, event_id):
    """Turn consistency points into chart points carrying the average-to-single ratio.

    The average is put on the single's scale first (Fewest Moves stores averages as
    moves times 100), so the ratio compares like with like. A ratio of 1.0 means the
    average equalled the single — a perfectly consistent sitting.
    """
    series = []
    for point in points:
        plotted_average = _plot_value(point.average, event_id, is_average=True)
        ratio = plotted_average / point.single
        series.append(
            {
                DATE_KEY: point.date,
                VALUE_KEY: round(ratio, CONSISTENCY_RATIO_DECIMAL_PLACES),
                DISPLAY_KEY: format_consistency(ratio),
            }
        )
    return series


def _plot_value(value, event_id, is_average):
    """Put both series on one scale; Fewest Moves averages are stored as moves times 100."""
    if event_id == FEWEST_MOVES_EVENT_ID and is_average:
        return value / CENTI_MOVES_PER_MOVE
    return value
