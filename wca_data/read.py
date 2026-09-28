"""Reading the built WCA database from Python. wca_data/SCHEMA.md describes the file itself.

Open it per request (or per short job) and close it afterwards, so each use sees the latest
nightly build:

    with WcaData.open() as data:
        data.results("2009ZEMD01", "333")

Everything comes back as plain frozen dataclasses, with values as WCA defines them.
"""

import os
import sqlite3
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wca_data.export import parse_export_date
from wca_data.schema import CJK_CHARACTER, SCHEMA_VERSION, spaced_cjk_characters


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


SEARCH_LIMIT = 25
# Past these, a search query is ignored, so no query can make a search arbitrarily expensive.
MAX_QUERY_CHARACTERS = 100
MAX_QUERY_WORDS = 10


def _query_words(text: str) -> list[str]:
    # Control characters (NUL above all, which ends an FTS5 query early) are dropped.
    text = "".join(
        char for char in text[:MAX_QUERY_CHARACTERS]
        if char.isspace() or unicodedata.category(char) != "Cc"
    )
    return text.split()[:MAX_QUERY_WORDS]


def _quoted(text: str) -> str:
    return '"' + text.replace('"', '""') + '"'


def _search_queries(text: str) -> tuple[str | None, str | None]:
    """FTS5 queries for persons_fts and persons_cjk from what the user typed.

    Each CJK run becomes a phrase of its characters for persons_cjk; every other word must
    start a word of the name or WCA ID in persons_fts. Everything is quoted, so nothing the
    user types is read as FTS5 syntax. Words with no letters or digits are dropped, since
    the index has no tokens for them. None for an index with nothing to look for.
    """
    words, phrases = [], []
    for word in _query_words(text):
        characters = spaced_cjk_characters(word)
        if any(char.isalnum() for char in characters):  # not punctuation such as ・ alone
            phrases.append(_quoted(characters))
        words += [
            part for part in CJK_CHARACTER.sub(" ", word).split()
            if any(char.isalnum() for char in part)
        ]
    word_query = " ".join(_quoted(word) + "*" for word in words) or None
    return word_query, " ".join(phrases) or None


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

        Raises DatabaseUnavailable if neither is given or there is no readable database
        there, and SchemaVersionMismatch if it was built for another schema version.
        """
        if path is None:
            path = (os.environ if environ is None else environ).get("WCA_DATA_DB_PATH")
            if not path:
                raise DatabaseUnavailable(
                    "Set WCA_DATA_DB_PATH to the WCA database's path, or pass the path"
                )
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

    def search_persons(self, text: str, limit: int = SEARCH_LIMIT) -> list[Person]:
        """Persons with a word of their name or WCA ID starting with every word of text.

        Chinese, Japanese and Korean characters match anywhere in the name, in the order
        typed, since those names have no spaces between words. Case and accents don't
        matter. Only the first MAX_QUERY_WORDS words of the first MAX_QUERY_CHARACTERS
        characters are read. A person whose whole WCA ID was typed comes first, then the
        rest by name and WCA ID; at most limit of them.
        """
        word_query, cjk_query = _search_queries(text)
        if (word_query is None and cjk_query is None) or limit < 1:
            return []
        conditions, params = [], []
        if word_query is not None:
            conditions.append("rowid IN (SELECT rowid FROM persons_fts WHERE persons_fts MATCH ?)")
            params.append(word_query)
        if cjk_query is not None:
            conditions.append("rowid IN (SELECT rowid FROM persons_cjk WHERE persons_cjk MATCH ?)")
            params.append(cjk_query)
        # Someone who types a whole WCA ID wants that person first.
        typed_ids = [word.upper() for word in _query_words(text)]
        rows = self.connection.execute(
            "SELECT wca_id, name, country_id FROM persons WHERE "
            + " AND ".join(conditions)
            + f" ORDER BY wca_id IN ({', '.join('?' * len(typed_ids))}) DESC, name, wca_id"
            + " LIMIT ?",
            (*params, *typed_ids, limit),
        )
        return [Person(*row) for row in rows]
