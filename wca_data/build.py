"""Builds the trimmed WCA SQLite database from the WCA public results export.

Run nightly as `python -m wca_data.build`. It builds only when WCA has published a new export
or the live database was built for another schema version. It checks the new database against
the live one and renames it into place, keeping the old one as <name>.prev. Anything that goes wrong leaves the live database as it was. Settings come
from the environment: WCA_DATA_DB_PATH (default /srv/wca-data/wca.sqlite) and, optionally,
WCA_DATA_PING_URL, a missed-build monitor that is pinged after every successful run.

The export's result_attempts table has about 32 million rows, so nothing is held in memory:
tables stream from the zip into SQLite, and attempts are packed into their results by a query
over a scratch database that is deleted afterwards.
"""

import fcntl
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from wca_data.export import (
    INTEGER,
    NULLABLE_INTEGER,
    TEXT,
    ExportFormatError,
    parse_export_date,
    read_metadata,
    read_table,
    utc_timestamp,
)
from wca_data.schema import INDEXES, SCHEMA_VERSION, TABLES, spaced_cjk_characters

EXPORT_INFO_URL = "https://www.worldcubeassociation.org/api/v0/export/public"
DEFAULT_DB_PATH = "/srv/wca-data/wca.sqlite"
USER_AGENT = "wca-records-analyser data build (+https://github.com/tdshaw2000/wca-records-analyser)"
TIMEOUT_SECONDS = 60
SUPPORTED_EXPORT_MAJOR = "v2"
# A competitor and event whose latest result is checked on every build: Feliks Zemdegs' 3x3,
# the known-good check in docs/shared-backend-tradeoffs.md.
SENTINEL_PERSON = "2009ZEMD01"
SENTINEL_EVENT = "333"
# A new build must keep this share of each table's rows, and grow it by less than GROWTH_LIMIT.
MIN_KEPT = 0.99
GROWTH_LIMIT = 1.5
COUNTED_TABLES = ("persons", "competitions", "events", "round_types", "results")
SCRATCH_PREFIXES = (".wca-build-", ".wca-download-")
MICRODEGREES = 1_000_000
BATCH = 50_000


class UnsupportedExportVersion(ExportFormatError):
    """WCA has moved to an export format version this builder doesn't know."""


class SanityCheckFailed(Exception):
    """The new database doesn't look like a good build, so it isn't swapped in."""


class BuildAlreadyRunning(Exception):
    """Another build holds the data directory's lock."""


def export_major(version: str) -> str:
    return str(version).split(".")[0]


def check_export_version(version: str) -> None:
    if export_major(version) != SUPPORTED_EXPORT_MAJOR:
        raise UnsupportedExportVersion(
            f"Export version {version} isn't supported; this builder reads "
            f"{SUPPORTED_EXPORT_MAJOR}.x. Update wca_data before building again."
        )


class _PackAttempts:
    """SQL aggregate: (attempt_number, value) rows, in any order, to "v1,v2,...".

    Attempt n goes in position n. A missing attempt number is written as 0, the WCA's "no
    result", so every value stays in its position.
    """

    def __init__(self):
        self.values = {}

    def step(self, attempt_number, value):
        if attempt_number is not None:
            self.values[attempt_number] = value

    def finalize(self):
        if not self.values:
            return ""
        return ",".join(str(self.values.get(n, 0)) for n in range(1, max(self.values) + 1))


def _run_script(connection, script):
    """Like executescript, but inside the current transaction (executescript commits it)."""
    for statement in script.split(";"):
        if statement.strip():
            connection.execute(statement)


def _insert(connection, sql, rows):
    batch = []
    for row in rows:
        batch.append(row)
        if len(batch) >= BATCH:
            connection.executemany(sql, batch)
            batch.clear()
    if batch:
        connection.executemany(sql, batch)


def _load_persons(connection, archive):
    columns = {"wca_id": TEXT, "sub_id": INTEGER, "name": TEXT, "country_id": TEXT}
    rows = read_table(archive, "persons", columns)
    _insert(
        connection,
        "INSERT INTO persons (wca_id, name, country_id) VALUES (?, ?, ?)",
        ((r["wca_id"], r["name"], r["country_id"]) for r in rows if r["sub_id"] == 1),
    )
    connection.execute("INSERT INTO persons_fts (persons_fts) VALUES ('rebuild')")
    _insert(
        connection,
        "INSERT INTO persons_cjk (rowid, characters) VALUES (?, ?)",
        (
            (rowid, characters)
            for rowid, name in connection.execute("SELECT rowid, name FROM persons")
            if (characters := spaced_cjk_characters(name))
        ),
    )


