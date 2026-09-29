"""``mysql`` en metadatos y consumidores: delegación del adapter, estrategias y paridad con ``mariadb``.

MySQL comparte con MariaDB el catálogo de queries y la forma de sus filas, así que cada consumidor debe tratar
``mysql`` exactamente igual que ``mariadb``.
"""

from __future__ import annotations

import asyncio
import json

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.doc.infrastructure.renderers.shared.generator_shared import GeneratorTabularRuntime
from util_bbdd.doc.infrastructure.runtime.headers_runtime import DocumentationHeadersRuntime
from util_bbdd.doc.infrastructure.storage.runtime import StorageInventoryRuntime
from util_bbdd.managers._manager_metadata_runtime import MariaDBMetadataFetchStrategy, get_metadata_fetch_strategy
from util_bbdd.metadata.mysql import MysqlAsyncAdapter, MysqlSyncAdapter
from util_bbdd.query import DatabaseQueries
from util_bbdd.query._documentation import (
    _get_temp_storage_variables_examples,
    _get_temp_tablespaces_example,
)

HEADERS_FILE = Path(__file__).resolve().parents[2] / "src/util_bbdd/doc/data/headers_config.json"


class TestMysqlAdapterDelegation:
    def test_columns_safe_uses_hex_query_through_manager(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        assert MysqlSyncAdapter(manager).fetch_columns_safe("db1", "t1") == []
        sql, params = manager.execute_custom_many.call_args.args
        assert "HEX(COLUMN_NAME)" in sql
        assert params == {"schema": "db1", "table": "t1"}

    def test_storage_inventory_uses_catalog_queries(self) -> None:
        manager = MagicMock()
        manager.execute_query_many.side_effect = lambda name, **_: [(name,)]
        result = MysqlSyncAdapter(manager).storage_inventory("db1")
        assert result == {"primary": [("ficheros_fisicos",)], "temp_tablespaces": [("temp_tablespaces",)]}

    def test_view_ddl_is_built_from_information_schema(self) -> None:
        manager = MagicMock()
        manager.execute_custom_one.return_value = ("select 1 AS `a`",)
        ddl = MysqlSyncAdapter(manager).fetch_view_from_information_schema("db1", "v1")
        assert ddl == "CREATE OR REPLACE VIEW `v1` AS\nselect 1 AS `a`"

    def test_reader_is_reused(self) -> None:
        adapter = MysqlSyncAdapter(MagicMock())
        assert adapter._engine_metadata() is adapter._engine_metadata()

    def test_async_columns_safe_delegates(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many = AsyncMock(return_value=[])
        assert asyncio.run(MysqlAsyncAdapter(manager).fetch_columns_safe("db1", "t1")) == []
        manager.execute_custom_many.assert_awaited_once()


class TestMysqlFollowsMariaDBInConsumers:
    def test_metadata_fetch_strategy_is_specialized(self) -> None:
        assert isinstance(get_metadata_fetch_strategy("mysql"), MariaDBMetadataFetchStrategy)

    def test_query_catalog_context_and_strategies(self) -> None:
        mysql, mariadb = DatabaseQueries("mysql"), DatabaseQueries("mariadb")
        assert mysql._build_context_kwargs("db1") == {}
        assert mysql.get_storage_inventory_queries("db1", None) == mariadb.get_storage_inventory_queries("db1", None)
        assert mysql._get_routine_ddl_strategy()("r", "PROCEDURE", "db1") == mariadb._get_routine_ddl_strategy()(
            "r", "PROCEDURE", "db1"
        )

    def test_query_documentation_examples(self) -> None:
        assert _get_temp_storage_variables_examples("mysql")
        assert "MySQL" in _get_temp_tablespaces_example("mysql")["description"]

    def test_headers_match_mariadb(self) -> None:
        runtime = DocumentationHeadersRuntime()
        config: Any = json.loads(HEADERS_FILE.read_text(encoding="utf-8"))
        assert runtime.build_headers(config, "mysql") == runtime.build_headers(config, "mariadb")

    @pytest.mark.parametrize("db_type", ["mysql", "mariadb"])
    def test_tabular_runtime_treats_mysql_like_mariadb(self, db_type: str) -> None:
        indices = [("ix", "col", 1, "BTREE")]
        fks = [("fk", "t", "col", "parent", "id")]
        assert GeneratorTabularRuntime.process_indices_data(indices, db_type) == [["ix", "col", "No", "BTREE"]]
        assert GeneratorTabularRuntime.get_flat_column_indexes(db_type) == list(range(7))
        assert GeneratorTabularRuntime.map_foreign_keys_by_column(foreign_keys=fks, db_type=db_type, arrow="->") == {
            "col": "fk -> parent(id)"
        }
        assert GeneratorTabularRuntime.map_indices_by_column(indices=indices, db_type=db_type) == {"col": ["ix"]}

    def test_storage_runtime_has_dedicated_mysql_strategy(self) -> None:
        manager = MagicMock()
        runtime = StorageInventoryRuntime(
            db_manager=manager, logger=MagicMock(), db_type="mysql", database="db1", print_config={}
        )
        assert runtime._uses_generic_storage_fallback() is False
        assert [name for name, _ in runtime._build_storage_query_specs()] == [
            "ficheros_fisicos",
            "temp_tablespaces",
            "temp_storage_variables",
        ]
        assert runtime._get_storage_headers_by_query("ficheros_fisicos")[0] == "DB"
