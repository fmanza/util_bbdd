"""Unit tests for helper methods in HTML/Excel/Word generators."""

from pathlib import Path

import pytest

pytest.importorskip("docx")
pytest.importorskip("jinja2")
pytest.importorskip("openpyxl")

from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.doc.excel_generator import ExcelGenerator
from util_bbdd.doc.html_generator import HtmlGenerator
from util_bbdd.doc.word_generator import WordGenerator


def test_html_generator_builds_unique_slugs_and_map() -> None:
    generator = HtmlGenerator(database="db", headers={})

    used_slugs: set[str] = set()
    first = generator._build_unique_slug("Users Table", used_slugs)
    second = generator._build_unique_slug("Users_Table", used_slugs)
    slug_map = generator._build_slug_map(["A B", "A-B", "###"])

    assert first == "users-table"
    assert second == "users-table-2"
    assert [slug_map["A B"], slug_map["A-B"], slug_map["###"]] == ["a-b", "a-b-2", "item"]


def test_html_generator_routine_helpers_default_path_and_entity_decode() -> None:
    generator = HtmlGenerator(database="db", headers={})

    default_path = generator._get_default_content_path(
        tables_index=[],
        views_index=[{"path": "views/v_users.html"}],
        procedures_index=[],
        functions_index=[],
        routines_index=[],
        storage_entries=[],
    )
    normalized = generator._normalize_routine_entry(("sp_users", "procedure", None))
    key = generator._build_routine_key(("sp_users", "procedure", ""))
    decoded = generator._decode_html_entities("&amp;amp;lt;h1&amp;amp;gt;Hi&amp;amp;lt;/h1&amp;amp;gt;")

    assert default_path == "views/v_users.html"
    assert normalized == ("sp_users", "PROCEDURE", "")
    assert key == "PROCEDURE:sp_users"
    assert decoded == "<h1>Hi</h1>"


def test_excel_generator_style_normalization_split_and_numeric_conversion() -> None:
    aliased = ExcelGenerator(database="db", headers={}, table_style="Medium Shading 2 Accent 1")
    valid_style = ExcelGenerator(database="db", headers={}, table_style="TableStyleDark1")
    fallback = ExcelGenerator(database="db", headers={}, table_style="MyInvalidStyle")

    routines = [
        ("p_sync", "PROCEDURE", "ok"),
        ("f_total", "function", "ok"),
        ("unknown", "TRIGGER", "ignored"),
        ("default_func", None, ""),
    ]
    procedures, functions = fallback._split_routines_by_type(routines)

    assert aliased.table_style == "TableStyleMedium2"
    assert valid_style.table_style == "TableStyleDark1"
    assert fallback.table_style == "TableStyleMedium2"
    assert procedures == [routines[0]]
    assert functions == [routines[1], routines[3]]
    assert fallback._safe_tuple_value(("A", None), 0) == "A"
    assert fallback._safe_tuple_value(("A", None), 1) == ""
    assert fallback._safe_tuple_value(("A",), 3) == ""
    assert fallback._convert_to_numeric(" 1,50 ") == 1.5
    assert fallback._convert_to_numeric("abc") == "abc"
    assert fallback._convert_to_numeric(None) == ""


def test_word_generator_chunking_output_file_and_routine_split() -> None:
    generator = WordGenerator(database="db", headers={})
    tables = [(f"table_{idx}", "") for idx in range(120)]

    chunks = generator._chunk_tables(tables=tables, tables_per_document=0)
    single_output = generator._build_output_file_for_chunk(Path("report.docx"), chunk_index=1, total_chunks=1)
    multi_output = generator._build_output_file_for_chunk(Path("report.docx"), chunk_index=2, total_chunks=3)
    normalized = generator._normalize_routine_entry((None, None, None))
    procedures, functions = generator._split_routines_by_type(
        [("p_sync", "procedure", ""), ("f_total", "FUNCTION", ""), ("x", "TRIGGER", "")]
    )

    assert [len(chunk) for chunk in chunks] == [50, 50, 20]
    assert single_output == Path("report.docx")
    assert multi_output == Path("report_part2.docx")
    assert normalized == ("", "FUNCTION", "")
    assert procedures == [("p_sync", "procedure", "")]
    assert functions == [("f_total", "FUNCTION", "")]


def test_database_documentation_parses_mariadb_temp_data_file_path() -> None:
    rows = DatabaseDocumentation._parse_mariadb_temp_data_file_path_rows(
        "innodb_temp_data_file_path",
        "ibtmp1:12M:autoextend:max:5G",
    )

    assert rows == [
        [
            "innodb_temp_data_file_path",
            "ibtmp1",
            12.0,
            "Si",
            5120.0,
            "ibtmp1:12M:autoextend:max:5G",
        ]
    ]


def test_database_documentation_parse_mariadb_size_to_mb_accepts_units() -> None:
    assert DatabaseDocumentation._parse_mariadb_size_to_mb("64K") == 0.06
    assert DatabaseDocumentation._parse_mariadb_size_to_mb("12M") == 12.0
    assert DatabaseDocumentation._parse_mariadb_size_to_mb("2G") == 2048.0


def test_database_documentation_formats_mariadb_files_access_error() -> None:
    doc = DatabaseDocumentation.__new__(DatabaseDocumentation)

    section = doc._DatabaseDocumentation__build_mariadb_temp_tablespaces_error_section(
        "temp_tablespaces",
        "Temp tablespaces",
        "Access denied to information_schema.FILES for user",
    )

    assert section["status"] == "error"
    assert "Sin acceso a information_schema.FILES" in section["message"]
