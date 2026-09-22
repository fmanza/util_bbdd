"""Tests para módulo Oracle: tipos, identificadores y escape."""

from __future__ import annotations

from util_bbdd.metadata.oracle.common import (
    escape_oracle_string,
    get_oracle_table_type,
    is_system_schema_oracle,
    normalize_oracle_type,
    oracle_type_mapping,
    parse_oracle_number_precision_scale,
    quote_oracle_identifier,
)


class TestOracleTypeMapping:
    """Tests para oracle_type_mapping()."""

    def test_type_mapping_returns_dict(self) -> None:
        mapping = oracle_type_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) >= 30

    def test_type_mapping_contains_varchar2(self) -> None:
        mapping = oracle_type_mapping()
        assert "VARCHAR2" in mapping
        assert mapping["VARCHAR2"] == "varchar"

    def test_type_mapping_contains_number(self) -> None:
        mapping = oracle_type_mapping()
        assert "NUMBER" in mapping
        assert mapping["NUMBER"] == "numeric"

    def test_type_mapping_contains_date(self) -> None:
        mapping = oracle_type_mapping()
        assert "DATE" in mapping
        assert mapping["DATE"] == "date"

    def test_type_mapping_contains_timestamp(self) -> None:
        mapping = oracle_type_mapping()
        assert "TIMESTAMP" in mapping
        assert mapping["TIMESTAMP"] == "timestamp"

    def test_type_mapping_contains_timestamp_with_tz(self) -> None:
        mapping = oracle_type_mapping()
        assert "TIMESTAMP WITH TIME ZONE" in mapping

    def test_type_mapping_contains_blob_clob(self) -> None:
        mapping = oracle_type_mapping()
        assert "BLOB" in mapping
        assert "CLOB" in mapping

    def test_type_mapping_contains_raw(self) -> None:
        mapping = oracle_type_mapping()
        assert "RAW" in mapping
        assert "LONG RAW" in mapping


class TestNormalizeOracleType:
    """Tests para normalize_oracle_type()."""

    def test_normalize_varchar2(self) -> None:
        assert normalize_oracle_type("VARCHAR2") == "varchar"

    def test_normalize_varchar2_with_params(self) -> None:
        assert normalize_oracle_type("VARCHAR2(255)") == "varchar"

    def test_normalize_number(self) -> None:
        assert normalize_oracle_type("NUMBER") == "numeric"

    def test_normalize_number_with_precision(self) -> None:
        assert normalize_oracle_type("NUMBER(10,2)") == "numeric"

    def test_normalize_date(self) -> None:
        assert normalize_oracle_type("DATE") == "date"

    def test_normalize_timestamp(self) -> None:
        assert normalize_oracle_type("TIMESTAMP") == "timestamp"

    def test_normalize_timestamp_with_tz(self) -> None:
        assert normalize_oracle_type("TIMESTAMP WITH TIME ZONE") == "timestamp"

    def test_normalize_unknown_type_returns_object(self) -> None:
        result = normalize_oracle_type("UNKNOWNTYPE")
        assert result in ("object", "unknowntype", "UNKNOWNTYPE")

    def test_normalize_empty_string_returns_object(self) -> None:
        assert normalize_oracle_type("") == "object"

    def test_normalize_none_returns_object(self) -> None:
        result = normalize_oracle_type(None)
        assert result == "object" or isinstance(result, str)

    def test_normalize_blob(self) -> None:
        assert normalize_oracle_type("BLOB") == "blob"

    def test_normalize_clob(self) -> None:
        assert normalize_oracle_type("CLOB") == "clob"

    def test_normalize_integer(self) -> None:
        assert normalize_oracle_type("INTEGER") == "integer"

    def test_normalize_float(self) -> None:
        assert normalize_oracle_type("FLOAT") == "float"


class TestQuoteOracleIdentifier:
    """Tests para quote_oracle_identifier()."""

    def test_quote_simple_identifier(self) -> None:
        result = quote_oracle_identifier("users")
        assert result == '"users"'

    def test_quote_identifier_with_spaces(self) -> None:
        result = quote_oracle_identifier("user table")
        assert result == '"user table"'

    def test_quote_identifier_with_internal_quotes(self) -> None:
        result = quote_oracle_identifier('user"name')
        assert result == '"user""name"'

    def test_quote_empty_identifier(self) -> None:
        result = quote_oracle_identifier("")
        assert result == '""'

    def test_quote_reserved_keyword(self) -> None:
        result = quote_oracle_identifier("ORDER")
        assert result == '"ORDER"'


