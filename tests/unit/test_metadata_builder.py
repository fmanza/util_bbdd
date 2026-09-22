"""Tests de regresión MDC-01 (sub-paso 1) para DDLBuilder.

Cubren dos bugs corregidos en `metadata/builder.py`:
- `_quote_identifier` no escapaba el carácter delimitador embebido en el propio
  identificador (inyección de identificador).
- `_build_column_definition` concatenaba `DEFAULT <valor>` sin citar literales
  string, generando DDL inválido o inyectable.
"""

from __future__ import annotations

import pytest

from util_bbdd.metadata.builder import DDLBuilder


class TestQuoteIdentifierEscaping:
    """`_quote_identifier` debe duplicar el delimitador embebido, no solo envolverlo."""

    @pytest.mark.parametrize(
        ("db_type", "identifier", "expected"),
        [
            ("mariadb", "normal_table", "`normal_table`"),
            ("mariadb", "weird`table", "`weird``table`"),
            ("mysql", "weird`table", "`weird``table`"),
            ("sqlite", "weird`table", "`weird``table`"),
            ("unknown_engine", "weird`table", "`weird``table`"),
            ("postgresql", 'weird"table', '"weird""table"'),
            ("oracle", 'weird"table', '"weird""table"'),
            ("sqlserver", "weird]table", "[weird]]table]"),
        ],
    )
    def test_embedded_delimiter_is_doubled(self, db_type: str, identifier: str, expected: str) -> None:
        builder = DDLBuilder(db_type=db_type)

        assert builder._quote_identifier(identifier) == expected

    def test_injection_payload_cannot_close_and_reopen_identifier(self) -> None:
        builder = DDLBuilder(db_type="mariadb")
        payload = "users`; DROP TABLE secrets; --"

        quoted = builder._quote_identifier(payload)

        # Un único par de backticks envolvente: el backtick embebido queda escapado (``),
        # no cierra el identificador a mitad de cadena.
        assert quoted.startswith("`")
        assert quoted.endswith("`")
        assert quoted.count("``") == 1
        assert quoted == "`users``; DROP TABLE secrets; --`"


class TestDefaultValueQuoting:
    """`build_create_table_from_columns` debe citar y escapar DEFAULT string."""

    def test_string_default_is_quoted(self) -> None:
        builder = DDLBuilder(db_type="mariadb")
        columns = [("status", "VARCHAR(20)", "NO", None, "active")]

        ddl = builder.build_create_table_from_columns("t", columns)

        assert "DEFAULT 'active'" in ddl

    def test_string_default_with_embedded_quote_is_escaped(self) -> None:
        builder = DDLBuilder(db_type="mariadb")
        columns = [("name", "VARCHAR(50)", "NO", None, "O'Brien")]

        ddl = builder.build_create_table_from_columns("t", columns)

        assert "DEFAULT 'O''Brien'" in ddl
        # No debe quedar una comilla suelta que cierre el literal antes de tiempo.
        assert "DEFAULT 'O'Brien'" not in ddl

    def test_default_injection_payload_is_contained_in_single_literal(self) -> None:
        builder = DDLBuilder(db_type="mariadb")
        payload = "x'); DROP TABLE secrets; --"
        columns = [("name", "VARCHAR(50)", "NO", None, payload)]

        ddl = builder.build_create_table_from_columns("t", columns)

        assert "DEFAULT 'x''); DROP TABLE secrets; --'" in ddl

    @pytest.mark.parametrize(
        "keyword_default",
        ["CURRENT_TIMESTAMP", "current_timestamp", "NULL", "NOW()", "CURRENT_TIMESTAMP(3)"],
    )
    def test_known_sql_keywords_and_functions_are_not_quoted(self, keyword_default: str) -> None:
        builder = DDLBuilder(db_type="mariadb")
        columns = [("created_at", "TIMESTAMP", "NO", None, keyword_default)]

        ddl = builder.build_create_table_from_columns("t", columns)

        assert f"DEFAULT {keyword_default}" in ddl
        assert f"DEFAULT '{keyword_default}'" not in ddl

    @pytest.mark.parametrize("numeric_default", ["0", "1", "3.14", "-5"])
    def test_numeric_defaults_are_not_quoted(self, numeric_default: str) -> None:
        builder = DDLBuilder(db_type="mariadb")
        columns = [("qty", "INT", "NO", None, numeric_default)]

        ddl = builder.build_create_table_from_columns("t", columns)

        assert f"DEFAULT {numeric_default}" in ddl

    def test_already_quoted_string_default_is_kept_as_is(self) -> None:
        builder = DDLBuilder(db_type="mariadb")
        columns = [("code", "VARCHAR(10)", "NO", None, "'6'")]

        ddl = builder.build_create_table_from_columns("t", columns)

        assert "DEFAULT '6'" in ddl
        assert "DEFAULT ''6''" not in ddl
