"""Formatting of WCA results for display."""

from dataclasses import dataclass

CENTISECONDS_PER_SECOND = 100
SECONDS_PER_MINUTE = 60
CENTISECONDS_PER_MINUTE = CENTISECONDS_PER_SECOND * SECONDS_PER_MINUTE
FEWEST_MOVES_EVENT_ID = "333fm"
MULTI_BLIND_EVENT_ID = "333mbf"
CENTI_MOVES_PER_MOVE = 100
TIME_UNIT = "time"
MOVES_UNIT = "moves"
POINTS_UNIT = "points"
CONSISTENCY_DECIMAL_PLACES = 2
CONSISTENCY_RATIO_SUFFIX = "×"
MIDPOINT_MOVES_DECIMAL_PLACES = 2
# Events scored by a single attempt rather than an average of several. Multi-Blind
# ranks one sitting by points, so it has no average to progress or chart.
EVENT_IDS_WITHOUT_AVERAGE = frozenset({MULTI_BLIND_EVENT_ID})

# The WCA API encodes a Multi-Blind result as one integer:
#   value = (99 - points) * MULTI_BLIND_DIFFERENCE_FACTOR
#           + time_in_seconds * MULTI_BLIND_TIME_FACTOR + missed
# where points = solved - missed. Lower values are better, so the same minimum
# ordering used for timed events still ranks Multi-Blind personal records.
MULTI_BLIND_POINTS_BASE = 99
MULTI_BLIND_DIFFERENCE_FACTOR = 10_000_000
MULTI_BLIND_TIME_FACTOR = 100
MULTI_BLIND_MISSED_MODULUS = 100


@dataclass(frozen=True)
class MultiBlindResult:
    """A decoded Multi-Blind attempt: cubes solved, attempted, and its score."""

    solved: int
    attempted: int
    missed: int
    points: int
    time_seconds: int


def decode_multi_blind(value):
    """Decode the WCA Multi-Blind encoded integer into its component fields."""
    difference = value // MULTI_BLIND_DIFFERENCE_FACTOR
    points = MULTI_BLIND_POINTS_BASE - difference
    time_seconds = (value % MULTI_BLIND_DIFFERENCE_FACTOR) // MULTI_BLIND_TIME_FACTOR
    missed = value % MULTI_BLIND_MISSED_MODULUS
    solved = points + missed
    attempted = solved + missed
    return MultiBlindResult(
        solved=solved,
        attempted=attempted,
        missed=missed,
        points=points,
        time_seconds=time_seconds,
    )


def format_time(centiseconds):
    """Render a result in centiseconds as a cubing time string."""
    minutes = centiseconds // CENTISECONDS_PER_MINUTE
    within_minute = centiseconds % CENTISECONDS_PER_MINUTE
    seconds = within_minute // CENTISECONDS_PER_SECOND
    hundredths = within_minute % CENTISECONDS_PER_SECOND
    if minutes:
        return f"{minutes}:{seconds:02d}.{hundredths:02d}"
    return f"{seconds}.{hundredths:02d}"


def format_minutes_seconds(total_seconds):
    """Render a whole-second duration as minutes and zero-padded seconds."""
    minutes = total_seconds // SECONDS_PER_MINUTE
    seconds = total_seconds % SECONDS_PER_MINUTE
    return f"{minutes}:{seconds:02d}"


def format_multi_blind(value):
    """Render a Multi-Blind result as ``solved/attempted MM:SS`` (e.g. ``8/10 34:21``)."""
    result = decode_multi_blind(value)
    return (
        f"{result.solved}/{result.attempted} "
        f"{format_minutes_seconds(result.time_seconds)}"
    )


def format_multi_blind_full(value):
    """Render a Multi-Blind result in full (e.g. ``8/10 in 34:21 (6 pts)``)."""
    result = decode_multi_blind(value)
    return (
        f"{result.solved}/{result.attempted} in "
        f"{format_minutes_seconds(result.time_seconds)} ({result.points} pts)"
    )


def format_single(value, event_id):
    """Render a single result per its event's units (time, moves, or Multi-Blind)."""
    if event_id == FEWEST_MOVES_EVENT_ID:
        return str(value)
    if event_id == MULTI_BLIND_EVENT_ID:
        return format_multi_blind(value)
    return format_time(value)


def format_average(value, event_id):
    """Render an average result; Fewest Moves averages are stored as moves times 100."""
    if event_id == FEWEST_MOVES_EVENT_ID:
        return f"{value / CENTI_MOVES_PER_MOVE:.2f}"
    return format_time(value)


def format_midpoint(value, event_id):
    """Render a midpoint between a single and an average in the event's plotted units.

    The value is already on the single's scale (Fewest Moves in moves, timed events
    in centiseconds) but may fall on a half unit, so timed values are rounded to a
    whole centisecond before formatting.
    """
    if event_id == FEWEST_MOVES_EVENT_ID:
        return f"{value:.{MIDPOINT_MOVES_DECIMAL_PLACES}f}"
    return format_time(round(value))


def format_consistency(ratio):
    """Render an average-to-single ratio; 1.00× means every solve was identical."""
    return f"{ratio:.{CONSISTENCY_DECIMAL_PLACES}f}{CONSISTENCY_RATIO_SUFFIX}"


def event_has_average(event_id):
    """Whether this event is scored by an average rather than a single attempt."""
    return event_id not in EVENT_IDS_WITHOUT_AVERAGE


def result_unit(event_id):
    """Return the unit a competitor's results are measured in for this event."""
    if event_id == FEWEST_MOVES_EVENT_ID:
        return MOVES_UNIT
    if event_id == MULTI_BLIND_EVENT_ID:
        return POINTS_UNIT
    return TIME_UNIT
