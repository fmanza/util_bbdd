"""Tests for AsyncDatabaseManager - Async database connection and query management"""

import asyncio

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from util_bbdd.exceptions import DatabaseOperationError, QueryNotFoundError
from util_bbdd.managers import AsyncDatabaseManager


class TestAsyncDatabaseManagerInit:
    """Basic AsyncDatabaseManager initialization tests"""

    def test_manager_init_basic(self):
        """AsyncDatabaseManager initializes with required params"""
        conn_factory = AsyncMock()
        pool_factory = AsyncMock()

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=True,
            connection_factory=conn_factory,
            pool_factory=pool_factory,
        )

        assert manager.db_type == "mariadb"
        assert manager.use_pool is True
        assert manager._initialized is False

    def test_manager_init_without_pool(self):
        """AsyncDatabaseManager can be initialized without pool"""
        conn_factory = AsyncMock()

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
            connection_factory=conn_factory,
        )

        assert manager.use_pool is False

    def test_manager_has_no_dead_lifecycle_or_session_manager_attributes(self):
        """MGR-02 (AUDIT_CODE 2026-09-22): AsyncLifecycleManager/AsyncSessionManager se
        construían en __init__ (y sus atributos se actualizaban en init()) pero ningún
        método suyo se invocaba jamás — código muerto que aparentaba funcionar. Retirados;
        AsyncDatabaseManager implementa su propio ciclo de vida directamente."""
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=True,
            connection_factory=AsyncMock(),
            pool_factory=AsyncMock(),
        )

        assert not hasattr(manager, "lifecycle_manager")
        assert not hasattr(manager, "session_manager")

    def test_manager_db_type_normalized(self):
        """AsyncDatabaseManager normalizes db_type to lowercase"""
        manager = AsyncDatabaseManager(
            db_type="MARIADB",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        assert manager.db_type == "mariadb"


class TestAsyncDatabaseManagerLifecycle:
    """AsyncDatabaseManager context manager and lifecycle tests"""

    @pytest.mark.asyncio
    async def test_context_manager_initialization(self):
        """AsyncDatabaseManager initializes properly via context manager"""
        mock_connection = MagicMock()

        async def fake_conn_factory(db_type, params):
            await asyncio.sleep(0)
            return mock_connection

        async with AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
            connection_factory=fake_conn_factory,
        ) as manager:
            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """AsyncDatabaseManager cleans up on context exit"""
        mock_pool_conn = AsyncMock()
        mock_pool_conn.close = AsyncMock()

        async def fake_pool_factory(db_type, params):
            await asyncio.sleep(0)
            return mock_pool_conn

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=True,
            pool_factory=fake_pool_factory,
        )

        manager.pool_connection = mock_pool_conn

        async with manager:
            assert manager.pool_connection is mock_pool_conn

        mock_pool_conn.close.assert_called_once_with(mode="immediate")

    @pytest.mark.asyncio
    async def test_direct_connection_cleanup(self):
        """AsyncDatabaseManager cleans up direct connection properly"""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()

        async def fake_conn_factory(db_type, params):
            await asyncio.sleep(0)
            return mock_conn

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
            connection_factory=fake_conn_factory,
        )

        await manager.init()
        await manager.close()

        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_aclose_delegates_to_pool_and_resets_state(self):
        """close delega el cierre al adapter async del pool y limpia estado."""
        mock_pool_conn = AsyncMock()
        mock_pool_conn.close = AsyncMock()

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=True,
        )
        manager.pool_connection = mock_pool_conn

        await manager.close()

        mock_pool_conn.close.assert_called_once_with(mode="immediate")
        assert manager.pool_connection is None
        assert manager._initialized is False


