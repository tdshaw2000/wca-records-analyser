"""Detection of personal records within a competitor's results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordPoint:
    """A result value and the date it was set (a record-setter or any attempt)."""

    date: str
    value: int


@dataclass(frozen=True)
class ConsistencyPoint:
    """A single result's single and average, with the date it was set.

    Holds the raw centisecond values; the average-to-single ratio that measures
    consistency is derived later, where the event's units are known.
    """

    date: str
    single: int
    average: int


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


def single_results_over_time(results, competition_dates):
    """Return every attempted single, with its date, in chronological order."""
    return _results_over_time(
        results, competition_dates, lambda result: result.single
    )


def average_results_over_time(results, competition_dates):
    """Return every attempted average, with its date, in chronological order."""
    return _results_over_time(
        results, competition_dates, lambda result: result.average
    )


def consistency_over_time(results, competition_dates):
    """Return a consistency point per result that has both a single and average.

    Unlike the record progressions, this keeps every qualifying result (not just
    record-setters), since consistency is a property of each individual sitting.
    Results missing a single or average (DNF/DNS, or formats without an average)
    are skipped.
    """
    full_results = [
        result
        for result in results
        if result.single > 0 and result.average > 0
    ]
    dated_results = sorted(
        full_results,
        key=lambda result: competition_dates[result.competition_id],
    )
    return [
        ConsistencyPoint(
            date=competition_dates[result.competition_id],
            single=result.single,
            average=result.average,
        )
        for result in dated_results
    ]


def _results_over_time(results, competition_dates, metric):
    """Return a metric's attempted values, with dates, chronologically.

    Unlike a record progression this keeps every attempt, not only the
    record-setters. Non-positive values (DNF/DNS, or formats without an average)
    are skipped.
    """
    dated_results = sorted(
        results,
        key=lambda result: competition_dates[result.competition_id],
    )
    return [
        RecordPoint(
            date=competition_dates[result.competition_id], value=metric(result)
        )
        for result in dated_results
        if metric(result) > 0
    ]


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