def _degrees(microdegrees):
    return None if microdegrees is None else microdegrees / MICRODEGREES


def _load_competitions(connection, archive):
    columns = {
        "id": TEXT,
        "name": TEXT,
        "city_name": TEXT,
        "country_id": TEXT,
        "year": INTEGER,
        "month": INTEGER,
        "day": INTEGER,
        "latitude_microdegrees": NULLABLE_INTEGER,
        "longitude_microdegrees": NULLABLE_INTEGER,
    }
    _insert(
        connection,
        "INSERT INTO competitions (id, name, start_date, city, country_id, latitude, longitude) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            (
                r["id"],
                r["name"],
                f"{r['year']:04d}-{r['month']:02d}-{r['day']:02d}",
                r["city_name"],
                r["country_id"],
                _degrees(r["latitude_microdegrees"]),
                _degrees(r["longitude_microdegrees"]),
            )
            for r in read_table(archive, "competitions", columns)
        ),
    )


def _load_events(connection, archive):
    columns = {"id": TEXT, "name": TEXT, "rank": INTEGER}
    _insert(
        connection,
        "INSERT INTO events (id, name, rank) VALUES (?, ?, ?)",
        ((r["id"], r["name"], r["rank"]) for r in read_table(archive, "events", columns)),
    )


def _load_round_types(connection, archive):
    columns = {"id": TEXT, "name": TEXT, "rank": INTEGER, "final": INTEGER}
    _insert(
        connection,
        "INSERT INTO round_types (id, name, rank, final) VALUES (?, ?, ?, ?)",
        (tuple(r.values()) for r in read_table(archive, "round_types", columns)),
    )


def _stage_results(connection, archive):
    """Results and attempts into the scratch database, keyed so they can be merged in order."""
    _run_script(
        connection,
        """
        CREATE TABLE staging.results (
            id INTEGER PRIMARY KEY, person_id TEXT NOT NULL, competition_id TEXT NOT NULL,
            event_id TEXT NOT NULL, round_type_id TEXT NOT NULL, best INTEGER NOT NULL,
            average INTEGER NOT NULL
        );
        CREATE TABLE staging.attempts (
            result_id INTEGER NOT NULL, attempt_number INTEGER NOT NULL, value INTEGER NOT NULL,
            PRIMARY KEY (result_id, attempt_number)
        ) WITHOUT ROWID;
        """
    )
    columns = {
        "id": INTEGER,
        "person_id": TEXT,
        "competition_id": TEXT,
        "event_id": TEXT,
        "round_type_id": TEXT,
        "best": INTEGER,
        "average": INTEGER,
    }
    try:
        _insert(
            connection,
            "INSERT INTO staging.results VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tuple(r.values()) for r in read_table(archive, "results", columns)),
        )
    except sqlite3.IntegrityError as error:
        raise ExportFormatError(f"The results table repeats a result id ({error})") from None
    columns = {"result_id": INTEGER, "attempt_number": INTEGER, "value": INTEGER}
    try:
        _insert(
            connection,
            "INSERT INTO staging.attempts VALUES (?, ?, ?)",
            (tuple(r.values()) for r in read_table(archive, "result_attempts", columns)),
        )
    except sqlite3.IntegrityError as error:
        raise ExportFormatError(
            f"The result_attempts table repeats an attempt of a result ({error})"
        ) from None
    orphans = connection.execute(
        "SELECT count(*) FROM staging.attempts a "
        "WHERE NOT EXISTS (SELECT 1 FROM staging.results r WHERE r.id = a.result_id)"
    ).fetchone()[0]
    if orphans:
        raise ExportFormatError(f"{orphans} result_attempts rows belong to no result")


def _load_results(connection):
    connection.create_aggregate("pack_attempts", 2, _PackAttempts)
    connection.execute(
        """
        INSERT INTO results
            (id, person_id, competition_id, event_id, round_type_id, best, average, attempts)
        SELECT r.id, r.person_id, r.competition_id, r.event_id, r.round_type_id, r.best,
               r.average, pack_attempts(a.attempt_number, a.value)
        FROM staging.results r LEFT JOIN staging.attempts a ON a.result_id = r.id
        GROUP BY r.id
        ORDER BY r.id
        """
    )


def _write_meta(connection, metadata, built_at):
    meta = {
        "schema_version": str(SCHEMA_VERSION),
        "export_date": utc_timestamp(parse_export_date(metadata.get("export_date"))),
        "export_version": metadata["export_format_version"],
        "built_at": utc_timestamp(built_at),
    }
    connection.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", meta.items())


