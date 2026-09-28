import sqlite3
from datetime import UTC, datetime

import pytest

from wca_data.build import UnsupportedExportVersion, build_database, parse_export_date
from wca_data.export import ExportFormatError
from wca_data.schema import SCHEMA_VERSION

from .export_zip import fixture_metadata, tsv, write_fixture_zip

BUILT_AT = datetime(2026, 9, 24, 3, 15, 0, tzinfo=UTC)
ATTEMPT_HEADER = ["value", "attempt_number", "result_id"]
RESULT_HEADER = ["id", "competition_id", "round_type_id", "event_id", "person_id", "best", "average"]


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "wca.sqlite"
    build_database(write_fixture_zip(tmp_path / "export.zip"), path, BUILT_AT)
    connection = sqlite3.connect(path)
    yield connection
    connection.close()


def _build_with(tmp_path, **tables):
    path = tmp_path / "wca.sqlite"
    build_database(write_fixture_zip(tmp_path / "export.zip", **tables), path, BUILT_AT)
    with sqlite3.connect(path) as connection:
        return dict(connection.execute("SELECT id, attempts FROM results"))


def test_keeps_only_each_competitors_current_name(db):
    rows = db.execute("SELECT wca_id, name, country_id FROM persons ORDER BY wca_id").fetchall()
    assert rows == [
        ("2009ZEMD01", "Feliks Zemdegs", "Australia"),
        ("2010WANG01", "Xiaoming Wang (王小明)", "China"),
        ("2012PARK03", "Max Park", "USA"),
        ("2015MART01", "Zoé Martínez", "France"),
    ]


def test_competitions_have_an_iso_start_date_and_coordinates_in_degrees(db):
    rows = db.execute(
        "SELECT id, name, start_date, city, country_id, latitude, longitude FROM competitions "
        "WHERE id IN ('AustralianNationals2026', 'ShanghaiSpring2012') ORDER BY id"
    ).fetchall()
    assert rows == [
        ("AustralianNationals2026", "Australian Nationals 2026", "2026-07-09",
         "Melbourne, Victoria", "Australia", -37.8136, 144.9631),
        ("ShanghaiSpring2012", "Shanghai Spring 2012", "2012-04-01",
         "上海 (Shanghai)", "China", None, None),
    ]


def test_events_come_from_the_export_with_their_rank(db):
    assert db.execute("SELECT id, name, rank FROM events ORDER BY rank").fetchall() == [
        ("333", "3x3x3 Cube", 10),
        ("222", "2x2x2 Cube", 20),
        ("333bf", "3x3x3 Blindfolded", 70),
    ]


def test_round_types_come_from_the_export_with_their_rank_and_whether_they_are_finals(db):
    rows = db.execute("SELECT id, name, rank, final FROM round_types ORDER BY rank").fetchall()
    assert rows[:3] == [("h", "Qualification round", 10, 0), ("0", "Qualification round", 19, 0),
                        ("d", "First round", 20, 0)]
    assert rows[-2:] == [("c", "Final", 90, 1), ("f", "Final", 99, 1)]
    assert len(rows) == 11


def test_feliks_zemdegs_latest_three_by_three_result_matches_the_wca(db):
    # The known-good check from docs/shared-backend-tradeoffs.md, on the fixture's copy of it.
    row = db.execute(
        "SELECT c.id, c.start_date, r.best, r.average, r.attempts, r.round_type_id "
        "FROM results r JOIN competitions c ON c.id = r.competition_id "
        "WHERE r.person_id = '2009ZEMD01' AND r.event_id = '333' "
        "ORDER BY c.start_date DESC LIMIT 1"
    ).fetchone()
    assert row == ("AustralianNationals2026", "2026-07-09", 593, 648, "623,593,705,693,629", "f")


def test_attempts_are_packed_in_attempt_order_whatever_the_export_row_order(db):
    assert dict(db.execute("SELECT id, attempts FROM results")) == {
        101: "1052,1203,1122,1146,1301",
        102: "1044,993,1120,1136,1101",
        103: "623,593,705,693,629",
        104: "-1,-1,-2",
        105: "1532,1701,1650,1713,1702",
        106: "2105,2250",
        107: "312,450,389,402,415",
    }


def test_dnf_dns_and_no_average_are_kept_as_the_wca_defines_them(db):
    rows = db.execute("SELECT id, best, average FROM results WHERE id IN (104, 106)").fetchall()
    assert rows == [(104, -1, -1), (106, 2105, 0)]


def test_a_gap_in_attempt_numbers_is_packed_as_zero_so_positions_survive(tmp_path):
    attempts = tsv(ATTEMPT_HEADER, [3120, 1, 1], [2980, 3, 1])
    results = tsv(RESULT_HEADER, [1, "ParisOpen2016", "f", "333bf", "2015MART01", 2980, 0])
    assert _build_with(tmp_path, results=results, result_attempts=attempts) == {1: "3120,0,2980"}