class TestEscapeOracleString:
    """Tests para escape_oracle_string()."""

    def test_escape_simple_string(self) -> None:
        result = escape_oracle_string("hello")
        assert result == "hello"

    def test_escape_string_with_single_quote(self) -> None:
        result = escape_oracle_string("O'Brien")
        assert result == "O''Brien"

    def test_escape_multiple_quotes(self) -> None:
        result = escape_oracle_string("it's a 'test'")
        assert result == "it''s a ''test''"

    def test_escape_empty_string(self) -> None:
        result = escape_oracle_string("")
        assert result == ""


class TestIsSystemSchemaOracle:
    """Tests para is_system_schema_oracle()."""

    def test_sys_is_system(self) -> None:
        assert is_system_schema_oracle("SYS") is True

    def test_system_is_system(self) -> None:
        assert is_system_schema_oracle("SYSTEM") is True

    def test_xdb_is_system(self) -> None:
        assert is_system_schema_oracle("XDB") is True

    def test_apex_prefix_is_system(self) -> None:
        assert is_system_schema_oracle("APEX_050000") is True

    def test_mdsys_is_system(self) -> None:
        assert is_system_schema_oracle("MDSYS") is True

    def test_orddata_is_system(self) -> None:
        assert is_system_schema_oracle("ORDDATA") is True

    def test_user_schema_is_not_system(self) -> None:
        assert is_system_schema_oracle("MYAPP") is False

    def test_users_schema_is_not_system(self) -> None:
        assert is_system_schema_oracle("USERS") is False

    def test_empty_string_is_not_system(self) -> None:
        assert is_system_schema_oracle("") is False

    def test_none_is_not_system(self) -> None:
        result = is_system_schema_oracle(None)
        assert result is False

    def test_lowercase_sys_is_system(self) -> None:
        assert is_system_schema_oracle("sys") is True

    def test_wmsys_is_system(self) -> None:
        assert is_system_schema_oracle("WMSYS") is True

    def test_user_schema_starting_with_wm_is_not_system(self) -> None:
        """MEO-06 (AUDIT_CODE 2026-09-22): el filtro por prefijo "WM" excluía por
        error esquemas de usuario legítimos que solo coincidían en el prefijo."""
        assert is_system_schema_oracle("WMHOLDINGS") is False

    def test_user_schema_wm_reports_is_not_system(self) -> None:
        assert is_system_schema_oracle("WM_REPORTS") is False


class TestGetOracleTableType:
    """Tests para get_oracle_table_type()."""

    def test_table_type(self) -> None:
        assert get_oracle_table_type("TABLE") == "TABLE"

    def test_view_type(self) -> None:
        assert get_oracle_table_type("VIEW") == "VIEW"

    def test_external_table_type(self) -> None:
        result = get_oracle_table_type("EXTERNAL TABLE")
        assert "EXTERNAL" in result

    def test_cluster_type(self) -> None:
        result = get_oracle_table_type("CLUSTER")
        assert "CLUSTER" in result or result == "CLUSTER"

    def test_empty_type_defaults_to_table(self) -> None:
        assert get_oracle_table_type("") == "TABLE"

    def test_none_type_defaults_to_table(self) -> None:
        assert get_oracle_table_type(None) == "TABLE"


class TestParseOracleNumberPrecisionScale:
    """Tests para parse_oracle_number_precision_scale()."""

    def test_parse_with_both_values(self) -> None:
        precision, scale = parse_oracle_number_precision_scale(10, 2)
        assert precision == 10
        assert scale == 2

    def test_parse_with_precision_only(self) -> None:
        precision, scale = parse_oracle_number_precision_scale(10, None)
        assert precision == 10
        assert scale is None

    def test_parse_with_scale_only(self) -> None:
        precision, scale = parse_oracle_number_precision_scale(None, 2)
        assert precision is None
        assert scale == 2

    def test_parse_with_both_none(self) -> None:
        precision, scale = parse_oracle_number_precision_scale(None, None)
        assert precision is None
        assert scale is None

    def test_parse_with_string_values(self) -> None:
        precision, scale = parse_oracle_number_precision_scale("10", "2")
        assert precision == 10
        assert scale == 2
