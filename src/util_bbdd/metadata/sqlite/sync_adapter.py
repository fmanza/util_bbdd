"""Adaptador sync de orquestación SQLite para SyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en SQLite.
"""

from __future__ import annotations

from typing import Any

from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import fetch_procedures_sync, fetch_triggers_sync
from .tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class SqliteSyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección sync de SQLite.

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
        """Obtiene lista de schemas (pseudo-schemas) en SQLite.

        Returns:
            list[tuple]: Filas (schema_name,) - típicamente [("main",), ("temp",)]
        """
        return fetch_schemas_sync()

    def fetch_tables_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en un schema.

        Args:
            schema: Nombre del schema (mapeado a database en SQLite)

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        # Obtener conexión desde manager
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        # Falback si no encontramos conexión
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
            list[tuple]: Filas (index_name, column_name, is_unique, ordinal_position)
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_indexes_sync(conn, schema, table)

    def fetch_triggers_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene triggers.

        Args:
            schema: Nombre del schema (opcional)
            table: Nombre de la tabla (opcional)

        Returns:
            list[tuple]: Filas (trigger_name, table_name, trigger_event, trigger_action)
        """
        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_triggers_sync(conn, schema, table)

    def fetch_procedures_sync(self, schema: str | None = None) -> list[tuple]:
        """Retorna lista vacía (SQLite no tiene procedimientos).

        Args:
            schema: Nombre del schema (no usado)

        Returns:
            list[tuple]: Lista vacía
        """
        return fetch_procedures_sync(self.manager.connection, schema)

    def fetch_functions_sync(self, schema: str | None = None) -> list[tuple]:
        """Retorna lista vacía (SQLite no tiene funciones definidas por usuario).

        Args:
            schema: Nombre del schema (no usado)

        Returns:
            list[tuple]: Lista vacía
        """
        return fetch_functions_sync(self.manager.connection, schema)


# Importar aquí para evitar circular imports
from .routines import fetch_functions_sync  # noqa: E402, F401
