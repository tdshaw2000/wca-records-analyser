"""The read library: how the web app, or any other Python app, reads the built database."""

import sqlite3
import threading
from datetime import UTC, datetime

import pytest

from wca_data.build import build_database
from wca_data.read import (
    Competition,
    DatabaseUnavailable,
    Event,
    Metadata,
    Person,
    Result,
    SchemaVersionMismatch,
    WcaData,
)
from wca_data.schema import SCHEMA_VERSION

from .export_zip import tsv, write_fixture_zip

BUILT_AT = datetime(2026, 9, 24, 3, 15, 0, tzinfo=UTC)
RESULT_HEADER = ["id", "competition_id", "round_type_id", "event_id", "person_id", "best", "average"]
ATTEMPT_HEADER = ["value", "attempt_number", "result_id"]


def _build(tmp_path, **tables):
    path = tmp_path / "wca.sqlite"
    build_database(write_fixture_zip(tmp_path / "export.zip", **tables), path, BUILT_AT)
    return path


@pytest.fixture
def db_path(tmp_path):
    return _build(tmp_path)


@pytest.fixture
def data(db_path):
    with WcaData.open(db_path) as opened:
        yield opened


# --- opening ---


def test_opens_the_database_named_by_wca_data_db_path(db_path):
    with WcaData.open(environ={"WCA_DATA_DB_PATH": str(db_path)}) as data:
        assert data.metadata().schema_version == SCHEMA_VERSION


def test_a_missing_database_is_reported_clearly_and_not_created(tmp_path):
    missing = tmp_path / "nowhere.sqlite"
    with pytest.raises(DatabaseUnavailable, match="nowhere.sqlite"):
        WcaData.open(missing)
    assert not missing.exists()


def test_a_file_that_is_not_a_wca_data_database_is_reported_clearly(tmp_path):
    other = tmp_path / "other.sqlite"
    with sqlite3.connect(other) as connection:
        connection.execute("CREATE TABLE t (x)")
    with pytest.raises(DatabaseUnavailable, match="other.sqlite"):
        WcaData.open(other)


def test_a_database_built_for_another_schema_version_is_refused(db_path):
    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE meta SET value = '1' WHERE key = 'schema_version'")
    with pytest.raises(SchemaVersionMismatch, match=f"version 1.*version {SCHEMA_VERSION}"):
        WcaData.open(db_path)


def test_the_database_is_opened_read_only(data):
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        data.connection.execute("DELETE FROM persons")


def test_closing_closes_the_connection(db_path):
    with WcaData.open(db_path) as data:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        data.connection.execute("SELECT 1")


def test_can_be_used_from_another_thread_than_the_one_that_opened_it(data):
    # Web frameworks may open it in one worker thread and use it in another, one at a time.
    found = []
    worker = threading.Thread(target=lambda: found.append(data.person("2009ZEMD01")))
    worker.start()
    worker.join()
    assert found == [Person(wca_id="2009ZEMD01", name="Feliks Zemdegs", country_id="Australia")]


def test_a_rebuilt_database_is_seen_by_the_next_open(tmp_path, db_path):
    replacement = tmp_path / "new" / "wca.sqlite"
    replacement.parent.mkdir()
    build_database(
        write_fixture_zip(
            tmp_path / "new" / "export.zip",
            persons=tsv(["name", "gender", "wca_id", "sub_id", "country_id"],
                        ["Feliks Zemdegs", "m", "2009ZEMD01", "1", "Australia"],
                        ["Max Park", "m", "2012PARK03", "1", "USA"],
                        ["New Person", "f", "2026NEWP01", "1", "Chile"]),
        ),
        replacement,
        BUILT_AT,
    )
    with WcaData.open(db_path) as before:
        replacement.replace(db_path)
        assert before.person("2026NEWP01") is None  # an open connection keeps its file
    with WcaData.open(db_path) as after:
        assert after.person("2026NEWP01") is not None


# --- metadata ---


def test_metadata_says_which_export_the_database_was_built_from(data):
    assert data.metadata() == Metadata(
        schema_version=SCHEMA_VERSION,
        export_date=datetime(2026, 9, 23, tzinfo=UTC),
        export_version="v2.0.2",
        built_at=BUILT_AT,
    )


# --- persons ---


