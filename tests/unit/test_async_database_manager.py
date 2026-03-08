"""Tests for AsyncDatabaseManager - Async database connection and query management"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from util_bbdd.async_database_manager import AsyncDatabaseManager
from util_bbdd.database_exceptions import QueryNotFoundError


class TestAsyncDatabaseManagerInit:
    """Basic AsyncDatabaseManager initialization tests"""

    def test_manager_init_basic(self):
        """AsyncDatabaseManager initializes with required params"""
        conn_factory = AsyncMock()
        pool_factory = AsyncMock()

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost", "user": "root"},
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
            conn_params={"host": "localhost"},
            use_pool=False,
            connection_factory=conn_factory,
        )

        assert manager.use_pool is False

    def test_manager_db_type_normalized(self):
        """AsyncDatabaseManager normalizes db_type to lowercase"""
        manager = AsyncDatabaseManager(
            db_type="MARIADB",
            conn_params={"host": "localhost"},
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
            return mock_connection

        async with AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost"},
            use_pool=False,
            connection_factory=fake_conn_factory,
        ) as manager:
            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_context_manager_cleanup(self):
        """AsyncDatabaseManager cleans up on context exit"""
        mock_pool_conn = AsyncMock()
        mock_pool_conn.aclose = AsyncMock()

        async def fake_pool_factory(db_type, params):
            return mock_pool_conn

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost"},
            use_pool=True,
            pool_factory=fake_pool_factory,
        )

        manager.pool_connection = mock_pool_conn

        async with manager:
            pass

        mock_pool_conn.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_connection_cleanup(self):
        """AsyncDatabaseManager cleans up direct connection properly"""
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()

        async def fake_conn_factory(db_type, params):
            return mock_conn

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost"},
            use_pool=False,
            connection_factory=fake_conn_factory,
        )

        await manager.ainit()
        await manager.aclose()

        mock_conn.close.assert_called_once()


class TestAsyncDatabaseManagerConnectionHandling:
    """Connection acquisition and release tests"""

    @pytest.mark.asyncio
    async def test_get_connection_from_pool(self):
        """get_connection acquires from pool when available"""
        mock_pool_conn = MagicMock()
        mock_acquired = MagicMock()
        mock_pool_conn.acquire = AsyncMock(return_value=mock_acquired)

        async def fake_pool_factory(db_type, params):
            return mock_pool_conn

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"host": "localhost"},
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
            conn_params={"host": "localhost"},
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

        # Should not raise, should be no-op


class TestAsyncDatabaseManagerQueryExecution:
    """Query execution tests"""

    @pytest.mark.asyncio
    async def test_execute_custom_query(self):
        """execute_custom_query calls executor properly"""
        mock_executor = AsyncMock()
        mock_executor.execute_custom_query = AsyncMock(return_value=[(1, "test")])

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost"},
            use_pool=False,
        )

        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.execute_custom_query(sql="SELECT * FROM users", fetch_one=False)

        mock_executor.execute_custom_query.assert_called_once()
        assert result == [(1, "test")]

    @pytest.mark.asyncio
    async def test_execute_custom_query_not_initialized(self):
        """execute_custom_query raises when executor not initialized"""
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost"},
            use_pool=False,
        )

        manager._initialized = True
        manager.query_executor = None

        with pytest.raises(RuntimeError, match="AsyncDatabaseQueryExecutor"):
            await manager.execute_custom_query(sql="SELECT 1")

    @pytest.mark.asyncio
    async def test_execute_query_by_name(self):
        """execute_query resolves and executes query by name"""
        mock_executor = AsyncMock()
        mock_result = [{"id": 1, "name": "Alice"}]
        mock_executor.execute_query = AsyncMock(return_value=mock_result)

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost"},
            use_pool=False,
        )

        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.execute_query(query_name="get_users", fetch_one=False)

        mock_executor.execute_query.assert_called_once()
        assert result == mock_result

    @pytest.mark.asyncio
    async def test_execute_query_propagates_not_found_error(self):
        """execute_query propagates QueryNotFoundError"""
        mock_executor = AsyncMock()
        mock_executor.execute_query = AsyncMock(side_effect=QueryNotFoundError("Query 'missing' not found"))

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost"},
            use_pool=False,
        )

        manager.query_executor = mock_executor
        manager._initialized = True

        with pytest.raises(QueryNotFoundError):
            await manager.execute_query(query_name="missing")


class TestAsyncDatabaseManagerIntegration:
    """Integration tests with context manager and executor"""

    @pytest.mark.asyncio
    async def test_full_workflow_with_context_manager(self):
        """Full workflow: init, execute, cleanup"""
        mock_pool = AsyncMock()
        mock_acquired = MagicMock()
        mock_pool.acquire = AsyncMock(return_value=mock_acquired)
        mock_pool.aclose = AsyncMock()

        mock_executor = AsyncMock()
        mock_executor.execute_custom_query = AsyncMock(return_value=[(1, "test")])

        async def fake_pool_factory(db_type, params):
            return mock_pool

        with patch(
            "util_bbdd.async_database_manager.AsyncDatabaseQueryExecutor",
            return_value=mock_executor,
        ):
            async with AsyncDatabaseManager(
                db_type="mariadb",
                conn_params={"host": "localhost"},
                use_pool=True,
                pool_factory=fake_pool_factory,
            ) as manager:
                result = await manager.execute_custom_query(sql="SELECT * FROM test")

                assert result == [(1, "test")]

            mock_pool.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_sequential_queries(self):
        """Execute multiple queries sequentially"""
        mock_executor = AsyncMock()
        mock_executor.execute_custom_query = AsyncMock(side_effect=[[(1, "first")], [(2, "second")]])

        async def fake_conn_factory(db_type, params):
            return MagicMock()

        async with AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"host": "localhost"},
            use_pool=False,
            connection_factory=fake_conn_factory,
        ) as manager:
            manager.query_executor = mock_executor
            manager._initialized = True

            result1 = await manager.execute_custom_query(sql="SELECT 1")
            result2 = await manager.execute_custom_query(sql="SELECT 2")

            assert result1 == [(1, "first")]
            assert result2 == [(2, "second")]
            assert mock_executor.execute_custom_query.call_count == 2


class TestAsyncDatabaseManagerConvenienceMethods:
    """Paridad de métodos de conveniencia async."""

    @pytest.mark.asyncio
    async def test_get_tables_uses_context_database(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query = AsyncMock(return_value=[("users",)])

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"schema": "public"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_tables()

        assert result == [("users",)]
        mock_executor.execute_query.assert_called_once_with(
            query_name="obtener_tablas",
            db_type="postgresql",
            params={"database": "public"},
            fetch_one=False,
        )

    @pytest.mark.asyncio
    async def test_get_database_version_returns_first_column(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query = AsyncMock(return_value=("15.0",))

        manager = AsyncDatabaseManager(
            db_type="sqlserver",
            conn_params={"database": "master"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_database_version()

        assert result == "15.0"

    @pytest.mark.asyncio
    async def test_get_available_queries_reads_registry(self):
        mock_executor = MagicMock()
        mock_executor.registry.get_available_queries.return_value = ["obtener_tablas", "columnas_tabla"]

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_available_queries()

        assert result == ["obtener_tablas", "columnas_tabla"]
