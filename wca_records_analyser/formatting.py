"""Formatting of WCA results for display."""

CENTISECONDS_PER_SECOND = 100
SECONDS_PER_MINUTE = 60
CENTISECONDS_PER_MINUTE = CENTISECONDS_PER_SECOND * SECONDS_PER_MINUTE


def format_time(centiseconds):
    """Render a result in centiseconds as a cubing time string."""
    minutes = centiseconds // CENTISECONDS_PER_MINUTE
    within_minute = centiseconds % CENTISECONDS_PER_MINUTE
    seconds = within_minute // CENTISECONDS_PER_SECOND
    hundredths = within_minute % CENTISECONDS_PER_SECOND
    if minutes:
        return f"{minutes}:{seconds:02d}.{hundredths:02d}"
    return f"{seconds}.{hundredths:02d}"
