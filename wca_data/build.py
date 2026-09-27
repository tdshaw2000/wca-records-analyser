"""Builds the trimmed WCA SQLite database from the WCA public results export.

The export's result_attempts table has about 32 million rows, so nothing is held in memory:
tables stream from the zip into SQLite, and attempts are packed into their results by a query
over a scratch database that is deleted afterwards.
"""

import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from wca_data.export import (
    INTEGER,
    NULLABLE_INTEGER,
    TEXT,
    ExportFormatError,
    read_metadata,
    read_table,
)
from wca_data.schema import INDEXES, SCHEMA_VERSION, TABLES

SUPPORTED_EXPORT_MAJOR = "v2"
MICRODEGREES = 1_000_000
BATCH = 50_000


class UnsupportedExportVersion(ExportFormatError):
    """WCA has moved to an export format version this builder doesn't know."""


def export_major(version: str) -> str:
    return str(version).split(".")[0]


def check_export_version(version: str) -> None:
    if export_major(version) != SUPPORTED_EXPORT_MAJOR:
        raise UnsupportedExportVersion(
            f"Export version {version} isn't supported; this builder reads "
            f"{SUPPORTED_EXPORT_MAJOR}.x. Update wca_data before building again."
        )


def utc_timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_export_date(value: str) -> datetime:
    """WCA writes the export date in more than one ISO 8601 shape; this reads any of them."""
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        raise ExportFormatError(f"Can't read the export date {value!r}") from None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


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
        _stage_results(connection, archive)
        _load_results(connection)
        _run_script(connection, INDEXES)
        _write_meta(connection, metadata, built_at)
        connection.execute("COMMIT")
        connection.execute("DETACH DATABASE staging")
        connection.execute("ANALYZE")
    finally:
        connection.close()
