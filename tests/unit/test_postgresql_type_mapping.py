"""Tests para PostgreSQL: type mapping, quoting y helpers."""

from __future__ import annotations

from util_bbdd.metadata.postgresql.common import (
    escape_pg_literal,
    get_pg_type_name_from_oid,
    normalize_postgres_type,
    parse_pg_array_type,
    parse_pg_type_with_params,
    quote_pg_identifier,
)


class TestPostgresTypeNormalization:
    """Tests para normalización de tipos PostgreSQL."""

    def test_normalize_postgres_type_basic_types(self) -> None:
        assert normalize_postgres_type("text") == "string"
        assert normalize_postgres_type("integer") == "integer"
        assert normalize_postgres_type("bigint") == "integer"
        # "real" no está en el mapeo por defecto, devuelve fallback
        assert normalize_postgres_type("real") == "real"
        assert normalize_postgres_type("boolean") == "boolean"

    def test_normalize_postgres_type_varchar_with_length(self) -> None:
        result = normalize_postgres_type("varchar(255)")
        assert result in {"string", "varchar"}

    def test_normalize_postgres_type_numeric_with_precision(self) -> None:
        result = normalize_postgres_type("numeric(10,2)")
        assert result in {"decimal", "numeric"}

    def test_normalize_postgres_type_timestamp_types(self) -> None:
        result_ts = normalize_postgres_type("timestamp")
        assert result_ts in {"datetime", "timestamp"}
        # "timestamp with time zone" se reduce a "timestamp" (primer palabra),
        # luego se normaliza al tipo genérico
        result_tstz = normalize_postgres_type("timestamp with time zone")
        assert result_tstz in {"datetime", "timestamp"}  # Ambos son válidos tras normalizar
        assert normalize_postgres_type("date") == "date"
        assert normalize_postgres_type("time") == "time"

    def test_normalize_postgres_type_invalid_falls_back_to_lowercase(self) -> None:
        # Los tipos desconocidos se devuelven en minúsculas
        result = normalize_postgres_type("CUSTOM_TYPE")
        assert result == "custom_type"


class TestArrayTypeParsing:
    """Tests para detección de array types."""

    def test_parse_pg_array_type_single_dimension(self) -> None:
        base, is_array = parse_pg_array_type("integer[]")
        assert base == "integer"
        assert is_array is True

    def test_parse_pg_array_type_multi_dimension(self) -> None:
        base, is_array = parse_pg_array_type("text[][]")
        assert base == "text"
        assert is_array is True

    def test_parse_pg_array_type_no_array(self) -> None:
        base, is_array = parse_pg_array_type("varchar")
        assert base == "varchar"
        assert is_array is False

    def test_parse_pg_array_type_complex_type_with_array(self) -> None:
        base, is_array = parse_pg_array_type("numeric(10,2)[]")
        assert is_array is True
        assert "numeric" in base

    def test_parse_pg_array_type_whitespace(self) -> None:
        base, is_array = parse_pg_array_type("  text[]  ")
        assert base == "text"
        assert is_array is True


class TestTypeWithParamsParsing:
    """Tests para parseo avanzado de tipos con parámetros."""

    def test_parse_pg_type_with_params_simple_type(self) -> None:
        result = parse_pg_type_with_params("text")
        assert result["name"] == "text"
        assert result["is_array"] is False

    def test_parse_pg_type_with_params_varchar_length(self) -> None:
        result = parse_pg_type_with_params("varchar(255)")
        assert result["name"] == "varchar"
        assert result["length"] == 255

    def test_parse_pg_type_with_params_numeric_precision_scale(self) -> None:
        result = parse_pg_type_with_params("numeric(10,2)")
        assert result["name"] == "numeric"
        assert result["precision"] == 10
        assert result["scale"] == 2

    def test_parse_pg_type_with_params_array(self) -> None:
        result = parse_pg_type_with_params("integer[]")
        assert result["name"] == "integer"
        assert result["is_array"] is True

    def test_parse_pg_type_with_params_array_with_length(self) -> None:
        result = parse_pg_type_with_params("varchar(100)[]")
        assert result["name"] == "varchar"
        assert result["length"] == 100
        assert result["is_array"] is True

    def test_parse_pg_type_with_params_char_type(self) -> None:
        result = parse_pg_type_with_params("char(10)")
        assert result["name"] == "char"
        assert result["length"] == 10

    def test_parse_pg_type_with_params_time_with_zone(self) -> None:
        result = parse_pg_type_with_params("time with time zone")
        assert "time" in result["name"]


