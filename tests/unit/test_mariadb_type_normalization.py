"""Tests de regresión: MariaDB normaliza tipos de columna a genérico [MEO-07].

Antes de este fix, MariaDB no tenía ninguna función de normalización de tipos
propia: MariaDBSyncAdapter/AsyncAdapter.fetch_columns_sync/async exponían el
tipo nativo crudo de information_schema.COLUMNS.COLUMN_TYPE (p.ej.
"varchar(255)") como `column_type`, a diferencia del resto de motores (mysql,
postgresql, sqlserver, oracle, sqlite), que devuelven un tipo genérico
normalizado ("varchar"). MySQL tampoco tenía mapeo para BIT (caía al
fallback "object").
"""

from __future__ import annotations

from util_bbdd.metadata.mariadb.common import mariadb_type_mapping, normalize_mariadb_type


class TestMariaDBTypeMapping:
    def test_type_mapping_returns_dict(self) -> None:
        mapping = mariadb_type_mapping()
        assert isinstance(mapping, dict)
        assert len(mapping) >= 40

    def test_type_mapping_contains_bit(self) -> None:
        mapping = mariadb_type_mapping()
        assert mapping["BIT"] == "bit"

    def test_type_mapping_matches_mysql_conventions(self) -> None:
        mapping = mariadb_type_mapping()
        assert mapping["INT"] == "integer"
        assert mapping["VARCHAR"] == "varchar"
        assert mapping["BIGINT"] == "bigint"


class TestNormalizeMariaDBType:
    def test_normalize_varchar_with_length(self) -> None:
        assert normalize_mariadb_type("varchar(255)") == "varchar"

    def test_normalize_int_with_display_width(self) -> None:
        assert normalize_mariadb_type("int(11)") == "integer"

    def test_normalize_decimal_with_precision(self) -> None:
        assert normalize_mariadb_type("decimal(10,2)") == "decimal"

    def test_normalize_bit(self) -> None:
        assert normalize_mariadb_type("bit(1)") == "bit"

    def test_normalize_unknown_type_returns_object(self) -> None:
        assert normalize_mariadb_type("some_unknown_type") == "object"

    def test_normalize_empty_returns_object(self) -> None:
        assert normalize_mariadb_type("") == "object"