def test_finds_a_person_by_wca_id(data):
    assert data.person("2010WANG01") == Person(
        wca_id="2010WANG01", name="Xiaoming Wang (王小明)", country_id="China"
    )


def test_an_unknown_wca_id_is_none(data):
    assert data.person("1999NONE01") is None


# --- events ---


def test_events_are_listed_in_wca_order(data):
    assert data.events() == [
        Event(id="333", name="3x3x3 Cube", rank=10),
        Event(id="222", name="2x2x2 Cube", rank=20),
        Event(id="333bf", name="3x3x3 Blindfolded", rank=70),
    ]


def test_a_persons_events_are_the_ones_they_have_results_in_in_wca_order(data):
    assert [event.id for event in data.competed_events("2009ZEMD01")] == ["333", "333bf"]
    assert data.competed_events("1999NONE01") == []


# --- competitions ---


def test_a_persons_competitions_are_listed_oldest_first_once_each(data):
    assert data.competitions("2009ZEMD01") == [
        Competition(
            id="MelbourneWinterOpen2009", name="Melbourne Winter Open 2009",
            start_date="2009-07-18", city="Melbourne", country_id="Australia",
            latitude=-37.8136, longitude=144.9631,
        ),
        Competition(
            id="AustralianNationals2026", name="Australian Nationals 2026",
            start_date="2026-07-09", city="Melbourne, Victoria", country_id="Australia",
            latitude=-37.8136, longitude=144.9631,
        ),
    ]


def test_a_competition_without_coordinates_has_none(data):
    [shanghai] = data.competitions("2010WANG01")
    assert (shanghai.latitude, shanghai.longitude) == (None, None)


def test_a_person_with_no_results_has_no_competitions(data):
    assert data.competitions("1999NONE01") == []


# --- results ---


def test_a_persons_results_for_one_event(data):
    assert data.results("2009ZEMD01", "333") == [
        Result(id=101, person_id="2009ZEMD01", competition_id="MelbourneWinterOpen2009",
               event_id="333", round_type_id="1", best=1052, average=1157,
               attempts=(1052, 1203, 1122, 1146, 1301)),
        Result(id=102, person_id="2009ZEMD01", competition_id="MelbourneWinterOpen2009",
               event_id="333", round_type_id="f", best=993, average=1120,
               attempts=(1044, 993, 1120, 1136, 1101)),
        Result(id=103, person_id="2009ZEMD01", competition_id="AustralianNationals2026",
               event_id="333", round_type_id="f", best=593, average=648,
               attempts=(623, 593, 705, 693, 629)),
    ]


def test_all_of_a_persons_results_when_no_event_is_given(data):
    assert [result.id for result in data.results("2009ZEMD01")] == [101, 102, 103, 104]


def test_dnf_dns_and_missing_attempts_are_kept_as_the_wca_defines_them(data):
    [blindfolded] = data.results("2009ZEMD01", "333bf")
    assert (blindfolded.best, blindfolded.average, blindfolded.attempts) == (-1, -1, (-1, -1, -2))


def test_a_result_with_no_attempts_listed_has_an_empty_tuple(tmp_path):
    path = _build(
        tmp_path,
        results=tsv(RESULT_HEADER, [1, "ParisOpen2016", "1", "333", "2015MART01", 1532, 1688]),
        result_attempts=tsv(ATTEMPT_HEADER),
    )
    with WcaData.open(path) as data:
        assert data.results("2015MART01", "333")[0].attempts == ()


def test_results_are_in_date_order_then_round_order_whatever_their_ids(tmp_path):
    # The final (round type f) was given a lower result id than the first round (1), and the
    # later competition's result a lower id than the earlier one's.
    path = _build(
        tmp_path,
        results=tsv(
            RESULT_HEADER,
            [1, "AustralianNationals2026", "f", "333", "2009ZEMD01", 593, 648],
            [2, "MelbourneWinterOpen2009", "f", "333", "2009ZEMD01", 993, 1120],
            [3, "MelbourneWinterOpen2009", "1", "333", "2009ZEMD01", 1052, 1157],
            [4, "MelbourneWinterOpen2009", "h", "333", "2009ZEMD01", 1100, 1200],
        ),
        result_attempts=tsv(ATTEMPT_HEADER),
    )
    with WcaData.open(path) as data:
        assert [result.id for result in data.results("2009ZEMD01", "333")] == [4, 3, 2, 1]


