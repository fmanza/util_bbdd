"""Tests que verifican los bugs P1 corregidos en los adapters de metadata.

Bugs cubiertos:
  1. Oracle/PG cache de rutinas usaba getattr(db_cache, {}).get(...) — AttributeError silencioso
  2. PostgreSQL _build_parameters_query hardcodeaba 'FUNCTION' — excluía PROCEDURE
  3. PostgreSQL fetch_primary_keys retornaba 2-tuple en vez de 3-tuple con constraint_name
  4. SQLite fetch_procedures/functions usaban self.manager.connection sin fallback
"""

from __future__ import annotations

import asyncio

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from util_bbdd.metadata.cache import DatabaseMetadataCache
from util_bbdd.metadata.oracle import OracleAsyncAdapter, OracleSyncAdapter
from util_bbdd.metadata.postgresql import PostgreSQLAsyncAdapter, PostgreSQLSyncAdapter
from util_bbdd.metadata.sqlite.sync_adapter import SqliteSyncAdapter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager_with_cache() -> MagicMock:
    """Manager mock que expone db_cache real para validar que el caché funciona."""
    manager = MagicMock()
    cache = DatabaseMetadataCache()
    type(manager).db_cache = PropertyMock(return_value=cache)

    def _get_cached_rows_impl(*, cache_lookup, cache_store, fetch_rows, **_):
        cached = cache_lookup()
        if cached is not None:
            return cached
        result = fetch_rows()
        cache_store(result)
        return result

    manager._get_cached_rows.side_effect = _get_cached_rows_impl
    return manager


def _make_manager_without_cached_rows() -> MagicMock:
    """Manager mock sin _get_cached_rows (usa fallback directo a db_cache)."""
    manager = MagicMock(spec=[])  # sin _get_cached_rows ni _get_cached_rows_async
    cache = DatabaseMetadataCache()
    type(manager).db_cache = PropertyMock(return_value=cache)
    # Asignación directa (no .return_value) para evitar AttributeError con spec=[]
    manager.execute_custom_many = MagicMock(return_value=[])
    return manager


# ---------------------------------------------------------------------------
# Bug 1: Oracle cache de rutinas — acceso correcto a db_cache
# ---------------------------------------------------------------------------


class TestOracleCacheFix:
    """Verifica que el caché de rutinas Oracle no lanza AttributeError."""

    def test_cache_lookup_does_not_raise_on_db_cache(self) -> None:
        """El cache_lookup de get_routine_details no debe lanzar AttributeError."""
        manager = _make_manager_without_cached_rows()
        manager.execute_custom_many.return_value = []

        adapter = OracleSyncAdapter(manager)
        # No debe lanzar; antes lanzaba AttributeError por .get() sobre DatabaseMetadataCache
        result = adapter.get_routine_details(schema="HR")
        assert result == []

    def test_cache_store_populates_routine_metadata_cache(self) -> None:
        """Después de la primera llamada, el caché debe estar poblado."""
        manager = _make_manager_without_cached_rows()
        manager.execute_custom_many.return_value = []

        adapter = OracleSyncAdapter(manager)
        adapter.get_routine_details(schema="HR")

        cache_key = "oracle:routines:HR"
        cached = manager.db_cache._routine_metadata_context_cache.get(cache_key)
        # Debe existir (lista vacía en este caso, pero sin KeyError)
        assert cached is not None

    def test_second_call_uses_cache_not_db(self) -> None:
        """La segunda llamada debe usar caché y no volver a ejecutar el query."""
        manager = _make_manager_without_cached_rows()
        manager.execute_custom_many.return_value = []

        adapter = OracleSyncAdapter(manager)
        adapter.get_routine_details(schema="SCOTT")
        adapter.get_routine_details(schema="SCOTT")

        # execute_custom_many solo se llama una vez (la segunda usa caché)
        assert manager.execute_custom_many.call_count == 1

    def test_cache_lookup_for_parameters_does_not_raise(self) -> None:
        """get_routine_parameters_details no debe lanzar AttributeError."""
        manager = _make_manager_without_cached_rows()
        manager.execute_custom_many.return_value = []

        adapter = OracleSyncAdapter(manager)
        result = adapter.get_routine_parameters_details(schema="HR")
        assert result == []