def build_database(export_zip: Path, db_path: Path, built_at: datetime) -> None:
    """Build a new database at db_path from an export zip. db_path must not exist yet.

    On any failure db_path and the scratch files are removed, so a failed build leaves
    nothing behind.
    """
    db_path = Path(db_path)
    if db_path.exists():
        raise FileExistsError(f"{db_path} already exists; build into a new file")
    try:
        with zipfile.ZipFile(export_zip) as archive:
            metadata = read_metadata(archive)
            check_export_version(metadata.get("export_format_version", "missing"))
            with tempfile.TemporaryDirectory(dir=db_path.parent, prefix=".wca-build-") as scratch:
                _build(archive, metadata, db_path, Path(scratch) / "staging.sqlite", built_at)
    except BaseException:
        db_path.unlink(missing_ok=True)
        raise


def _build(archive, metadata, db_path, staging_path, built_at):
    # A half-built file is never used (it is deleted, or renamed into place only when done),
    # so no journal and no fsyncs while building.
    connection = sqlite3.connect(db_path, isolation_level=None)
    try:
        connection.execute("ATTACH DATABASE ? AS staging", (str(staging_path),))
        for schema in ("main", "staging"):
            connection.execute(f"PRAGMA {schema}.journal_mode = OFF")
            connection.execute(f"PRAGMA {schema}.synchronous = OFF")
        connection.execute("BEGIN")
        _run_script(connection, TABLES)
        _load_persons(connection, archive)
        _load_competitions(connection, archive)
        _load_events(connection, archive)
        _load_round_types(connection, archive)
        _stage_results(connection, archive)
        _load_results(connection)
        _run_script(connection, INDEXES)
        _write_meta(connection, metadata, built_at)
        connection.execute("COMMIT")
        connection.execute("DETACH DATABASE staging")
        connection.execute("ANALYZE")
    finally:
        connection.close()


# --- the nightly job ---


def database_path(environ: Mapping[str, str]) -> Path:
    return Path(environ.get("WCA_DATA_DB_PATH") or DEFAULT_DB_PATH)


def _open_read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def _live_is_current(db_path: Path, export_date: datetime) -> bool:
    """True if the live database was built from this export with the current schema.

    A missing or unreadable database, or one built for another schema version, is not.
    """
    if not db_path.exists():
        return False
    try:
        with closing(_open_read_only(db_path)) as connection:
            meta = dict(connection.execute("SELECT key, value FROM meta"))
        return (
            meta.get("schema_version") == str(SCHEMA_VERSION)
            and parse_export_date(meta.get("export_date")) == export_date
        )
    except (sqlite3.Error, ExportFormatError):
        return False


def _counts(connection) -> dict[str, int]:
    """Row counts of the counted tables this database has. An older schema may lack some."""
    present = {name for (name,) in connection.execute("SELECT name FROM sqlite_master")}
    return {
        table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in COUNTED_TABLES
        if table in present
    }


def _latest_result(connection, person_id):
    return connection.execute(
        "SELECT r.id, r.competition_id, r.event_id, r.best, r.average, r.attempts "
        "FROM results r JOIN competitions c ON c.id = r.competition_id "
        "WHERE r.person_id = ? AND r.event_id = ? ORDER BY c.start_date DESC, r.id DESC LIMIT 1",
        (person_id, SENTINEL_EVENT),
    ).fetchone()


def _result(connection, result_id):
    return connection.execute(
        "SELECT id, competition_id, event_id, best, average, attempts FROM results WHERE id = ?",
        (result_id,),
    ).fetchone()


def check_sanity(new_path: Path, live_path: Path, sentinel: str = SENTINEL_PERSON) -> None:
    """Raise SanityCheckFailed unless the new database looks like a good build.

    Every table has rows, and the sentinel competitor is there with a 3x3 result. Against a readable live
    database: no table loses more than 1% of its rows or grows by half again, and the
    sentinel's latest live result is still there, unchanged.
    """
    with closing(_open_read_only(new_path)) as new:
        counts = _counts(new)
        empty = [table for table in COUNTED_TABLES if counts.get(table, 0) == 0]
        if empty:
            raise SanityCheckFailed(f"The new build has no rows in {', '.join(empty)}")
        known = new.execute("SELECT 1 FROM persons WHERE wca_id = ?", (sentinel,)).fetchone()
        if known is None or _latest_result(new, sentinel) is None:
            raise SanityCheckFailed(f"The new build is missing {sentinel} or their 3x3 results")
        try:
            with closing(_open_read_only(live_path)) as live:
                live_counts = _counts(live)
                live_latest = _latest_result(live, sentinel)
        except sqlite3.Error:
            return  # nothing readable to compare with
        for table, before in live_counts.items():
            after = counts[table]
            if after < before * MIN_KEPT or (before and after > before * GROWTH_LIMIT):
                raise SanityCheckFailed(
                    f"{table} would go from {before} rows to {after}, outside the expected range"
                )
        if live_latest is not None and _result(new, live_latest[0]) != live_latest:
            raise SanityCheckFailed(
                f"{sentinel}'s latest result {live_latest} is missing or changed in the new build"
            )


