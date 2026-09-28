"""The database's tables. wca_data/SCHEMA.md documents them for readers in any language.

Bump SCHEMA_VERSION on any change that could break an existing reader.
"""

import re

SCHEMA_VERSION = 2

# Scripts that write names without spaces between words: Han ideographs (with the iteration
# marks 々 and 〻, 〆 and the ideographic zero 〇), kana and Hangul. persons_cjk indexes these
# characters one by one, so any run of them can be searched for.
CJK_CHARACTER = re.compile(
    "[\u1100-\u11ff\u3005-\u3007\u303b\u3040-\u30ff\u3130-\u318f\u31f0-\u31ff"
    "\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff\uff66-\uff9f\U00020000-\U0003134f]"
)


def spaced_cjk_characters(text: str) -> str:
    """text's CJK characters, in order, one space between each: "王小明" -> "王 小 明"."""
    return " ".join(CJK_CHARACTER.findall(text))


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
CREATE VIRTUAL TABLE persons_cjk USING fts5(
    characters, content='', tokenize='unicode61'
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
