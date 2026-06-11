import httpx

from wca_records_analyser.wca_client import (
    Person,
    Result,
    WCA_API_BASE_URL,
    get_results,
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

WCA_ID = "2023SHAW10"
EVENT_ID = "333"
FIRST_COMPETITION_ID = "WestonsuperMareAutumn2023"
SECOND_COMPETITION_ID = "RubiksUKChampionship2024"
FIRST_SINGLE = 1807
SECOND_SINGLE = 1498

RESULTS_RESPONSE = [
    {
        "best": FIRST_SINGLE,
        "average": 2177,
        "event_id": EVENT_ID,
        "competition_id": FIRST_COMPETITION_ID,
        "round_type_id": "d",
    },
    {
        "best": SECOND_SINGLE,
        "average": 1646,
        "event_id": EVENT_ID,
        "competition_id": SECOND_COMPETITION_ID,
        "round_type_id": "f",
    },
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


def test_get_results_returns_single_and_competition_for_each_result():
    client = _client_returning(RESULTS_RESPONSE)

    results = get_results(WCA_ID, EVENT_ID, client=client)

    assert results == [
        Result(single=FIRST_SINGLE, competition_id=FIRST_COMPETITION_ID),
        Result(single=SECOND_SINGLE, competition_id=SECOND_COMPETITION_ID),
    ]


def test_get_results_requests_the_event_results_for_the_competitor():
    recorded_requests = []
    client = _client_returning([], recorded_requests=recorded_requests)

    get_results(WCA_ID, EVENT_ID, client=client)

    request = recorded_requests[0]
    assert request.url.path == f"/api/v0/persons/{WCA_ID}/results"
    assert request.url.params["event_id"] == EVENT_ID
