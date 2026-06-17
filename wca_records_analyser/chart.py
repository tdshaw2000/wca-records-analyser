"""Shaping of personal-record data into a series for client-side charting."""

from wca_records_analyser.formatting import (
    CENTI_MOVES_PER_MOVE,
    FEWEST_MOVES_EVENT_ID,
    MULTI_BLIND_EVENT_ID,
    decode_multi_blind,
    format_average,
    format_consistency,
    format_gap,
    format_multi_blind_full,
    format_single,
)

DATE_KEY = "x"
VALUE_KEY = "y"
DISPLAY_KEY = "display"
LOWER_BOUND_KEY = "lower"
UPPER_BOUND_KEY = "upper"
CONSISTENCY_RATIO_DECIMAL_PLACES = 3
GAP_PLOT_DECIMAL_PLACES = 2
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


def to_gap_series(single_series, average_series, event_id):
    """Plot the gap between the best average and best single as the records fall.

    Both inputs already carry plotted values (Fewest Moves averages scaled to
    moves), so the difference is on the event's own scale and gets its own chart.
    Walking the union of their dates and carrying each running best forward, a
    point is emitted on every date either record improves, from the first date both
    a single and an average exist. The gap can never be negative, since the best
    average came from a round whose single was no faster than the best single.
    """
    singles_by_date = {point[DATE_KEY]: point[VALUE_KEY] for point in single_series}
    averages_by_date = {
        point[DATE_KEY]: point[VALUE_KEY] for point in average_series
    }
    series = []
    best_single = None
    best_average = None
    for date in sorted(set(singles_by_date) | set(averages_by_date)):
        if date in singles_by_date:
            best_single = singles_by_date[date]
        if date in averages_by_date:
            best_average = averages_by_date[date]
        if best_single is None or best_average is None:
            continue
        gap = round(best_average - best_single, GAP_PLOT_DECIMAL_PLACES)
        series.append(
            {
                DATE_KEY: date,
                VALUE_KEY: gap,
                DISPLAY_KEY: format_gap(gap, event_id),
            }
        )
    return series


def to_daily_range_series(daily_ranges, event_id):
    """Split each day's solve range into the fastest and slowest bounds of a band.

    The two bounds share the single's scale, so a chart can shade the area between
    them; each bound carries its own formatted value for display.
    """
    return {
        LOWER_BOUND_KEY: [
            _bound_point(daily_range.date, daily_range.fastest, event_id)
            for daily_range in daily_ranges
        ],
        UPPER_BOUND_KEY: [
            _bound_point(daily_range.date, daily_range.slowest, event_id)
            for daily_range in daily_ranges
        ],
    }


def _bound_point(date, value, event_id):
    return {
        DATE_KEY: date,
        VALUE_KEY: value,
        DISPLAY_KEY: format_single(value, event_id),
    }


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
