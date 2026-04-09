"""Tests para módulo SQL Server: tipos, identificadores y cascade actions."""

from __future__ import annotations

from util_bbdd.metadata.sqlserver.common import (
    decode_sqlserver_cascade_action,
    escape_sqlserver_string,
    is_system_schema_sqlserver,
    normalize_sqlserver_type,
    quote_sqlserver_identifier,
    sqlserver_type_mapping,
)


class TestSqlServerTypeMapping:
    """Tests para sqlserver_type_mapping()."""

    def test_type_mapping_returns_dict(self) -> None:
        mapping = sqlserver_type_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) >= 39

    def test_type_mapping_contains_integer_types(self) -> None:
        mapping = sqlserver_type_mapping()
        assert "INT" in mapping
        assert "BIGINT" in mapping
        assert "SMALLINT" in mapping
        assert mapping["INT"] == "integer"

    def test_type_mapping_contains_numeric_types(self) -> None:
        mapping = sqlserver_type_mapping()
        assert "NUMERIC" in mapping
        assert "DECIMAL" in mapping
        assert "MONEY" in mapping

    def test_type_mapping_contains_string_types(self) -> None:
        mapping = sqlserver_type_mapping()
        assert "VARCHAR" in mapping
        assert "NVARCHAR" in mapping
        assert "CHAR" in mapping

    def test_type_mapping_contains_binary_types(self) -> None:
        mapping = sqlserver_type_mapping()
        assert "BINARY" in mapping
        assert "VARBINARY" in mapping
        assert "IMAGE" in mapping

    def test_type_mapping_contains_datetime_types(self) -> None:
        mapping = sqlserver_type_mapping()
        assert "DATE" in mapping
        assert "DATETIME" in mapping
        assert "DATETIMEOFFSET" in mapping

    def test_type_mapping_contains_special_types(self) -> None:
        mapping = sqlserver_type_mapping()
        assert "UNIQUEIDENTIFIER" in mapping
        assert "XML" in mapping


class TestNormalizeSqlServerType:
    """Tests para normalize_sqlserver_type()."""

    def test_normalize_int(self) -> None:
        assert normalize_sqlserver_type("INT") == "integer"

    def test_normalize_bigint(self) -> None:
        assert normalize_sqlserver_type("BIGINT") == "bigint"

    def test_normalize_varchar(self) -> None:
        assert normalize_sqlserver_type("VARCHAR") == "varchar"

    def test_normalize_varchar_with_length(self) -> None:
        assert normalize_sqlserver_type("VARCHAR(255)") == "varchar"

    def test_normalize_nvarchar_max(self) -> None:
        assert normalize_sqlserver_type("NVARCHAR(MAX)") == "text"

    def test_normalize_numeric(self) -> None:
        assert normalize_sqlserver_type("NUMERIC") == "numeric"

    def test_normalize_numeric_with_precision(self) -> None:
        assert normalize_sqlserver_type("NUMERIC(10,2)") == "numeric"

    def test_normalize_datetime(self) -> None:
        assert normalize_sqlserver_type("DATETIME") == "datetime"

    def test_normalize_datetime2(self) -> None:
        assert normalize_sqlserver_type("DATETIME2") == "datetime2"

    def test_normalize_uniqueidentifier(self) -> None:
        assert normalize_sqlserver_type("UNIQUEIDENTIFIER") == "varchar"

    def test_normalize_xml(self) -> None:
        assert normalize_sqlserver_type("XML") == "xml"

    def test_normalize_money(self) -> None:
        result = normalize_sqlserver_type("MONEY")
        assert result in ("money", "decimal", "numeric")

    def test_normalize_unknown_type_returns_object(self) -> None:
        result = normalize_sqlserver_type("UNKNOWNTYPE")
        assert result in ("object", "unknowntype", "UNKNOWNTYPE")

    def test_normalize_empty_string_returns_object(self) -> None:
        assert normalize_sqlserver_type("") == "object"

    def test_normalize_case_insensitive(self) -> None:
        assert normalize_sqlserver_type("int") == "integer"
        assert normalize_sqlserver_type("Int") == "integer"


