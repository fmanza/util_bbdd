"""Adaptador async de orquestación Snowflake para AsyncDatabaseManager.

Snowflake no tiene soporte nativo async en snowflake-connector-python.
Los métodos `*_sync` son la implementación real (compatibles con SnowflakeSyncAdapter).
Los métodos `*_async` son wrappers sobre los sync usando run_in_executor.

Nota: Snowflake usa jerarquía de 3 niveles (database/schema/table),
por lo que los métodos aceptan `database` además de `schema`/`table`.
"""

from __future__ import annotations

import asyncio
import functools

from typing import Any

from ._snowflake_models import SnowflakeRoutineDetail
from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import fetch_routine_parameters_sync, fetch_routines_sync
from .tables import fetch_columns_sync, fetch_tables_sync


class SnowflakeAsyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección async de Snowflake.

    Snowflake no tiene driver nativo async (snowflake-connector-python es bloqueante).
    Los métodos `*_sync` son la implementación real, idénticos a SnowflakeSyncAdapter.
    Los métodos `*_async` los envuelven en run_in_executor.

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

    def fetch_databases_sync(self) -> list[tuple]:
        """Obtiene lista de bases de datos.

        Returns:
            list[tuple]: Filas (database_name,)
        """
        return []

    def fetch_schemas_sync(self, database: str | None = None) -> list[tuple]:
        """Obtiene lista de schemas.

        Args:
            database: Nombre de la base de datos

        Returns:
            list[tuple]: Filas (schema_name,)
        """
        if not self.manager or not database:
            return []
        conn = self._get_conn()
        if not conn:
            return []
        from .tables import fetch_schemas_sync as _fetch_schemas

        return _fetch_schemas(conn, database)

    def fetch_tables_sync(self, database: str | None = None, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        if not self.manager or not database or not schema:
            return []
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_tables_sync(conn, database, schema)

    def fetch_columns_sync(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Obtiene columnas de una tabla.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema
            table: Nombre de la tabla

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable,
                               ordinal_position, column_default, column_comment)
        """
        if not self.manager or not database or not schema or not table:
            return []
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_columns_sync(conn, database, schema, table)

    def fetch_primary_keys_sync(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Obtiene claves primarias.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema
            table: Nombre de la tabla

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ordinal_position)
        """
        if not self.manager or not database or not schema or not table:
            return []
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_primary_keys_sync(conn, database, schema, table)

    def fetch_foreign_keys_sync(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Obtiene claves foráneas.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema
            table: Nombre de la tabla

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                               on_delete_action, on_update_action, ordinal_position)
        """
        if not self.manager or not database or not schema or not table:
            return []
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_foreign_keys_sync(conn, database, schema, table)

    def fetch_indexes_sync(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Obtiene índices (Snowflake no tiene índices de usuario; devuelve lista vacía).

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema
            table: Nombre de la tabla

        Returns:
            list[tuple]: Lista vacía
        """
        if not self.manager or not database or not schema or not table:
            return []
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_indexes_sync(conn, database, schema, table)

    def fetch_routines_sync(
        self, database: str | None = None, schema: str | None = None
    ) -> list[SnowflakeRoutineDetail]:
        """Obtiene rutinas.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema

        Returns:
            list[SnowflakeRoutineDetail]: Detalles de rutinas
        """
        if not self.manager or not database or not schema:
            return []
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_routines_sync(conn, database, schema)

    def fetch_routine_parameters_sync(
        self,
        database: str | None = None,
        schema: str | None = None,
        routine_name: str | None = None,
    ) -> list[tuple]:
        """Obtiene parámetros de una rutina.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema
            routine_name: Nombre de la rutina

        Returns:
            list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
        """
        if not self.manager or not database or not schema or not routine_name:
            return []
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_routine_parameters_sync(conn, database, schema, routine_name)

    # ────────────────────────── Wrappers async ────────────────────────────────

    async def fetch_databases_async(self) -> list[tuple]:
        """Versión async de fetch_databases_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fetch_databases_sync)

    async def fetch_schemas_async(self, database: str | None = None) -> list[tuple]:
        """Versión async de fetch_schemas_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_schemas_sync, database))

    async def fetch_tables_async(self, database: str | None = None, schema: str | None = None) -> list[tuple]:
        """Versión async de fetch_tables_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_tables_sync, database, schema))

    async def fetch_columns_async(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Versión async de fetch_columns_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_columns_sync, database, schema, table))

    async def fetch_primary_keys_async(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Versión async de fetch_primary_keys_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(self.fetch_primary_keys_sync, database, schema, table)
        )

    async def fetch_foreign_keys_async(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Versión async de fetch_foreign_keys_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(self.fetch_foreign_keys_sync, database, schema, table)
        )

    async def fetch_indexes_async(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Versión async de fetch_indexes_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_indexes_sync, database, schema, table))

    async def fetch_routines_async(
        self, database: str | None = None, schema: str | None = None
    ) -> list[SnowflakeRoutineDetail]:
        """Versión async de fetch_routines_sync."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self.fetch_routines_sync, database, schema))

    async def fetch_routine_parameters_async(
        self,
        database: str | None = None,
        schema: str | None = None,
        routine_name: str | None = None,
        routine_type: str | None = None,
    ) -> list[tuple]:
        """Versión async de fetch_routine_parameters_sync.

        Args:
            routine_type: Tipo de rutina (no usado en Snowflake).
        """
        del routine_type  # not applicable in Snowflake; kept for interface compatibility
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, functools.partial(self.fetch_routine_parameters_sync, database, schema, routine_name)
        )

    async def fetch_routine_definition_async(
        self,
        database: str | None = None,
        schema: str | None = None,
        routine: str | None = None,
        routine_type: str | None = None,
    ) -> str:
        """Obtiene DDL de una rutina (no soportado directamente en Snowflake)."""
        del database, schema  # not applicable in this stub; kept for interface compatibility
        await asyncio.sleep(0)
        return f"-- {routine_type or 'ROUTINE'} {routine} definition not available via this adapter\n"
