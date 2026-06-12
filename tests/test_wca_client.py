import httpx

from wca_records_analyser.wca_client import (
    Person,
    Result,
    WCA_API_BASE_URL,
    get_competed_events,
    get_competition_dates,
    get_person,
    get_results,
    search_persons,
)

SEARCH_NAME = "Mats Valk"
EXPECTED_NAME = "Mats Valk"
EXPECTED_WCA_ID = "2007VALK01"
EXPECTED_PROFILE_URL = "https://www.worldcubeassociation.org/persons/2007VALK01"

SINGLE_PERSON_RESPONSE = [
    {
        "person": {
            "name": EXPECTED_NAME,
            "wca_id": EXPECTED_WCA_ID,
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
FIRST_AVERAGE = 2177
SECOND_AVERAGE = 1646

RESULTS_RESPONSE = [
    {
        "best": FIRST_SINGLE,
        "average": FIRST_AVERAGE,
        "event_id": EVENT_ID,
        "competition_id": FIRST_COMPETITION_ID,
        "round_type_id": "d",
    },
    {
        "best": SECOND_SINGLE,
        "average": SECOND_AVERAGE,
        "event_id": EVENT_ID,
        "competition_id": SECOND_COMPETITION_ID,
        "round_type_id": "f",
    },
]

FIRST_COMPETITION_START_DATE = "2023-11-18"
SECOND_COMPETITION_START_DATE = "2024-11-01"

COMPETITIONS_RESPONSE = [
    {
        "id": FIRST_COMPETITION_ID,
        "start_date": FIRST_COMPETITION_START_DATE,
        "end_date": "2023-11-19",
    },
    {
        "id": SECOND_COMPETITION_ID,
        "start_date": SECOND_COMPETITION_START_DATE,
        "end_date": "2024-11-03",
    },
]

COMPETED_EVENT_IDS = ["333", "222", "pyram"]
PERSON_DETAIL_RESPONSE = {
    "person": {
        "name": "Tim Shaw",
        "wca_id": WCA_ID,
        "url": f"https://www.worldcubeassociation.org/persons/{WCA_ID}",
    },
    "personal_records": {
        "333": {"single": {"best": 1355}, "average": {"best": 1646}},
        "222": {"single": {"best": 585}, "average": {"best": 708}},
        "pyram": {"single": {"best": 911}, "average": {"best": 1147}},
    },
}


def _client_returning(payload, recorded_requests=None):
    def handler(request):
        if recorded_requests is not None:
            recorded_requests.append(request)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url=WCA_API_BASE_URL)


def test_search_persons_returns_person_name_wca_id_and_profile_url():
    client = _client_returning(SINGLE_PERSON_RESPONSE)

    results = search_persons(SEARCH_NAME, client=client)

    assert results == [
        Person(
            name=EXPECTED_NAME,
            wca_id=EXPECTED_WCA_ID,
            profile_url=EXPECTED_PROFILE_URL,
        )
    ]


def test_search_persons_sends_searched_name_as_query_parameter():
    recorded_requests = []
    client = _client_returning([], recorded_requests=recorded_requests)

    search_persons(SEARCH_NAME, client=client)

    assert recorded_requests[0].url.params["q"] == SEARCH_NAME


def test_search_persons_returns_empty_list_when_no_matches():
    client = _client_returning([])

    assert search_persons("no such competitor", client=client) == []


def test_get_results_returns_single_average_and_competition_for_each_result():
    client = _client_returning(RESULTS_RESPONSE)

    results = get_results(WCA_ID, EVENT_ID, client=client)

    assert results == [
        Result(
            single=FIRST_SINGLE,
            average=FIRST_AVERAGE,
            competition_id=FIRST_COMPETITION_ID,
        ),
        Result(
            single=SECOND_SINGLE,
            average=SECOND_AVERAGE,
            competition_id=SECOND_COMPETITION_ID,
        ),
    ]


def test_get_results_requests_the_event_results_for_the_competitor():
    recorded_requests = []
    client = _client_returning([], recorded_requests=recorded_requests)

    get_results(WCA_ID, EVENT_ID, client=client)

    request = recorded_requests[0]
    assert request.url.path == f"/api/v0/persons/{WCA_ID}/results"
    assert request.url.params["event_id"] == EVENT_ID


def test_get_competition_dates_maps_each_competition_to_its_start_date():
    client = _client_returning(COMPETITIONS_RESPONSE)

    dates = get_competition_dates(WCA_ID, client=client)

    assert dates == {
        FIRST_COMPETITION_ID: FIRST_COMPETITION_START_DATE,
        SECOND_COMPETITION_ID: SECOND_COMPETITION_START_DATE,
    }


def test_get_competition_dates_requests_the_competitions_for_the_competitor():
    recorded_requests = []
    client = _client_returning([], recorded_requests=recorded_requests)

    get_competition_dates(WCA_ID, client=client)

    assert (
        recorded_requests[0].url.path == f"/api/v0/persons/{WCA_ID}/competitions"
    )


def test_get_competed_events_returns_the_events_the_competitor_has_records_in():
    client = _client_returning(PERSON_DETAIL_RESPONSE)

    events = get_competed_events(WCA_ID, client=client)

    assert events == COMPETED_EVENT_IDS


def test_get_competed_events_requests_the_competitor_profile():
    recorded_requests = []
    client = _client_returning(
        PERSON_DETAIL_RESPONSE, recorded_requests=recorded_requests
    )

    get_competed_events(WCA_ID, client=client)

    assert recorded_requests[0].url.path == f"/api/v0/persons/{WCA_ID}"


def test_get_person_returns_the_competitor_identity():
    client = _client_returning(PERSON_DETAIL_RESPONSE)

    person = get_person(WCA_ID, client=client)

    assert person == Person(
        name="Tim Shaw",
        wca_id=WCA_ID,
        profile_url=f"https://www.worldcubeassociation.org/persons/{WCA_ID}",
    )


def test_get_person_requests_the_competitor_profile():
    recorded_requests = []
    client = _client_returning(
        PERSON_DETAIL_RESPONSE, recorded_requests=recorded_requests
    )

    get_person(WCA_ID, client=client)

    assert recorded_requests[0].url.path == f"/api/v0/persons/{WCA_ID}"
