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

import asyncio

from unittest.mock import MagicMock

from util_bbdd.metadata.mariadb.async_adapter import MariaDBAsyncAdapter
from util_bbdd.metadata.mariadb.common import mariadb_type_mapping, normalize_mariadb_type
from util_bbdd.metadata.mariadb.sync_adapter import MariaDBSyncAdapter


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


class TestMariaDBSyncAdapterNormalizesColumnType:
    def test_fetch_columns_sync_returns_generic_type_not_raw(self) -> None:
        manager = MagicMock()
        manager.get_columns.return_value = [
            ("id", "int(11)", "NO", "PRI", None, "auto_increment", ""),
            ("name", "varchar(255)", "YES", "", None, "", "Nombre"),
        ]
        adapter = MariaDBSyncAdapter(manager)

        result = adapter.fetch_columns_sync("ignored_schema", "users")

        assert result[0][0] == "id"
        assert result[0][1] == "integer"
        assert result[1][0] == "name"
        assert result[1][1] == "varchar"

    def test_fetch_columns_sync_preserves_rest_of_row(self) -> None:
        manager = MagicMock()
        manager.get_columns.return_value = [
            ("id", "int(11)", "NO", "PRI", None, "auto_increment", ""),
        ]
        adapter = MariaDBSyncAdapter(manager)

        result = adapter.fetch_columns_sync("ignored_schema", "users")

        assert result[0] == ("id", "integer", "NO", "PRI", None, "auto_increment", "")

    def test_fetch_columns_sync_handles_short_rows_gracefully(self) -> None:
        """Filas con un solo elemento (sin tipo) no deben romper la normalización."""
        manager = MagicMock()
        manager.get_columns.return_value = [("COL1",)]
        adapter = MariaDBSyncAdapter(manager)

        result = adapter.fetch_columns_sync("ignored_schema", "users")

        assert result == [("COL1",)]


class TestMariaDBAsyncAdapterNormalizesColumnType:
    def test_fetch_columns_async_returns_generic_type_not_raw(self) -> None:
        async def _get_columns(table: str) -> list[tuple]:
            await asyncio.sleep(0)
            return [("id", "int(11)", "NO", "PRI", None, "auto_increment", "")]

        manager = MagicMock()
        manager.get_columns = _get_columns
        adapter = MariaDBAsyncAdapter(manager)

        result = asyncio.run(adapter.fetch_columns_async("ignored_schema", "users"))

        assert result[0][1] == "integer"