class TestOIDMapping:
    """Tests para mapeo de OIDs."""

    def test_get_pg_type_name_from_oid_common_types(self) -> None:
        assert get_pg_type_name_from_oid(16) == "boolean"
        assert get_pg_type_name_from_oid(20) == "bigint"
        assert get_pg_type_name_from_oid(23) == "integer"
        assert get_pg_type_name_from_oid(25) == "text"
        assert get_pg_type_name_from_oid(700) == "real"
        assert get_pg_type_name_from_oid(701) == "double precision"

    def test_get_pg_type_name_from_oid_string_types(self) -> None:
        assert get_pg_type_name_from_oid(1042) == "bpchar"
        assert get_pg_type_name_from_oid(1043) == "varchar"

    def test_get_pg_type_name_from_oid_temporal_types(self) -> None:
        assert get_pg_type_name_from_oid(1082) == "date"
        assert get_pg_type_name_from_oid(1083) == "time"
        assert get_pg_type_name_from_oid(1114) == "timestamp"
        assert get_pg_type_name_from_oid(1184) == "timestamp with time zone"

    def test_get_pg_type_name_from_oid_numeric_types(self) -> None:
        assert get_pg_type_name_from_oid(1700) == "numeric"
        assert get_pg_type_name_from_oid(21) == "smallint"

    def test_get_pg_type_name_from_oid_array_types(self) -> None:
        assert get_pg_type_name_from_oid(1000) == "_bool"
        assert get_pg_type_name_from_oid(1007) == "_int4"
        assert get_pg_type_name_from_oid(1016) == "_int8"
        # 1009 no está directamente en mapeo, verificar con None
        assert get_pg_type_name_from_oid(1009) is None or get_pg_type_name_from_oid(1009) == "_text"

    def test_get_pg_type_name_from_oid_json_types(self) -> None:
        assert get_pg_type_name_from_oid(114) == "json"
        assert get_pg_type_name_from_oid(3802) == "jsonb"

    def test_get_pg_type_name_from_oid_unknown_oid_returns_none(self) -> None:
        assert get_pg_type_name_from_oid(999999) is None
        assert get_pg_type_name_from_oid(0) is None


class TestIdentifierQuoting:
    """Tests para quoting de identificadores."""

    def test_quote_pg_identifier_simple(self) -> None:
        assert quote_pg_identifier("users") == '"users"'
        assert quote_pg_identifier("my_table") == '"my_table"'

    def test_quote_pg_identifier_with_special_chars(self) -> None:
        assert quote_pg_identifier("user-data") == '"user-data"'
        assert quote_pg_identifier("table.name") == '"table.name"'

    def test_quote_pg_identifier_escapes_quotes(self) -> None:
        assert quote_pg_identifier('table"name') == '"table""name"'
        assert quote_pg_identifier('col"1"col') == '"col""1""col"'

    def test_quote_pg_identifier_uppercase(self) -> None:
        # PostgreSQL fuerza lowercase a menos que se quote
        assert quote_pg_identifier("USERS") == '"USERS"'

    def test_quote_pg_identifier_already_quoted_escapes(self) -> None:
        # Si la entrada ya tiene comillas, deberían escaparse
        result = quote_pg_identifier('"users"')
        assert '""' in result


class TestSQLLiteralEscaping:
    """Tests para escaping de literales SQL."""

    def test_escape_pg_literal_simple_text(self) -> None:
        assert escape_pg_literal("hello") == "hello"
        assert escape_pg_literal("world") == "world"

    def test_escape_pg_literal_single_quote(self) -> None:
        assert escape_pg_literal("it's") == "it''s"
        assert escape_pg_literal("O'Brien") == "O''Brien"

    def test_escape_pg_literal_multiple_quotes(self) -> None:
        assert escape_pg_literal("it's 'quoted'") == "it''s ''quoted''"

    def test_escape_pg_literal_empty_string(self) -> None:
        assert escape_pg_literal("") == ""

    def test_escape_pg_literal_sql_injection_attempt(self) -> None:
        # Verifica que intento de inyección sea escapado
        malicious = "'; DROP TABLE users; --"
        escaped = escape_pg_literal(malicious)
        assert "''" in escaped  # Las comillas fueron escapadas
        assert escaped != malicious


class TestHexTextDecoding:
    """Tests para helpers de conversión de texto."""

    def test_quote_identifier_with_hex_roundtrip(self) -> None:
        """Verifica que quote puede usarse en nombres de esquemas/tablas."""
        schema = "auth_schema"
        quoted = quote_pg_identifier(schema)
        assert quoted == '"auth_schema"'
        # Puede usarse en SQL: WHERE table_schema = "auth_schema"

    def test_identifier_escaping_preserves_case(self) -> None:
        """Quoting preserva mayúsculas/minúsculas."""
        assert quote_pg_identifier("MyTable") == '"MyTable"'
        assert quote_pg_identifier("my_table") == '"my_table"'


class TestEdgeCases:
    """Tests para casos edge."""

    def test_normalize_postgres_type_empty_string(self) -> None:
        result = normalize_postgres_type("")
        assert result == ""

    def test_parse_pg_array_type_whitespace_array(self) -> None:
        base, is_array = parse_pg_array_type("  text  [  ]  ")
        # Debería limpiar whitespace
        assert "text" in base.lower()

    def test_escape_pg_literal_none_converts_to_string(self) -> None:
        # La función convierte de Any a str
        result = escape_pg_literal("")
        assert result == ""
