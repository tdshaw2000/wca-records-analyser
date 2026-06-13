"""Client for searching competitors via the World Cube Association API."""

from dataclasses import dataclass

import httpx
import truststore


def use_operating_system_trust_store() -> None:
    """Verify TLS against the OS certificate store rather than certifi's bundle.

    httpx defaults to certifi's public root list, which omits any private root a
    TLS-inspecting proxy presents (e.g. a corporate Zscaler CA installed into the
    OS store). Honouring the OS store lets verification succeed wherever the host
    trusts the issuer, with no environment variables to set.
    """
    truststore.inject_into_ssl()


use_operating_system_trust_store()

WCA_API_BASE_URL = "https://www.worldcubeassociation.org/api/v0"
PERSONS_SEARCH_ENDPOINT = "/persons"
PERSON_PROFILE_ENDPOINT = "/persons/{wca_id}"
PERSON_RESULTS_ENDPOINT = "/persons/{wca_id}/results"
PERSON_COMPETITIONS_ENDPOINT = "/persons/{wca_id}/competitions"
SEARCH_QUERY_PARAMETER = "q"
EVENT_QUERY_PARAMETER = "event_id"
PERSON_KEY = "person"
PERSON_NAME_KEY = "name"
PERSON_WCA_ID_KEY = "wca_id"
PERSON_PROFILE_URL_KEY = "url"
PERSON_AVATAR_KEY = "avatar"
AVATAR_THUMBNAIL_URL_KEY = "thumb_url"
RESULT_SINGLE_KEY = "best"
RESULT_AVERAGE_KEY = "average"
RESULT_ATTEMPTS_KEY = "attempts"
RESULT_COMPETITION_KEY = "competition_id"
COMPETITION_ID_KEY = "id"
COMPETITION_START_DATE_KEY = "start_date"
PERSONAL_RECORDS_KEY = "personal_records"


@dataclass(frozen=True)
class Person:
    """A competitor returned by a WCA search."""

    name: str
    wca_id: str
    profile_url: str
    avatar_thumb_url: str = ""


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


def search_persons(name, client=None):
    """Return the competitors whose names match the given search term."""
    matches = _get_json(
        PERSONS_SEARCH_ENDPOINT,
        params={SEARCH_QUERY_PARAMETER: name},
        client=client,
    )
    return [_to_person(match) for match in matches]


def get_results(wca_id, event_id, client=None):
    """Return a competitor's results for one event, newest WCA order preserved."""
    endpoint = PERSON_RESULTS_ENDPOINT.format(wca_id=wca_id)
    results = _get_json(
        endpoint,
        params={EVENT_QUERY_PARAMETER: event_id},
        client=client,
    )
    return [_to_result(result) for result in results]


def get_competition_dates(wca_id, client=None):
    """Return a competitor's competitions mapped to their start dates."""
    endpoint = PERSON_COMPETITIONS_ENDPOINT.format(wca_id=wca_id)
    competitions = _get_json(endpoint, params=None, client=client)
    return {
        competition[COMPETITION_ID_KEY]: competition[COMPETITION_START_DATE_KEY]
        for competition in competitions
    }


def get_profile(wca_id, client=None):
    """Return a competitor's identity and competed events from one profile fetch."""
    endpoint = PERSON_PROFILE_ENDPOINT.format(wca_id=wca_id)
    profile = _get_json(endpoint, params=None, client=client)
    return Profile(
        person=_to_person(profile),
        event_ids=list(profile[PERSONAL_RECORDS_KEY]),
    )


def _get_json(endpoint, params, client):
    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=WCA_API_BASE_URL)
    try:
        response = client.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            client.close()


def _to_person(match):
    person = match[PERSON_KEY]
    return Person(
        name=person[PERSON_NAME_KEY],
        wca_id=person[PERSON_WCA_ID_KEY],
        profile_url=person[PERSON_PROFILE_URL_KEY],
        avatar_thumb_url=person[PERSON_AVATAR_KEY][AVATAR_THUMBNAIL_URL_KEY],
    )


def _to_result(result):
    return Result(
        single=result[RESULT_SINGLE_KEY],
        average=result[RESULT_AVERAGE_KEY],
        competition_id=result[RESULT_COMPETITION_KEY],
        solves=tuple(result[RESULT_ATTEMPTS_KEY]),
    )
