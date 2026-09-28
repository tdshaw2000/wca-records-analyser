import fcntl
import os
import shutil
import sqlite3
from datetime import UTC, datetime

import pytest

from wca_data.build import (
    EXPORT_INFO_URL,
    BuildAlreadyRunning,
    SanityCheckFailed,
    UnsupportedExportVersion,
    database_path,
    main,
    run,
)
from wca_data.schema import SCHEMA_VERSION

from .export_zip import fixture_tables, tsv, write_fixture_zip

NOW = datetime(2026, 9, 24, 3, 15, tzinfo=UTC)
FIRST_EXPORT = "2026-09-23T00:00:00Z"
NEXT_EXPORT = "2026-09-24T00:00:00Z"
TSV_URL = "https://www.worldcubeassociation.org/export/results/v2/tsv"
RESULT_HEADER = ["id", "competition_id", "round_type_id", "event_id", "person_id", "best", "average"]


class FakeWca:
    """Stands in for the export API and its download, counting what the job asks for."""

    def __init__(self, tmp_path, export_date=FIRST_EXPORT, version="v2.0.2", **tables):
        self.tmp_path = tmp_path
        self.downloads = 0
        self.fetched = []
        self.publish(export_date, version, **tables)

    def publish(self, export_date, version="v2.0.2", size=None, **tables):
        metadata = {"export_format_version": version, "export_date": export_date}
        self.zip = write_fixture_zip(self.tmp_path / f"published-{export_date[:10]}.zip", metadata, **tables)
        self.info = {
            "export_date": export_date,
            "export_version": version,
            "tsv_url": TSV_URL,
            "tsv_filesize_bytes": size if size is not None else self.zip.stat().st_size,
        }

    def fetch_json(self, url):
        self.fetched.append(url)
        return dict(self.info)

    def download(self, url, destination):
        assert url == TSV_URL
        self.downloads += 1
        shutil.copyfile(self.zip, destination)


class Pings:
    def __init__(self):
        self.count = 0

    def __call__(self):
        self.count += 1


@pytest.fixture
def data_dir(tmp_path):
    folder = tmp_path / "srv-wca-data"
    folder.mkdir()
    return folder


def _run(wca, data_dir, pings=None):
    return run(
        data_dir / "wca.sqlite",
        fetch_json=wca.fetch_json,
        download=wca.download,
        now=lambda: NOW,
        ping=pings or Pings(),
    )


def _meta(path, key="export_date"):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()[0]


def _files(folder):
    return sorted(path.name for path in folder.iterdir())


def _results_without(*ids):
    """The fixture's results table with some rows left out."""
    lines = fixture_tables()["results"].splitlines(keepends=True)
    return "".join(line for line in lines if line.split("\t")[0] not in {str(i) for i in ids})


def _attempts_without(*ids):
    lines = fixture_tables()["result_attempts"].splitlines(keepends=True)
    return "".join(line for line in lines if line.rstrip("\n").split("\t")[2] not in {str(i) for i in ids})


def test_the_first_run_builds_the_database_and_pings(tmp_path, data_dir):
    pings = Pings()
    wca = FakeWca(tmp_path)
    assert _run(wca, data_dir, pings) == "built"
    assert wca.fetched == [EXPORT_INFO_URL]
    assert _meta(data_dir / "wca.sqlite") == FIRST_EXPORT
    assert _files(data_dir) == ["wca.sqlite"]
    assert pings.count == 1


