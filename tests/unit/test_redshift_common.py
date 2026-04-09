"""Tests para módulo Redshift: tipos, identificadores y helpers."""

from __future__ import annotations

from util_bbdd.metadata.redshift.common import (
    escape_redshift_string,
    is_system_schema_redshift,
    normalize_redshift_type,
    quote_redshift_identifier,
    redshift_type_mapping,
)


class TestRedshiftTypeMapping:
    """Tests para redshift_type_mapping()."""

    def test_type_mapping_returns_dict(self) -> None:
        mapping = redshift_type_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) >= 30

    def test_type_mapping_contains_integer_types(self) -> None:
        mapping = redshift_type_mapping()
        assert "SMALLINT" in mapping
        assert "INT" in mapping
        assert "INTEGER" in mapping
        assert "BIGINT" in mapping
        assert mapping["INT"] == "integer"

    def test_type_mapping_contains_floating_point(self) -> None:
        mapping = redshift_type_mapping()
        assert "FLOAT" in mapping
        assert "DOUBLE" in mapping
        assert "REAL" in mapping

    def test_type_mapping_contains_string_types(self) -> None:
        mapping = redshift_type_mapping()
        assert "VARCHAR" in mapping
        assert "CHAR" in mapping
        assert "TEXT" in mapping

    def test_type_mapping_contains_datetime_types(self) -> None:
        mapping = redshift_type_mapping()
        assert "DATE" in mapping
        assert "TIME" in mapping
        assert "TIMESTAMP" in mapping

    def test_type_mapping_contains_boolean(self) -> None:
        mapping = redshift_type_mapping()
        assert "BOOLEAN" in mapping
        assert "BOOL" in mapping

    def test_type_mapping_contains_numeric_types(self) -> None:
        mapping = redshift_type_mapping()
        assert "DECIMAL" in mapping
        assert "NUMERIC" in mapping

    def test_type_mapping_no_arrays_or_ranges(self) -> None:
        """Redshift no soporta arrays ni ranges (a diferencia de PostgreSQL)."""
        mapping = redshift_type_mapping()
        # Verificar que no hay tipos como "ARRAY", "RANGE"
        assert "ARRAY" not in mapping
        assert "RANGE" not in mapping


class TestNormalizeRedshiftType:
    """Tests para normalize_redshift_type()."""

    def test_normalize_int(self) -> None:
        assert normalize_redshift_type("INT") == "integer"

    def test_normalize_integer(self) -> None:
        assert normalize_redshift_type("INTEGER") == "integer"

    def test_normalize_bigint(self) -> None:
        assert normalize_redshift_type("BIGINT") == "bigint"

    def test_normalize_varchar(self) -> None:
        assert normalize_redshift_type("VARCHAR") == "varchar"

    def test_normalize_varchar_with_length(self) -> None:
        assert normalize_redshift_type("VARCHAR(255)") == "varchar"

    def test_normalize_varchar_with_length_mixed_case(self) -> None:
        assert normalize_redshift_type("varchar(100)") == "varchar"

    def test_normalize_decimal(self) -> None:
        assert normalize_redshift_type("DECIMAL") == "decimal"

    def test_normalize_decimal_with_precision(self) -> None:
        assert normalize_redshift_type("DECIMAL(10,2)") == "decimal"

    def test_normalize_timestamp(self) -> None:
        assert normalize_redshift_type("TIMESTAMP") == "timestamp"

    def test_normalize_timestamp_with_timezone(self) -> None:
        assert normalize_redshift_type("TIMESTAMPTZ") == "timestamp"

    def test_normalize_date(self) -> None:
        assert normalize_redshift_type("DATE") == "date"

    def test_normalize_boolean(self) -> None:
        assert normalize_redshift_type("BOOLEAN") == "boolean"

    def test_normalize_bool(self) -> None:
        assert normalize_redshift_type("BOOL") == "boolean"

    def test_normalize_character_varying(self) -> None:
        """PostgreSQL alias para VARCHAR."""
        assert normalize_redshift_type("CHARACTER VARYING") == "varchar"

    def test_normalize_unknown_type_returns_object(self) -> None:
        """Fallback para tipos no reconocidos (p.ej. GEOMETRY con soporte limitado)."""
        result = normalize_redshift_type("UNKNOWN_TYPE")
        assert result == "object"

    def test_normalize_empty_type_returns_object(self) -> None:
        assert normalize_redshift_type("") == "object"


class TestQuoteRedshiftIdentifier:
    """Tests para quote_redshift_identifier()."""

    def test_quote_simple_identifier(self) -> None:
        assert quote_redshift_identifier("users") == '"users"'

    def test_quote_with_spaces(self) -> None:
        assert quote_redshift_identifier("user name") == '"user name"'

    def test_quote_with_special_chars(self) -> None:
        assert quote_redshift_identifier("user-name") == '"user-name"'

    def test_quote_with_double_quotes(self) -> None:
        assert quote_redshift_identifier('user"name') == '"user""name"'

    def test_quote_empty_identifier(self) -> None:
        assert quote_redshift_identifier("") == '""'

    def test_quote_multiple_double_quotes(self) -> None:
        assert quote_redshift_identifier('user""name') == '"user""""name"'


class TestEscapeRedshiftString:
    """Tests para escape_redshift_string()."""

    def test_escape_simple_string(self) -> None:
        result = escape_redshift_string("hello")
        assert result == "'hello'"

    def test_escape_with_single_quotes(self) -> None:
        result = escape_redshift_string("it's")
        assert result == "'it''s'"

    def test_escape_multiple_single_quotes(self) -> None:
        result = escape_redshift_string("it's a 'test'")
        assert result == "'it''s a ''test'''"

    def test_escape_empty_string(self) -> None:
        assert escape_redshift_string("") == "''"


class TestIsSystemSchemaRedshift:
    """Tests para is_system_schema_redshift()."""

    def test_system_schema_pg_catalog(self) -> None:
        assert is_system_schema_redshift("pg_catalog") is True

    def test_system_schema_pg_with_underscore_prefix(self) -> None:
        assert is_system_schema_redshift("pg_temp") is True

    def test_system_schema_information_schema(self) -> None:
        assert is_system_schema_redshift("information_schema") is True

    def test_user_schema(self) -> None:
        assert is_system_schema_redshift("myschema") is False

    def test_user_schema_with_pg_in_name(self) -> None:
        """pg_ debe estar al inicio para considerarse sistema."""
        assert is_system_schema_redshift("mypg_schema") is False

    def test_case_insensitive(self) -> None:
        assert is_system_schema_redshift("PG_CATALOG") is True
        assert is_system_schema_redshift("INFORMATION_SCHEMA") is True

    def test_none_schema(self) -> None:
        assert is_system_schema_redshift(None) is False

    def test_empty_schema(self) -> None:
        assert is_system_schema_redshift("") is False
