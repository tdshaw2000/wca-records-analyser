from wca_records_analyser.overview import EventAges, overview_rows
from wca_records_analyser.wca_client import Result

TODAY = "2026-07-02"

# One shared competition-date table, exactly as a competitor's fetch returns it.
A_MONTH_AGO_COMPETITION = "BirminghamJune2026"
A_WEEK_AGO_COMPETITION = "ManchesterLateJune2026"
THREE_MONTHS_AGO_COMPETITION = "LondonApril2026"
YESTERDAY_COMPETITION = "LeedsJuly2026"
COMPETITION_DATES = {
    A_MONTH_AGO_COMPETITION: "2026-06-02",
    A_WEEK_AGO_COMPETITION: "2026-06-25",
    THREE_MONTHS_AGO_COMPETITION: "2026-04-03",
    YESTERDAY_COMPETITION: "2026-07-01",
}

# 3x3x3: the single keeps improving to the recent competition, but the average's
# only personal record was set a month ago (it got worse afterwards), so the two
# latest-PR dates differ.
THREE_BY_THREE_EVENT_ID = "333"
THREE_BY_THREE_RESULTS = [
    Result(single=900, average=1100, competition_id=A_MONTH_AGO_COMPETITION),
    Result(single=850, average=1200, competition_id=A_WEEK_AGO_COMPETITION),
]

# 2x2x2: a single competition set both records three months ago.
TWO_BY_TWO_EVENT_ID = "222"
TWO_BY_TWO_RESULTS = [
    Result(single=300, average=400, competition_id=THREE_MONTHS_AGO_COMPETITION),
]

# 3x3x3 Blindfolded: only ever attempted as a single (average encoded as 0), so it
# has a single PR but no average PR.
BLINDFOLDED_EVENT_ID = "333bf"
BLINDFOLDED_RESULTS = [
    Result(single=5000, average=0, competition_id=YESTERDAY_COMPETITION),
]

EVENT_IDS = [THREE_BY_THREE_EVENT_ID, BLINDFOLDED_EVENT_ID, TWO_BY_TWO_EVENT_ID]
RESULTS_BY_EVENT = {
    THREE_BY_THREE_EVENT_ID: THREE_BY_THREE_RESULTS,
    BLINDFOLDED_EVENT_ID: BLINDFOLDED_RESULTS,
    TWO_BY_TWO_EVENT_ID: TWO_BY_TWO_RESULTS,
}


def _rows():
    return overview_rows(EVENT_IDS, RESULTS_BY_EVENT, COMPETITION_DATES, TODAY)


def test_overview_rows_orders_events_by_display_name():
    rows = _rows()

    assert [row.event_id for row in rows] == [
        TWO_BY_TWO_EVENT_ID,
        BLINDFOLDED_EVENT_ID,
        THREE_BY_THREE_EVENT_ID,
    ]
    assert [row.event_name for row in rows] == [
        "2x2x2 Cube",
        "3x3x3 Blindfolded",
        "3x3x3 Cube",
    ]


def test_overview_rows_report_the_ages_of_the_latest_single_and_average_prs():
    rows = {row.event_id: row for row in _rows()}

    three_by_three = rows[THREE_BY_THREE_EVENT_ID]
    assert three_by_three.single_age == "1 week ago"
    assert three_by_three.average_age == "1 month ago"

    two_by_two = rows[TWO_BY_TWO_EVENT_ID]
    assert two_by_two.single_age == "3 months ago"
    assert two_by_two.average_age == "3 months ago"


def test_overview_rows_report_no_average_age_when_there_is_no_average_pr():
    blindfolded = {row.event_id: row for row in _rows()}[BLINDFOLDED_EVENT_ID]

    assert blindfolded.single_age == "yesterday"
    assert blindfolded.average_age is None
