"""wca_data/SCHEMA.md is the interface for apps that read the file directly, so it must match."""

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from wca_data.build import build_database
from wca_data.schema import SCHEMA_VERSION

from .export_zip import write_fixture_zip

SCHEMA_DOC = Path(__file__).resolve().parents[2] / "wca_data" / "SCHEMA.md"


def _documented_columns():
    """{table: {column, ...}} from "### `table`" headings and the "| `column` |" rows under them."""
    documented, table = {}, None
    for line in SCHEMA_DOC.read_text("utf-8").splitlines():
        heading = re.match(r"^### `(\w+)`", line)
        if heading:
            table = heading.group(1)
            documented[table] = set()
            continue
        row = re.match(r"^\| `(\w+)` \|", line)
        if row and table:
            documented[table].add(row.group(1))
    return documented


def _built_columns(tmp_path):
    path = tmp_path / "wca.sqlite"
    build_database(write_fixture_zip(tmp_path / "export.zip"), path, datetime(2026, 9, 24, tzinfo=UTC))
    with sqlite3.connect(path) as connection:
        tables = [
            name for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "AND name NOT LIKE 'persons_fts_%' AND name NOT LIKE 'persons_cjk_%'"
            )
        ]
        return {
            table: {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            for table in tables
        }


def test_schema_md_documents_every_table_and_column_the_build_creates(tmp_path):
    assert _documented_columns() == _built_columns(tmp_path)


def test_schema_md_states_the_current_schema_version():
    assert f"Schema version: **{SCHEMA_VERSION}**" in SCHEMA_DOC.read_text("utf-8")
