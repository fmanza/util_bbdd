"""Tests para SyncQueryExecutor (contrato)"""

import tempfile

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from util_bbdd.database_exceptions import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query_registry import QueryRegistry


@pytest.fixture
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


class TestSyncExecutorBasics:
    """Pruebas básicas del SyncQueryExecutor"""

    def test_executor_init(self, temp_queries_file):
        """Inicializa SyncQueryExecutor correctamente"""
        provider = MagicMock()
        releaser = MagicMock()
        registry = QueryRegistry(temp_queries_file)

        executor = SyncQueryExecutor(provider, releaser, registry)

        assert executor is not None
        assert executor.connection_provider == provider
        assert executor.connection_releaser == releaser

    def test_execute_query_by_name(self, temp_queries_file):
        """Test ejecución de query por nombre"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("table1",), ("table2",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == [("table1",), ("table2",)]
        releaser.assert_called_once_with(mock_conn)

    def test_execute_custom_one(self, temp_queries_file):
        """Test ejecución de SQL custom"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("value",)
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_custom_one("SELECT 1")

        assert result == ("value",)
        releaser.assert_called_once_with(mock_conn)


class TestSyncExecutorErrorHandling:
    """Pruebas de manejo de errores en SyncQueryExecutor"""

    def test_connection_released_on_error(self, temp_queries_file):
        """Test que conexión se libera aunque haya error"""
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = RuntimeError("DB error")

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(DatabaseOperationError):
            executor.execute_custom_many("SELECT 1")

        releaser.assert_called_once_with(mock_conn)

    def test_query_not_found_error(self, temp_queries_file):
        """Test error cuando query no existe"""
        provider = MagicMock()
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(QueryNotFoundError):
            executor.execute_query_many("query_inexistente", "mariadb", {})

    def test_missing_required_param_error(self, temp_queries_file):
        """Test error cuando falta parámetro requerido"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(QueryValidationError):
            executor.execute_query_many("obtener_tablas", "mariadb", {})


class TestSyncExecutorFetchOptions:
    """Pruebas de contrato explícito one vs many."""

    def test_execute_query_one(self, temp_queries_file):
        """Test execute_query_one retorna un registro"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("table1",)
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == ("table1",)
        mock_cursor.fetchone.assert_called_once()

    def test_execute_query_many(self, temp_queries_file):
        """Test execute_query_many retorna todos los registros"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("table1",), ("table2",), ("table3",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == [("table1",), ("table2",), ("table3",)]
        mock_cursor.fetchall.assert_called_once()

    def test_execute_query_one_mariadb_decode_fallback_uses_binary_cursor(self, temp_queries_file):
        """Si fetchone falla por decode en MariaDB, reintenta en cursor binario."""
        text_cursor = MagicMock()
        binary_cursor = MagicMock()
        text_cursor.fetchone.side_effect = UnicodeDecodeError(
            "utf-8",
            b"\xd3",
            0,
            1,
            "invalid continuation byte",
        )
        binary_cursor.fetchone.return_value = (b"CREATE TABLE t (\xd3)",)

        mock_conn = MagicMock()

        def _cursor_factory(*args, **kwargs):
            if kwargs.get("binary") is True:
                return binary_cursor
            return text_cursor

        mock_conn.cursor.side_effect = _cursor_factory

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == ("CREATE TABLE t (Ó)",)
        assert mock_conn.cursor.call_count == 2
        binary_cursor.close.assert_called_once()
        releaser.assert_called_once_with(mock_conn)

    def test_execute_query_one_mariadb_wrapped_decode_error_uses_binary_cursor(self, temp_queries_file):
        """Reintenta también cuando fetchone lanza SystemError con causa UnicodeDecodeError."""
        text_cursor = MagicMock()
        binary_cursor = MagicMock()

        def _broken_fetchone():
            try:
                raise UnicodeDecodeError("utf-8", b"\xd3", 0, 1, "invalid continuation byte")
            except UnicodeDecodeError as decode_err:
                raise SystemError(
                    "<method 'fetchone' of 'mariadb.cursor' objects> returned a result with an exception set"
                ) from decode_err

        text_cursor.fetchone.side_effect = _broken_fetchone
        binary_cursor.fetchone.return_value = (b"CREATE TABLE t (\xd3)",)

        mock_conn = MagicMock()

        def _cursor_factory(*args, **kwargs):
            if kwargs.get("binary") is True:
                return binary_cursor
            return text_cursor

        mock_conn.cursor.side_effect = _cursor_factory

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == ("CREATE TABLE t (Ó)",)
        assert mock_conn.cursor.call_count == 2
        binary_cursor.close.assert_called_once()
        releaser.assert_called_once_with(mock_conn)


class TestSyncExecutorTimeout:
    """Pruebas de timeout en sync"""

    def test_timeout_during_execute_query_many(self, temp_queries_file):
        """Lanza QueryTimeoutError cuando execute_query_many excede timeout."""
        import time

        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def slow_execute(sql, params):
            time.sleep(0.05)

        mock_cursor.execute.side_effect = slow_execute
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(QueryTimeoutError):
            executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"}, timeout=0.01)

        releaser.assert_called_once_with(mock_conn)

    def test_timeout_during_execute_custom_many(self, temp_queries_file):
        """Lanza QueryTimeoutError cuando execute_custom_many excede timeout."""
        import time

        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def slow_execute(sql, params):
            time.sleep(0.05)

        mock_cursor.execute.side_effect = slow_execute
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(QueryTimeoutError):
            executor.execute_custom_many("SELECT 1", timeout=0.01)

        releaser.assert_called_once_with(mock_conn)


class TestSyncExecutorMetadata:
    """Pruebas de logging y metadata de ejecución"""

    def test_logging_on_success(self, temp_queries_file, caplog):
        """Test que se loguea exitosamente"""
        import logging

        caplog.set_level(logging.DEBUG)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("table1",)]
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"})

        # Verificar que hay logs de debug
        assert any("Query executed" in record.message for record in caplog.records)

    def test_custom_query_logging(self, temp_queries_file, caplog):
        """Test logging en custom query"""
        import logging

        caplog.set_level(logging.DEBUG)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        executor.execute_custom_many("SELECT 1")

        assert any("custom query" in record.message.lower() for record in caplog.records)
