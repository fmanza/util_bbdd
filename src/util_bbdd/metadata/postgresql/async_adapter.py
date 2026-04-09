"""Adaptador async de orquestación PostgreSQL para AsyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en PostgreSQL con soporte asíncrono.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ...results import Rows
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


class PostgreSQLAsyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección async de PostgreSQL.

    Responsabilidades:
    - Extracción asíncrona de metadatos: tablas, columnas, constraints, índices, routines.
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

    async def _get_cached_entries(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_entries: Callable[[], Awaitable[list[Any]]],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str,
    ) -> list[Any]:
        """Abstracción genérica para caché coherente (async)."""
        # Intentar usar el mecanismo de caché del manager si existe
        if hasattr(self.manager, "_get_cached_rows_async"):
            return list(
                await self.manager._get_cached_rows_async(
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

        entries = await fetch_entries()
        cache_store(entries)
        return entries

    async def get_routine_details(self, schema: str | None = None) -> list[PgRoutineDetail]:
        """Obtiene detalles de rutinas (funciones, procedimientos) del schema.

        Args:
            schema: Nombre del schema. Si None, usa public.

        Returns:
            list[PgRoutineDetail]: Rutinas decodificadas
        """
        schema_name = schema or "public"
        cache_key: str = f"pg_routines:{schema_name}"

        async def _fetch_rows() -> list[PgRoutineDetail]:
            rows: Rows = await self.manager.execute_custom_many(
                self._build_routines_query(schema_name),
                params={"schema": schema_name},
            )
            return decode_postgres_routine_rows(rows)

        entries = await self._get_cached_entries(
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
            fetch_entries=_fetch_rows,
            cache_hit_message=f"♻️  Usando metadata detallada de rutinas PostgreSQL en caché para {schema_name}",
            success_message=f"✅ {{count}} rutinas PostgreSQL detalladas obtenidas para {schema_name}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de rutinas PostgreSQL para {schema_name}",
        )
        return [entry for entry in entries if isinstance(entry, PgRoutineDetail)]

    async def get_routine_parameters_details(self, schema: str | None = None) -> list[PgParameterDetail]:
        """Obtiene detalles de parámetros de rutinas del schema.

        Args:
            schema: Nombre del schema.

        Returns:
            list[PgParameterDetail]: Parámetros decodificados
        """
        schema_name = schema or "public"
        cache_key: str = f"pg_routine_parameters:{schema_name}"

        async def _fetch_rows() -> list[PgParameterDetail]:
            rows: Rows = await self.manager.execute_custom_many(
                self._build_parameters_query(schema_name),
                params={"schema": schema_name},
            )
            return decode_postgres_parameter_rows(rows)

        entries = await self._get_cached_entries(
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
            fetch_entries=_fetch_rows,
            cache_hit_message=f"♻️  Usando metadata detallada de parámetros PostgreSQL en caché para {schema_name}",
            success_message=f"✅ {{count}} parámetros de rutinas PostgreSQL obtenidos para {schema_name}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de parámetros de rutinas PostgreSQL para {schema_name}",
        )
        return [entry for entry in entries if isinstance(entry, PgParameterDetail)]

    async def fetch_tables_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en modo asíncrono.

        Args:
            schema: Nombre del esquema (público por defecto).

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        schema_name = schema or "public"
        sql = build_tables_sql(schema_name)
        rows = await self.manager.execute_custom_many(sql, params={"schema": schema_name})
        return [(str(r[0]), str(r[1]), str(r[2]) if len(r) > 2 else "") for r in rows]

    async def fetch_columns_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla en modo asíncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable, column_key,
                               column_default, extra, column_comment)
        """
        sql = build_columns_safe_sql(schema, table)
        rows = await self.manager.execute_custom_many(sql, params={"schema": schema, "table": table})
        return decode_postgres_column_rows(rows)

    async def fetch_primary_keys_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves primarias en modo asíncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, ordinal_position)
        """
        sql = build_pk_constraint_sql(schema, table)
        rows = await self.manager.execute_custom_many(sql, params={"schema": schema, "table": table})
        return [(str(r[0]), int(r[1]) if len(r) > 1 else 0) for r in rows]

    async def fetch_foreign_keys_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves foráneas en modo asíncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, referenced_table_schema,
                               referenced_table_name, referenced_column_name, delete_rule, update_rule)
        """
        sql = build_fk_constraint_sql(schema, table)
        rows = await self.manager.execute_custom_many(sql, params={"schema": schema, "table": table})
        result = []
        for r in rows:
            result.append(
                (
                    str(r[0]) if r[0] else "",
                    str(r[1]) if len(r) > 1 and r[1] else "",
                    str(r[2]) if len(r) > 2 and r[2] else "",
                    str(r[3]) if len(r) > 3 and r[3] else "",
                    str(r[4]) if len(r) > 4 and r[4] else "",
                    str(r[5]) if len(r) > 5 and r[5] else "",
                    str(r[6]) if len(r) > 6 and r[6] else "",
                )
            )
        return result

    async def fetch_indexes_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene índices de una tabla en modo asíncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, index_definition, is_unique, is_primary)
        """
        sql = build_indexes_safe_sql(schema, table)
        rows = await self.manager.execute_custom_many(sql, params={"schema": schema, "table": table})
        result = []
        for r in rows:
            result.append(
                (
                    str(r[0]) if r[0] else "",
                    str(r[1]) if len(r) > 1 and r[1] else "",
                    bool(r[2]) if len(r) > 2 else False,
                    bool(r[3]) if len(r) > 3 else False,
                )
            )
        return result

    async def fetch_routines_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de rutinas (funciones/procedimientos) en modo asíncrono.

        Args:
            schema: Nombre del esquema.

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_owner)
        """
        routines = await self.get_routine_details(schema)
        return routine_entries_to_rows(routines)

    async def fetch_routine_parameters_async(self, schema: str, routine_name: str, routine_type: str) -> list[tuple]:
        """Obtiene parámetros de una rutina en modo asíncrono.

        Args:
            schema: Nombre del esquema.
            routine_name: Nombre de la rutina.
            routine_type: Tipo (FUNCTION, PROCEDURE).

        Returns:
            list[tuple]: Filas (mode, name, data_type, default, ordinal_position)
        """
        parameters = await self.get_routine_parameters_details(schema)
        filtered = filter_postgres_routine_parameter_entries(
            parameters, routine_name=routine_name, routine_type=routine_type
        )
        return build_public_postgres_routine_parameter_entry_rows(filtered)

    def _build_routines_query(self, schema: str) -> str:
        """Construye la consulta SQL para rutinas de PostgreSQL."""
        from .routines import fetch_routines_sql

        return fetch_routines_sql(schema)

    def _build_parameters_query(self, schema: str) -> str:
        """Construye la consulta SQL para parámetros de rutinas de PostgreSQL."""
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


__all__: list[str] = ["PostgreSQLAsyncAdapter"]
