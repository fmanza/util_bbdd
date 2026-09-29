"""Adaptador async de orquestación MySQL para AsyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en MySQL con soporte asíncrono.

Nota: Delega a sync adapter via run_in_executor para evitar duplicación de código.
"""

from __future__ import annotations

import asyncio

from collections.abc import Callable
from typing import Any, TypeVar

from ...results import Rows
from ..mariadb.async_adapter import MariaDBAsyncAdapter
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

    # ==================== Lecturas especializadas (EngineMetadataAdapterAsync) ====================
    # MySQL 8 comparte con MariaDB el information_schema que usan estas lecturas (validado contra MySQL 8.4): se
    # delegan en MariaDBAsyncAdapter sobre el mismo manager, que las resuelve con el catálogo de queries de "mysql".

    def _engine_metadata(self) -> MariaDBAsyncAdapter:
        reader: MariaDBAsyncAdapter | None = getattr(self, "_engine_metadata_reader", None)
        if reader is None:
            reader = MariaDBAsyncAdapter(self.manager)
            self._engine_metadata_reader = reader
        return reader

    async def fetch_routines(self, context_database: str) -> Rows:
        """Rutinas del contexto (nombre, tipo, comentario)."""
        return await self._engine_metadata().fetch_routines(context_database)

    async def build_table_ddl_from_metadata(self, tabla: str) -> str:
        """DDL de una tabla reconstruido desde columnas y PK."""
        return await self._engine_metadata().build_table_ddl_from_metadata(tabla)

    async def fetch_view_from_information_schema(self, database: str, view_name: str) -> str:
        """DDL de una vista desde information_schema.views."""
        return await self._engine_metadata().fetch_view_from_information_schema(database, view_name)

    async def fetch_columns_safe(self, context_database: str, tabla: str) -> Rows:
        """Columnas de una tabla leídas en HEX (seguras frente a problemas de charset)."""
        return await self._engine_metadata().fetch_columns_safe(context_database, tabla)

    async def fetch_routine_parameters_public_rows(
        self, *, database: str, routine_name: str, routine_type: str
    ) -> Rows:
        """Parámetros públicos de una rutina."""
        return await self._engine_metadata().fetch_routine_parameters_public_rows(
            database=database, routine_name=routine_name, routine_type=routine_type
        )

    async def fetch_routine_from_information_schema(self, database: str, routine_name: str, routine_type: str) -> str:
        """DDL de una rutina."""
        return await self._engine_metadata().fetch_routine_from_information_schema(database, routine_name, routine_type)

    async def storage_inventory(self, context_database: str) -> dict[str, Any]:
        """Inventario de almacenamiento (ficheros por tabla y tablespaces temporales)."""
        return await self._engine_metadata().storage_inventory(context_database)
