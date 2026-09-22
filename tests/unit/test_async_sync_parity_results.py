"""Tests de paridad de resultados normalizados entre ejecutores sync y async."""

from __future__ import annotations

import tempfile

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query import QueryRegistry


@pytest.fixture
def temp_queries_file() -> Generator[Path, None, None]:
    import json

    queries_data = {
        "mariadb": {
            "obtener_tablas": "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = {database}",
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(queries_data, f)
        temp_path = f.name

    yield Path(temp_path)
    Path(temp_path).unlink()


class TestAsyncSyncParityResults:
    def test_execute_query_many_normalizes_to_list_in_sync(self, temp_queries_file: Path) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = (("users",), ("orders",))
        mock_conn.cursor.return_value = mock_cursor

        executor = SyncQueryExecutor(
            connection_provider=MagicMock(return_value=mock_conn),
            connection_releaser=MagicMock(),
            registry=QueryRegistry(temp_queries_file),
        )

        result = executor.execute_query_many("obtener_tablas", "mariadb", {"database": "db"})

        assert isinstance(result, list)
        assert result == [("users",), ("orders",)]

    @pytest.mark.asyncio
    async def test_execute_query_many_normalizes_to_list_in_async(self, temp_queries_file: Path) -> None:
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = (("users",), ("orders",))
        mock_conn.cursor.return_value = mock_cursor

        executor = AsyncQueryExecutor(
            connection_provider=AsyncMock(return_value=mock_conn),
            connection_releaser=AsyncMock(),
            registry=QueryRegistry(temp_queries_file),
        )

        result = await executor.execute_query_many("obtener_tablas", "mariadb", {"database": "db"})

        assert isinstance(result, list)
        assert result == [("users",), ("orders",)]

    @pytest.mark.asyncio
    async def test_execute_query_one_normalizes_to_tuple_in_both_modes(self, temp_queries_file: Path) -> None:
        sync_conn = MagicMock()
        sync_cursor = MagicMock()
        sync_cursor.fetchone.return_value = ["users"]
        sync_conn.cursor.return_value = sync_cursor
        sync_executor = SyncQueryExecutor(
            connection_provider=MagicMock(return_value=sync_conn),
            connection_releaser=MagicMock(),
            registry=QueryRegistry(temp_queries_file),
        )

        async_conn = AsyncMock()
        async_cursor = AsyncMock()
        async_cursor.fetchone.return_value = ["users"]
        async_conn.cursor.return_value = async_cursor
        async_executor = AsyncQueryExecutor(
            connection_provider=AsyncMock(return_value=async_conn),
            connection_releaser=AsyncMock(),
            registry=QueryRegistry(temp_queries_file),
        )

        sync_result = sync_executor.execute_query_one("obtener_tablas", "mariadb", {"database": "db"})
        async_result = await async_executor.execute_query_one("obtener_tablas", "mariadb", {"database": "db"})

        assert sync_result == ("users",)
        assert async_result == ("users",)
        assert type(sync_result) is type(async_result)


class TestNormalizeSqlForDbParity:
    """SVC-03 (AUDIT_CODE 2026-09-22): el escape de ``%`` literales para MariaDB
    (paramstyle pyformat) existía solo en AsyncQueryExecutor; SyncQueryExecutor
    ejecutaba el SQL sin escapar, arriesgando que un LIKE con wildcard `%` fuera
    malinterpretado por el driver DBAPI como un placeholder de formato."""

    def test_mariadb_doubles_literal_percent(self) -> None:
        sql = "SELECT * FROM users WHERE name LIKE '%test%'"
        assert (
            SyncQueryExecutor._normalize_sql_for_db(sql, "mariadb") == "SELECT * FROM users WHERE name LIKE '%%test%%'"
        )
        assert (
            AsyncQueryExecutor._normalize_sql_for_db(sql, "mariadb") == "SELECT * FROM users WHERE name LIKE '%%test%%'"
        )

    def test_non_mariadb_leaves_sql_unchanged(self) -> None:
        sql = "SELECT * FROM users WHERE name LIKE '%test%'"
        for db_type in ("oracle", "postgresql", "sqlserver", "sqlite"):
            assert SyncQueryExecutor._normalize_sql_for_db(sql, db_type) == sql
            assert AsyncQueryExecutor._normalize_sql_for_db(sql, db_type) == sql

    def test_sync_and_async_normalization_are_identical(self) -> None:
        sql = "SELECT * FROM t WHERE a LIKE '%foo%' AND b LIKE '%bar%'"
        for db_type in ("mariadb", "oracle", "postgresql", "sqlserver", "sqlite"):
            assert SyncQueryExecutor._normalize_sql_for_db(sql, db_type) == AsyncQueryExecutor._normalize_sql_for_db(
                sql, db_type
            )

    def test_execute_resolved_applies_normalization_before_cursor_execute(self, temp_queries_file: Path) -> None:
        """Verifica que la normalización se aplica de verdad en el flujo real de ejecución."""
        import json
        import tempfile

        queries_data = {"mariadb": {"buscar": "SELECT * FROM users WHERE name LIKE '%test%'"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(queries_data, f)
            registry_path = Path(f.name)

        try:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = ()
            mock_conn.cursor.return_value = mock_cursor

            executor = SyncQueryExecutor(
                connection_provider=MagicMock(return_value=mock_conn),
                connection_releaser=MagicMock(),
                registry=QueryRegistry(registry_path),
            )
            executor.execute_query_many("buscar", "mariadb", {})

            executed_sql = mock_cursor.execute.call_args[0][0]
            assert "%%test%%" in executed_sql
        finally:
            registry_path.unlink()
