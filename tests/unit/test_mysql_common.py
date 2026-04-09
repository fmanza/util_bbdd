"""Tests para módulo MySQL: tipos, identificadores y cascade actions."""

from __future__ import annotations

from util_bbdd.metadata.mysql.common import (
    decode_mysql_cascade_action,
    escape_mysql_string,
    is_system_schema_mysql,
    mysql_type_mapping,
    normalize_mysql_type,
    quote_mysql_identifier,
)


class TestMysqlTypeMapping:
    """Tests para mysql_type_mapping()."""

    def test_type_mapping_returns_dict(self) -> None:
        mapping = mysql_type_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) >= 40

    def test_type_mapping_contains_integer_types(self) -> None:
        mapping = mysql_type_mapping()
        assert "TINYINT" in mapping
        assert "SMALLINT" in mapping
        assert "INT" in mapping
        assert "BIGINT" in mapping
        assert mapping["INT"] == "integer"

    def test_type_mapping_contains_floating_point(self) -> None:
        mapping = mysql_type_mapping()
        assert "FLOAT" in mapping
        assert "DOUBLE" in mapping

    def test_type_mapping_contains_string_types(self) -> None:
        mapping = mysql_type_mapping()
        assert "VARCHAR" in mapping
        assert "CHAR" in mapping
        assert "TEXT" in mapping

    def test_type_mapping_contains_binary_types(self) -> None:
        mapping = mysql_type_mapping()
        assert "BINARY" in mapping
        assert "VARBINARY" in mapping
        assert "BLOB" in mapping

    def test_type_mapping_contains_datetime_types(self) -> None:
        mapping = mysql_type_mapping()
        assert "DATE" in mapping
        assert "TIME" in mapping
        assert "DATETIME" in mapping
        assert "TIMESTAMP" in mapping

    def test_type_mapping_contains_special_types(self) -> None:
        mapping = mysql_type_mapping()
        assert "JSON" in mapping
        assert "ENUM" in mapping
        assert "SET" in mapping
        assert "GEOMETRY" in mapping


class TestNormalizeMysqlType:
    """Tests para normalize_mysql_type()."""

    def test_normalize_int(self) -> None:
        assert normalize_mysql_type("INT") == "integer"

    def test_normalize_bigint(self) -> None:
        assert normalize_mysql_type("BIGINT") == "bigint"

    def test_normalize_varchar(self) -> None:
        assert normalize_mysql_type("VARCHAR") == "varchar"

    def test_normalize_varchar_with_length(self) -> None:
        assert normalize_mysql_type("VARCHAR(255)") == "varchar"

    def test_normalize_varchar_with_length_mixed_case(self) -> None:
        assert normalize_mysql_type("varchar(100)") == "varchar"

    def test_normalize_decimal(self) -> None:
        assert normalize_mysql_type("DECIMAL") == "decimal"

    def test_normalize_decimal_with_precision(self) -> None:
        assert normalize_mysql_type("DECIMAL(10,2)") == "decimal"

    def test_normalize_datetime(self) -> None:
        assert normalize_mysql_type("DATETIME") == "datetime"

    def test_normalize_timestamp(self) -> None:
        assert normalize_mysql_type("TIMESTAMP") == "timestamp"

    def test_normalize_json(self) -> None:
        assert normalize_mysql_type("JSON") == "json"

    def test_normalize_enum(self) -> None:
        assert normalize_mysql_type("ENUM") == "enum"

    def test_normalize_set(self) -> None:
        assert normalize_mysql_type("SET") == "set"

    def test_normalize_geometry(self) -> None:
        assert normalize_mysql_type("GEOMETRY") == "geometry"

    def test_normalize_unknown_type_returns_object(self) -> None:
        result = normalize_mysql_type("UNKNOWN_TYPE")
        assert result == "object"  # Should fallback to object

    def test_normalize_empty_type_returns_object(self) -> None:
        assert normalize_mysql_type("") == "object"


class TestQuoteMysqlIdentifier:
    """Tests para quote_mysql_identifier()."""

    def test_quote_simple_identifier(self) -> None:
        assert quote_mysql_identifier("users") == "`users`"

    def test_quote_with_spaces(self) -> None:
        assert quote_mysql_identifier("user name") == "`user name`"

    def test_quote_with_special_chars(self) -> None:
        assert quote_mysql_identifier("user-name") == "`user-name`"

    def test_quote_with_backticks(self) -> None:
        assert quote_mysql_identifier("user`name") == "`user``name`"

    def test_quote_empty_identifier(self) -> None:
        assert quote_mysql_identifier("") == "``"

    def test_quote_multiple_backticks(self) -> None:
        assert quote_mysql_identifier("user``name") == "`user````name`"


class TestEscapeMysqlString:
    """Tests para escape_mysql_string()."""

    def test_escape_simple_string(self) -> None:
        result = escape_mysql_string("hello")
        assert result == "'hello'"

    def test_escape_with_single_quotes(self) -> None:
        result = escape_mysql_string("it's")
        assert result == "'it\\'s'"

    def test_escape_with_backslash(self) -> None:
        result = escape_mysql_string("path\\file")
        assert result == "'path\\\\file'"

    def test_escape_empty_string(self) -> None:
        assert escape_mysql_string("") == "''"

    def test_escape_multiple_quotes(self) -> None:
        result = escape_mysql_string("it's a 'test'")
        assert "\\'" in result


class TestIsSystemSchemaMysql:
    """Tests para is_system_schema_mysql()."""

    def test_mysql_schema_is_system(self) -> None:
        assert is_system_schema_mysql("mysql")

    def test_mysql_schema_case_insensitive(self) -> None:
        assert is_system_schema_mysql("MySQL")
        assert is_system_schema_mysql("MYSQL")

    def test_information_schema_is_system(self) -> None:
        assert is_system_schema_mysql("information_schema")

    def test_performance_schema_is_system(self) -> None:
        assert is_system_schema_mysql("performance_schema")

    def test_sys_schema_is_system(self) -> None:
        assert is_system_schema_mysql("sys")

    def test_user_schema_is_not_system(self) -> None:
        assert not is_system_schema_mysql("myapp")

    def test_user_schema_uppercase_is_not_system(self) -> None:
        assert not is_system_schema_mysql("MYAPP")


class TestDecodeMysqlCascadeAction:
    """Tests para decode_mysql_cascade_action()."""

    def test_decode_restrict(self) -> None:
        assert decode_mysql_cascade_action("RESTRICT") == "RESTRICT"

    def test_decode_cascade(self) -> None:
        assert decode_mysql_cascade_action("CASCADE") == "CASCADE"

    def test_decode_set_null(self) -> None:
        assert decode_mysql_cascade_action("SET NULL") == "SET NULL"

    def test_decode_no_action(self) -> None:
        assert decode_mysql_cascade_action("NO ACTION") == "NO ACTION"

    def test_decode_set_default(self) -> None:
        assert decode_mysql_cascade_action("SET DEFAULT") == "SET DEFAULT"

    def test_decode_lowercase(self) -> None:
        assert decode_mysql_cascade_action("cascade") == "CASCADE"

    def test_decode_unknown_defaults_to_restrict(self) -> None:
        assert decode_mysql_cascade_action("UNKNOWN") == "RESTRICT"

    def test_decode_empty_defaults_to_restrict(self) -> None:
        assert decode_mysql_cascade_action("") == "RESTRICT"