class TestQuoteSqlServerIdentifier:
    """Tests para quote_sqlserver_identifier()."""

    def test_quote_simple_identifier(self) -> None:
        result = quote_sqlserver_identifier("TableName")
        assert result == "[TableName]"

    def test_quote_identifier_with_space(self) -> None:
        result = quote_sqlserver_identifier("my table")
        assert result == "[my table]"

    def test_quote_identifier_with_brackets(self) -> None:
        result = quote_sqlserver_identifier("my[table]")
        assert result == "[my[table]]]"  # Internal ] is doubled

    def test_quote_reserved_keyword(self) -> None:
        result = quote_sqlserver_identifier("select")
        assert result == "[select]"

    def test_quote_identifier_with_special_chars(self) -> None:
        result = quote_sqlserver_identifier("my-table.name")
        assert result == "[my-table.name]"

    def test_quote_empty_string(self) -> None:
        result = quote_sqlserver_identifier("")
        assert result == "[]"

    def test_quote_schema_qualified_name(self) -> None:
        # Note: This quotes each part, caller should handle schema.table separately
        result = quote_sqlserver_identifier("dbo.users")
        assert "[" in result and "]" in result


class TestEscapeSqlServerString:
    """Tests para escape_sqlserver_string()."""

    def test_escape_simple_string(self) -> None:
        result = escape_sqlserver_string("hello")
        assert result == "'hello'"

    def test_escape_string_with_single_quote(self) -> None:
        result = escape_sqlserver_string("it's")
        assert result == "'it''s'"

    def test_escape_string_with_multiple_quotes(self) -> None:
        result = escape_sqlserver_string("it's what's")
        assert result == "'it''s what''s'"

    def test_escape_empty_string(self) -> None:
        result = escape_sqlserver_string("")
        assert result == "''"

    def test_escape_string_with_special_chars(self) -> None:
        result = escape_sqlserver_string("hello\nworld")
        assert "hello" in result and "world" in result


class TestIsSystemSchemaSqlServer:
    """Tests para is_system_schema_sqlserver()."""

    def test_sys_schema_is_system(self) -> None:
        assert is_system_schema_sqlserver("sys") is True

    def test_information_schema_is_system(self) -> None:
        assert is_system_schema_sqlserver("INFORMATION_SCHEMA") is True

    def test_tempdb_is_system(self) -> None:
        assert is_system_schema_sqlserver("tempdb") is True

    def test_model_is_system(self) -> None:
        assert is_system_schema_sqlserver("model") is True

    def test_msdb_is_system(self) -> None:
        assert is_system_schema_sqlserver("msdb") is True

    def test_dbo_is_not_system(self) -> None:
        assert is_system_schema_sqlserver("dbo") is False

    def test_custom_schema_is_not_system(self) -> None:
        assert is_system_schema_sqlserver("custom") is False

    def test_case_insensitive_system_detection(self) -> None:
        assert is_system_schema_sqlserver("SYS") is True
        assert is_system_schema_sqlserver("Sys") is True

    def test_none_schema_is_not_system(self) -> None:
        assert is_system_schema_sqlserver(None) is False


class TestDecodeSqlServerCascadeAction:
    """Tests para decode_sqlserver_cascade_action()."""

    def test_decode_no_action(self) -> None:
        assert decode_sqlserver_cascade_action(0) == "NO ACTION"

    def test_decode_cascade(self) -> None:
        assert decode_sqlserver_cascade_action(1) == "CASCADE"

    def test_decode_set_null(self) -> None:
        assert decode_sqlserver_cascade_action(2) == "SET NULL"

    def test_decode_set_default(self) -> None:
        assert decode_sqlserver_cascade_action(3) == "SET DEFAULT"

    def test_decode_trigger(self) -> None:
        assert decode_sqlserver_cascade_action(4) == "TRIGGER"

    def test_decode_invalid_code_returns_no_action(self) -> None:
        assert decode_sqlserver_cascade_action(99) == "NO ACTION"

    def test_decode_none_returns_no_action(self) -> None:
        assert decode_sqlserver_cascade_action(None) == "NO ACTION"

    def test_decode_all_valid_codes(self) -> None:
        for code in range(5):
            result = decode_sqlserver_cascade_action(code)
            assert isinstance(result, str)
            assert result != ""
