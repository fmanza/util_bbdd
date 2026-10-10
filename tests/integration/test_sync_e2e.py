"""
Tests E2E/Integración para SyncDatabaseManager (SYNC) sin mocks.
Prueba flujos completos: conexión real a BD, CRUD, validación, consultas.
"""

import pytest

from util_bbdd import SyncDatabaseManager


@pytest.mark.e2e
@pytest.mark.sqlite
@pytest.mark.integration
class TestSyncDatabaseManagerE2E:
    """Tests E2E para SyncDatabaseManager con BD real."""

    def test_e2e_connect_and_get_tables(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Conectar a BD real y obtener lista de tablas."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            tables = manager.get_tables()

            table_names = [t.name for t in tables]
            assert "users" in table_names
            assert "orders" in table_names
            assert len(table_names) >= 2
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_get_columns_info(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Obtener información de columnas de tabla real."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            columns = manager.get_columns("users")

            assert len(columns) > 0
            col_names = [col.name for col in columns]
            assert "id" in col_names
            assert "nombre" in col_names
            assert "email" in col_names
            assert "edad" in col_names
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_simple_select_query(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Ejecutar SELECT simple sin parámetros (template-only)."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            users = manager.execute_query_many("get_all_users")

            assert users is not None
            assert len(users) == 3
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_select_with_parameters(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Ejecutar SELECT con parámetros."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            result = manager.execute_query_many("get_user_by_id", user_id=1)

            assert len(result) == 1
            user = result[0]
            assert user[1] == "Alice Johnson"
            assert user[2] == "alice@example.com"
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_insert_and_verify(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: INSERT real en BD y verificar con SELECT."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            result_before = manager.execute_query_many("get_user_count")
            rows_before = result_before
            count_before = rows_before[0][0]
            assert count_before == 3

            manager.execute_query_many("insert_user", nombre="Diana Prince", email="diana@example.com", edad=28)

            result_after = manager.execute_query_many("get_user_count")
            rows_after = result_after
            count_after = rows_after[0][0]
            assert count_after == count_before + 1

            result_diana = manager.execute_query_many("get_user_by_id", user_id=4)
            rows = result_diana
            assert len(rows) == 1
            assert rows[0][1] == "Diana Prince"
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_update_and_verify(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: UPDATE real en BD y verificar cambios."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            new_email = "alice_updated@example.com"
            manager.execute_query_many("update_user", user_id=1, email=new_email, edad=31)

            result_after = manager.execute_query_many("get_user_by_id", user_id=1)
            rows_after = result_after
            user_after = rows_after[0]
            assert user_after[2] == new_email
            assert user_after[3] == 31
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_delete_and_verify(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: DELETE real en BD y verificar eliminación."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            result_before = manager.execute_query_many("get_user_count")
            rows_before = result_before
            count_before = rows_before[0][0]

            manager.execute_query_many("delete_user", user_id=2)

            result_after = manager.execute_query_many("get_user_count")
            rows_after = result_after
            count_after = rows_after[0][0]
            assert count_after == count_before - 1

            result_deleted = manager.execute_query_many("get_user_by_id", user_id=2)
            rows = result_deleted
            assert len(rows) == 0
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_query_not_found(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Error cuando query no existe en sql_queries.json."""
        from util_bbdd.exceptions import QueryNotFoundError

        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            with pytest.raises(QueryNotFoundError):
                manager.execute_query_many("nonexistent_query")
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_connection_reuse(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Reutilizar manager para múltiples consultas."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            tables1 = manager.get_tables()
            tables2 = manager.get_tables()
            users1 = manager.execute_query_many("get_all_users")
            users2 = manager.execute_query_many("get_all_users")

            assert tables1 == tables2
            assert len(users1) == len(users2) == 3
        finally:
            manager.close(timeout_seconds=10.0, force=False)

    def test_e2e_transaction_consistency(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Consistencia en transacciones múltiples."""
        manager = SyncDatabaseManager(**sqlite_connection_config)
        try:
            manager.execute_query_many("insert_user", nombre="Eve Wilson", email="eve@example.com", edad=27)

            rows = manager.execute_query_many("get_all_users")

            assert len(rows) == 4
            names = [row[1] for row in rows]
            assert "Eve Wilson" in names
        finally:
            manager.close(timeout_seconds=10.0, force=False)
