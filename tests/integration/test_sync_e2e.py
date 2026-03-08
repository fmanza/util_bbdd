"""
Tests E2E/Integración para DatabaseManager (SYNC) sin mocks.
Prueba flujos completos: conexión real a BD, CRUD, validación, consultas.
"""

import pytest

from util_bbdd import DatabaseManager


@pytest.mark.e2e
@pytest.mark.sqlite
class TestSyncDatabaseManagerE2E:
    """Tests E2E para DatabaseManager sincrónico con BD real."""

    def test_e2e_connect_and_get_tables(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Conectar a BD real y obtener lista de tablas."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Act
            tables = manager.get_tables()

            # Assert
            # SQLite devuelve tuplas, extraer primer elemento de cada tupla si es necesario
            table_names = [t[0] if isinstance(t, tuple) else t for t in tables]
            assert "users" in table_names
            assert "orders" in table_names
            assert len(table_names) >= 2
        finally:
            manager.close()

    def test_e2e_get_columns_info(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Obtener información de columnas de tabla real."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Act
            columns = manager.get_columns("users")

            # Assert
            assert len(columns) > 0
            # SQLite devuelve: (cid, name, type, notnull, dflt_value, pk)
            col_names = [col[1] for col in columns]  # Extraer nombres
            assert "id" in col_names
            assert "nombre" in col_names
            assert "email" in col_names
            assert "edad" in col_names
        finally:
            manager.close()

    def test_e2e_simple_select_query(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Ejecutar SELECT simple sin parámetros (template-only)."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Act
            users = manager.execute_query("get_all_users")

            # Assert
            assert users is not None
            # La BD tiene 3 usuarios insertados en seed
            rows = users.fetchall() if hasattr(users, "fetchall") else list(users)
            assert len(rows) == 3
        finally:
            manager.close()

    def test_e2e_select_with_parameters(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Ejecutar SELECT con parámetros."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Act
            result = manager.execute_query("get_user_by_id", user_id=1)

            # Assert
            rows = result.fetchall() if hasattr(result, "fetchall") else list(result)
            assert len(rows) == 1
            user = rows[0]
            assert user[1] == "Alice Johnson"  # nombre
            assert user[2] == "alice@example.com"  # email
        finally:
            manager.close()

    def test_e2e_insert_and_verify(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: INSERT real en BD y verificar con SELECT."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Verificar estado inicial
            result_before = manager.execute_query("get_user_count")
            # execute_query retorna una lista de tuplas
            rows_before = result_before if isinstance(result_before, list) else list(result_before)
            count_before = rows_before[0][0]
            assert count_before == 3

            # Act: Insertar nuevo usuario
            manager.execute_query("insert_user", nombre="Diana Prince", email="diana@example.com", edad=28)

            # Assert: Verificar que fue insertado
            result_after = manager.execute_query("get_user_count")
            rows_after = result_after if isinstance(result_after, list) else list(result_after)
            count_after = rows_after[0][0]
            assert count_after == count_before + 1

            # Verificar que está en la BD
            result_diana = manager.execute_query("get_user_by_id", user_id=4)
            rows = result_diana if isinstance(result_diana, list) else list(result_diana)
            assert len(rows) == 1
            assert rows[0][1] == "Diana Prince"
        finally:
            manager.close()

    def test_e2e_update_and_verify(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: UPDATE real en BD y verificar cambios."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Obtener usuario original
            result_before = manager.execute_query("get_user_by_id", user_id=1)
            rows_before = result_before if isinstance(result_before, list) else list(result_before)
            user_before = rows_before[0]
            email_before = user_before[2]

            # Act: Actualizar usuario
            new_email = "alice_updated@example.com"
            manager.execute_query("update_user", user_id=1, email=new_email, edad=31)

            # Assert: Verificar que se actualizó
            result_after = manager.execute_query("get_user_by_id", user_id=1)
            rows_after = result_after if isinstance(result_after, list) else list(result_after)
            user_after = rows_after[0]
            assert user_after[2] == new_email
            assert user_after[3] == 31  # edad is at index 3: id(0), nombre(1), email(2), edad(3), created_at(4)
        finally:
            manager.close()

    def test_e2e_delete_and_verify(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: DELETE real en BD y verificar eliminación."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Contar antes
            result_before = manager.execute_query("get_user_count")
            rows_before = result_before if isinstance(result_before, list) else list(result_before)
            count_before = rows_before[0][0]

            # Act: Eliminar usuario
            manager.execute_query("delete_user", user_id=2)

            # Assert: Contar después
            result_after = manager.execute_query("get_user_count")
            rows_after = result_after if isinstance(result_after, list) else list(result_after)
            count_after = rows_after[0][0]
            assert count_after == count_before - 1

            # Verificar que no está
            result_deleted = manager.execute_query("get_user_by_id", user_id=2)
            rows = result_deleted if isinstance(result_deleted, list) else list(result_deleted)
            assert len(rows) == 0
        finally:
            manager.close()

    def test_e2e_query_not_found(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Error cuando query no existe en sql_queries.json."""
        from util_bbdd.database_exceptions import DatabaseOperationError

        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Act & Assert - The query not found raises DatabaseOperationError (wrapped ValueError)
            with pytest.raises(DatabaseOperationError):
                manager.execute_query("nonexistent_query")
        finally:
            manager.close()

    def test_e2e_connection_reuse(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Reutilizar manager para múltiples consultas."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Act & Assert: Ejecutar varias operaciones sin reconectar
            tables1 = manager.get_tables()
            tables2 = manager.get_tables()
            users1 = manager.execute_query("get_all_users")
            users2 = manager.execute_query("get_all_users")

            assert tables1 == tables2
            rows1 = users1.fetchall() if hasattr(users1, "fetchall") else list(users1)
            rows2 = users2.fetchall() if hasattr(users2, "fetchall") else list(users2)
            assert len(rows1) == len(rows2) == 3
        finally:
            manager.close()

    def test_e2e_transaction_consistency(self, sqlite_engine_with_schema, sqlite_connection_config):
        """Test: Consistencia en transacciones múltiples."""
        manager = DatabaseManager(**sqlite_connection_config)
        try:
            # Act: Insertar y leer en la misma sesión
            manager.execute_query("insert_user", nombre="Eve Wilson", email="eve@example.com", edad=27)

            result = manager.execute_query("get_all_users")
            rows = result if isinstance(result, list) else list(result)

            # Assert
            assert len(rows) == 4
            names = [row[1] for row in rows]
            assert "Eve Wilson" in names
        finally:
            manager.close()