class TestAsyncDatabaseManagerConnectionHandling:
    """Connection acquisition and release tests"""

    @pytest.mark.asyncio
    async def test_get_connection_from_pool(self):
        """get_connection acquires from pool when available"""
        mock_pool_conn = MagicMock()
        mock_acquired = MagicMock()
        mock_pool_conn.acquire = AsyncMock(return_value=mock_acquired)

        async def fake_pool_factory(db_type, params):
            await asyncio.sleep(0)
            return mock_pool_conn

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=True,
            pool_factory=fake_pool_factory,
        )

        manager.pool_connection = mock_pool_conn
        manager._initialized = True

        conn = await manager.get_connection()

        mock_pool_conn.acquire.assert_called_once()
        assert conn is mock_acquired

    @pytest.mark.asyncio
    async def test_get_connection_direct(self):
        """get_connection returns direct connection when pool not used"""
        mock_conn = MagicMock()

        async def fake_conn_factory(db_type, params):
            await asyncio.sleep(0)
            return mock_conn

        manager = AsyncDatabaseManager(
            db_type="sqlite",
            conn_params={"database": ":memory:"},
            use_pool=False,
            connection_factory=fake_conn_factory,
        )

        manager._connection = mock_conn
        manager._initialized = True

        conn = await manager.get_connection()

        assert conn is mock_conn

    @pytest.mark.asyncio
    async def test_release_connection_to_pool(self):
        """release_connection returns connection to pool"""
        mock_pool = AsyncMock()
        mock_pool.release = AsyncMock()
        mock_conn = MagicMock()

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=True,
        )

        manager.pool_connection = mock_pool

        await manager.release_connection(mock_conn)

        mock_pool.release.assert_called_once_with(mock_conn)

    @pytest.mark.asyncio
    async def test_release_connection_direct_noop(self):
        """release_connection is no-op for direct connections"""
        manager = AsyncDatabaseManager(
            db_type="sqlite",
            conn_params={"database": ":memory:"},
            use_pool=False,
        )

        mock_conn = MagicMock()
        await manager.release_connection(mock_conn)

        assert manager.pool_connection is None


class TestAsyncDatabaseManagerQueryExecution:
    """Query execution tests"""

    @pytest.mark.asyncio
    async def test_execute_custom_many(self):
        """execute_custom_many calls executor properly"""
        mock_executor = AsyncMock()
        mock_executor.execute_custom_many = AsyncMock(return_value=[(1, "test")])

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.execute_custom_many(sql="SELECT * FROM users")

        mock_executor.execute_custom_many.assert_called_once()
        assert result == [(1, "test")]

    @pytest.mark.asyncio
    async def test_execute_custom_many_not_initialized(self):
        """execute_custom_many raises domain error when executor not initialized"""
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        manager._initialized = True
        manager.query_executor = None

        with pytest.raises(DatabaseOperationError, match="AsyncQueryExecutor"):
            await manager.execute_custom_many(sql="SELECT 1")

    @pytest.mark.asyncio
    async def test_execute_query_many_by_name(self):
        """execute_query_many resolves and executes query by name"""
        mock_executor = AsyncMock()
        mock_result = [{"id": 1, "name": "Alice"}]
        mock_executor.execute_query_many = AsyncMock(return_value=mock_result)

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.execute_query_many(query_name="get_users")

        mock_executor.execute_query_many.assert_called_once()
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_execute_query_many_propagates_not_found_error(self):
        """execute_query_many propagates QueryNotFoundError"""
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(side_effect=QueryNotFoundError("Query 'missing' not found"))

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        manager.query_executor = mock_executor
        manager._initialized = True

        with pytest.raises(QueryNotFoundError):
            await manager.execute_query_many(query_name="missing")


class TestAsyncDatabaseManagerIntegration:
    """Integration tests with context manager and executor"""

    @pytest.mark.asyncio
    async def test_full_workflow_with_context_manager(self):
        """Full workflow: init, execute, cleanup"""
        mock_pool = AsyncMock()
        mock_acquired = MagicMock()
        mock_pool.acquire = AsyncMock(return_value=mock_acquired)
        mock_pool.close = AsyncMock()

        mock_executor = AsyncMock()
        mock_executor.execute_custom_many = AsyncMock(return_value=[(1, "test")])

        async def fake_pool_factory(db_type, params):
            await asyncio.sleep(0)
            return mock_pool

        with patch(
            "util_bbdd.managers.async_mgr.AsyncQueryExecutor",
            return_value=mock_executor,
        ):
            async with AsyncDatabaseManager(
                db_type="mariadb",
                conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
                use_pool=True,
                pool_factory=fake_pool_factory,
            ) as manager:
                result = await manager.execute_custom_many(sql="SELECT * FROM test")

                assert result == [(1, "test")]

            mock_pool.close.assert_called_once_with(mode="immediate")

    @pytest.mark.asyncio
    async def test_multiple_sequential_queries(self):
        """Execute multiple queries sequentially"""
        mock_executor = AsyncMock()
        mock_executor.execute_custom_many = AsyncMock(side_effect=[[(1, "first")], [(2, "second")]])

        async def fake_conn_factory(db_type, params):
            await asyncio.sleep(0)
            return MagicMock()

        async with AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
            connection_factory=fake_conn_factory,
        ) as manager:
            manager.query_executor = mock_executor
            manager._initialized = True

            result1 = await manager.execute_custom_many(sql="SELECT 1")
            result2 = await manager.execute_custom_many(sql="SELECT 2")

            assert result1 == [(1, "first")]
            assert result2 == [(2, "second")]
            assert mock_executor.execute_custom_many.call_count == 2


