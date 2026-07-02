"""Assembly of a competitor's per-event latest-PR ages for the overview table."""

from dataclasses import dataclass

from wca_records_analyser.events import named_events
from wca_records_analyser.formatting import format_age
from wca_records_analyser.records import (
    average_record_progression,
    single_record_progression,
)


@dataclass(frozen=True)
class EventAges:
    """One overview row: how long ago an event's latest single and average PRs fell."""

    event_id: str
    event_name: str
    single_age: str | None
    average_age: str | None


def _latest_pr_age(progression, today):
    """The age of a progression's most recent record, or None when it holds none."""
    if not progression:
        return None
    return format_age(progression[-1].date, today)


def overview_rows(event_ids, results_by_event, competition_dates, today):
    """Summarise each event's latest single and average PR as a human-readable age.

    Events are ordered by display name; an event with no average PR (a single-only
    event, or one never averaged) reports ``None`` for its average age.
    """
    rows = []
    for event in named_events(event_ids):
        results = results_by_event[event.event_id]
        singles = single_record_progression(results, competition_dates)
        averages = average_record_progression(results, competition_dates)
        rows.append(
            EventAges(
                event_id=event.event_id,
                event_name=event.name,
                single_age=_latest_pr_age(singles, today),
                average_age=_latest_pr_age(averages, today),
            )
        )
    return rows
