"""Detection of personal records within a competitor's results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordPoint:
    """A personal-record value and the date it was set."""

    date: str
    value: int


def personal_record_flags(values):
    """Flag each value that beats every preceding value in chronological order."""
    flags = []
    best_so_far = None
    for value in values:
        is_attempted = value > 0
        is_record = is_attempted and (best_so_far is None or value < best_so_far)
        flags.append(is_record)
        if is_record:
            best_so_far = value
    return flags


def single_record_progression(results, competition_dates):
    """Return the personal-record singles, with their dates, in chronological order."""
    return _record_progression(
        results, competition_dates, lambda result: result.single
    )


def average_record_progression(results, competition_dates):
    """Return the personal-record averages, with their dates, in chronological order."""
    return _record_progression(
        results, competition_dates, lambda result: result.average
    )


def _record_progression(results, competition_dates, metric):
    """Return the personal-record values of a metric, with their dates, chronologically."""
    dated_results = sorted(
        results,
        key=lambda result: competition_dates[result.competition_id],
    )
    values = [metric(result) for result in dated_results]
    flags = personal_record_flags(values)
    records_by_date = {}
    for result, is_record in zip(dated_results, flags):
        if is_record:
            date = competition_dates[result.competition_id]
            records_by_date[date] = RecordPoint(date=date, value=metric(result))
    return list(records_by_date.values())
