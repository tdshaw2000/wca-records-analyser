import zipfile

import pytest

from wca_data.export import (
    INTEGER,
    NULLABLE_INTEGER,
    TEXT,
    ExportFormatError,
    read_metadata,
    read_table,
)

from .export_zip import METADATA, tsv, write_export_zip


def _rows(tmp_path, table_text, columns, table="persons"):
    path = write_export_zip(tmp_path / "export.zip", {table: table_text})
    with zipfile.ZipFile(path) as archive:
        return list(read_table(archive, table, columns))


def test_reads_the_requested_columns_by_header_name_in_any_order(tmp_path):
    text = tsv(["name", "gender", "wca_id", "sub_id", "country_id"], ["Feliks Zemdegs", "m", "2009ZEMD01", 1, "Australia"])
    rows = _rows(tmp_path, text, {"wca_id": TEXT, "sub_id": INTEGER, "name": TEXT})
    assert rows == [{"wca_id": "2009ZEMD01", "sub_id": 1, "name": "Feliks Zemdegs"}]


def test_undoes_the_mysql_batch_escapes_for_tab_newline_backslash_and_nul(tmp_path):
    text = tsv(["id", "name"], ["c1", r"Tab\there", ], ["c2", r"Two\nlines"], ["c3", r"Back\\slash"], ["c4", r"Nul\0byte"])
    rows = _rows(tmp_path, text, {"name": TEXT}, table="competitions")
    assert [row["name"] for row in rows] == ["Tab\there", "Two\nlines", "Back\\slash", "Nul\0byte"]


def test_keeps_utf8_names_intact(tmp_path):
    names = ["Zoé Martínez", "王小明", "Ølstrøm-Łukasz"]
    text = tsv(["wca_id", "name"], *[[f"2015TEST0{i}", name] for i, name in enumerate(names)])
    rows = _rows(tmp_path, text, {"name": TEXT})
    assert [row["name"] for row in rows] == names


def test_null_becomes_none_in_a_nullable_integer_column(tmp_path):
    text = tsv(["id", "latitude_microdegrees"], ["c1", "NULL"], ["c2", "-37813600"])
    rows = _rows(tmp_path, text, {"latitude_microdegrees": NULLABLE_INTEGER}, table="competitions")
    assert [row["latitude_microdegrees"] for row in rows] == [None, -37813600]


def test_negative_integers_such_as_dnf_and_dns_are_kept(tmp_path):
    text = tsv(["id", "best"], [1, -1], [2, -2], [3, 0])
    rows = _rows(tmp_path, text, {"best": INTEGER}, table="results")
    assert [row["best"] for row in rows] == [-1, -2, 0]


def test_a_header_only_table_has_no_rows(tmp_path):
    assert _rows(tmp_path, tsv(["wca_id", "name"]), {"name": TEXT}) == []


def test_a_missing_column_is_an_export_format_error_naming_it(tmp_path):
    text = tsv(["wca_id", "name"], ["2009ZEMD01", "Feliks Zemdegs"])
    with pytest.raises(ExportFormatError, match="persons.*sub_id"):
        _rows(tmp_path, text, {"sub_id": INTEGER})


def test_a_missing_table_is_an_export_format_error(tmp_path):
    path = write_export_zip(tmp_path / "export.zip", {})
    with zipfile.ZipFile(path) as archive, pytest.raises(ExportFormatError, match="persons"):
        list(read_table(archive, "persons", {"name": TEXT}))


def test_a_row_with_the_wrong_number_of_fields_is_an_export_format_error(tmp_path):
    text = "wca_id\tname\n2009ZEMD01\tFeliks Zemdegs\textra\n"
    with pytest.raises(ExportFormatError, match="line 2"):
        _rows(tmp_path, text, {"name": TEXT})


def test_a_non_integer_in_an_integer_column_is_an_export_format_error(tmp_path):
    text = tsv(["id", "best"], [1, "fast"])
    with pytest.raises(ExportFormatError, match="best"):
        _rows(tmp_path, text, {"best": INTEGER}, table="results")


def test_read_metadata_returns_the_export_metadata(tmp_path):
    path = write_export_zip(tmp_path / "export.zip", {})
    with zipfile.ZipFile(path) as archive:
        assert read_metadata(archive) == METADATA


def test_missing_metadata_is_an_export_format_error(tmp_path):
    path = write_export_zip(tmp_path / "export.zip", {}, metadata=None)
    with zipfile.ZipFile(path) as archive, pytest.raises(ExportFormatError, match="metadata.json"):
        read_metadata(archive)
