"""Adaptador async de orquestación Redshift para AsyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
asíncrona de metadatos en Redshift.

Redshift soporta dos drivers async:
- asyncpg (recomendado, con tipo genérico asyncpg.Connection)
- asyncio + psycopg para cambios incrementales
"""

from __future__ import annotations

from typing import Any

from ._redshift_models import RedshiftRoutineDetail
from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import fetch_routine_parameters_sync, fetch_routines_sync
from .tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class RedshiftAsyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección async de Redshift.

    NOTA: Actualmente usa métodos sync a través del manager (como PostgreSQL).
    En futuro, si se requiere I/O verdaderamente asíncrono, migrar a asyncpg.

    Responsabilidades:
    - Extracción de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple] (excepto routines).

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def __init__(self, manager: Any) -> None:
        """Inicializa el adaptador con un manager.

        Args:
            manager: AsyncDbManagerProtocol (duck-typed) con atributos de conexión
        """
        self.manager = manager

    def fetch_schemas_sync(self) -> list[tuple]:
        """Obtiene lista de schemas en Redshift (sync wrapper).

        Returns:
            list[tuple]: Filas (schema_name,)
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_schemas_sync(conn)

    def fetch_tables_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en un schema (sync wrapper).

        Args:
            schema: Nombre del schema

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_tables_sync(conn, schema)

    def fetch_columns_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene columnas de una tabla (sync wrapper).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable,
                               ordinal_position, column_default, column_comment)
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_columns_sync(conn, schema, table)

    def fetch_primary_keys_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene claves primarias de una tabla (sync wrapper).

        IMPORTANTE: Redshift PK son advisory (no enforced).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ordinal_position)
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_primary_keys_sync(conn, schema, table)

    def fetch_foreign_keys_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene claves foráneas de una tabla (sync wrapper).

        IMPORTANTE: Redshift FK son advisory (no enforced).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ref_table, ref_column,
                               on_delete_action, on_update_action, ordinal_position)
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_foreign_keys_sync(conn, schema, table)

    def fetch_indexes_sync(self, schema: str | None = None, table: str | None = None) -> list[tuple]:
        """Obtiene índices de una tabla (sync wrapper).

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, column_name, seq_in_index, is_unique)
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_indexes_sync(conn, schema, table)

    def fetch_routines_sync(self, schema: str | None = None) -> list[RedshiftRoutineDetail]:
        """Obtiene rutinas (UDFs) del schema (sync wrapper).

        Returns:
            list[RedshiftRoutineDetail]: Detalles de rutinas
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_routines_sync(conn, schema)

    def fetch_routine_parameters_sync(self, schema: str | None = None, routine_name: str | None = None) -> list[tuple]:
        """Obtiene parámetros de una rutina (sync wrapper).

        Redshift tiene soporte limitado para introspección de parámetros.

        Args:
            schema: Nombre del schema.
            routine_name: Nombre de la rutina.

        Returns:
            list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_routine_parameters_sync(conn, schema, routine_name)
