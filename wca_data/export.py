"""Reading the WCA public results export (TSV zip, format v2) without unpacking it.

The zip holds metadata.json, README.md and one WCA_export_<table>.tsv per table. WCA writes
each table with `mysql --batch`: a header line, then one line per row, fields separated by
tabs. Tab, newline, backslash and NUL inside a value are escaped as \\t, \\n, \\\\ and \\0, and
SQL NULL is written as the bare word NULL, which only a nullable column should read as None.
Columns are always found by header name, never by position.
"""

import json
import re
import zipfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

METADATA_FILE = "metadata.json"
ESCAPES = {"t": "\t", "n": "\n", "\\": "\\", "0": "\0"}
ESCAPE = re.compile(r"\\(.)", re.DOTALL)

Converter = Callable[[str], object]


class ExportFormatError(Exception):
    """The export isn't shaped the way this builder expects."""


def TEXT(value: str) -> str:
    return value


def INTEGER(value: str) -> int:
    return int(value)


def NULLABLE_INTEGER(value: str) -> int | None:
    return None if value == "NULL" else int(value)


def table_file(table: str) -> str:
    return f"WCA_export_{table}.tsv"


def read_metadata(archive: zipfile.ZipFile) -> dict:
    try:
        return json.loads(archive.read(METADATA_FILE).decode("utf-8"))
    except KeyError:
        raise ExportFormatError(f"The export has no {METADATA_FILE}") from None
    except ValueError as error:
        raise ExportFormatError(f"The export's {METADATA_FILE} can't be read: {error}") from None


def utc_timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_export_date(value: str) -> datetime:
    """Reads the export date in any ISO 8601 shape, or as metadata.json writes it:
    "2026-09-27 00:00:42 UTC"."""
    text = str(value)
    if text.endswith(" UTC"):
        text = text.removesuffix(" UTC") + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise ExportFormatError(f"Can't read the export date {value!r}") from None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _unescape(field: str) -> str:
    if "\\" not in field:
        return field
    return ESCAPE.sub(lambda match: ESCAPES.get(match.group(1), match.group(1)), field)


def _fields(raw_line: bytes, filename: str, line_number: int) -> list[str]:
    try:
        line = raw_line.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ExportFormatError(f"{filename} line {line_number} isn't UTF-8: {error}") from None
    return line.removesuffix("\n").split("\t")


def read_table(
    archive: zipfile.ZipFile, table: str, columns: dict[str, Converter]
) -> Iterator[dict]:
    """Yield each row of a table as {column: converted value}, for just the columns asked for.

    Streams the file from the zip, so a table of tens of millions of rows is never held in
    memory.
    """
    filename = table_file(table)
    try:
        stream = archive.open(filename)
    except KeyError:
        raise ExportFormatError(f"The export has no {filename} ({table} table)") from None
    with stream:
        header = _fields(stream.readline(), filename, 1)
        missing = [name for name in columns if name not in header]
        if missing:
            raise ExportFormatError(f"{filename} ({table} table) has no column {missing[0]!r}")
        positions = {name: header.index(name) for name in columns}
        for line_number, raw_line in enumerate(stream, start=2):
            fields = _fields(raw_line, filename, line_number)
            if len(fields) != len(header):
                raise ExportFormatError(
                    f"{filename} line {line_number} has {len(fields)} fields, "
                    f"expected {len(header)}"
                )
            row = {}
            for name, convert in columns.items():
                try:
                    row[name] = convert(_unescape(fields[positions[name]]))
                except ValueError:
                    raise ExportFormatError(
                        f"{filename} line {line_number}: bad value "
                        f"{fields[positions[name]]!r} in column {name!r}"
                    ) from None
            yield row
