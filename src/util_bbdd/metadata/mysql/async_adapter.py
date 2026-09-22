"""Adaptador async de orquestación MySQL para AsyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en MySQL con soporte asíncrono.

Nota: Delega a sync adapter via run_in_executor para evitar duplicación de código.
"""

from __future__ import annotations

import asyncio

from collections.abc import Callable
from typing import Any, TypeVar

from ._mysql_models import MysqlRoutineDetail
from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import (
    fetch_routine_definition_sync,
    fetch_routine_parameters_sync,
    fetch_routines_sync,
)
from .tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync

_T = TypeVar("_T")


class MysqlAsyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección async de MySQL.

    Responsabilidades:
    - Extracción asíncrona de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def __init__(self, manager: Any) -> None:
        """Inicializa el adaptador con un manager.

        Args:
            manager: DbManagerProtocol (duck-typed) con métodos async
        """
        self.manager = manager

    def _get_conn(self) -> Any:
        """Devuelve la conexión activa del manager."""
        return self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

    async def _run_sync(self, fn: Callable[..., _T], *args: Any) -> _T:
        """Ejecuta fn(*args) en el executor por defecto del event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn, *args)

    async def fetch_schemas_async(self) -> list[tuple]:
        """Obtiene lista de schemas en MySQL.

        Returns:
            list[tuple]: Filas (schema_name,)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return await self._run_sync(fetch_schemas_sync, conn)

    async def fetch_tables_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en un schema.

        Args:
            schema: Nombre del schema

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return await self._run_sync(fetch_tables_sync, conn, schema)

    async def fetch_columns_async(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
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
        return await self._run_sync(fetch_columns_sync, conn, schema, table)

    async def fetch_primary_keys_async(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene claves primarias.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ordinal_position)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return await self._run_sync(fetch_primary_keys_sync, conn, schema, table)

    async def fetch_foreign_keys_async(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene claves foráneas.

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
        return await self._run_sync(fetch_foreign_keys_sync, conn, schema, table)

    async def fetch_indexes_async(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
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
        return await self._run_sync(fetch_indexes_sync, conn, schema, table)

    async def fetch_routines_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene rutinas (PROCEDURE, FUNCTION) de un schema (RoutineAdapter).

        Convierte ``MysqlRoutineDetail`` (dataclass interno) a tupla en el límite
        público del adapter, para cumplir el Protocol ``RoutineAdapterAsync``
        (MDC-03, AUDIT_CODE 2026-09-22; ver nota en ``sync_adapter.py``).

        Args:
            schema: Nombre del schema.

        Returns:
            list[tuple]: Filas (routine_name, routine_type, created_datetime)
        """
        conn = self._get_conn()
        if not conn:
            return []
        details: list[MysqlRoutineDetail] = await self._run_sync(fetch_routines_sync, conn, schema)
        return [(d.routine_name, d.routine_type, d.created_datetime) for d in details]

    async def fetch_routine_parameters_async(
        self, schema: str | None = None, routine_name: str | None = None, routine_type: str | None = None
    ) -> list[tuple]:
        """Obtiene parámetros de una rutina.

        Args:
            schema: Nombre del schema.
            routine_name: Nombre de la rutina.
            routine_type: Tipo de rutina ('PROCEDURE' o 'FUNCTION'). No usado en MySQL
                (information_schema.PARAMETERS no filtra por tipo).

        Returns:
            list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return await self._run_sync(fetch_routine_parameters_sync, conn, schema, routine_name)

    async def fetch_routine_definition_async(self, schema: str, routine: str, routine_type: str) -> str:
        """Obtiene el DDL completo de una rutina (RoutineAdapter).

        Args:
            schema: Nombre del schema.
            routine: Nombre de la rutina.
            routine_type: Tipo de rutina ('PROCEDURE' o 'FUNCTION').

        Returns:
            str: DDL de la rutina (p.ej. 'CREATE PROCEDURE ...') o cadena vacía si no disponible.
        """
        conn = self._get_conn()
        if not conn:
            return ""
        return await self._run_sync(fetch_routine_definition_sync, conn, schema, routine, routine_type)
