"""Client for searching competitors via the World Cube Association API."""

from dataclasses import dataclass

import httpx

WCA_API_BASE_URL = "https://www.worldcubeassociation.org/api/v0"
PERSONS_SEARCH_ENDPOINT = "/persons"
PERSON_RESULTS_ENDPOINT = "/persons/{wca_id}/results"
PERSON_COMPETITIONS_ENDPOINT = "/persons/{wca_id}/competitions"
SEARCH_QUERY_PARAMETER = "q"
EVENT_QUERY_PARAMETER = "event_id"
PERSON_KEY = "person"
PERSON_NAME_KEY = "name"
PERSON_PROFILE_URL_KEY = "url"
RESULT_SINGLE_KEY = "best"
RESULT_COMPETITION_KEY = "competition_id"
COMPETITION_ID_KEY = "id"
COMPETITION_START_DATE_KEY = "start_date"


@dataclass(frozen=True)
class Person:
    """A competitor returned by a WCA search."""

    name: str
    profile_url: str


@dataclass(frozen=True)
class Result:
    """A competitor's single for one round, tied to the competition it was set at."""

    single: int
    competition_id: str


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
        profile_url=person[PERSON_PROFILE_URL_KEY],
    )


def _to_result(result):
    return Result(
        single=result[RESULT_SINGLE_KEY],
        competition_id=result[RESULT_COMPETITION_KEY],
    )
