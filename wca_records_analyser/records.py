"""Detection of personal records within a competitor's results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RecordPoint:
    """A personal-record single and the date it was set."""

    date: str
    single: int


def personal_record_flags(singles):
    """Flag each single that beats every preceding single in chronological order."""
    flags = []
    best_so_far = None
    for single in singles:
        is_attempted = single > 0
        is_record = is_attempted and (best_so_far is None or single < best_so_far)
        flags.append(is_record)
        if is_record:
            best_so_far = single
    return flags


def single_record_progression(results, competition_dates):
    """Return the personal-record singles, with their dates, in chronological order."""
    dated_results = sorted(
        results,
        key=lambda result: competition_dates[result.competition_id],
    )
    singles = [result.single for result in dated_results]
    flags = personal_record_flags(singles)
    records_by_date = {}
    for result, is_record in zip(dated_results, flags):
        if is_record:
            date = competition_dates[result.competition_id]
            records_by_date[date] = RecordPoint(date=date, single=result.single)
    return list(records_by_date.values())