def test_an_unknown_person_or_event_has_no_results(data):
    assert data.results("1999NONE01", "333") == []
    assert data.results("2009ZEMD01", "sq1") == []


def test_results_are_read_through_the_person_and_event_index(data):
    statements = []
    data.connection.set_trace_callback(statements.append)
    data.results("2009ZEMD01", "333")
    data.connection.set_trace_callback(None)
    [query] = [sql for sql in statements if "FROM results" in sql]
    plan = " ".join(row[3] for row in data.connection.execute("EXPLAIN QUERY PLAN " + query))
    assert "results_person_event" in plan


# --- search ---


def _ids(people):
    return [person.wca_id for person in people]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Feliks", ["2009ZEMD01"]),
        ("feli", ["2009ZEMD01"]),  # the start of a word, as someone types
        ("zem feli", ["2009ZEMD01"]),  # every word must match, in any order
        ("  Max   Park ", ["2012PARK03"]),
        ("zoe martinez", ["2015MART01"]),  # accents don't matter
        ("ZOÉ", ["2015MART01"]),
        ("2009zemd01", ["2009ZEMD01"]),  # a WCA ID, or the start of one
        ("2009ZEMD", ["2009ZEMD01"]),
        ("wang", ["2010WANG01"]),
        ("王小明", ["2010WANG01"]),
        ("feliks park", []),
        ("Felix", []),  # only current names are searched
    ],
)
def test_search_matches_the_start_of_each_word_of_a_name_or_wca_id(data, query, expected):
    assert _ids(data.search_persons(query)) == expected


@pytest.mark.parametrize("query", ["", "   ", "()", "-", '"', "*", "^"])
def test_a_query_with_nothing_to_search_for_finds_nobody(data, query):
    assert data.search_persons(query) == []


@pytest.mark.parametrize(
    "query",
    ['feliks"', '"feliks', "feliks AND", "OR max", "NOT zoe", "NEAR(max park)", "name:max",
     "-zoe", "max*", "(max", "feliks + max", "{wca_id}: 2009", "zoe'"],
)
def test_search_input_is_never_read_as_query_syntax(data, query):
    data.search_persons(query)  # no sqlite3.OperationalError


def test_search_treats_query_operators_as_words(data):
    assert _ids(data.search_persons("max*")) == ["2012PARK03"]
    assert _ids(data.search_persons("-zoe")) == ["2015MART01"]
    assert data.search_persons("feliks OR max") == []


def test_search_results_are_whole_persons_in_name_order(tmp_path):
    header = ["name", "gender", "wca_id", "sub_id", "country_id"]
    path = _build(
        tmp_path,
        persons=tsv(header,
                    ["Feliks Zemdegs", "m", "2009ZEMD01", "1", "Australia"],
                    ["Anna Smith", "f", "2020SMIT02", "1", "Canada"],
                    ["Anna Smith", "f", "2019SMIT01", "1", "Canada"],
                    ["Aaron Smith", "m", "2021SMIT01", "1", "USA"]),
    )
    with WcaData.open(path) as data:
        assert data.search_persons("smith") == [
            Person(wca_id="2021SMIT01", name="Aaron Smith", country_id="USA"),
            Person(wca_id="2019SMIT01", name="Anna Smith", country_id="Canada"),
            Person(wca_id="2020SMIT02", name="Anna Smith", country_id="Canada"),
        ]


def test_search_returns_at_most_the_limit(tmp_path):
    header = ["name", "gender", "wca_id", "sub_id", "country_id"]
    rows = [[f"Sam Lee {n:02d}", "m", f"20{n:02d}LEES01", "1", "USA"] for n in range(30)]
    path = _build(tmp_path, persons=tsv(header, *rows))
    with WcaData.open(path) as data:
        assert len(data.search_persons("lee")) == 25
        assert _ids(data.search_persons("lee", limit=3)) == ["2000LEES01", "2001LEES01", "2002LEES01"]


# --- CJK names: Chinese, Japanese and Korean names have no spaces between words ---