def test_an_unchanged_export_date_stops_quietly_without_downloading(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    before = (data_dir / "wca.sqlite").stat()
    wca.info["export_date"] = "2026-09-23T00:00:00.000+00:00"  # same moment, other spelling
    pings = Pings()
    assert _run(wca, data_dir, pings) == "unchanged"
    assert wca.downloads == 1
    assert (data_dir / "wca.sqlite").stat().st_ino == before.st_ino
    assert pings.count == 1


def test_a_new_export_replaces_the_database_and_keeps_the_previous_one(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    wca.publish(NEXT_EXPORT)
    assert _run(wca, data_dir) == "built"
    assert _meta(data_dir / "wca.sqlite") == NEXT_EXPORT
    assert _meta(data_dir / "wca.sqlite.prev") == FIRST_EXPORT
    assert _files(data_dir) == ["wca.sqlite", "wca.sqlite.prev"]


def test_a_reader_holding_the_old_file_open_keeps_reading_it_after_the_swap(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    reader = sqlite3.connect((data_dir / "wca.sqlite").as_uri() + "?mode=ro", uri=True)
    wca.publish(NEXT_EXPORT)
    _run(wca, data_dir)
    assert reader.execute("SELECT value FROM meta WHERE key = 'export_date'").fetchone() == (FIRST_EXPORT,)
    reader.close()


def test_an_unsupported_export_version_fails_before_downloading(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    wca.publish(NEXT_EXPORT, version="v3.0.0")
    pings = Pings()
    with pytest.raises(UnsupportedExportVersion, match="v3.0.0"):
        _run(wca, data_dir, pings)
    assert wca.downloads == 1
    assert _meta(data_dir / "wca.sqlite") == FIRST_EXPORT
    assert pings.count == 0


def _assert_failed_run_changed_nothing(wca, data_dir, error, match):
    """Run against an already-built data_dir and check the failure changed nothing there."""
    live = (data_dir / "wca.sqlite").read_bytes()
    pings = Pings()
    with pytest.raises(error, match=match):
        _run(wca, data_dir, pings)
    assert (data_dir / "wca.sqlite").read_bytes() == live
    assert _files(data_dir) == ["wca.sqlite"]
    assert pings.count == 0


def test_a_failed_download_leaves_the_live_database_and_no_scratch_files(tmp_path, data_dir):
    wca = FakeWca(tmp_path)

    def broken_download(url, destination):
        destination.write_bytes(b"half a zip")
        raise OSError("connection reset")

    _run(wca, data_dir)
    wca.publish(NEXT_EXPORT)
    wca.download = broken_download
    _assert_failed_run_changed_nothing(wca, data_dir, OSError, "connection reset")


def test_a_download_of_the_wrong_size_is_rejected(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    wca.publish(NEXT_EXPORT, size=123)
    _assert_failed_run_changed_nothing(wca, data_dir, SanityCheckFailed, "123")


def test_a_corrupt_zip_is_rejected(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    wca.publish(NEXT_EXPORT)
    wca.zip.write_bytes(b"not a zip at all")
    wca.info["tsv_filesize_bytes"] = wca.zip.stat().st_size
    _assert_failed_run_changed_nothing(wca, data_dir, Exception, "zip")


def test_losing_more_than_one_percent_of_any_table_fails_the_sanity_check(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    wca.publish(NEXT_EXPORT, results=_results_without(105), result_attempts=_attempts_without(105))
    _assert_failed_run_changed_nothing(wca, data_dir, SanityCheckFailed, "results")


def test_an_export_with_no_round_types_fails_the_sanity_check(tmp_path, data_dir):
    # Without them, readers would order rounds by result id and nothing would say so.
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    header = fixture_tables()["round_types"].splitlines()[0]
    wca.publish(NEXT_EXPORT, round_types=header + "\n")
    _assert_failed_run_changed_nothing(wca, data_dir, SanityCheckFailed, "round_types")


def test_a_table_growing_by_half_again_fails_the_sanity_check(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    extra = [[900 + i, "ParisOpen2016", "1", "222", "2015MART01", 500, 600] for i in range(4)]
    kept = fixture_tables()["results"]
    header = kept.splitlines()[0].split("\t")
    rows = [dict(zip(RESULT_HEADER, row)) for row in extra]
    added = "".join("\t".join(str(row.get(column, "NULL")) for column in header) + "\n" for row in rows)
    wca.publish(NEXT_EXPORT, results=kept + added)
    _assert_failed_run_changed_nothing(wca, data_dir, SanityCheckFailed, "results")


def test_normal_growth_passes_the_sanity_check(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    kept = fixture_tables()["results"]
    header = kept.splitlines()[0].split("\t")
    row = dict(zip(RESULT_HEADER, [900, "ParisOpen2016", "1", "222", "2015MART01", 500, 600]))
    wca.publish(NEXT_EXPORT, results=kept + "\t".join(str(row.get(c, "NULL")) for c in header) + "\n")
    assert _run(wca, data_dir) == "built"


def test_the_known_competitors_latest_result_must_survive_unchanged(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    changed = fixture_tables()["result_attempts"].replace("623\t1\t103", "624\t1\t103")
    wca.publish(NEXT_EXPORT, result_attempts=changed)
    _assert_failed_run_changed_nothing(wca, data_dir, SanityCheckFailed, "2009ZEMD01")


def test_a_first_build_without_the_known_competitor_fails(tmp_path, data_dir):
    persons = tsv(["name", "wca_id", "sub_id", "country_id"], ["Max Park", "2012PARK03", 1, "USA"])
    wca = FakeWca(tmp_path, persons=persons)
    with pytest.raises(SanityCheckFailed, match="2009ZEMD01"):
        _run(wca, data_dir)
    assert _files(data_dir) == []


def test_an_unreadable_live_file_is_rebuilt_and_kept_as_previous(tmp_path, data_dir):
    (data_dir / "wca.sqlite").write_bytes(b"not a database")
    assert _run(FakeWca(tmp_path), data_dir) == "built"
    assert _meta(data_dir / "wca.sqlite") == FIRST_EXPORT
    assert (data_dir / "wca.sqlite.prev").read_bytes() == b"not a database"


def test_leftovers_from_a_killed_run_are_cleared_first(tmp_path, data_dir):
    (data_dir / ".wca-build-abc").mkdir()
    (data_dir / ".wca-build-abc" / "staging.sqlite").write_bytes(b"x")
    (data_dir / "wca.sqlite.new").write_bytes(b"half built")
    assert _run(FakeWca(tmp_path), data_dir) == "built"
    assert _files(data_dir) == ["wca.sqlite"]


def test_a_second_run_while_one_is_going_refuses_to_start(tmp_path, data_dir):
    folder = os.open(data_dir, os.O_RDONLY)
    try:
        fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BuildAlreadyRunning):
            _run(FakeWca(tmp_path), data_dir)
    finally:
        os.close(folder)


def test_the_database_path_comes_from_the_environment_with_the_vm_default():
    assert str(database_path({})) == "/srv/wca-data/wca.sqlite"
    assert str(database_path({"WCA_DATA_DB_PATH": "/data/other.sqlite"})) == "/data/other.sqlite"


def test_main_builds_where_the_environment_says_and_pings_the_monitor(tmp_path, data_dir, capsys):
    wca = FakeWca(tmp_path)
    opened = []
    environ = {"WCA_DATA_DB_PATH": str(data_dir / "wca.sqlite"), "WCA_DATA_PING_URL": "https://hc.example/ping/abc"}
    code = main(environ, fetch_json=wca.fetch_json, download=wca.download, open_url=opened.append)
    assert code == 0
    assert opened == ["https://hc.example/ping/abc"]
    assert "built" in capsys.readouterr().out


def test_main_reports_a_failure_and_exits_non_zero_without_pinging(tmp_path, data_dir, capsys):
    wca = FakeWca(tmp_path, version="v3.0.0")
    opened = []
    environ = {"WCA_DATA_DB_PATH": str(data_dir / "wca.sqlite"), "WCA_DATA_PING_URL": "https://hc.example/ping/abc"}
    code = main(environ, fetch_json=wca.fetch_json, download=wca.download, open_url=opened.append)
    assert code == 1
    assert opened == []
    assert "v3.0.0" in capsys.readouterr().err


def test_main_without_a_ping_url_pings_nothing(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    opened = []
    code = main({"WCA_DATA_DB_PATH": str(data_dir / "wca.sqlite")}, fetch_json=wca.fetch_json, download=wca.download, open_url=opened.append)
    assert code == 0
    assert opened == []


def test_a_failed_monitor_ping_does_not_fail_a_good_build(tmp_path, data_dir, capsys):
    wca = FakeWca(tmp_path)

    def monitor_down(url):
        raise OSError("monitor unreachable")

    environ = {"WCA_DATA_DB_PATH": str(data_dir / "wca.sqlite"), "WCA_DATA_PING_URL": "https://hc.example/ping/abc"}
    code = main(environ, fetch_json=wca.fetch_json, download=wca.download, open_url=monitor_down)
    assert code == 0
    assert _meta(data_dir / "wca.sqlite") == FIRST_EXPORT
    assert "monitor unreachable" in capsys.readouterr().err


def test_a_killed_download_and_a_half_made_prev_link_are_cleared_first(tmp_path, data_dir):
    (data_dir / ".wca-download-xyz").mkdir()
    (data_dir / ".wca-download-xyz" / "export.zip").write_bytes(b"most of an export")
    (data_dir / "wca.sqlite.prev.tmp").write_bytes(b"old database")
    assert _run(FakeWca(tmp_path), data_dir) == "built"
    assert _files(data_dir) == ["wca.sqlite"]


def test_a_live_export_date_that_cant_be_read_is_rebuilt(tmp_path, data_dir):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    with sqlite3.connect(data_dir / "wca.sqlite") as connection:
        connection.execute("UPDATE meta SET value = 'not a date' WHERE key = 'export_date'")
    connection.close()
    assert _run(wca, data_dir) == "built"
    assert _meta(data_dir / "wca.sqlite") == FIRST_EXPORT


def test_a_live_database_from_an_older_schema_is_rebuilt_from_the_same_export(tmp_path, data_dir, monkeypatch):
    wca = FakeWca(tmp_path)
    _run(wca, data_dir)
    newer = SCHEMA_VERSION + 1
    monkeypatch.setattr("wca_data.build.SCHEMA_VERSION", newer)
    pings = Pings()
    assert _run(wca, data_dir, pings) == "built"
    assert _meta(data_dir / "wca.sqlite", "schema_version") == str(newer)
    assert _meta(data_dir / "wca.sqlite", "export_date") == FIRST_EXPORT
    assert pings.count == 1
