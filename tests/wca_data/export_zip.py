"""Writes small WCA-style export zips for tests: no network, no real export needed."""

import json
import zipfile

METADATA = {
    "export_format_version": "v2.0.2",
    "version_label": "current",
    "end_of_life_date": None,
    "export_date": "2026-09-23T00:00:00.000+00:00",
}


def tsv(header, *rows):
    """A table file as the export writes it: tab-separated, header first, one line per row."""
    lines = ["\t".join(header)] + ["\t".join(str(value) for value in row) for row in rows]
    return "\n".join(lines) + "\n"


def write_export_zip(path, tables, metadata=METADATA):
    """tables maps a table name (e.g. "persons") to its TSV text. metadata=None leaves it out."""
    with zipfile.ZipFile(path, "w") as archive:
        if metadata is not None:
            archive.writestr("metadata.json", json.dumps(metadata))
        archive.writestr("README.md", "Test export.\n")
        for table, text in tables.items():
            archive.writestr(f"WCA_export_{table}.tsv", text.encode("utf-8"))
    return path
