"""Shaping of personal-record data into a series for client-side charting."""

from wca_records_analyser.formatting import (
    CENTI_MOVES_PER_MOVE,
    FEWEST_MOVES_EVENT_ID,
    MULTI_BLIND_EVENT_ID,
    decode_multi_blind,
    format_average,
    format_consistency,
    format_multi_blind_full,
    format_single,
)

DATE_KEY = "x"
VALUE_KEY = "y"
DISPLAY_KEY = "display"
CONSISTENCY_RATIO_DECIMAL_PLACES = 3
DNF_POINTS_THRESHOLD = 0


def to_record_series(progression, event_id, is_average):
    """Turn record points into chart points carrying date, plotted value, and display."""
    if event_id == MULTI_BLIND_EVENT_ID and not is_average:
        return _to_multi_blind_series(progression)
    formatter = format_average if is_average else format_single
    return [
        {
            DATE_KEY: record.date,
            VALUE_KEY: _plot_value(record.value, event_id, is_average),
            DISPLAY_KEY: formatter(record.value, event_id),
        }
        for record in progression
    ]


def _to_multi_blind_series(progression):
    """Plot Multi-Blind records by points (higher is better), excluding DNFs.

    Each point carries the full result string for the tooltip; the raw encoded
    value is decoded here so the chart's Y axis can show points directly.
    """
    series = []
    for record in progression:
        decoded = decode_multi_blind(record.value)
        if decoded.points <= DNF_POINTS_THRESHOLD:
            continue
        series.append(
            {
                DATE_KEY: record.date,
                VALUE_KEY: decoded.points,
                DISPLAY_KEY: format_multi_blind_full(record.value),
            }
        )
    return series


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
