"""Adaptador sync de orquestación SQL Server para SyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en SQL Server.
"""

from __future__ import annotations

from typing import Any

from ._sqlserver_models import SqlServerParameterDetail, SqlServerRoutineDetail
from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import fetch_routine_parameters_sync, fetch_routines_sync
from .tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class SqlServerSyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección sync de SQL Server.

    Responsabilidades:
    - Extracción de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def __init__(self, manager: Any) -> None:
        """Inicializa el adaptador con un manager.

        Args:
            manager: DbManagerProtocol (duck-typed) con atributos de conexión
        """
        self.manager = manager

    def fetch_schemas_sync(self) -> list[tuple]:
        """Obtiene lista de schemas en SQL Server.

        Returns:
            list[tuple]: Filas (schema_name,)
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_schemas_sync(conn)

    def fetch_tables_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en un schema.

        Args:
            schema: Nombre del schema (por defecto 'dbo')

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_tables_sync(conn, schema)

    def fetch_columns_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable,
                               ordinal_position, column_default, column_comment)
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_columns_sync(conn, schema, table)

    def fetch_primary_keys_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves primarias.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ordinal_position)
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_primary_keys_sync(conn, schema, table)

    def fetch_foreign_keys_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves foráneas.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                               on_delete_action, on_update_action, ordinal_position)
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_foreign_keys_sync(conn, schema, table)

    def fetch_indexes_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene índices de una tabla.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, column_name, is_unique, ordinal_position, index_type)
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_indexes_sync(conn, schema, table)

    def fetch_routines_sync(self, schema: str | None = None) -> list[SqlServerRoutineDetail]:
        """Obtiene procedimientos y funciones.

        Args:
            schema: Nombre del schema (por defecto 'dbo')

        Returns:
            list[SqlServerRoutineDetail]: Detalles de routines
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_routines_sync(conn, schema)

    def fetch_routine_parameters_sync(self, object_id: int) -> list[SqlServerParameterDetail]:
        """Obtiene parámetros de un procedimiento/función.

        Args:
            object_id: ID del procedimiento/función en SQL Server

        Returns:
            list[SqlServerParameterDetail]: Detalles de parámetros
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_routine_parameters_sync(conn, object_id)