class TestOracleAsyncCacheFix:
    """Verifica que el caché async de rutinas Oracle funciona."""

    def test_async_cache_does_not_raise(self) -> None:
        manager = _make_manager_without_cached_rows()
        # Necesita AsyncMock porque OracleAsyncAdapter usa `await execute_custom_many(...)`
        manager.execute_custom_many = AsyncMock(return_value=[])

        async def _run() -> None:
            adapter = OracleAsyncAdapter(manager)
            # _get_cached_rows_async no existe → usa fallback a db_cache
            result = await adapter.get_routine_details(schema="HR")
            assert result == []

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bug 2: PostgreSQL _build_parameters_query — ya no hardcodea FUNCTION
# ---------------------------------------------------------------------------


class TestPostgreSQLParametersQueryFix:
    """Verifica que la query de parámetros incluye PROCEDURE vía JOIN."""

    def test_parameters_query_contains_join_with_routines(self) -> None:
        manager = MagicMock()
        adapter = PostgreSQLSyncAdapter(manager)
        sql = adapter._build_parameters_query()

        assert "JOIN information_schema.routines" in sql, (
            "La query debe hacer JOIN con information_schema.routines para obtener routine_type real"
        )

    def test_parameters_query_does_not_hardcode_function(self) -> None:
        manager = MagicMock()
        adapter = PostgreSQLSyncAdapter(manager)
        sql = adapter._build_parameters_query()

        assert "'FUNCTION'" not in sql, (
            "La query no debe hardcodear 'FUNCTION' — debe obtener routine_type del catálogo"
        )

    def test_parameters_query_uses_r_routine_type(self) -> None:
        manager = MagicMock()
        adapter = PostgreSQLSyncAdapter(manager)
        sql = adapter._build_parameters_query()

        assert "r.routine_type" in sql, "La query debe seleccionar r.routine_type desde la tabla routines"

    def test_async_parameters_query_also_fixed(self) -> None:
        """El mismo bug existía en async_adapter — verificar que también está corregido."""
        manager = MagicMock()
        adapter = PostgreSQLAsyncAdapter(manager)
        sql = adapter._build_parameters_query()

        assert "JOIN information_schema.routines" in sql
        assert "'FUNCTION'" not in sql


# ---------------------------------------------------------------------------
# Bug 3: PostgreSQL fetch_primary_keys — retorna 3-tuple con constraint_name
# ---------------------------------------------------------------------------


