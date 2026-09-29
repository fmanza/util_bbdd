"""``mysql`` como motor propio: escape de ``%`` (T1), validador, registros por motor y catálogo de queries."""

from __future__ import annotations

import pytest

from util_bbdd._drivers import get_supported_db_types
from util_bbdd.core.capabilities import is_async_supported
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.managers._manager_storage import (
    get_async_storage_inventory_strategy,
    get_sync_storage_inventory_strategy,
)
from util_bbdd.managers._metadata_context import MetadataContextResolver
from util_bbdd.query import DatabaseQueries
from util_bbdd.validators import get_type_validator

EXECUTORS = [SyncQueryExecutor, AsyncQueryExecutor]


@pytest.mark.parametrize("executor", EXECUTORS, ids=lambda e: e.__name__)
class TestPercentEscapingForMySQL:
    """T1: PyMySQL/aiomysql solo formatean con ``%`` cuando reciben parámetros."""

    def test_without_params_sql_is_untouched(self, executor: type) -> None:
        sql = "SELECT 1 FROM t WHERE c LIKE 'FK_%'"
        assert executor._normalize_sql_for_db(sql, "mysql", {}) == sql
        assert executor._normalize_sql_for_db(sql, "mysql") == sql

    def test_with_params_escapes_only_literal_percent(self, executor: type) -> None:
        sql = "SELECT %(x)s, %s FROM t WHERE c LIKE 'a%' AND d = '100%%'"
        normalized = executor._normalize_sql_for_db(sql, "mysql", {"x": 1})
        assert normalized == "SELECT %(x)s, %s FROM t WHERE c LIKE 'a%%' AND d = '100%%'"

    def test_params_not_used_by_sql_do_not_escape(self, executor: type) -> None:
        sql = "SELECT 1 FROM t WHERE c LIKE 'a%'"
        assert executor._normalize_sql_for_db(sql, "mysql", {"unused": 1}) == sql

    def test_mariadb_behaviour_is_unchanged(self, executor: type) -> None:
        assert executor._normalize_sql_for_db("LIKE 'a%'", "mariadb") == "LIKE 'a%%'"
        assert executor._normalize_sql_for_db("LIKE 'a%'", "mariadb", {"x": 1}) == "LIKE 'a%%'"


class TestMySQLRegistration:
    def test_supported_and_async_capable(self) -> None:
        assert "mysql" in get_supported_db_types()
        assert is_async_supported("mysql") is True

    def test_validator_is_mysql(self) -> None:
        validator = get_type_validator("mysql")
        assert validator.db_type == "mysql"
        assert type(validator).__name__ == "MySQLValidator"

    def test_query_catalog_loads_for_mysql(self) -> None:
        queries = DatabaseQueries("mysql")
        assert set(queries.registry.get_available_queries("mysql")) == set(
            queries.registry.get_available_queries("mariadb")
        )
        assert "INFORMATION_SCHEMA" in queries.get_query("claves_primarias", tabla="t").upper()

    def test_storage_strategies_registered(self) -> None:
        assert type(get_sync_storage_inventory_strategy("mysql")) is type(
            get_sync_storage_inventory_strategy("mariadb")
        )
        assert type(get_async_storage_inventory_strategy("mysql")) is type(
            get_async_storage_inventory_strategy("mariadb")
        )

    def test_metadata_context_does_not_add_schema_params(self) -> None:
        assert MetadataContextResolver.add_context_params(db_type="mysql", params={"tabla": "t"}, context="db1") == {
            "tabla": "t"
        }
