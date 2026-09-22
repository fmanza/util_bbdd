"""Adaptador async de orquestación Oracle para AsyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en Oracle con soporte asíncrono.

Nota: Actualmente delega a sync adapter via run_in_executor para evitar
duplicación de código. En futuro puede optimizarse con drivers Oracle async nativos.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ...results import Rows
from ._adapter_helpers import (
    build_oracle_columns_query,
    build_oracle_fk_query,
    build_oracle_indexes_query,
    build_oracle_parameters_query,
    build_oracle_pk_query,
    build_oracle_routine_body_query,
    build_oracle_routines_query,
    build_oracle_schemas_query,
    build_oracle_tables_query,
    decode_oracle_parameter_rows,
    decode_oracle_routine_body,
    decode_oracle_routine_rows,
    routine_entries_to_rows,
)
from ._manager_protocol import OracleAsyncManagerProtocol
from ._oracle_models import OracleParameterDetail, OracleRoutineDetail
from .constraints import OracleConstraintDefaults
from .indexes import decode_oracle_index_rows
from .tables import decode_oracle_column_rows


class OracleAsyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección async de Oracle.

    Responsabilidades:
    - Extracción asíncrona de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def __init__(self, manager: OracleAsyncManagerProtocol) -> None:
        """Inicializa el adaptador con un manager.

        Args:
            manager: OracleAsyncManagerProtocol con métodos execute_custom_many async, db_cache, etc.
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

    async def fetch_schemas_async(self) -> list[tuple]:
        """Obtiene lista de schemas (owners) en modo asíncrono.

        Returns:
            list[tuple]: Filas (schema_name,)
        """
        sql = build_oracle_schemas_query()
        rows: Rows = await self.manager.execute_custom_many(sql, params={})
        return [(str(r[0]).strip(),) if r else ("",) for r in rows if r]

    async def fetch_tables_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en modo asíncrono (SourceAdapter).

        Args:
            schema: Nombre del esquema (owner).

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        schema_name = schema or ""
        sql = build_oracle_tables_query()
        rows: Rows = await self.manager.execute_custom_many(sql, params={"owner": schema_name})
        return [(str(r[0]), str(r[1]) if len(r) > 1 else "TABLE", str(r[2]) if len(r) > 2 else "") for r in rows if r]

    async def fetch_columns_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla en modo asíncrono (SourceAdapter).

        Args:
            schema: Nombre del schema (owner).
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable,
                               ordinal_position, column_default, column_comment)
        """
        sql = build_oracle_columns_query()
        rows: Rows = await self.manager.execute_custom_many(sql, params={"owner": schema, "table_name": table})
        return decode_oracle_column_rows(rows)

    async def fetch_primary_keys_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves primarias en modo asíncrono (SourceAdapter).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ordinal_position)
        """
        sql = build_oracle_pk_query()
        rows: Rows = await self.manager.execute_custom_many(sql, params={"owner": schema, "table_name": table})
        return OracleConstraintDefaults.decode_pk_rows(rows)

    async def fetch_foreign_keys_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves foráneas en modo asíncrono (SourceAdapter).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ref_owner, ref_table,
                               ref_column, on_delete_action, on_update_action, ordinal_position)
        """
        sql = build_oracle_fk_query()
        rows: Rows = await self.manager.execute_custom_many(sql, params={"owner": schema, "table_name": table})
        return OracleConstraintDefaults.decode_fk_rows(rows)

    async def fetch_indexes_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene índices en modo asíncrono (SourceAdapter).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, column_name, order_direction, uniqueness, ordinal_position)
        """
        sql = build_oracle_indexes_query()
        rows: Rows = await self.manager.execute_custom_many(sql, params={"owner": schema, "table_name": table})
        return decode_oracle_index_rows(rows)

    async def get_routine_details(self, schema: str | None = None) -> list[OracleRoutineDetail]:
        """Obtiene detalles de rutinas (funciones, procedimientos) del schema.

        Args:
            schema: Nombre del schema (owner).

        Returns:
            list[OracleRoutineDetail]: Rutinas decodificadas
        """
        schema_name = schema or ""
        cache_key: str = f"oracle:routines:{schema_name}"

        async def _fetch_rows() -> list[OracleRoutineDetail]:
            rows: Rows = await self.manager.execute_custom_many(
                build_oracle_routines_query(),
                params={"owner": schema_name},
            )
            return decode_oracle_routine_rows(rows)

        entries = await self._get_cached_entries(
            cache_lookup=lambda: (
                self.manager.db_cache._routine_metadata_context_cache.get(cache_key)
                if hasattr(self.manager, "db_cache")
                else None
            ),
            cache_store=lambda items: (
                self.manager.db_cache._routine_metadata_context_cache.__setitem__(cache_key, list(items))
                if hasattr(self.manager, "db_cache")
                else None
            ),
            fetch_entries=_fetch_rows,
            cache_hit_message=f"♻️  Usando metadata detallada de rutinas Oracle en caché para {schema_name}",
            success_message=f"✅ {{count}} rutinas Oracle detalladas obtenidas para {schema_name}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de rutinas Oracle para {schema_name}",
        )
        return [entry for entry in entries if isinstance(entry, OracleRoutineDetail)]

    async def get_routine_parameters_details(
        self, schema: str | None = None, routine_name: str | None = None, routine_type: str = "PROCEDURE"
    ) -> list[OracleParameterDetail]:
        """Obtiene detalles de parámetros de rutinas del schema.

        Args:
            schema: Nombre del schema (owner).
            routine_name: Nombre de la rutina específica (si None, todas).
            routine_type: Tipo de rutina (PROCEDURE, FUNCTION, etc).

        Returns:
            list[OracleParameterDetail]: Parámetros decodificados
        """
        schema_name = schema or ""
        routine_name_param = routine_name or ""
        cache_key: str = f"oracle:routine_parameters:{schema_name}:{routine_name_param}"

        async def _fetch_rows() -> list[OracleParameterDetail]:
            rows: Rows = await self.manager.execute_custom_many(
                build_oracle_parameters_query(),
                params={"owner": schema_name, "routine_name": routine_name or ""},
            )
            return decode_oracle_parameter_rows(schema_name, routine_name or "", routine_type, rows)

        entries = await self._get_cached_entries(
            cache_lookup=lambda: (
                self.manager.db_cache._routine_parameters_context_cache.get(cache_key)
                if hasattr(self.manager, "db_cache")
                else None
            ),
            cache_store=lambda items: (
                self.manager.db_cache._routine_parameters_context_cache.__setitem__(cache_key, list(items))
                if hasattr(self.manager, "db_cache")
                else None
            ),
            fetch_entries=_fetch_rows,
            cache_hit_message=f"♻️  Usando metadata detallada de parámetros Oracle en caché para {schema_name}.{routine_name}",
            success_message=f"✅ {{count}} parámetros de rutinas Oracle obtenidos para {schema_name}.{routine_name}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de parámetros de rutinas Oracle para {schema_name}.{routine_name}",
        )
        return [entry for entry in entries if isinstance(entry, OracleParameterDetail)]

    async def get_routines_public_rows(self, schema: str | None = None) -> list[tuple]:
        """Obtiene rutinas en formato público de fila.

        Args:
            schema: Nombre del schema (owner).

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_owner)
        """
        routines = await self.get_routine_details(schema)
        return routine_entries_to_rows(routines)

    # ==================== RoutineAdapter Protocol ====================
    # MEO-01 (AUDIT_CODE 2026-09-22): OracleAsyncAdapter se registra como routine adapter
    # (metadata/oracle/__init__.py) pero no implementaba estos 3 métodos del Protocol.

    async def fetch_routines_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de routines en modo asíncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (owner).

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_owner).
        """
        return await self.get_routines_public_rows(schema)

    async def fetch_routine_parameters_async(self, schema: str, routine: str, routine_type: str) -> list[tuple]:
        """Obtiene parámetros de una routine en modo asíncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (owner).
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            list[tuple]: Filas (in_out, parameter_name, data_type, ordinal_position).
        """
        details = await self.get_routine_parameters_details(schema, routine, routine_type)
        return [detail.to_public_row() for detail in details]

    async def fetch_routine_definition_async(self, schema: str, routine: str, routine_type: str) -> str:
        """Obtiene el DDL completo de una routine en modo asíncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (owner).
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            str: DDL de la rutina (p.ej. 'CREATE OR REPLACE PROCEDURE ...').
        """
        sql = build_oracle_routine_body_query()
        rows: Rows = await self.manager.execute_custom_many(
            sql,
            params={"owner": schema, "routine_name": routine, "routine_type": routine_type.upper()},
        )
        return decode_oracle_routine_body(routine_type, routine, rows)


__all__: list[str] = [
    "OracleAsyncAdapter",
]