def _fsync_directory(folder: Path) -> None:
    descriptor = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def swap_into_place(new_path: Path, live_path: Path) -> None:
    """Rename the new database over the live one, keeping the live one as <name>.prev.

    The live name always points at a whole database: the old file is hard-linked to .prev
    first, then the new file is renamed over the live name in one atomic step. Readers that
    already have the old file open keep reading it.
    """
    with open(new_path, "rb+") as new_file:
        os.fsync(new_file.fileno())
    if live_path.exists():
        previous = live_path.with_name(live_path.name + ".prev")
        linking = live_path.with_name(live_path.name + ".prev.tmp")
        linking.unlink(missing_ok=True)
        os.link(live_path, linking)
        os.replace(linking, previous)
    os.replace(new_path, live_path)
    _fsync_directory(live_path.parent)


def _clear_leftovers(db_path: Path) -> None:
    """Remove scratch files a killed run may have left. Only called while holding the lock."""
    for path in db_path.parent.iterdir():
        if path.is_dir() and path.name.startswith(SCRATCH_PREFIXES):
            shutil.rmtree(path)
    for suffix in (".new", ".prev.tmp"):
        db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)


class _DirectoryLock:
    """An exclusive flock on the data directory, so two builds never run at once."""

    def __init__(self, folder: Path):
        self.folder = folder

    def __enter__(self):
        self.descriptor = os.open(self.folder, os.O_RDONLY)
        try:
            fcntl.flock(self.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.descriptor)
            raise BuildAlreadyRunning(f"Another build is running in {self.folder}") from None
        return self

    def __exit__(self, *exc_info):
        os.close(self.descriptor)  # closing releases the lock


def run(
    db_path: Path,
    *,
    fetch_json: Callable[[str], dict],
    download: Callable[[str, Path], None],
    now: Callable[[], datetime],
    ping: Callable[[], None],
) -> str:
    """One nightly run. Returns "unchanged" or "built"; raises if anything fails.

    ping is called only when the run succeeds, whether or not there was a new export.
    """
    db_path = Path(db_path)
    with _DirectoryLock(db_path.parent):
        _clear_leftovers(db_path)
        info = fetch_json(EXPORT_INFO_URL)
        if _live_is_current(db_path, parse_export_date(info["export_date"])):
            ping()
            return "unchanged"
        check_export_version(info["export_version"])
        new_path = db_path.with_name(db_path.name + ".new")
        try:
            with tempfile.TemporaryDirectory(dir=db_path.parent, prefix=".wca-download-") as work:
                export_zip = Path(work) / "export.zip"
                download(info["tsv_url"], export_zip)
                expected = info.get("tsv_filesize_bytes")
                if expected is not None and export_zip.stat().st_size != expected:
                    raise SanityCheckFailed(
                        f"Downloaded {export_zip.stat().st_size} bytes, WCA says {expected}"
                    )
                build_database(export_zip, new_path, now())
            check_sanity(new_path, db_path)
            swap_into_place(new_path, db_path)
        finally:
            new_path.unlink(missing_ok=True)
    ping()
    return "built"


def _request(url: str):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=TIMEOUT_SECONDS
    )


def fetch_json(url: str) -> dict:
    with _request(url) as response:
        return json.load(response)


def download(url: str, destination: Path) -> None:
    with _request(url) as response, open(destination, "wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)


def open_url(url: str) -> None:
    with _request(url) as response:
        response.read()


def main(
    environ: Mapping[str, str] | None = None,
    *,
    fetch_json: Callable[[str], dict] = fetch_json,
    download: Callable[[str, Path], None] = download,
    open_url: Callable[[str], None] = open_url,
) -> int:
    environ = os.environ if environ is None else environ
    db_path = database_path(environ)
    ping_url = environ.get("WCA_DATA_PING_URL")

    def ping():
        if not ping_url:
            return
        try:
            open_url(ping_url)
        except OSError as error:  # a monitor outage mustn't fail a good build
            print(f"wca_data build: couldn't ping the monitor: {error}", file=sys.stderr)

    try:
        outcome = run(
            db_path,
            fetch_json=fetch_json,
            download=download,
            now=lambda: datetime.now(UTC),
            ping=ping,
        )
    except Exception as error:  # noqa: BLE001 - report every failure, keep the old database
        print(f"wca_data build failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"wca_data build: {outcome} ({db_path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
