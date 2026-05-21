"""Tests para SyncQueryExecutor (contrato)"""

from unittest.mock import MagicMock

import pytest

from util_bbdd import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
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

    temp_path = tmp_path_factory.mktemp("sync_executor_contract") / "sync_executor_queries.json"
    temp_path.write_text(json.dumps(queries_data), encoding="utf-8")
    return temp_path


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

        _call_count = [0]

        def _cursor_factory(*args, **kwargs):
            _call_count[0] += 1
            return text_cursor if _call_count[0] == 1 else binary_cursor

        mock_conn.cursor.side_effect = _cursor_factory

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == ("CREATE TABLE t (Ó)",)
        assert mock_conn.cursor.call_count == 4
        binary_cursor.close.assert_called()
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

        _call_count = [0]

        def _cursor_factory(*args, **kwargs):
            _call_count[0] += 1
            return text_cursor if _call_count[0] == 1 else binary_cursor

        mock_conn.cursor.side_effect = _cursor_factory

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == ("CREATE TABLE t (Ó)",)
        assert mock_conn.cursor.call_count == 4
        binary_cursor.close.assert_called()
        releaser.assert_called_once_with(mock_conn)

    def test_execute_custom_mariadb_fetchrows_systemeror_triggers_binary_fallback(self, temp_queries_file):
        """fetchall() vía fetchrows (C-ext) sin UnicodeDecodeError encadenado activa fallback binario."""
        text_cursor = MagicMock()
        binary_cursor = MagicMock()

        text_cursor.fetchall.side_effect = SystemError(
            "<method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set"
        )
        # cursor de reintento usa fetchone en bucle (no fetchall) para evitar fetchrows
        binary_cursor.fetchone.side_effect = [(b"dato\xd3",), None]

        mock_conn = MagicMock()
        mock_conn.__class__.__module__ = "mariadb"

        _call_count = [0]

        def _cursor_factory(*args, **kwargs):
            _call_count[0] += 1
            return text_cursor if _call_count[0] == 1 else binary_cursor

        mock_conn.cursor.side_effect = _cursor_factory

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        executor = SyncQueryExecutor(provider, releaser)
        result = executor.execute_custom_many("SELECT 1")

        assert result is not None
        binary_cursor.fetchall.assert_not_called()
        assert mock_conn.cursor.call_count == 4
        binary_cursor.close.assert_called()
        releaser.assert_called_once_with(mock_conn)

    def test_execute_custom_mariadb_binary_fetchall_avoided_when_main_fetchall_fails(self, temp_queries_file):
        """El cursor binario usa fetchone loop; fetchall no se llama aunque el cursor binario lo soportaría."""
        text_cursor = MagicMock()
        binary_cursor = MagicMock()

        fetchrows_error = SystemError(
            "<method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set"
        )
        text_cursor.fetchall.side_effect = fetchrows_error
        # fetchall en cursor de reintento también fallaría — pero con el fix no se llama
        binary_cursor.fetchall.side_effect = fetchrows_error
        binary_cursor.fetchone.side_effect = [("fila1",), ("fila2",), None]

        mock_conn = MagicMock()
        mock_conn.__class__.__module__ = "mariadb"

        _call_count = [0]

        def _cursor_factory(*args, **kwargs):
            _call_count[0] += 1
            return text_cursor if _call_count[0] == 1 else binary_cursor

        mock_conn.cursor.side_effect = _cursor_factory

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        executor = SyncQueryExecutor(provider, releaser)
        result = executor.execute_custom_many("SELECT 1")

        assert result == [("fila1",), ("fila2",)]
        binary_cursor.fetchall.assert_not_called()
        binary_cursor.close.assert_called()

    def test_execute_custom_mariadb_set_names_binary_sent_via_sql(self, temp_queries_file):
        """SET NAMES 'binary' se envía al servidor vía SQL (no vía property setter) para cambiar charset."""
        text_cursor = MagicMock()    # cursor principal (fetchall falla)
        set_names_cursor = MagicMock()  # cursor para SET NAMES 'binary'
        retry_cursor = MagicMock()   # cursor de fetch real
        restore_cursor = MagicMock()  # cursor para SET NAMES de restauración

        text_cursor.fetchall.side_effect = SystemError(
            "<method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set"
        )
        retry_cursor.fetchone.side_effect = [(b"resultado\xd3",), None]

        mock_conn = MagicMock()
        mock_conn.__class__.__module__ = "mariadb"
        mock_conn.character_set = "utf8mb4"

        cursor_seq = [text_cursor, set_names_cursor, retry_cursor, restore_cursor]
        _call_count = [0]

        def _cursor_factory(*args, **kwargs):
            idx = _call_count[0]
            _call_count[0] += 1
            return cursor_seq[idx] if idx < len(cursor_seq) else MagicMock()

        mock_conn.cursor.side_effect = _cursor_factory

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        executor = SyncQueryExecutor(provider, releaser)
        result = executor.execute_custom_many("SELECT 1")

        assert result is not None
        set_names_cursor.execute.assert_called_once_with("SET NAMES 'binary'")
        set_names_cursor.close.assert_called_once()
        retry_cursor.fetchall.assert_not_called()
        retry_cursor.close.assert_called_once()
        restore_cursor.execute.assert_called_once_with("SET NAMES 'utf8mb4'")
        restore_cursor.close.assert_called_once()
        releaser.assert_called_once_with(mock_conn)

    def test_execute_query_one_mariadb_binary_cursor_preserves_unknown_bytes_as_hex(self, temp_queries_file):
        """Si el byte binario no es fiable en utf-8/cp1252, se preserva como HEX."""
        text_cursor = MagicMock()
        binary_cursor = MagicMock()
        text_cursor.fetchone.side_effect = UnicodeDecodeError(
            "utf-8",
            b"\x81",
            0,
            1,
            "invalid start byte",
        )
        binary_cursor.fetchone.return_value = (b"\x81",)

        mock_conn = MagicMock()

        _call_count = [0]

        def _cursor_factory(*args, **kwargs):
            _call_count[0] += 1
            return text_cursor if _call_count[0] == 1 else binary_cursor

        mock_conn.cursor.side_effect = _cursor_factory

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        result = executor.execute_query_one("obtener_tablas", "mariadb", {"database": "test_db"})

        assert result == ("0x81",)
        assert mock_conn.cursor.call_count == 4
        binary_cursor.close.assert_called()
        releaser.assert_called_once_with(mock_conn)