@pytest.fixture
def cjk_data(tmp_path):
    header = ["name", "gender", "wca_id", "sub_id", "country_id"]
    path = _build(
        tmp_path,
        persons=tsv(header,
                    ["Feliks Zemdegs", "m", "2009ZEMD01", "1", "Australia"],
                    ["Xiaoming Wang (王小明)", "m", "2010WANG01", "1", "China"],
                    ["Ken'ichi Ueno (上野健一)", "m", "1982UENO01", "1", "Japan"],
                    ["Taro Tanaka (たなかタロウ)", "m", "2015TANA01", "1", "Japan"],
                    ["Minsoo Kim (김민수)", "m", "2016KIMM01", "1", "Korea"],
                    ["Yi Wang (王一)", "f", "2018WANG02", "1", "China"],
                    ["Yuki Sasaki (佐々木雄貴)", "m", "2019SASA01", "1", "Japan"],
                    ["Ling Wang (王〇玲)", "f", "2020WANG05", "1", "China"]),
    )
    with WcaData.open(path) as opened:
        yield opened


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("小明", ["2010WANG01"]),  # any run of characters inside the name
        ("明", ["2010WANG01"]),
        ("王", ["2020WANG05", "2010WANG01", "2018WANG02"]),
        ("王小明", ["2010WANG01"]),
        ("(王小明)", ["2010WANG01"]),
        ("明小", []),  # the characters must be in that order
        ("王 明", ["2010WANG01"]),  # separate words each match
        ("健一", ["1982UENO01"]),
        ("タロウ", ["2015TANA01"]),  # katakana
        ("なか", ["2015TANA01"]),  # hiragana
        ("민수", ["2016KIMM01"]),  # hangul
        ("wang 王", ["2020WANG05", "2010WANG01", "2018WANG02"]),
        ("佐々木", ["2019SASA01"]),  # the iteration mark 々 is part of the name
        ("々木", ["2019SASA01"]),
        ("佐々木雄貴", ["2019SASA01"]),
        ("王〇玲", ["2020WANG05"]),  # 〇, the ideographic zero  # mixed with a latin word
        ("xiao 王", ["2010WANG01"]),
        ("Wang王一", ["2018WANG02"]),
        ("feliks 王", []),
    ],
)
def test_search_finds_any_part_of_a_cjk_name(cjk_data, query, expected):
    assert _ids(cjk_data.search_persons(query)) == expected


def test_a_full_wca_id_puts_that_person_first(tmp_path):
    header = ["name", "gender", "wca_id", "sub_id", "country_id"]
    path = _build(
        tmp_path,
        persons=tsv(header,
                    ["Aaron Smith", "m", "2021SMIT01", "1", "USA"],
                    ["Zed Smith", "m", "2021SMIT02", "1", "USA"],
                    ["Anna Smith", "f", "2021SMIT03", "1", "Canada"]),
    )
    with WcaData.open(path) as data:
        assert _ids(data.search_persons("2021smit02")) == ["2021SMIT02"]
        assert _ids(data.search_persons("2021SMIT")) == ["2021SMIT01", "2021SMIT03", "2021SMIT02"]
        assert _ids(data.search_persons("smith 2021SMIT03")) == ["2021SMIT03"]
        assert _ids(data.search_persons("smith 2021smit02 ")) == ["2021SMIT02"]


def test_a_full_wca_id_comes_before_names_that_merely_start_with_it(tmp_path):
    header = ["name", "gender", "wca_id", "sub_id", "country_id"]
    path = _build(
        tmp_path,
        persons=tsv(header,
                    ["Aaron Lee", "m", "2019LEEA01", "1", "USA"],
                    ["Zoe Lee", "f", "2019LEEZ01", "1", "USA"],
                    ["Bob 2019leez01", "m", "2020BOBB01", "1", "USA"]),
    )
    with WcaData.open(path) as data:
        assert _ids(data.search_persons("2019LEEZ01")) == ["2019LEEZ01", "2020BOBB01"]


@pytest.mark.parametrize("limit", [0, -1])
def test_a_limit_below_one_finds_nobody(data, limit):
    assert data.search_persons("feliks", limit=limit) == []


def test_search_reads_only_the_first_ten_words(data):
    # A stranger's query can't make the search arbitrarily expensive.
    assert _ids(data.search_persons("feliks " * 10 + "nobody")) == ["2009ZEMD01"]
    assert data.search_persons("feliks " * 9 + "nobody") == []


def test_search_reads_only_the_first_hundred_characters(data):
    assert _ids(data.search_persons("feliks" + " " * 94 + "nobody")) == ["2009ZEMD01"]
    assert data.search_persons("feliks" + " " * 93 + "nobody") == []
