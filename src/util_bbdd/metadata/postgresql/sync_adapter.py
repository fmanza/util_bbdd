"""Adaptador sync de orquestación PostgreSQL para SyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ._adapter_helpers import (
    build_columns_safe_sql,
    build_fk_constraint_sql,
    build_indexes_safe_sql,
    build_pk_constraint_sql,
    build_tables_sql,
    routine_entries_to_rows,
)
from ._postgres_models import PgParameterDetail, PgRoutineDetail
from .routines import (
    build_public_postgres_routine_parameter_entry_rows,
    decode_postgres_parameter_rows,
    decode_postgres_routine_rows,
    filter_postgres_routine_parameter_entries,
)
from .tables import decode_postgres_column_rows


class PostgreSQLSyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección sync de PostgreSQL.

    Responsabilidades:
    - Extracción de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def __init__(self, manager: Any) -> None:
        """Inicializa el adaptador con un manager.

        Args:
            manager: DbManagerProtocol (duck-typed) con métodos execute_custom_one(), execute_custom_many()
        """
        self.manager = manager

    def _get_cached_entries(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_entries: Callable[[], list[Any]],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str,
    ) -> list[Any]:
        """Abstracción genérica para caché coherente."""
        # Intentar usar el mecanismo de caché del manager si existe
        if hasattr(self.manager, "_get_cached_rows"):
            return list(
                self.manager._get_cached_rows(
                    cache_lookup=cache_lookup,
                    cache_store=cache_store,
                    fetch_rows=fetch_entries,
                    cache_hit_message=cache_hit_message,
                    success_message=success_message,
                    fetch_debug_message=fetch_debug_message,
                )
            )

        # Fallback: caché simple
        cached = cache_lookup()
        if cached is not None:
            return cached

        entries = fetch_entries()
        cache_store(entries)
        return entries

    def get_routine_details(self, schema: str | None = None) -> list[PgRoutineDetail]:
        """Obtiene detalles de rutinas (funciones, procedimientos) del schema.

        Args:
            schema: Nombre del schema. Si None, usa public.

        Returns:
            list[PgRoutineDetail]: Rutinas decodificadas
        """
        schema_name = schema or "public"
        cache_key: str = f"pg_routines:{schema_name}"

        entries = self._get_cached_entries(
            cache_lookup=lambda: (
                getattr(self.manager, "db_cache", {}).get("_routine_metadata_context_cache", {}).get(cache_key)
            ),
            cache_store=lambda items: (
                getattr(self.manager, "db_cache", {})
                .get("_routine_metadata_context_cache", {})
                .__setitem__(cache_key, list(items))
                if hasattr(self.manager, "db_cache")
                else None
            ),
            fetch_entries=lambda: decode_postgres_routine_rows(
                self.manager.execute_custom_many(
                    self._build_routines_query(schema_name),
                    params={"schema": schema_name},
                )
            ),
            cache_hit_message=f"♻️  Usando metadata detallada de rutinas PostgreSQL en caché para {schema_name}",
            success_message=f"✅ {{count}} rutinas PostgreSQL detalladas obtenidas para {schema_name}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de rutinas PostgreSQL para {schema_name}",
        )
        return [entry for entry in entries if isinstance(entry, PgRoutineDetail)]

    def get_routine_parameters_details(self, schema: str | None = None) -> list[PgParameterDetail]:
        """Obtiene detalles de parámetros de rutinas del schema.

        Args:
            schema: Nombre del schema.

        Returns:
            list[PgParameterDetail]: Parámetros decodificados
        """
        schema_name = schema or "public"
        cache_key: str = f"pg_routine_parameters:{schema_name}"

        entries = self._get_cached_entries(
            cache_lookup=lambda: (
                getattr(self.manager, "db_cache", {}).get("_routine_parameters_context_cache", {}).get(cache_key)
            ),
            cache_store=lambda items: (
                getattr(self.manager, "db_cache", {})
                .get("_routine_parameters_context_cache", {})
                .__setitem__(cache_key, list(items))
                if hasattr(self.manager, "db_cache")
                else None
            ),
            fetch_entries=lambda: decode_postgres_parameter_rows(
                self.manager.execute_custom_many(
                    self._build_parameters_query(),
                    params={"schema": schema_name},
                )
            ),
            cache_hit_message=f"♻️  Usando metadata detallada de parámetros PostgreSQL en caché para {schema_name}",
            success_message=f"✅ {{count}} parámetros de rutinas PostgreSQL obtenidos para {schema_name}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de parámetros de rutinas PostgreSQL para {schema_name}",
        )
        return [entry for entry in entries if isinstance(entry, PgParameterDetail)]

    def fetch_tables_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en modo síncrono.

        Args:
            schema: Nombre del esquema (público por defecto).

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        schema_name = schema or "public"
        sql = build_tables_sql(schema_name)
        rows = self.manager.execute_custom_many(sql, params={"schema": schema_name})
        return [(str(r[0]), str(r[1]), str(r[2]) if len(r) > 2 else "") for r in rows]

    def fetch_columns_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla en modo síncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable, column_key,
                               column_default, extra, column_comment)
        """
        sql = build_columns_safe_sql(schema, table)
        rows = self.manager.execute_custom_many(sql, params={"schema": schema, "table": table})
        return decode_postgres_column_rows(rows)

    def fetch_primary_keys_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves primarias en modo síncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, ordinal_position)
        """
        sql = build_pk_constraint_sql(schema, table)
        rows = self.manager.execute_custom_many(sql, params={"schema": schema, "table": table})
        return [(str(r[0]), int(r[1]) if len(r) > 1 else 0) for r in rows]

    @staticmethod
    def _extract_fk_tuple_from_row(row: Any) -> tuple[str, str, str, str, str, str, str]:
        """Extrae los 7 campos de clave foránea de una fila individual.

        Args:
            row: Tupla/lista de FK del query

        Returns:
            tuple: (constraint_name, column_name, referenced_table_schema, referenced_table_name,
                   referenced_column_name, delete_rule, update_rule) con strings vacíos como defecto
        """
        return (
            str(row[0]) if row[0] else "",
            str(row[1]) if len(row) > 1 and row[1] else "",
            str(row[2]) if len(row) > 2 and row[2] else "",
            str(row[3]) if len(row) > 3 and row[3] else "",
            str(row[4]) if len(row) > 4 and row[4] else "",
            str(row[5]) if len(row) > 5 and row[5] else "",
            str(row[6]) if len(row) > 6 and row[6] else "",
        )

    def fetch_foreign_keys_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves foráneas en modo síncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, referenced_table_schema,
                               referenced_table_name, referenced_column_name, delete_rule, update_rule)
        """
        sql = build_fk_constraint_sql(schema, table)
        rows = self.manager.execute_custom_many(sql, params={"schema": schema, "table": table})
        return [self._extract_fk_tuple_from_row(r) for r in rows]

    @staticmethod
    def _extract_index_tuple_from_row(row: Any) -> tuple[str, str, bool, bool]:
        """Extrae los 4 campos de índice de una fila individual.

        Args:
            row: Tupla/lista de index del query

        Returns:
            tuple: (index_name, index_definition, is_unique, is_primary) con valores por defecto
        """
        return (
            str(row[0]) if row[0] else "",
            str(row[1]) if len(row) > 1 and row[1] else "",
            bool(row[2]) if len(row) > 2 else False,
            bool(row[3]) if len(row) > 3 else False,
        )

    def fetch_indexes_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene índices de una tabla en modo síncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, index_definition, is_unique, is_primary)
        """
        sql = build_indexes_safe_sql(schema, table)
        rows = self.manager.execute_custom_many(sql, params={"schema": schema, "table": table})
        return [self._extract_index_tuple_from_row(r) for r in rows]

    def fetch_routines_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de rutinas (funciones/procedimientos) en modo síncrono.

        Args:
            schema: Nombre del esquema.

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_owner)
        """
        routines = self.get_routine_details(schema)
        return routine_entries_to_rows(routines)

    def fetch_routine_parameters_sync(self, schema: str, routine_name: str, routine_type: str) -> list[tuple]:
        """Obtiene parámetros de una rutina en modo síncrono.

        Args:
            schema: Nombre del esquema.
            routine_name: Nombre de la rutina.
            routine_type: Tipo (FUNCTION, PROCEDURE).

        Returns:
            list[tuple]: Filas (mode, name, data_type, default, ordinal_position)
        """
        parameters = self.get_routine_parameters_details(schema)
        filtered = filter_postgres_routine_parameter_entries(
            parameters, routine_name=routine_name, routine_type=routine_type
        )
        return build_public_postgres_routine_parameter_entry_rows(filtered)

    def _build_routines_query(self, schema: str) -> str:
        """Construye la consulta SQL para rutinas de PostgreSQL."""
        from .routines import fetch_routines_sql

        return fetch_routines_sql(schema)

    def _build_parameters_query(self) -> str:
        """Construye la consulta SQL para parámetros de rutinas de PostgreSQL."""

        # Nota: Esta es una versión simplificada que obtiene todos los parámetros del schema
        # En una implementación real, habría que filtrar por rutina específica
        return (
            "SELECT "
            "ia.ordinal_position, "
            "ia.parameter_mode, "
            "ia.parameter_name, "
            "ia.data_type, "
            "NULL AS default_value, "
            "ia.routine_name, "
            "'FUNCTION' AS routine_type "
            "FROM information_schema.parameters ia "
            "WHERE ia.specific_schema = %(schema)s "
            "ORDER BY ia.routine_name, ia.ordinal_position"
        )


__all__: list[str] = ["PostgreSQLSyncAdapter"]