class TestSyncExecutorTimeout:
    """Pruebas de timeout en sync"""

    def test_timeout_during_execute_query_many(self, temp_queries_file, monkeypatch: pytest.MonkeyPatch):
        """Lanza QueryTimeoutError cuando execute_query_many excede timeout."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def execute_noop(*_args, **_kwargs):
            return None

        ticks = iter([100.0, 100.0, 100.0, 100.02])
        monkeypatch.setattr(
            "util_bbdd.executors.sync_query_executor.time.monotonic",
            lambda: next(ticks, 100.02),
        )
        mock_cursor.execute.side_effect = execute_noop
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor

        provider = MagicMock(return_value=mock_conn)
        releaser = MagicMock()

        registry = QueryRegistry(temp_queries_file)
        executor = SyncQueryExecutor(provider, releaser, registry)

        with pytest.raises(QueryTimeoutError):
            executor.execute_query_many("obtener_tablas", "mariadb", {"database": "test_db"}, timeout=0.01)

        releaser.assert_called_once_with(mock_conn)

    def test_timeout_during_execute_custom_many(self, temp_queries_file, monkeypatch: pytest.MonkeyPatch):
        """Lanza QueryTimeoutError cuando execute_custom_many excede timeout."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def execute_noop(*_args, **_kwargs):
            return None

        ticks = iter([200.0, 200.0, 200.02])
        monkeypatch.setattr(
            "util_bbdd.executors.sync_query_executor.time.monotonic",
            lambda: next(ticks, 200.02),
        )
        mock_cursor.execute.side_effect = execute_noop
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