def test_a_result_with_no_attempts_has_an_empty_attempts_field(tmp_path):
    results = tsv(RESULT_HEADER, [1, "ParisOpen2016", "f", "333", "2015MART01", 0, 0])
    attempts = tsv(ATTEMPT_HEADER)
    assert _build_with(tmp_path, results=results, result_attempts=attempts) == {1: ""}


def test_a_repeated_attempt_fails_the_build_instead_of_dropping_one(tmp_path):
    attempts = tsv(ATTEMPT_HEADER, [1000, 1, 1], [1100, 1, 1])
    results = tsv(RESULT_HEADER, [1, "ParisOpen2016", "f", "333", "2015MART01", 1000, 0])
    with pytest.raises(ExportFormatError, match="attempt"):
        _build_with(tmp_path, results=results, result_attempts=attempts)


def test_an_attempt_for_an_unknown_result_fails_the_build(tmp_path):
    attempts = tsv(ATTEMPT_HEADER, [1000, 1, 1], [900, 1, 2])
    results = tsv(RESULT_HEADER, [1, "ParisOpen2016", "f", "333", "2015MART01", 1000, 0])
    with pytest.raises(ExportFormatError, match="result"):
        _build_with(tmp_path, results=results, result_attempts=attempts)


def test_a_repeated_result_id_fails_the_build(tmp_path):
    results = tsv(RESULT_HEADER, [1, "ParisOpen2016", "f", "333", "2015MART01", 1000, 0],
                  [1, "ParisOpen2016", "f", "333", "2015MART01", 1000, 0])
    with pytest.raises(ExportFormatError, match="result"):
        _build_with(tmp_path, results=results, result_attempts=tsv(ATTEMPT_HEADER))


def test_meta_records_the_schema_and_export_it_was_built_from(db):
    assert dict(db.execute("SELECT key, value FROM meta")) == {
        "schema_version": str(SCHEMA_VERSION),
        "export_date": "2026-09-23T00:00:00Z",
        "export_version": "v2.0.2",
        "built_at": "2026-09-24T03:15:00Z",
    }


def test_a_persons_results_for_one_event_are_found_through_the_index(db):
    plan = " ".join(
        row[3] for row in db.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM results WHERE person_id = ? AND event_id = ?",
            ("2009ZEMD01", "333"),
        )
    )
    assert "USING INDEX" in plan and "(person_id=? AND event_id=?)" in plan


@pytest.mark.parametrize(
    ("query", "expected"),
    [("zoe", "2015MART01"), ("Martinez", "2015MART01"), ("王小明", "2010WANG01"),
     ('"2009ZEMD01"', "2009ZEMD01"), ("feli*", "2009ZEMD01")],
)
def test_names_and_wca_ids_are_full_text_searchable(db, query, expected):
    rows = db.execute(
        "SELECT p.wca_id FROM persons_fts f JOIN persons p ON p.rowid = f.rowid "
        "WHERE persons_fts MATCH ?", (query,)
    ).fetchall()
    assert rows == [(expected,)]


def test_the_database_passes_sqlites_integrity_check(db):
    assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert db.execute("INSERT INTO persons_fts(persons_fts) VALUES ('integrity-check')")


def test_an_unsupported_export_version_fails_without_leaving_a_database(tmp_path):
    export = write_fixture_zip(tmp_path / "export.zip", fixture_metadata() | {"export_format_version": "v3.0.0"})
    with pytest.raises(UnsupportedExportVersion, match="v3.0.0"):
        build_database(export, tmp_path / "wca.sqlite", BUILT_AT)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["export.zip"]


def test_a_failed_build_leaves_nothing_behind(tmp_path):
    export = write_fixture_zip(tmp_path / "export.zip", events=tsv(["id", "name"], ["333", "3x3x3 Cube"]))
    with pytest.raises(ExportFormatError, match="rank"):
        build_database(export, tmp_path / "wca.sqlite", BUILT_AT)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["export.zip"]


def test_refuses_to_overwrite_an_existing_file(tmp_path):
    existing = tmp_path / "wca.sqlite"
    existing.write_text("the live database")
    with pytest.raises(FileExistsError):
        build_database(write_fixture_zip(tmp_path / "export.zip"), existing, BUILT_AT)
    assert existing.read_text() == "the live database"


def test_an_export_date_without_a_timezone_is_read_as_utc():
    assert parse_export_date("2026-09-23T00:00:00") == parse_export_date("2026-09-23T00:00:00Z")


def test_reads_the_export_date_as_metadata_json_writes_it():
    # The real export's metadata.json says "2026-09-27 00:00:42 UTC"; the API says
    # "2026-09-27T00:00:42Z" for the same export.
    assert parse_export_date("2026-09-27 00:00:42 UTC") == parse_export_date("2026-09-27T00:00:42Z")
