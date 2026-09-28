"""The database's tables. wca_data/SCHEMA.md documents them for readers in any language.

Bump SCHEMA_VERSION on any change that could break an existing reader.
"""

SCHEMA_VERSION = 2

TABLES = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE persons (
    wca_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country_id TEXT NOT NULL
);
CREATE VIRTUAL TABLE persons_fts USING fts5(
    name, wca_id, content='persons', tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE competitions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    city TEXT NOT NULL,
    country_id TEXT NOT NULL,
    latitude REAL,
    longitude REAL
);
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rank INTEGER NOT NULL
);
CREATE TABLE round_types (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    final INTEGER NOT NULL
);
CREATE TABLE results (
    id INTEGER PRIMARY KEY,
    person_id TEXT NOT NULL,
    competition_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    round_type_id TEXT NOT NULL,
    best INTEGER NOT NULL,
    average INTEGER NOT NULL,
    attempts TEXT NOT NULL
);
"""

INDEXES = """
CREATE INDEX results_person_event ON results (person_id, event_id);
"""
