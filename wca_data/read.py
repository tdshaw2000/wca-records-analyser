"""Reading the built WCA database from Python. wca_data/SCHEMA.md describes the file itself.

Open it per request (or per short job) and close it afterwards, so each use sees the latest
nightly build:

    with WcaData.open() as data:
        data.results("2009ZEMD01", "333")

Everything comes back as plain frozen dataclasses, with values as WCA defines them.
"""

import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wca_data.build import database_path, parse_export_date
from wca_data.schema import SCHEMA_VERSION


class DatabaseUnavailable(Exception):
    """There is no readable wca_data database at the configured path."""


class SchemaVersionMismatch(Exception):
    """The database was built for a schema version this library doesn't read."""


@dataclass(frozen=True)
class Metadata:
    schema_version: int
    export_date: datetime
    export_version: str
    built_at: datetime


@dataclass(frozen=True)
class Person:
    wca_id: str
    name: str
    country_id: str


@dataclass(frozen=True)
class Event:
    id: str
    name: str
    rank: int


@dataclass(frozen=True)
class Competition:
    id: str
    name: str
    start_date: str
    city: str
    country_id: str
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class Result:
    """One competitor's round. Times are centiseconds; -1 is DNF, -2 DNS, 0 no result."""

    id: int
    person_id: str
    competition_id: str
    event_id: str
    round_type_id: str
    best: int
    average: int
    attempts: tuple[int, ...]


def _connect_read_only(path: Path) -> sqlite3.Connection:
    # One request may open it in one thread and use it in another, but never at the same time.
    return sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False
    )


def _attempts(packed: str) -> tuple[int, ...]:
    return tuple(int(value) for value in packed.split(",")) if packed else ()


class WcaData:
    """A read-only connection to the database. Use as a context manager, or call close()."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    @classmethod
    def open(
        cls, path: Path | str | None = None, *, environ: Mapping[str, str] | None = None
    ) -> "WcaData":
        """Open the database at path, or else the one WCA_DATA_DB_PATH names.

        Raises DatabaseUnavailable if there is no readable database there, and
        SchemaVersionMismatch if it was built for another schema version.
        """
        if path is None:
            path = database_path(os.environ if environ is None else environ)
        path = Path(path)
        try:
            connection = _connect_read_only(path)
        except sqlite3.Error as error:
            raise DatabaseUnavailable(f"Can't open the WCA database {path}: {error}") from None
        try:
            found = cls._schema_version(connection, path)
        except BaseException:
            connection.close()
            raise
        if found != str(SCHEMA_VERSION):
            connection.close()
            raise SchemaVersionMismatch(
                f"{path} was built for schema version {found}, but this code reads "
                f"version {SCHEMA_VERSION}. Rebuild it or update wca_data."
            )
        return cls(connection)

    @staticmethod
    def _schema_version(connection, path):
        try:
            row = connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
        except sqlite3.Error as error:
            raise DatabaseUnavailable(
                f"{path} isn't a readable WCA database: {error}"
            ) from None
        if row is None:
            raise DatabaseUnavailable(f"{path} has no schema version in its meta table")
        return row[0]

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "WcaData":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def metadata(self) -> Metadata:
        meta = dict(self.connection.execute("SELECT key, value FROM meta"))
        return Metadata(
            schema_version=int(meta["schema_version"]),
            export_date=parse_export_date(meta["export_date"]),
            export_version=meta["export_version"],
            built_at=parse_export_date(meta["built_at"]),
        )

    def person(self, wca_id: str) -> Person | None:
        row = self.connection.execute(
            "SELECT wca_id, name, country_id FROM persons WHERE wca_id = ?", (wca_id,)
        ).fetchone()
        return None if row is None else Person(*row)

    def events(self) -> list[Event]:
        """Every event, in WCA's display order."""
        rows = self.connection.execute("SELECT id, name, rank FROM events ORDER BY rank, id")
        return [Event(*row) for row in rows]

    def competed_events(self, wca_id: str) -> list[Event]:
        """The events a person has any result in, in WCA's display order."""
        rows = self.connection.execute(
            "SELECT id, name, rank FROM events "
            "WHERE id IN (SELECT event_id FROM results WHERE person_id = ?) ORDER BY rank, id",
            (wca_id,),
        )
        return [Event(*row) for row in rows]

    def competitions(self, wca_id: str) -> list[Competition]:
        """The competitions a person has results in, oldest first."""
        rows = self.connection.execute(
            "SELECT id, name, start_date, city, country_id, latitude, longitude "
            "FROM competitions "
            "WHERE id IN (SELECT competition_id FROM results WHERE person_id = ?) "
            "ORDER BY start_date, id",
            (wca_id,),
        )
        return [Competition(*row) for row in rows]

    def results(self, wca_id: str, event_id: str | None = None) -> list[Result]:
        """A person's results, for one event or all of them.

        Ordered by competition date, then competition, then WCA's round order, so a running
        minimum over them follows the order the rounds were competed in.
        """
        sql = (
            "SELECT r.id, r.person_id, r.competition_id, r.event_id, r.round_type_id, "
            "r.best, r.average, r.attempts "
            "FROM results r "
            "LEFT JOIN competitions c ON c.id = r.competition_id "
            "LEFT JOIN round_types t ON t.id = r.round_type_id "
            "WHERE r.person_id = ?"
        )
        params = [wca_id]
        if event_id is not None:
            sql += " AND r.event_id = ?"
            params.append(event_id)
        sql += " ORDER BY c.start_date, r.competition_id, t.rank, r.id"
        return [
            Result(*row[:7], attempts=_attempts(row[7]))
            for row in self.connection.execute(sql, params)
        ]
