"""Tests para verificar contrato unificado sync/async"""

import tempfile

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query import QueryRegistry


@pytest.fixture
def queries_data():
    """Crea datos de queries para testing"""
    return {
        "mariadb": {
            "obtener_tablas": "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = {database}",
        },
    }


@pytest.fixture
def temp_queries_file(queries_data):
    """Crea un archivo temporal con queries de test"""
    import json

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(queries_data, f)
        temp_path = f.name

    yield Path(temp_path)

    # Cleanup
    Path(temp_path).unlink()


class TestSyncAsyncContract:
    """Verifica que sync y async implementan el mismo contrato"""

    def test_same_resolver_output_sync(self, temp_queries_file):
        """Sync executor usa QueryResolver correctamente"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("table1",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        executor.execute_query_many("obtener_tablas", "mariadb", {"database": "mydatabase"})

        # Verificar que el SQL contiene el parámetro interpolado
        call_args = mock_cursor.execute.call_args
        executed_sql = call_args[0][0]
        assert "mydatabase" in executed_sql

    @pytest.mark.asyncio
    async def test_same_resolver_output_async(self, temp_queries_file):
        """Async executor usa QueryResolver correctamente (igual que sync)"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("table1",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        await executor.execute_query_many("obtener_tablas", "mariadb", {"database": "mydatabase"})

        # Verificar que el SQL contiene el parámetro interpolado
        call_args = mock_cursor.execute.call_args
        executed_sql = call_args[0][0]
        assert "mydatabase" in executed_sql

    def test_sync_return_types_match(self, temp_queries_file):
        """Sync executor retorna tipos correctos"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("table1",), ("table2",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test"})

        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_async_return_types_match(self, temp_queries_file):
        """Async executor retorna tipos correctos (igual que sync)"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("table1",), ("table2",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        result = await executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test"})

        assert isinstance(result, list)
        assert len(result) == 2

    def test_sync_one_behavior(self, temp_queries_file):
        """Sync executor con execute_query_one retorna tuple"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("table1",)
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test"})

        assert isinstance(result, tuple)

    @pytest.mark.asyncio
    async def test_async_one_behavior(self, temp_queries_file):
        """Async executor con execute_query_one retorna tuple (igual que sync)"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = ("table1",)
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        result = await executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test"})

        assert isinstance(result, tuple)
