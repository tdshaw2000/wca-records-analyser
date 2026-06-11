"""Client for searching competitors via the World Cube Association API."""

from dataclasses import dataclass

import httpx

WCA_API_BASE_URL = "https://www.worldcubeassociation.org/api/v0"
PERSONS_SEARCH_ENDPOINT = "/persons"
SEARCH_QUERY_PARAMETER = "q"
PERSON_KEY = "person"
PERSON_NAME_KEY = "name"
PERSON_PROFILE_URL_KEY = "url"


@dataclass(frozen=True)
class Person:
    """A competitor returned by a WCA search."""

    name: str
    profile_url: str


def search_persons(name, client=None):
    """Return the competitors whose names match the given search term."""
    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=WCA_API_BASE_URL)
    try:
        response = client.get(
            PERSONS_SEARCH_ENDPOINT,
            params={SEARCH_QUERY_PARAMETER: name},
        )
        response.raise_for_status()
        matches = response.json()
    finally:
        if owns_client:
            client.close()
    return [_to_person(match) for match in matches]


def _to_person(match):
    person = match[PERSON_KEY]
    return Person(
        name=person[PERSON_NAME_KEY],
        profile_url=person[PERSON_PROFILE_URL_KEY],
    )