class TestPostgreSQLPrimaryKeysTupleFix:
    """Verifica que fetch_primary_keys_sync retorna (constraint_name, column_name, ordinal_position)."""

    def test_fetch_primary_keys_returns_3_tuple(self) -> None:
        manager = MagicMock()
        # Simulamos lo que devolvería el SQL actualizado: (constraint_name, column_name, ordinal_pos)
        manager.execute_custom_many.return_value = [
            ("pk_users", "id", 1),
            ("pk_users", "tenant_id", 2),
        ]
        adapter = PostgreSQLSyncAdapter(manager)
        result = adapter.fetch_primary_keys_sync("public", "users")

        assert len(result) == 2
        assert len(result[0]) == 3, "Debe ser 3-tuple: (constraint_name, column_name, ordinal_position)"
        assert result[0] == ("pk_users", "id", 1)
        assert result[1] == ("pk_users", "tenant_id", 2)

    def test_fetch_primary_keys_constraint_name_is_string(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = [("pk_orders", "order_id", 1)]
        adapter = PostgreSQLSyncAdapter(manager)
        result = adapter.fetch_primary_keys_sync("public", "orders")

        constraint_name = result[0][0]
        assert isinstance(constraint_name, str)
        assert constraint_name == "pk_orders"

    def test_fetch_primary_keys_empty_table(self) -> None:
        manager = MagicMock()
        manager.execute_custom_many.return_value = []
        adapter = PostgreSQLSyncAdapter(manager)
        result = adapter.fetch_primary_keys_sync("public", "no_pk_table")
        assert result == []

    def test_async_fetch_primary_keys_also_returns_3_tuple(self) -> None:
        async def _run() -> None:
            manager = MagicMock()
            manager.execute_custom_many = AsyncMock(return_value=[("pk_items", "item_id", 1)])
            adapter = PostgreSQLAsyncAdapter(manager)
            result = await adapter.fetch_primary_keys_async("public", "items")
            assert len(result[0]) == 3
            assert result[0][0] == "pk_items"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bug 4: SQLite fetch_procedures/functions — usa fallback .db si no hay .connection
# ---------------------------------------------------------------------------


class TestSQLiteFallbackConnectionFix:
    """Verifica que fetch_procedures/functions_sync usa fallback a .db."""

    def test_fetch_procedures_uses_db_fallback_when_no_connection(self) -> None:
        """Si manager no tiene .connection, debe usar .db sin lanzar AttributeError."""
        mock_conn = MagicMock()
        manager = MagicMock(spec=["db"])  # spec sin 'connection'
        manager.db = mock_conn

        adapter = SqliteSyncAdapter(manager)
        # No debe lanzar AttributeError aunque manager no tenga .connection
        try:
            adapter.fetch_procedures_sync()
        except AttributeError as exc:
            pytest.fail(f"No debe lanzar AttributeError: {exc}")

    def test_fetch_functions_uses_db_fallback_when_no_connection(self) -> None:
        mock_conn = MagicMock()
        manager = MagicMock(spec=["db"])
        manager.db = mock_conn

        adapter = SqliteSyncAdapter(manager)
        try:
            adapter.fetch_functions_sync()
        except AttributeError as exc:
            pytest.fail(f"No debe lanzar AttributeError: {exc}")

    def test_fetch_procedures_returns_empty_when_no_conn(self) -> None:
        """Si no hay conexión disponible (ni .connection ni .db), retorna []."""
        manager = MagicMock(spec=["connection"])
        manager.connection = None

        adapter = SqliteSyncAdapter(manager)
        result = adapter.fetch_procedures_sync()
        assert result == []

    def test_fetch_functions_returns_empty_when_no_conn(self) -> None:
        manager = MagicMock(spec=["connection"])
        manager.connection = None

        adapter = SqliteSyncAdapter(manager)
        result = adapter.fetch_functions_sync()
        assert result == []


# ---------------------------------------------------------------------------
# Bug 1 (PostgreSQL): cache de rutinas PG — acceso correcto a db_cache
# ---------------------------------------------------------------------------


class TestPostgreSQLCacheFix:
    """Verifica que el caché de rutinas PostgreSQL no lanza AttributeError."""

    def test_cache_lookup_does_not_raise_on_pg_routine_cache(self) -> None:
        manager = _make_manager_without_cached_rows()
        manager.execute_custom_many.return_value = []

        adapter = PostgreSQLSyncAdapter(manager)
        result = adapter.get_routine_details(schema="public")
        assert result == []

    def test_pg_cache_store_populates_after_first_call(self) -> None:
        manager = _make_manager_without_cached_rows()
        manager.execute_custom_many.return_value = []

        adapter = PostgreSQLSyncAdapter(manager)
        adapter.get_routine_details(schema="myschema")

        cache_key = "pg_routines:myschema"
        cached = manager.db_cache._routine_metadata_context_cache.get(cache_key)
        assert cached is not None

    def test_pg_second_call_uses_cache(self) -> None:
        manager = _make_manager_without_cached_rows()
        manager.execute_custom_many.return_value = []

        adapter = PostgreSQLSyncAdapter(manager)
        adapter.get_routine_details(schema="public")
        adapter.get_routine_details(schema="public")

        assert manager.execute_custom_many.call_count == 1