class TestAsyncDatabaseManagerConvenienceMethods:
    """Paridad de métodos de conveniencia async."""

    @pytest.mark.asyncio
    async def test_get_available_queries_reads_registry(self):
        mock_executor = MagicMock()
        mock_executor.registry.get_available_queries.return_value = ["obtener_tablas", "columnas_tabla"]

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_available_queries()

        assert result == ["obtener_tablas", "columnas_tabla"]

    @pytest.mark.asyncio
    async def test_get_query_info_reads_queries_from_registry(self):
        mock_executor = MagicMock()
        mock_executor.registry.queries = {
            "mariadb": {
                "obtener_tablas": "SELECT * FROM information_schema.tables WHERE table_schema = '{database}'",
                "database_version": "SELECT VERSION()",
            }
        }

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_query_info()

        assert result["db_type"] == "mariadb"
        assert result["total_queries"] == 2
        assert set(result["query_names"]) == {"obtener_tablas", "database_version"}
        assert result["queries"]["obtener_tablas"]["template"]
        assert set(result["queries"]["obtener_tablas"]["required_parameters"]) == {"database"}
        assert result["queries"]["database_version"]["required_parameters"] == []

    @pytest.mark.asyncio
    async def test_get_storage_inventory_unknown_db_type_rejected_at_init(self):
        with pytest.raises(Exception) as exc_info:
            AsyncDatabaseManager(
                db_type="db_inexistente",
                conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
                use_pool=False,
            )

        assert "no soportado" in str(exc_info.value).lower()

    def test_get_database_type_description_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_description()

        assert result
        assert isinstance(result, str)

    def test_get_database_type_info_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_info()

        assert result
        assert isinstance(result, dict)

    def test_get_database_type_name_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_name()

        assert result
        assert isinstance(result, str)

    def test_get_database_type_features_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_features()

        assert isinstance(result, list)

    def test_get_database_type_driver_info_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_driver_info()

        assert isinstance(result, dict)

    def test_get_required_and_optional_params_use_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        required = manager.get_required_params()
        optional = manager.get_optional_params()

        assert isinstance(required, list)
        assert isinstance(optional, list)

    def test_get_database_type_examples_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_examples()

        assert isinstance(result, dict)

    def test_get_default_port_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )

        result = manager.get_default_port()

        assert isinstance(result, int)
        assert result > 0

    @pytest.mark.asyncio
    async def test_get_database_info_aggregates_informative_fields(self):
        mock_executor = MagicMock()
        mock_executor.registry.get_available_queries.return_value = ["obtener_tablas", "database_version"]

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "u", "password": "p", "database": "db"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True
        manager._connection = object()

        result = await manager.get_database_info()

        assert result["db_type"] == "mariadb"
        assert isinstance(result["db_type_name"], str)
        assert isinstance(result["db_type_description"], str)
        assert result["database"] == "db"
        assert isinstance(result["default_port"], int)
        assert isinstance(result["required_params"], list)
        assert isinstance(result["optional_params"], list)
        assert isinstance(result["supported_features"], list)
        assert isinstance(result["driver_info"], dict)
        assert result["available_queries"] == ["obtener_tablas", "database_version"]
        assert result["connection_status"] == "connected"

    def test_get_supported_db_types_static(self):
        result = AsyncDatabaseManager.get_supported_db_types()
        assert isinstance(result, list)
        assert "mariadb" in result

    def test_get_db_type_info_static(self):
        result = AsyncDatabaseManager.get_db_type_info_static("mariadb")
        assert isinstance(result, dict)
        assert result

    @pytest.mark.asyncio
    async def test_get_sqlalchemy_engine_delegates_async_factory(self):
        fake_engine = object()
        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={
                "host": "localhost",
                "user": "u",
                "password": "p",
                "database": "db",
                "pool_size": 7,
                "pool_timeout": 25,
            },
            use_pool=True,
        )

        with patch(
            "util_bbdd.managers.async_mgr.AsyncSQLAlchemyEngineFactory.create_engine",
            new=AsyncMock(return_value=fake_engine),
        ) as mock_create_engine:
            result = await manager.get_sqlalchemy_engine()

        assert result is fake_engine
        mock_create_engine.assert_awaited_once_with(
            "postgresql",
            manager.conn_params,
            "db",
            use_pool=True,
            sql_server_driver="aioodbc",
        )
        # Los pool_* ya no los pasa el manager: la factory los toma de conn_params (factory/_pool_policy.py, v0.36.0).
