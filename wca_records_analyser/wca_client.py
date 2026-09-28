"""A competitor's WCA data, read from the wca_data database built from the WCA export.

Each function opens the database WCA_DATA_DB_PATH names for the one lookup, so it sees the
latest nightly build; pass ``data`` (an open WcaData) to read from another one, as tests do.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

from wca_data.read import WcaData

WCA_PERSON_URL = "https://www.worldcubeassociation.org/persons/{wca_id}"


class PersonNotFound(LookupError):
    """No competitor has this WCA ID."""


@dataclass(frozen=True)
class Competition:
    """A competition with its location, used to place PR results on a map.

    ``latitude`` and ``longitude`` are None when WCA has no location for it.
    """

    id: str
    start_date: str
    latitude: float | None
    longitude: float | None
    city: str


@dataclass(frozen=True)
class Person:
    """A competitor, with a link to their profile on the WCA site."""

    name: str
    wca_id: str
    profile_url: str


@dataclass(frozen=True)
class Profile:
    """A competitor's identity and the events they hold a personal record in."""

    person: Person
    event_ids: list


@dataclass(frozen=True)
class Result:
    """A competitor's round result, tied to its competition.

    ``single`` is the round's best solve and ``average`` its average; ``solves``
    holds every individual attempt (raw centiseconds, including DNF/DNS sentinels).
    """

    single: int
    competition_id: str
    average: int = 0
    solves: tuple = ()


@contextmanager
def _reading(data: WcaData | None) -> Iterator[WcaData]:
    if data is not None:
        yield data
        return
    with WcaData.open() as opened:
        yield opened


def _to_person(person) -> Person:
    return Person(
        name=person.name,
        wca_id=person.wca_id,
        profile_url=WCA_PERSON_URL.format(wca_id=person.wca_id),
    )


def search_persons(name, data=None):
    """Return the competitors whose names or WCA IDs match the given search term."""
    with _reading(data) as reader:
        return [_to_person(person) for person in reader.search_persons(name)]


def get_results(wca_id, event_id, data=None):
    """Return a competitor's results for one event, oldest competition and round first."""
    with _reading(data) as reader:
        return [
            Result(
                single=result.best,
                competition_id=result.competition_id,
                average=result.average,
                solves=result.attempts,
            )
            for result in reader.results(wca_id, event_id)
        ]


def get_competitions(wca_id, data=None):
    """Return a competitor's competitions, keyed by competition id."""
    with _reading(data) as reader:
        return {
            competition.id: Competition(
                id=competition.id,
                start_date=competition.start_date,
                latitude=competition.latitude,
                longitude=competition.longitude,
                city=competition.city,
            )
            for competition in reader.competitions(wca_id)
        }


def get_competition_dates(wca_id, data=None):
    """Return a competitor's competitions mapped to their start dates."""
    return {
        comp_id: comp.start_date
        for comp_id, comp in get_competitions(wca_id, data=data).items()
    }


def get_profile(wca_id, data=None):
    """Return a competitor's identity and the events they have a successful result in.

    Raises PersonNotFound for an unknown WCA ID.
    """
    with _reading(data) as reader:
        person = reader.person(wca_id)
        if person is None:
            raise PersonNotFound(f"No competitor has the WCA ID {wca_id}")
        # As on the WCA site, an event holds a record only once a solve is completed.
        recorded = {result.event_id for result in reader.results(wca_id) if result.best > 0}
        event_ids = [
            event.id for event in reader.competed_events(wca_id) if event.id in recorded
        ]
        return Profile(person=_to_person(person), event_ids=event_ids)


def get_export_date(data=None) -> date:
    """The day of the WCA export the database was built from, for the licence notice."""
    with _reading(data) as reader:
        return reader.metadata().export_date.date()
