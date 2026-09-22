"""Tests de regresión: Oracle normaliza schema/table/routine a mayúsculas antes de bindear [MEO-04].

Antes de este fix, los adaptadores Oracle bindeaban `schema`/`table`/`routine` tal
cual en `:owner`/`:table_name`/`:routine_name`. Los diccionarios de datos Oracle
(ALL_TABLES.OWNER, ALL_TAB_COLUMNS.TABLE_NAME, etc.) almacenan los nombres en
MAYÚSCULAS por defecto; un input en minúsculas devolvía 0 filas silenciosamente,
sin ningún error.
"""

from __future__ import annotations

import asyncio

from unittest.mock import MagicMock

from util_bbdd.metadata.oracle.async_adapter import OracleAsyncAdapter
from util_bbdd.metadata.oracle.common import normalize_oracle_bind_identifier
from util_bbdd.metadata.oracle.sync_adapter import OracleSyncAdapter


class TestNormalizeOracleBindIdentifier:
    def test_lowercase_becomes_uppercase(self) -> None:
        assert normalize_oracle_bind_identifier("myschema") == "MYSCHEMA"

    def test_mixed_case_becomes_uppercase(self) -> None:
        assert normalize_oracle_bind_identifier("MySchema") == "MYSCHEMA"

    def test_already_uppercase_unchanged(self) -> None:
        assert normalize_oracle_bind_identifier("MYSCHEMA") == "MYSCHEMA"

    def test_none_preserved(self) -> None:
        assert normalize_oracle_bind_identifier(None) is None

    def test_empty_string_preserved(self) -> None:
        assert normalize_oracle_bind_identifier("") == ""


class TestOracleSyncAdapterNormalizesLowercaseInputs:
    def test_fetch_tables_sync_uppercases_schema(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_tables_sync("myschema")

        params = manager.execute_custom_many.call_args[1]["params"]
        assert params["owner"] == "MYSCHEMA"

    def test_fetch_columns_sync_uppercases_schema_and_table(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_columns_sync("myschema", "users")

        params = manager.execute_custom_many.call_args[1]["params"]
        assert params["owner"] == "MYSCHEMA"
        assert params["table_name"] == "USERS"

    def test_fetch_primary_keys_sync_uppercases_schema_and_table(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_primary_keys_sync("myschema", "users")

        params = manager.execute_custom_many.call_args[1]["params"]
        assert params["owner"] == "MYSCHEMA"
        assert params["table_name"] == "USERS"

    def test_fetch_foreign_keys_sync_uppercases_schema_and_table(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_foreign_keys_sync("myschema", "orders")

        params = manager.execute_custom_many.call_args[1]["params"]
        assert params["owner"] == "MYSCHEMA"
        assert params["table_name"] == "ORDERS"

    def test_fetch_indexes_sync_uppercases_schema_and_table(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_indexes_sync("myschema", "orders")

        params = manager.execute_custom_many.call_args[1]["params"]
        assert params["owner"] == "MYSCHEMA"
        assert params["table_name"] == "ORDERS"

    def test_fetch_routine_definition_sync_uppercases_schema_and_routine(self) -> None:
        manager = MagicMock()
        cursor_result = []
        manager.execute_custom_many.return_value = cursor_result
        adapter = OracleSyncAdapter(manager)

        adapter.fetch_routine_definition_sync("myschema", "my_proc", "PROCEDURE")

        params = manager.execute_custom_many.call_args[1]["params"]
        assert params["owner"] == "MYSCHEMA"
        assert params["routine_name"] == "MY_PROC"


class TestOracleAsyncAdapterNormalizesLowercaseInputs:
    def test_fetch_tables_async_uppercases_schema(self) -> None:
        manager = MagicMock()

        async def _execute_custom_many(sql, params=None):
            return []

        manager.execute_custom_many = _execute_custom_many
        adapter = OracleAsyncAdapter(manager)

        captured = {}

        async def _execute_and_capture(sql, params=None):
            captured["params"] = params
            return []

        manager.execute_custom_many = _execute_and_capture

        asyncio.run(adapter.fetch_tables_async("myschema"))

        assert captured["params"]["owner"] == "MYSCHEMA"

    def test_fetch_columns_async_uppercases_schema_and_table(self) -> None:
        manager = MagicMock()
        captured = {}

        async def _execute_and_capture(sql, params=None):
            captured["params"] = params
            return []

        manager.execute_custom_many = _execute_and_capture
        adapter = OracleAsyncAdapter(manager)

        asyncio.run(adapter.fetch_columns_async("myschema", "users"))

        assert captured["params"]["owner"] == "MYSCHEMA"
        assert captured["params"]["table_name"] == "USERS"
