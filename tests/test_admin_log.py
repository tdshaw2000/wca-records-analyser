"""wca_records_analyser.admin_log: who used the app, from the web container's access log.

No docker access here — deploy/collect_admin_log.py filters `docker compose logs` on the VM
down to the lines naming a wca_id and writes them to a file this just reads as text.
"""

from wca_records_analyser.admin_log import parse_visits, usage_by_wca_id

OVERVIEW_LINE = (
    'web-1  | 2026-10-02T06:46:50.123456789Z INFO:     1.2.3.4:5 - '
    '"GET /overview?wca_id=2015DOEJ01 HTTP/1.1" 200 OK'
)
RECORDS_LINE = (
    'web-1  | 2026-10-02T06:47:01.987654321Z INFO:     1.2.3.4:5 - '
    '"GET /records?wca_id=2015DOEJ01&event_id=333 HTTP/1.1" 200 OK'
)
OTHER_COMPETITOR_LINE = (
    'web-1  | 2026-10-02T06:48:00.000000000Z INFO:     1.2.3.4:5 - '
    '"GET /overview?wca_id=2009ZEMD01 HTTP/1.1" 200 OK'
)
NO_WCA_ID_LINE = (
    'web-1  | 2026-10-02T06:48:10.000000000Z INFO:     1.2.3.4:5 - '
    '"GET /healthz HTTP/1.1" 200 OK'
)
UNPARSEABLE_LINE = "web-1  | garbage, not an access log line at all"


def test_parse_visits_reads_the_wca_id_and_path_and_timestamp_off_an_access_log_line():
    visits = parse_visits(OVERVIEW_LINE)
    assert len(visits) == 1
    visit = visits[0]
    assert visit.wca_id == "2015DOEJ01"
    assert visit.path == "/overview?wca_id=2015DOEJ01"
    assert visit.timestamp == "2026-10-02T06:46:50.123456789Z"


def test_parse_visits_skips_lines_with_no_wca_id_or_that_dont_parse():
    assert parse_visits(NO_WCA_ID_LINE) == []
    assert parse_visits(UNPARSEABLE_LINE) == []


def test_parse_visits_reads_every_line_given_several():
    text = "\n".join([OVERVIEW_LINE, RECORDS_LINE, NO_WCA_ID_LINE])
    visits = parse_visits(text)
    assert [visit.path for visit in visits] == [
        "/overview?wca_id=2015DOEJ01",
        "/records?wca_id=2015DOEJ01&event_id=333",
    ]


def test_usage_by_wca_id_lists_only_competitors_who_requested_the_overview_page():
    text = "\n".join([RECORDS_LINE, NO_WCA_ID_LINE])
    assert usage_by_wca_id(parse_visits(text)) == []


def test_usage_by_wca_id_nests_every_other_page_under_its_competitors_overview_visit():
    text = "\n".join([OVERVIEW_LINE, RECORDS_LINE, OTHER_COMPETITOR_LINE])
    usage = usage_by_wca_id(parse_visits(text))
    assert [entry.wca_id for entry in usage] == ["2009ZEMD01", "2015DOEJ01"]
    doe = next(entry for entry in usage if entry.wca_id == "2015DOEJ01")
    assert [visit.path for visit in doe.overview_visits] == ["/overview?wca_id=2015DOEJ01"]
    assert [visit.path for visit in doe.other_visits] == [
        "/records?wca_id=2015DOEJ01&event_id=333"
    ]


def test_usage_by_wca_id_orders_competitors_by_most_recent_overview_visit_first():
    earlier_overview = (
        'web-1  | 2026-10-02T06:40:00.000000000Z INFO:     1.2.3.4:5 - '
        '"GET /overview?wca_id=2009ZEMD01 HTTP/1.1" 200 OK'
    )
    text = "\n".join([earlier_overview, OVERVIEW_LINE])
    usage = usage_by_wca_id(parse_visits(text))
    assert [entry.wca_id for entry in usage] == ["2015DOEJ01", "2009ZEMD01"]
