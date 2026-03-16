"""Tests for AsyncDatabaseManager - Async database connection and query management"""

import asyncio

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from util_bbdd.database_exceptions import DatabaseOperationError, QueryNotFoundError
from util_bbdd.managers import AsyncDatabaseManager
from util_bbdd.metadata import DatabaseMetadataCache, RelationshipMetadataCache


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
            await asyncio.sleep(0)
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
        mock_pool_conn.close = AsyncMock()

        async def fake_pool_factory(db_type, params):
            await asyncio.sleep(0)
            return mock_pool_conn

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"host": "localhost"},
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
            conn_params={"host": "localhost"},
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
            conn_params={"host": "localhost"},
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
            conn_params={"host": "localhost"},
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
            conn_params={"host": "localhost"},
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
            conn_params={"host": "localhost"},
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
            conn_params={"host": "localhost"},
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
                conn_params={"host": "localhost"},
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
            conn_params={"host": "localhost"},
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
    async def test_get_tables_uses_context_database(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(return_value=[("users",)])

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"schema": "public"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_tables()
        result_cached = await manager.get_tables()

        assert result == [("users",)]
        assert result_cached == [("users",)]
        mock_executor.execute_query_many.assert_called_once_with(
            query_name="obtener_tablas",
            db_type="postgresql",
            params={"database": "public"},
        )

    @pytest.mark.asyncio
    async def test_get_database_version_returns_first_column(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_one = AsyncMock(return_value=("15.0",))

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
    async def test_get_ddl_mariadb_uses_metadata_builder_as_primary_path(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.get_columns = AsyncMock(
            return_value=[
                ("id", "int", "NO", "PRI", None, "auto_increment", ""),
                ("name", "varchar(50)", "YES", "", "Óscar", "", ""),
            ]
        )
        manager.get_primary_keys = AsyncMock(return_value=[("id",)])
        manager._execute_metadata_one = AsyncMock()

        result = await manager.get_ddl("users")

        assert result.startswith("CREATE TABLE")
        manager._execute_metadata_one.assert_not_awaited()
        manager.get_columns.assert_awaited_once_with("users")
        manager.get_primary_keys.assert_awaited_once_with("users")

    @pytest.mark.asyncio
    async def test_get_view_ddl_mariadb_uses_information_schema_as_primary_path(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.execute_custom_one = AsyncMock(return_value=("SELECT 1",))
        manager._execute_metadata_one = AsyncMock()

        result = await manager.get_view_ddl("v_users")

        assert result.startswith("CREATE OR REPLACE VIEW `v_users` AS")
        manager.execute_custom_one.assert_awaited_once()
        manager._execute_metadata_one.assert_not_awaited()
        await_args = cast(Any, manager.execute_custom_one.await_args)
        assert await_args is not None
        assert "information_schema.views" in await_args.args[0]

    @pytest.mark.asyncio
    async def test_get_routine_ddl_mariadb_uses_information_schema_as_primary_path(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager._execute_metadata_many = AsyncMock(
            side_effect=[
                [
                    (
                        "6d795f70726f63",
                        "PROCEDURE",
                        "50726f63656475726120646520707275656261",
                        "726f6f74406c6f63616c686f7374",
                        "444546494e4552",
                        "4d4f4449464945532053514c2044415441",
                        "NO",
                        "",
                        "",
                        "424547494e20454e44",
                    )
                ],
                [
                    ("494e", "505f4944434f4e5441444f52", "PROCEDURE", "6d795f70726f63", "494e5445474552", "", "", 1),
                    ("4f5554", "505f434f4e5441444f52", "PROCEDURE", "6d795f70726f63", "494e5445474552", "", "", 2),
                ],
            ]
        )
        manager._execute_metadata_one = AsyncMock()

        result = await manager.get_routine_ddl("my_proc", "procedure")

        assert result.startswith("CREATE DEFINER=`root`@`localhost` PROCEDURE `db`.`my_proc`(\n")
        assert "IN P_IDCONTADOR INTEGER" in result
        assert "OUT P_CONTADOR INTEGER" in result
        assert "MODIFIES SQL DATA" not in result
        assert "SQL SECURITY DEFINER" not in result
        assert "COMMENT 'Procedura de prueba'" in result
        assert manager._execute_metadata_many.await_count == 2
        manager._execute_metadata_one.assert_not_awaited()
        assert manager._execute_metadata_many.await_args_list[0].args[0] == "rutinas_mariadb_detalle"
        assert manager._execute_metadata_many.await_args_list[1].args[0] == "parametros_rutinas_mariadb_detalle"

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

    @pytest.mark.asyncio
    async def test_get_database_charset_collation_parses_mariadb(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_one = AsyncMock(return_value=("utf8mb4", "utf8mb4_general_ci"))

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_database_charset_collation()

        assert result == {"charset": "utf8mb4", "collation": "utf8mb4_general_ci"}
        mock_executor.execute_query_one.assert_called_once_with(
            query_name="database_charset_collation",
            db_type="mariadb",
            params={"database": "db"},
        )

    @pytest.mark.asyncio
    async def test_get_columns_charset_collation_parses_postgresql(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(
            return_value=[("id", "integer", "en_US"), ("name", "text", "es_ES")]
        )

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"schema": "public"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_columns_charset_collation("users")
        result_cached = await manager.get_columns_charset_collation("users")

        assert result == [("id", None, "en_US"), ("name", None, "es_ES")]
        assert result_cached == [("id", None, "en_US"), ("name", None, "es_ES")]
        mock_executor.execute_query_many.assert_called_once_with(
            query_name="columns_charset_collation",
            db_type="postgresql",
            params={"tabla": "users", "database": "public"},
        )

    @pytest.mark.asyncio
    async def test_get_columns_charset_collation_returns_empty_for_oracle_without_query(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock()

        manager = AsyncDatabaseManager(
            db_type="oracle",
            conn_params={
                "user": "DA_DPSS",
                "password": "secret",  # noqa: S105
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
            },
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_columns_charset_collation("V_SAAD_VALORACIONEVE")

        assert result == []
        mock_executor.execute_query_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_columns_charset_collation_uses_oracle_collation_query_for_12_2_plus(self):
        manager = AsyncDatabaseManager(
            db_type="oracle",
            conn_params={
                "user": "DA_DPSS",
                "password": "secret",  # noqa: S105
                "host": "localhost",
                "port": 1521,
                "service_name": "XE",
            },
            use_pool=False,
        )
        manager._initialized = True
        manager.get_database_version = AsyncMock(
            return_value="Oracle Database 19c Enterprise Edition Release 19.0.0.0.0 - Production"
        )
        manager._execute_metadata_many = AsyncMock(return_value=[("COL1", None, "BINARY_CI")])

        result = await manager.get_columns_charset_collation("V_SAAD_VALORACIONEVE")

        assert result == [("COL1", None, "BINARY_CI")]
        manager._execute_metadata_many.assert_awaited_once_with(
            "columns_charset_collation",
            params={"tabla": "V_SAAD_VALORACIONEVE", "database": "DA_DPSS"},
            error_message="Error obteniendo charset/collation de columnas",
            table_name="V_SAAD_VALORACIONEVE",
        )

    @pytest.mark.asyncio
    async def test_clear_cache_context_invalidates_metadata_cache(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(side_effect=[[("users",)], [("orders",)]])

        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={"schema": "public"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        first = await manager.get_tables()
        second = await manager.get_tables()
        manager.clear_cache(context_database="public")
        third = await manager.get_tables()

        assert first == [("users",)]
        assert second == [("users",)]
        assert third == [("orders",)]
        assert mock_executor.execute_query_many.call_count == 2

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
            conn_params={"database": "db"},
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
    async def test_get_storage_inventory_mariadb_keeps_shape_with_fragmented_queries(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(
            side_effect=[
                [("db", "users", "InnoDB", 12.5, 1.5, 14.0)],
                [],
                [("ibtmp1", "ibtmp1", 1.0, 12.0, 512.0)],
            ]
        )

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_storage_inventory()

        assert result == {
            "primary": [("db", "users", "InnoDB", 12.5, 1.5, 14.0)],
            "secondary": [],
            "temp_tablespaces": [("ibtmp1", "ibtmp1", 1.0, 12.0, 512.0)],
        }
        assert mock_executor.execute_query_many.await_count == 3
        assert mock_executor.execute_query_many.await_args_list[0].kwargs == {
            "query_name": "ficheros_fisicos",
            "db_type": "mariadb",
            "params": {"database": "db"},
        }
        assert mock_executor.execute_query_many.await_args_list[1].kwargs == {
            "query_name": "ficheros_fisicos_adicional",
            "db_type": "mariadb",
            "params": {"database": "db"},
        }
        assert mock_executor.execute_query_many.await_args_list[2].kwargs == {
            "query_name": "temp_tablespaces",
            "db_type": "mariadb",
            "params": {},
        }

    @pytest.mark.asyncio
    async def test_get_storage_inventory_mariadb_keeps_optional_sections_empty_on_error(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(
            side_effect=[
                [("db", "users", "InnoDB", 12.5, 1.5, 14.0)],
                DatabaseOperationError("sin acceso a info adicional", operation="SELECT", db_type="mariadb"),
                DatabaseOperationError(
                    "sin acceso a information_schema.FILES",
                    operation="SELECT",
                    db_type="mariadb",
                ),
            ]
        )

        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_storage_inventory()

        assert result == {
            "primary": [("db", "users", "InnoDB", 12.5, 1.5, 14.0)],
            "secondary": [],
            "temp_tablespaces": [],
        }

    @pytest.mark.asyncio
    async def test_get_storage_inventory_sqlite_includes_temp_tablespaces_key(self):
        mock_executor = AsyncMock()
        mock_executor.execute_query_many = AsyncMock(side_effect=[[("main.db",)], [("wal.db",)], RuntimeError("boom")])

        manager = AsyncDatabaseManager(
            db_type="sqlite",
            conn_params={"database": ":memory:"},
            use_pool=False,
        )
        manager.query_executor = mock_executor
        manager._initialized = True

        result = await manager.get_storage_inventory()

        assert result["primary"] == [("main.db",)]
        assert result["secondary"] == [("wal.db",)]
        assert result["temp_tablespaces"] == []

    @pytest.mark.asyncio
    async def test_get_storage_inventory_oracle_requires_tablespace(self):
        manager = AsyncDatabaseManager(
            db_type="oracle",
            conn_params={"user": "SCOTT"},
            use_pool=False,
        )

        with pytest.raises(ValueError, match="tablespace"):
            await manager.get_storage_inventory()

    @pytest.mark.asyncio
    async def test_get_storage_inventory_unknown_db_type_returns_empty_shape(self):
        manager = AsyncDatabaseManager(
            db_type="db_inexistente",
            conn_params={"database": "db"},
            use_pool=False,
        )

        result = await manager.get_storage_inventory()

        assert result == {"primary": [], "secondary": []}

    @pytest.mark.asyncio
    async def test_get_routines_mariadb_falls_back_to_show_status_when_metadata_is_empty(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager._execute_metadata_many = AsyncMock(return_value=[])
        manager.execute_custom_many = AsyncMock(
            side_effect=[
                [("db", "LOPD_FINAL", "PROCEDURE", None, None, None, None, "")],
                [("db", "REMOVER_ACENTOS", "FUNCTION", None, None, None, None, "texto")],
            ]
        )

        result = await manager.get_routines()

        assert result == [
            ("REMOVER_ACENTOS", "FUNCTION", "texto"),
            ("LOPD_FINAL", "PROCEDURE", ""),
        ]
        manager._execute_metadata_many.assert_awaited_once()
        assert manager.execute_custom_many.await_count == 2

    @pytest.mark.asyncio
    async def test_get_tables_normalized_maps_raw_rows(self):
        manager = AsyncDatabaseManager(
            db_type="sqlite",
            conn_params={"database": ":memory:"},
            use_pool=False,
        )
        manager.get_tables = AsyncMock(return_value=[("users",), ("orders",)])

        result = await manager.get_tables_normalized()

        assert result == [
            {"name": "users", "raw": ("users",)},
            {"name": "orders", "raw": ("orders",)},
        ]

    @pytest.mark.asyncio
    async def test_get_columns_normalized_maps_raw_rows(self):
        manager = AsyncDatabaseManager(
            db_type="sqlite",
            conn_params={"database": ":memory:"},
            use_pool=False,
        )
        manager.get_columns = AsyncMock(return_value=[(0, "id", "INTEGER"), (1, "name", "TEXT")])

        result = await manager.get_columns_normalized("users")

        assert result == [
            {"name": "id", "data_type": "INTEGER", "raw": (0, "id", "INTEGER")},
            {"name": "name", "data_type": "TEXT", "raw": (1, "name", "TEXT")},
        ]

    def test_get_database_type_description_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_description()

        assert result
        assert isinstance(result, str)

    def test_get_database_type_info_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_info()

        assert result
        assert isinstance(result, dict)

    def test_get_database_type_name_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_name()

        assert result
        assert isinstance(result, str)

    def test_get_database_type_features_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_features()

        assert isinstance(result, list)

    def test_get_database_type_driver_info_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_driver_info()

        assert isinstance(result, dict)

    def test_get_required_and_optional_params_use_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )

        required = manager.get_required_params()
        optional = manager.get_optional_params()

        assert isinstance(required, list)
        assert isinstance(optional, list)

    def test_get_database_type_examples_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )

        result = manager.get_database_type_examples()

        assert isinstance(result, dict)

    def test_get_default_port_uses_validator(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
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
            conn_params={"database": "db"},
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

    def test_get_relationship_cache_returns_cache_instance(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )

        cache = manager.get_relationship_cache()

        assert isinstance(cache, RelationshipMetadataCache)
        assert cache is manager.relationship_cache
        assert isinstance(manager.db_cache, DatabaseMetadataCache)
        assert manager.relationship_cache.db_cache is manager.db_cache

    def test_clear_cache_global_clears_db_and_relationship_caches(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.db_cache._tables_cache["db"] = [("users",)]
        manager.db_cache._columns_cache[("db", "users")] = [("id", "int")]
        manager.relationship_cache._is_pk_cache[("users", "id")] = True

        manager.clear_cache()

        assert manager.db_cache.get_cache_stats()["total_entries"] == 0
        assert manager.relationship_cache.get_cache_stats()["total_entries"] == 0

    def test_clear_cache_by_table_invalidates_table_and_relationship_entries(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        manager.db_cache._columns_cache[("db", "users")] = [("id", "int")]
        manager.db_cache._ddl_cache[("db", "users")] = "CREATE TABLE users (id INT)"
        manager.relationship_cache._is_pk_cache[("users", "id")] = True
        manager.relationship_cache._table_columns_typed_cache["users"] = [("id", "int")]

        manager.clear_cache(context_database="db", table="users")

        assert ("db", "users") not in manager.db_cache._columns_cache
        assert ("db", "users") not in manager.db_cache._ddl_cache
        assert ("users", "id") not in manager.relationship_cache._is_pk_cache
        assert "users" not in manager.relationship_cache._table_columns_typed_cache

    def test_clear_cache_by_routine_supports_typed_and_untyped_invalidation(self):
        manager = AsyncDatabaseManager(
            db_type="mariadb",
            conn_params={"database": "db"},
            use_pool=False,
        )
        procedure_key = ("db", "my_routine", "PROCEDURE")
        function_key = ("db", "my_routine", "FUNCTION")
        manager.db_cache._routine_parameters_cache[procedure_key] = [("p_id", "INT")]
        manager.db_cache._routine_parameters_cache[function_key] = [("f_id", "INT")]
        manager.db_cache._routine_ddl_cache[procedure_key] = "CREATE PROCEDURE my_routine()"
        manager.db_cache._routine_ddl_cache[function_key] = "CREATE FUNCTION my_routine()"

        manager.clear_cache(context_database="db", routine="my_routine", routine_type="procedure")
        assert procedure_key not in manager.db_cache._routine_parameters_cache
        assert procedure_key not in manager.db_cache._routine_ddl_cache
        assert function_key in manager.db_cache._routine_parameters_cache
        assert function_key in manager.db_cache._routine_ddl_cache

        manager.clear_cache(context_database="db", routine="my_routine")
        assert function_key not in manager.db_cache._routine_parameters_cache
        assert function_key not in manager.db_cache._routine_ddl_cache

    @pytest.mark.asyncio
    async def test_get_sqlalchemy_engine_delegates_async_factory(self):
        fake_engine = object()
        manager = AsyncDatabaseManager(
            db_type="postgresql",
            conn_params={
                "database": "db",
                "pool_size": 7,
                "max_overflow": 11,
                "pool_timeout": 25,
                "pool_recycle": 900,
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
            pool_size=7,
            max_overflow=11,
            pool_timeout=25,
            pool_recycle=900,
            sql_server_driver="aioodbc",
        )
