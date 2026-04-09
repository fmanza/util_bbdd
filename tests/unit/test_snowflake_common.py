"""Tests para módulo Snowflake: tipos, identificadores y helpers."""

from __future__ import annotations

from util_bbdd.metadata.snowflake.common import (
    escape_snowflake_string,
    is_system_schema_snowflake,
    normalize_snowflake_identifier,
    normalize_snowflake_type,
    parse_snowflake_database_schema_table,
    quote_snowflake_identifier,
    snowflake_type_mapping,
)


class TestSnowflakeTypeMapping:
    """Tests para snowflake_type_mapping()."""

    def test_type_mapping_returns_dict(self) -> None:
        mapping = snowflake_type_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) >= 40

    def test_type_mapping_contains_integer_types(self) -> None:
        mapping = snowflake_type_mapping()
        assert "INT" in mapping
        assert "INTEGER" in mapping
        assert "BIGINT" in mapping
        assert "SMALLINT" in mapping
        assert mapping["INT"] == "integer"

    def test_type_mapping_contains_floating_point(self) -> None:
        mapping = snowflake_type_mapping()
        assert "FLOAT" in mapping
        assert "DOUBLE" in mapping
        assert "REAL" in mapping

    def test_type_mapping_contains_decimal_types(self) -> None:
        mapping = snowflake_type_mapping()
        assert "DECIMAL" in mapping
        assert "NUMERIC" in mapping
        assert "NUMBER" in mapping

    def test_type_mapping_contains_string_types(self) -> None:
        mapping = snowflake_type_mapping()
        assert "VARCHAR" in mapping
        assert "CHAR" in mapping
        assert "TEXT" in mapping
        assert "STRING" in mapping

    def test_type_mapping_contains_date_time_types(self) -> None:
        mapping = snowflake_type_mapping()
        assert "DATE" in mapping
        assert "TIME" in mapping
        assert "TIMESTAMP" in mapping
        assert "TIMESTAMP_NTZ" in mapping
        assert "TIMESTAMP_TZ" in mapping
        assert "TIMESTAMP_LTZ" in mapping

    def test_type_mapping_contains_boolean(self) -> None:
        mapping = snowflake_type_mapping()
        assert "BOOLEAN" in mapping
        assert "BOOL" in mapping

    def test_type_mapping_contains_semi_structured(self) -> None:
        mapping = snowflake_type_mapping()
        assert "OBJECT" in mapping
        assert "ARRAY" in mapping
        assert "VARIANT" in mapping

    def test_type_mapping_contains_geography(self) -> None:
        mapping = snowflake_type_mapping()
        assert "GEOGRAPHY" in mapping
        assert "GEOMETRY" in mapping


class TestNormalizeSnowflakeType:
    """Tests para normalize_snowflake_type()."""

    def test_normalize_integer_type(self) -> None:
        assert normalize_snowflake_type("INT") == "integer"
        assert normalize_snowflake_type("int") == "integer"
        assert normalize_snowflake_type("INTEGER") == "integer"

    def test_normalize_varchar_type(self) -> None:
        assert normalize_snowflake_type("VARCHAR") == "varchar"
        assert normalize_snowflake_type("VARCHAR(255)") == "varchar"
        assert normalize_snowflake_type("varchar(100)") == "varchar"

    def test_normalize_decimal_type(self) -> None:
        assert normalize_snowflake_type("NUMBER") == "numeric"
        assert normalize_snowflake_type("NUMBER(10, 2)") == "numeric"
        assert normalize_snowflake_type("DECIMAL(18, 4)") == "decimal"

    def test_normalize_timestamp_types(self) -> None:
        assert normalize_snowflake_type("TIMESTAMP") == "timestamp"
        assert normalize_snowflake_type("TIMESTAMP_NTZ") == "timestamp"
        assert normalize_snowflake_type("TIMESTAMP_TZ") == "timestamp"
        assert normalize_snowflake_type("TIMESTAMP_LTZ") == "timestamp"

    def test_normalize_semi_structured_types(self) -> None:
        assert normalize_snowflake_type("OBJECT") == "object"
        assert normalize_snowflake_type("ARRAY") == "object"
        assert normalize_snowflake_type("VARIANT") == "object"

    def test_normalize_empty_type_returns_object(self) -> None:
        assert normalize_snowflake_type("") == "object"
        assert normalize_snowflake_type(None) == "object"

    def test_normalize_unknown_type_returns_object(self) -> None:
        assert normalize_snowflake_type("UNKNOWN_TYPE") == "object"
        assert normalize_snowflake_type("CUSTOM_TYPE") == "object"

    def test_normalize_case_insensitive(self) -> None:
        assert normalize_snowflake_type("varchar") == normalize_snowflake_type("VARCHAR")
        assert normalize_snowflake_type("int") == normalize_snowflake_type("INT")


