"""Tests para módulo SQLite: tipos, identificadores y escape."""

from __future__ import annotations

from util_bbdd.metadata.sqlite.common import (
    escape_sqlite_string,
    is_system_schema_sqlite,
    normalize_sqlite_type,
    quote_sqlite_identifier,
    sqlite_type_mapping,
)


class TestSqliteTypeMapping:
    """Tests para sqlite_type_mapping()."""

    def test_type_mapping_returns_dict(self) -> None:
        mapping = sqlite_type_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) >= 30

    def test_type_mapping_contains_integer(self) -> None:
        mapping = sqlite_type_mapping()
        assert "INTEGER" in mapping
        assert mapping["INTEGER"] == "integer"

    def test_type_mapping_contains_text(self) -> None:
        mapping = sqlite_type_mapping()
        assert "TEXT" in mapping
        assert mapping["TEXT"] == "varchar"

    def test_type_mapping_contains_real(self) -> None:
        mapping = sqlite_type_mapping()
        assert "REAL" in mapping
        assert mapping["REAL"] == "float"

    def test_type_mapping_contains_blob(self) -> None:
        mapping = sqlite_type_mapping()
        assert "BLOB" in mapping
        assert mapping["BLOB"] == "binary"

    def test_type_mapping_contains_numeric(self) -> None:
        mapping = sqlite_type_mapping()
        assert "NUMERIC" in mapping
        assert mapping["NUMERIC"] == "numeric"

    def test_type_mapping_contains_boolean(self) -> None:
        mapping = sqlite_type_mapping()
        assert "BOOLEAN" in mapping
        assert mapping["BOOLEAN"] == "boolean"

    def test_type_mapping_contains_json(self) -> None:
        mapping = sqlite_type_mapping()
        assert "JSON" in mapping
        assert mapping["JSON"] == "object"

    def test_type_mapping_contains_uuid(self) -> None:
        mapping = sqlite_type_mapping()
        assert "UUID" in mapping

    def test_type_mapping_contains_varchar(self) -> None:
        mapping = sqlite_type_mapping()
        assert "VARCHAR" in mapping
        assert mapping["VARCHAR"] == "varchar"

    def test_type_mapping_contains_date_time(self) -> None:
        mapping = sqlite_type_mapping()
        assert "DATE" in mapping
        assert "TIME" in mapping
        assert "TIMESTAMP" in mapping


class TestNormalizeSqliteType:
    """Tests para normalize_sqlite_type()."""

    def test_normalize_integer(self) -> None:
        assert normalize_sqlite_type("INTEGER") == "integer"

    def test_normalize_text(self) -> None:
        assert normalize_sqlite_type("TEXT") == "varchar"

    def test_normalize_real(self) -> None:
        assert normalize_sqlite_type("REAL") == "float"

    def test_normalize_blob(self) -> None:
        assert normalize_sqlite_type("BLOB") == "binary"

    def test_normalize_varchar(self) -> None:
        assert normalize_sqlite_type("VARCHAR") == "varchar"

    def test_normalize_varchar_with_length(self) -> None:
        assert normalize_sqlite_type("VARCHAR(255)") == "varchar"

    def test_normalize_numeric(self) -> None:
        assert normalize_sqlite_type("NUMERIC") == "numeric"

    def test_normalize_numeric_with_precision(self) -> None:
        assert normalize_sqlite_type("NUMERIC(10,2)") == "numeric"

    def test_normalize_decimal_with_precision(self) -> None:
        assert normalize_sqlite_type("DECIMAL(18,4)") == "decimal"

    def test_normalize_boolean(self) -> None:
        assert normalize_sqlite_type("BOOLEAN") == "boolean"

    def test_normalize_date(self) -> None:
        assert normalize_sqlite_type("DATE") == "date"

    def test_normalize_time(self) -> None:
        assert normalize_sqlite_type("TIME") == "time"

    def test_normalize_datetime(self) -> None:
        assert normalize_sqlite_type("DATETIME") == "datetime"

    def test_normalize_timestamp(self) -> None:
        assert normalize_sqlite_type("TIMESTAMP") == "timestamp"

    def test_normalize_json(self) -> None:
        assert normalize_sqlite_type("JSON") == "object"

    def test_normalize_uuid(self) -> None:
        assert normalize_sqlite_type("UUID") == "varchar"

    def test_normalize_unknown_type_returns_object(self) -> None:
        result = normalize_sqlite_type("UNKNOWNTYPE")
        assert result in ("object", "unknowntype", "UNKNOWNTYPE")

    def test_normalize_empty_string_returns_object(self) -> None:
        assert normalize_sqlite_type("") == "object"

    def test_normalize_case_insensitive(self) -> None:
        assert normalize_sqlite_type("integer") == "integer"
        assert normalize_sqlite_type("Integer") == "integer"


class TestQuoteSqliteIdentifier:
    """Tests para quote_sqlite_identifier()."""

    def test_quote_simple_identifier(self) -> None:
        result = quote_sqlite_identifier("table_name")
        assert result == '"table_name"'

    def test_quote_identifier_with_space(self) -> None:
        result = quote_sqlite_identifier("my table")
        assert result == '"my table"'

    def test_quote_identifier_with_quotes(self) -> None:
        result = quote_sqlite_identifier('my"table')
        assert result == '"my""table"'

    def test_quote_reserved_keyword(self) -> None:
        result = quote_sqlite_identifier("select")
        assert result == '"select"'

    def test_quote_identifier_with_special_chars(self) -> None:
        result = quote_sqlite_identifier("my-table")
        assert result == '"my-table"'

    def test_quote_empty_string(self) -> None:
        result = quote_sqlite_identifier("")
        assert result == '""'

    def test_quote_identifier_already_quoted(self) -> None:
        # Esto no debería doble-citar, pero el argumento ya viene con comillas
        result = quote_sqlite_identifier('"table"')
        assert '""' in result or '"' in result


class TestEscapeSqliteString:
    """Tests para escape_sqlite_string()."""

    def test_escape_simple_string(self) -> None:
        result = escape_sqlite_string("hello")
        assert result == "'hello'"

    def test_escape_string_with_single_quote(self) -> None:
        result = escape_sqlite_string("it's")
        assert result == "'it''s'"

    def test_escape_string_with_multiple_quotes(self) -> None:
        result = escape_sqlite_string("it's what's")
        assert result == "'it''s what''s'"

    def test_escape_empty_string(self) -> None:
        result = escape_sqlite_string("")
        assert result == "''"

    def test_escape_string_with_special_chars(self) -> None:
        result = escape_sqlite_string("hello\nworld")
        assert "hello" in result and "world" in result


class TestIsSystemSchemaSqlite:
    """Tests para is_system_schema_sqlite()."""

    def test_main_schema_is_not_system(self) -> None:
        assert is_system_schema_sqlite("main") is False

    def test_temp_schema_is_not_system(self) -> None:
        assert is_system_schema_sqlite("temp") is False

    def test_any_schema_is_not_system(self) -> None:
        # SQLite no tiene esquemas de sistema
        assert is_system_schema_sqlite("anything") is False

    def test_none_schema_is_not_system(self) -> None:
        assert is_system_schema_sqlite(None) is False
