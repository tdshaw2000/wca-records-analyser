"""Formatting of WCA results for display."""

CENTISECONDS_PER_SECOND = 100
SECONDS_PER_MINUTE = 60
CENTISECONDS_PER_MINUTE = CENTISECONDS_PER_SECOND * SECONDS_PER_MINUTE
FEWEST_MOVES_EVENT_ID = "333fm"
CENTI_MOVES_PER_MOVE = 100
TIME_UNIT = "time"
MOVES_UNIT = "moves"
CONSISTENCY_DECIMAL_PLACES = 2
CONSISTENCY_RATIO_SUFFIX = "×"


def format_time(centiseconds):
    """Render a result in centiseconds as a cubing time string."""
    minutes = centiseconds // CENTISECONDS_PER_MINUTE
    within_minute = centiseconds % CENTISECONDS_PER_MINUTE
    seconds = within_minute // CENTISECONDS_PER_SECOND
    hundredths = within_minute % CENTISECONDS_PER_SECOND
    if minutes:
        return f"{minutes}:{seconds:02d}.{hundredths:02d}"
    return f"{seconds}.{hundredths:02d}"


def format_single(value, event_id):
    """Render a single result, as a move count for Fewest Moves or a time otherwise."""
    if event_id == FEWEST_MOVES_EVENT_ID:
        return str(value)
    return format_time(value)


def format_average(value, event_id):
    """Render an average result; Fewest Moves averages are stored as moves times 100."""
    if event_id == FEWEST_MOVES_EVENT_ID:
        return f"{value / CENTI_MOVES_PER_MOVE:.2f}"
    return format_time(value)


def format_consistency(ratio):
    """Render an average-to-single ratio; 1.00× means every solve was identical."""
    return f"{ratio:.{CONSISTENCY_DECIMAL_PLACES}f}{CONSISTENCY_RATIO_SUFFIX}"


def result_unit(event_id):
    """Return the unit a competitor's results are measured in for this event."""
    if event_id == FEWEST_MOVES_EVENT_ID:
        return MOVES_UNIT
    return TIME_UNIT
