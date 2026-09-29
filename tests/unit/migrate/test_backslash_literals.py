"""A4 (hotfix 2026-09-29): barras invertidas en literales de la familia MySQL/MariaDB.

- Destino MariaDB/MySQL: en sus literales la barra escapa; ``'C:\\datos'`` llegaba como ``C:datos``.
- Origen MariaDB: ``COLUMN_DEFAULT`` devuelve el literal con escapes (``'C:\\\\datos'``, ``\\n``); sin decodificarlo
  llegaba duplicado a PostgreSQL, SQL Server y Oracle (y el arreglo del emisor lo habría duplicado hacia MySQL).
"""

from __future__ import annotations

import pytest

from util_bbdd.migrate._compat.default_normalizer import normalize_default
from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter, _format_default
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable


class TestMariaDBSourceLiterals:
    @pytest.mark.parametrize(
        ("catalog", "canonical"),
        [
            (r"'C:\\datos\\x'", r"'C:\datos\x'"),
            (r"'a\nb\tc'", "'a\nb\tc'"),
            ("'it''s'", "'it''s'"),
            (r"'it\'s'", "'it''s'"),
            (r"'100\%'", r"'100\%'"),
            ("'sin escapes'", "'sin escapes'"),
        ],
    )
    def test_catalog_literal_is_decoded(self, catalog: str, canonical: str) -> None:
        assert normalize_default("mariadb", catalog) == canonical

    @pytest.mark.parametrize("value", ["5", "NULL", "concat('a','b')", "'a' 'b'", "uuid()"])
    def test_non_literals_are_unchanged(self, value: str) -> None:
        assert normalize_default("mariadb", value) == value

    def test_other_sources_are_not_decoded(self) -> None:
        # MySQL devuelve el valor sin comillas (el extractor lo entrecomilla ya canónico); PostgreSQL usa cadenas
        # estándar: la barra es un carácter más.
        assert normalize_default("postgresql", r"'C:\datos'::character varying") == r"'C:\datos'"
        assert normalize_default("oracle", r"'C:\datos'") == r"'C:\datos'"


class TestMariaDBTargetLiterals:
    def test_quoted_default_escapes_backslash(self) -> None:
        assert _format_default(r"'C:\datos\x''q'") == r"'C:\\datos\\x''q'"

    def test_unquoted_default_escapes_backslash_and_quote(self) -> None:
        assert _format_default(r"C:\x'q") == r"'C:\\x''q'"

    def test_comments_escape_backslash(self) -> None:
        column = CanonicalColumn(
            name="ruta",
            original_name="ruta",
            oracle_type="VARCHAR2",
            target_type="VARCHAR(80)",
            nullable=True,
            default=None,
            comment=r"C:\ruta'x",
            ordinal=1,
        )
        table = CanonicalTable(
            name="t",
            original_name="t",
            schema="s",
            columns=[column],
            primary_key=[],
            indexes=[],
            foreign_keys=[],
            comment=r"tabla C:\y",
            warnings=[],
        )
        [ddl] = MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_bin").emit_statements([table])
        assert r"COMMENT 'C:\\ruta''x'" in ddl
        assert r"COMMENT='tabla C:\\y'" in ddl

    def test_round_trip_mariadb_to_mysql_keeps_the_catalog_literal(self) -> None:
        # Mismo valor: la barra vuelve escapada y el salto de línea va literal dentro de las comillas (válido en MySQL).
        catalog = r"'C:\\datos\nfin''q'"
        assert _format_default(normalize_default("mariadb", catalog) or "") == "'C:\\\\datos\nfin''q'"
