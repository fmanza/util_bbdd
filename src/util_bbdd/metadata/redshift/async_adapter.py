"""Adaptador async de orquestación Redshift para AsyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
asíncrona de metadatos en Redshift.

Redshift usa psycopg2 (bloqueante). Los métodos `*_sync` son la implementación
real; los métodos `*_async` son wrappers que los envuelven en run_in_executor.
"""

from __future__ import annotations

import asyncio
import functools

from typing import Any

from ._redshift_models import RedshiftRoutineDetail
from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import fetch_routine_parameters_sync, fetch_routines_sync
from .tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class RedshiftAsyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección async de Redshift.

    Redshift no tiene driver nativo async (psycopg2 es bloqueante).
    Los métodos `*_sync` contienen la implementación real.
    Los métodos `*_async` los envuelven en run_in_executor.

    Responsabilidades:
    - Extracción asíncrona de metadatos: tablas, columnas, constraints, índices, routines.
    - Normalización de retornos a list[tuple] (excepto routines).

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def __init__(self, manager: Any) -> None:
        """Inicializa el adaptador con un manager.

        Args:
            manager: AsyncDbManagerProtocol (duck-typed) con atributos de conexión
        """
        self.manager = manager

    def _get_conn(self) -> Any:
        """Devuelve la conexión activa del manager."""
        if not self.manager:
            return None
        return self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

    # ─────────────────────────── Implementación sync ──────────────────────────

    def fetch_schemas_sync(self) -> list[tuple]:
        """Obtiene lista de schemas en Redshift.

        Returns:
            list[tuple]: Filas (schema_name,)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_schemas_sync(conn)

    def fetch_tables_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en un schema.

        Args:
            schema: Nombre del schema

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_tables_sync(conn, schema)

    def fetch_columns_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene columnas de una tabla.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable,
                               ordinal_position, column_default, column_comment)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_columns_sync(conn, schema, table)

    def fetch_primary_keys_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene claves primarias (advisory en Redshift).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ordinal_position)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_primary_keys_sync(conn, schema, table)

    def fetch_foreign_keys_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene claves foráneas (advisory en Redshift).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                               on_delete_action, on_update_action, ordinal_position)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_foreign_keys_sync(conn, schema, table)

    def fetch_indexes_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene índices de una tabla.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, column_name, seq_in_index, is_unique)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_indexes_sync(conn, schema, table)

    def fetch_routines_sync(self, schema: str | None = None) -> list[RedshiftRoutineDetail]:
        """Obtiene rutinas (UDFs) del schema.

        Returns:
            list[RedshiftRoutineDetail]: Detalles de rutinas
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_routines_sync(conn, schema)

    def fetch_routine_parameters_sync(self, schema: str | None = None, routine_name: str | None = None) -> list[tuple]:
        """Obtiene parámetros de una rutina.

        Args:
            schema: Nombre del schema.
            routine_name: Nombre de la rutina.

        Returns:
            list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_routine_parameters_sync(conn, schema, routine_name)

    # ────────────────────────── Wrappers async ────────────────────────────────

    async def fetch_schemas_async(self) -> list[tuple]:
        """Versión async de fetch_schemas_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fetch_schemas_sync)

    async def fetch_tables_async(self, schema: str | None = None) -> list[tuple]:
        """Versión async de fetch_tables_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_tables_sync, schema))

    async def fetch_columns_async(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Versión async de fetch_columns_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_columns_sync, schema, table))

    async def fetch_primary_keys_async(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Versión async de fetch_primary_keys_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_primary_keys_sync, schema, table))

    async def fetch_foreign_keys_async(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Versión async de fetch_foreign_keys_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_foreign_keys_sync, schema, table))

    async def fetch_indexes_async(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Versión async de fetch_indexes_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_indexes_sync, schema, table))

    async def fetch_routines_async(self, schema: str | None = None) -> list[RedshiftRoutineDetail]:
        """Versión async de fetch_routines_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_routines_sync, schema))

    async def fetch_routine_parameters_async(
        self, schema: str | None = None, routine_name: str | None = None, routine_type: str | None = None
    ) -> list[tuple]:
        """Versión async de fetch_routine_parameters_sync.

        Args:
            schema: Nombre del schema.
            routine_name: Nombre de la rutina.
            routine_type: Tipo de rutina (no usado en Redshift).
        """
        del routine_type  # not applicable in Redshift; kept for interface compatibility
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(self.fetch_routine_parameters_sync, schema, routine_name)
        )

    async def fetch_routine_definition_async(
        self, schema: str | None = None, routine: str | None = None, routine_type: str | None = None
    ) -> str:
        """Obtiene DDL de una rutina (no soportado directamente en Redshift)."""
        del schema  # not applicable in Redshift; kept for interface compatibility
        await asyncio.sleep(0)
        return f"-- {routine_type or 'ROUTINE'} {routine} definition not available in Redshift\n"
