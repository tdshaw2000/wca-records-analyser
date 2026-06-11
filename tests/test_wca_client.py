import httpx

from wca_records_analyser.wca_client import (
    Person,
    WCA_API_BASE_URL,
    search_persons,
)

SEARCH_NAME = "Mats Valk"
EXPECTED_NAME = "Mats Valk"
EXPECTED_PROFILE_URL = "https://www.worldcubeassociation.org/persons/2007VALK01"

SINGLE_PERSON_RESPONSE = [
    {
        "person": {
            "name": EXPECTED_NAME,
            "wca_id": "2007VALK01",
            "url": EXPECTED_PROFILE_URL,
        }
    }
]


def _client_returning(payload, recorded_requests=None):
    def handler(request):
        if recorded_requests is not None:
            recorded_requests.append(request)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url=WCA_API_BASE_URL)


def test_search_persons_returns_person_name_and_profile_url():
    client = _client_returning(SINGLE_PERSON_RESPONSE)

    results = search_persons(SEARCH_NAME, client=client)

    assert results == [
        Person(name=EXPECTED_NAME, profile_url=EXPECTED_PROFILE_URL)
    ]


def test_search_persons_sends_searched_name_as_query_parameter():
    recorded_requests = []
    client = _client_returning([], recorded_requests=recorded_requests)

    search_persons(SEARCH_NAME, client=client)

    assert recorded_requests[0].url.params["q"] == SEARCH_NAME


def test_search_persons_returns_empty_list_when_no_matches():
    client = _client_returning([])

    assert search_persons("no such competitor", client=client) == []