class TestQuoteSnowflakeIdentifier:
    """Tests para quote_snowflake_identifier()."""

    def test_quote_simple_identifier(self) -> None:
        assert quote_snowflake_identifier("my_table") == '"my_table"'
        assert quote_snowflake_identifier("column1") == '"column1"'

    def test_quote_identifier_with_spaces(self) -> None:
        assert quote_snowflake_identifier("my table") == '"my table"'

    def test_quote_identifier_with_double_quotes(self) -> None:
        assert quote_snowflake_identifier('my"table') == '"my""table"'
        assert quote_snowflake_identifier('"quoted"') == '"""quoted"""'

    def test_quote_empty_identifier(self) -> None:
        assert quote_snowflake_identifier("") == '""'

    def test_quote_preserves_case(self) -> None:
        assert quote_snowflake_identifier("MyTable") == '"MyTable"'
        assert quote_snowflake_identifier("UPPERCASE") == '"UPPERCASE"'


class TestEscapeSnowflakeString:
    """Tests para escape_snowflake_string()."""

    def test_escape_simple_string(self) -> None:
        assert escape_snowflake_string("hello") == "'hello'"

    def test_escape_string_with_apostrophe(self) -> None:
        assert escape_snowflake_string("it's") == "'it''s'"
        assert escape_snowflake_string("can't") == "'can''t'"

    def test_escape_string_with_multiple_apostrophes(self) -> None:
        assert escape_snowflake_string("it's a test") == "'it''s a test'"

    def test_escape_empty_string(self) -> None:
        assert escape_snowflake_string("") == "''"

    def test_escape_string_with_quotes(self) -> None:
        # SQL uses single quotes, so double quotes don't need escaping
        result = escape_snowflake_string('say "hello"')
        assert result == "'say \"hello\"'"


class TestNormalizeSnowflakeIdentifier:
    """Tests para normalize_snowflake_identifier()."""

    def test_normalize_unquoted_identifier(self) -> None:
        assert normalize_snowflake_identifier("my_table") == "MY_TABLE"
        assert normalize_snowflake_identifier("column1") == "COLUMN1"

    def test_normalize_unquoted_lowercase(self) -> None:
        assert normalize_snowflake_identifier("lowercase") == "LOWERCASE"

    def test_normalize_quoted_identifier(self) -> None:
        # Quoted identifiers preserve case and remove quotes
        assert normalize_snowflake_identifier('"MyTable"') == "MyTable"
        assert normalize_snowflake_identifier('"lowercase"') == "lowercase"

    def test_normalize_empty_identifier(self) -> None:
        assert normalize_snowflake_identifier("") == ""
        assert normalize_snowflake_identifier(None) == ""

    def test_normalize_with_whitespace(self) -> None:
        assert normalize_snowflake_identifier("  my_table  ") == "MY_TABLE"


class TestIsSystemSchemaSnowflake:
    """Tests para is_system_schema_snowflake()."""

    def test_information_schema_is_system(self) -> None:
        assert is_system_schema_snowflake("INFORMATION_SCHEMA") is True
        assert is_system_schema_snowflake("information_schema") is True

    def test_snowflake_schema_is_system(self) -> None:
        assert is_system_schema_snowflake("SNOWFLAKE") is True
        assert is_system_schema_snowflake("snowflake") is True

    def test_user_schema_is_not_system(self) -> None:
        assert is_system_schema_snowflake("PUBLIC") is False
        assert is_system_schema_snowflake("my_schema") is False
        assert is_system_schema_snowflake("dbo") is False

    def test_empty_schema_is_not_system(self) -> None:
        assert is_system_schema_snowflake("") is False
        assert is_system_schema_snowflake(None) is False

    def test_case_insensitive_check(self) -> None:
        assert is_system_schema_snowflake("information_schema") is True
        assert is_system_schema_snowflake("INFORMATION_SCHEMA") is True
        assert is_system_schema_snowflake("InFormation_Schema") is True


class TestParseSnowflakeDatabaseSchemaTable:
    """Tests para parse_snowflake_database_schema_table()."""

    def test_parse_table_only(self) -> None:
        db, schema, table = parse_snowflake_database_schema_table("my_table")
        assert db == ""
        assert schema == ""
        assert table == "my_table"

    def test_parse_schema_table(self) -> None:
        db, schema, table = parse_snowflake_database_schema_table("public.my_table")
        assert db == ""
        assert schema == "public"
        assert table == "my_table"

    def test_parse_database_schema_table(self) -> None:
        db, schema, table = parse_snowflake_database_schema_table("mydb.public.my_table")
        assert db == "mydb"
        assert schema == "public"
        assert table == "my_table"

    def test_parse_more_than_three_parts(self) -> None:
        # Take last 3 parts
        db, schema, table = parse_snowflake_database_schema_table("a.b.c.d.e")
        assert db == "c"
        assert schema == "d"
        assert table == "e"

    def test_parse_empty_string(self) -> None:
        db, schema, table = parse_snowflake_database_schema_table("")
        assert db == ""
        assert schema == ""
        assert table == ""

    def test_parse_with_whitespace(self) -> None:
        db, schema, table = parse_snowflake_database_schema_table("  mydb.public.my_table  ")
        assert db == "mydb"
        assert schema == "public"
        assert table == "my_table"

    def test_parse_quoted_names(self) -> None:
        # Parse doesn't unquote, just splits
        db, schema, table = parse_snowflake_database_schema_table('"mydb"."public"."my_table"')
        assert db == '"mydb"'
        assert schema == '"public"'
        assert table == '"my_table"'
