"""B5: Contrato de excepciones para SyncDatabaseManager y AsyncDatabaseManager.

Verifica que:
1. Todas las excepciones lanzadas por los managers son subclases de DatabaseException.
2. Escenarios concretos lanzan el tipo de excepción correcto en la jerarquía.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd import DatabaseException
from util_bbdd.exceptions import (
    ConnectionError,
    DatabaseOperationError,
    InvalidDatabaseType,
    PoolTimeoutError,
    ValidationError,
)
from util_bbdd.managers import AsyncDatabaseManager, SyncDatabaseManager

# ---------------------------------------------------------------------------
# Jerarquía — todos los tipos que pueden salir de un manager
# ---------------------------------------------------------------------------


class TestManagerExceptionHierarchy:
    """Verifica que los tipos de excepción del contrato heredan de DatabaseException."""

    def test_connection_error_is_database_exception(self) -> None:
        assert issubclass(ConnectionError, DatabaseException)

    def test_validation_error_is_database_exception(self) -> None:
        assert issubclass(ValidationError, DatabaseException)

    def test_invalid_database_type_is_validation_error(self) -> None:
        assert issubclass(InvalidDatabaseType, ValidationError)
        assert issubclass(InvalidDatabaseType, DatabaseException)

    def test_database_operation_error_is_database_exception(self) -> None:
        assert issubclass(DatabaseOperationError, DatabaseException)

    def test_pool_timeout_error_is_connection_error(self) -> None:
        assert issubclass(PoolTimeoutError, ConnectionError)
        assert issubclass(PoolTimeoutError, DatabaseException)


# ---------------------------------------------------------------------------
# SyncDatabaseManager — inicialización con db_type inválido
# ---------------------------------------------------------------------------


class TestSyncManagerInvalidDbType:
    """Escenario: db_type no soportado → InvalidDatabaseType."""

    def test_invalid_db_type_raises_invalid_database_type(self) -> None:
        with pytest.raises(InvalidDatabaseType):
            SyncDatabaseManager(db_type="nosql", conn_params={"database": "test"})

    def test_invalid_db_type_is_database_exception(self) -> None:
        with pytest.raises(DatabaseException):
            SyncDatabaseManager(db_type="mongodb", conn_params={"database": "test"})

    def test_invalid_db_type_is_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            SyncDatabaseManager(db_type="redis", conn_params={"database": "test"})


# ---------------------------------------------------------------------------
# SyncDatabaseManager — executor no inicializado
# ---------------------------------------------------------------------------


class TestSyncManagerUninitializedExecutor:
    """Escenario: execute_query_many/one sin connect() previo → DatabaseOperationError."""

    def _make_unconnected_manager(self) -> SyncDatabaseManager:
        """Crea un manager en estado post-init sin conexión activa."""
        manager = object.__new__(SyncDatabaseManager)
        manager.sync_query_executor = None
        manager.db_type = "sqlite"
        return manager

    def test_execute_query_many_raises_when_executor_not_initialized(self) -> None:
        manager = self._make_unconnected_manager()
        with pytest.raises(DatabaseOperationError):
            manager.execute_query_many("select_tables")

    def test_execute_query_one_raises_when_executor_not_initialized(self) -> None:
        manager = self._make_unconnected_manager()
        with pytest.raises(DatabaseOperationError):
            manager.execute_query_one("select_tables")

    def test_database_operation_error_is_database_exception(self) -> None:
        manager = self._make_unconnected_manager()
        with pytest.raises(DatabaseException):
            manager.execute_query_many("select_tables")


# ---------------------------------------------------------------------------
# AsyncDatabaseManager — executor no inicializado
# ---------------------------------------------------------------------------


class TestAsyncManagerUninitializedExecutor:
    """Escenario: execute_query_many/one async sin connect() previo → DatabaseOperationError."""

    def _make_unconnected_manager(self) -> AsyncDatabaseManager:
        manager = object.__new__(AsyncDatabaseManager)
        manager.query_executor = None
        manager._initialized = True  # skip lazy init; executor is explicitly None
        manager.db_type = "sqlite"
        manager.logger = MagicMock()
        return manager

    @pytest.mark.asyncio
    async def test_execute_query_many_raises_when_executor_not_initialized(self) -> None:
        manager = self._make_unconnected_manager()
        with pytest.raises(DatabaseOperationError):
            await manager.execute_query_many("select_tables")

    @pytest.mark.asyncio
    async def test_execute_query_one_raises_when_executor_not_initialized(self) -> None:
        manager = self._make_unconnected_manager()
        with pytest.raises(DatabaseOperationError):
            await manager.execute_query_one("select_tables")

    @pytest.mark.asyncio
    async def test_database_operation_error_is_database_exception(self) -> None:
        manager = self._make_unconnected_manager()
        with pytest.raises(DatabaseException):
            await manager.execute_query_many("select_tables")


# ---------------------------------------------------------------------------
# SyncDatabaseManager — wrapping de errores ajenos
# ---------------------------------------------------------------------------


class TestSyncManagerOperationErrorWrapping:
    """Escenario: errores del executor son envueltos como DatabaseOperationError."""

    def test_executor_runtime_error_is_wrapped_as_database_operation_error(self) -> None:
        """Un error inesperado del executor sale como DatabaseOperationError."""
        mock_executor = MagicMock()
        mock_executor.execute_query_many.side_effect = RuntimeError("driver crash")

        manager = object.__new__(SyncDatabaseManager)
        manager.sync_query_executor = mock_executor
        manager.db_type = "mariadb"
        manager.logger = MagicMock()
        manager._query_catalog = MagicMock()

        with pytest.raises(DatabaseException):
            manager.execute_query_many("select_tables")
