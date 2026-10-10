"""Tests para AsyncQueryExecutor (contrato)"""

import asyncio

from unittest.mock import AsyncMock

import pytest

from util_bbdd.exceptions import DatabaseOperationError, QueryNotFoundError, QueryTimeoutError, QueryValidationError
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.query import QueryRegistry


@pytest.fixture(scope="module")
def queries_data():
    """Crea datos de queries para testing"""
    return {
        "mariadb": {
            "obtener_tablas": "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = {database}",
            "obtener_usuarios": "SELECT * FROM users WHERE id = {id}",
        },
        "postgresql": {
            "obtener_tablas": "SELECT table_name FROM information_schema.tables WHERE table_schema = {schema}",
        },
    }


@pytest.fixture(scope="module")
def temp_queries_file(queries_data, tmp_path_factory: pytest.TempPathFactory):
    """Crea un archivo temporal con queries de test"""
    import json

    temp_path = tmp_path_factory.mktemp("async_executor_contract") / "async_executor_queries.json"
    temp_path.write_text(json.dumps(queries_data), encoding="utf-8")
    return temp_path


class TestAsyncExecutorBasics:
    """Pruebas básicas del AsyncQueryExecutor"""

    @pytest.mark.asyncio
    async def test_executor_init(self, temp_queries_file):
        """Inicializa AsyncQueryExecutor correctamente"""
        provider = AsyncMock()
        releaser = AsyncMock()
        registry = QueryRegistry(temp_queries_file)

        executor = AsyncQueryExecutor(provider, releaser, registry)

        assert executor is not None
        assert executor.connection_provider == provider
        assert executor.connection_releaser == releaser

    @pytest.mark.asyncio
    async def test_execute_query_by_name(self, temp_queries_file):
        """Test ejecución async de query por nombre"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("table1",), ("table2",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        result = await executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == [("table1",), ("table2",)]
        releaser.assert_called_once_with(mock_conn)

    @pytest.mark.asyncio
    async def test_execute_custom_one(self, temp_queries_file):
        """Test ejecución de SQL custom async"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = ("value",)
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        result = await executor.execute_custom_one("SELECT 1")

        assert result == ("value",)
        releaser.assert_called_once_with(mock_conn)


class TestAsyncExecutorErrorHandling:
    """Pruebas de manejo de errores en AsyncQueryExecutor"""

    @pytest.mark.asyncio
    async def test_connection_released_on_error(self, temp_queries_file):
        """Test que conexión se libera aunque haya error"""
        mock_conn = AsyncMock()
        mock_conn.cursor.side_effect = RuntimeError("DB error")

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(DatabaseOperationError):
            await executor.execute_custom_many("SELECT 1")

        releaser.assert_called_once_with(mock_conn)

    @pytest.mark.asyncio
    async def test_query_not_found_error(self, temp_queries_file):
        """Test error cuando query no existe"""
        provider = AsyncMock()
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(QueryNotFoundError):
            await executor.execute_query_many("query_inexistente", "mariadb", {})

    @pytest.mark.asyncio
    async def test_missing_required_param_error(self, temp_queries_file):
        """Test error cuando falta parámetro requerido"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(QueryValidationError):
            await executor.execute_query_many("obtener_tablas", "mariadb", {})


class TestAsyncExecutorFetchOptions:
    """Pruebas de contrato explícito one vs many."""

    @pytest.mark.asyncio
    async def test_execute_query_one(self, temp_queries_file):
        """Test execute_query_one retorna un registro"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = ("table1",)
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        result = await executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == ("table1",)
        mock_cursor.fetchone.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_many(self, temp_queries_file):
        """Test execute_query_many retorna todos los registros"""
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("table1",), ("table2",), ("table3",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        result = await executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == [("table1",), ("table2",), ("table3",)]
        mock_cursor.fetchall.assert_called_once()


class TestAsyncExecutorTimeout:
    """Pruebas de timeout en async"""

    @pytest.mark.asyncio
    async def test_timeout_during_execution(self, temp_queries_file):
        """Test que se lanza QueryTimeoutError cuando se excede timeout"""
        blocker = asyncio.Event()

        # Create a mock that blocks until cancellation by timeout
        async def mock_provider():
            await asyncio.sleep(0)
            conn = AsyncMock()
            cursor = AsyncMock()

            async def blocking_execute(*_args, **_kwargs):
                await blocker.wait()

            cursor.execute = blocking_execute
            cursor.fetchall = AsyncMock(return_value=[])
            conn.cursor = AsyncMock(return_value=cursor)
            return conn

        async def mock_releaser(conn):
            await asyncio.sleep(0)

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(mock_provider, mock_releaser, registry)

        with pytest.raises(QueryTimeoutError):
            await executor.execute_custom_many("SELECT 1", deadline_seconds=0.1)


class TestAsyncExecutorMetadata:
    """Pruebas de logging y metadata de ejecución"""

    @pytest.mark.asyncio
    async def test_logging_on_success(self, temp_queries_file, caplog):
        """Test que se loguea exitosamente"""
        import logging

        caplog.set_level(logging.DEBUG)

        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("table1",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        await executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"})

        # Verificar que hay logs de debug
        assert any("Query executed" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_custom_query_logging(self, temp_queries_file, caplog):
        """Test logging en custom query"""
        import logging

        caplog.set_level(logging.DEBUG)

        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        provider = AsyncMock(return_value=mock_conn)
        releaser = AsyncMock()

        registry = QueryRegistry(temp_queries_file)
        executor = AsyncQueryExecutor(provider, releaser, registry)

        await executor.execute_custom_many("SELECT 1")

        assert any("custom query" in record.message.lower() for record in caplog.records)
