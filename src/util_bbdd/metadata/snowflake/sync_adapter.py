"""Adaptador sync de orquestación Snowflake para SyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en Snowflake via snowflake-connector-python.

Snowflake es un cloud warehouse con características únicas:
- Esquema de 3 niveles: DATABASE.SCHEMA.TABLE
- Constraints: ADVISORY (no enforced)
- Índices: NO nativos (usar CLUSTERING KEY)
- Tipos: estándar SQL + tipos semi-estructurados (OBJECT, ARRAY, VARIANT)
"""

from __future__ import annotations

from typing import Any

from ._snowflake_models import SnowflakeRoutineDetail
from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import fetch_routine_parameters_sync, fetch_routines_sync
from .tables import fetch_columns_sync, fetch_tables_sync


class SnowflakeSyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección sync de Snowflake.

    Responsabilidades:
    - Extracción de metadatos: tablas, columnas, constraints,  índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple] (excepto routines).
    - Log de advertencias sobre naturaleza advisory de constraints.
    - Manejo de arquitectura 3-level: DATABASE.SCHEMA.TABLE

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def __init__(self, manager: Any) -> None:
        """Inicializa el adaptador con un manager.

        Args:
            manager: DbManagerProtocol (duck-typed) con atributos de conexión
        """
        self.manager = manager

    def fetch_databases_sync(self) -> list[tuple]:
        """Obtiene lista de bases de datos en Snowflake.

        Returns:
            list[tuple]: Filas (database_name,)
        """
        if not self.manager:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        # Snowflake typically uses current_database() context
        # Para introspección multi-base, necesitaríamos query adicional
        # Por ahora, retornar lista vacía (delegado al manager)
        return []

    def fetch_schemas_sync(self, database: str | None = None) -> list[tuple]:
        """Obtiene lista de schemas en Snowflake.

        Args:
            database: Nombre de la base de datos

        Returns:
            list[tuple]: Filas (schema_name,)
        """
        if not self.manager or not database:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        from .tables import fetch_schemas_sync as _fetch_schemas

        return _fetch_schemas(conn, database)

    def fetch_tables_sync(self, database: str | None = None, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en un schema Snowflake.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        if not self.manager or not database or not schema:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_tables_sync(conn, database, schema)

    def fetch_columns_sync(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Obtiene columnas de una tabla Snowflake.

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

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_columns_sync(conn, database, schema, table)

    def fetch_primary_keys_sync(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Obtiene claves primarias de una tabla Snowflake.

        IMPORTANTE: Snowflake PK son advisory (no enforced).

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema
            table: Nombre de la tabla

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ordinal_position)
        """
        if not self.manager or not database or not schema or not table:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_primary_keys_sync(conn, database, schema, table)

    def fetch_foreign_keys_sync(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Obtiene claves foráneas de una tabla Snowflake.

        IMPORTANTE: Snowflake FK son advisory (no enforced).

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

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_foreign_keys_sync(conn, database, schema, table)

    def fetch_indexes_sync(
        self, database: str | None = None, schema: str | None = None, table: str | None = None
    ) -> list[tuple]:
        """Obtiene índices de una tabla Snowflake.

        IMPORTANTE: Snowflake NO tiene índices nativos; retorna vacío.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema
            table: Nombre de la tabla

        Returns:
            list[tuple]: Lista vacía
        """
        if not self.manager or not database or not schema or not table:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_indexes_sync(conn, database, schema, table)

    def fetch_routines_sync(
        self, database: str | None = None, schema: str | None = None
    ) -> list[SnowflakeRoutineDetail]:
        """Obtiene rutinas (UDFs, procedures) de un schema Snowflake.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema

        Returns:
            list[SnowflakeRoutineDetail]: Detalles de rutinas
        """
        if not self.manager or not database or not schema:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_routines_sync(conn, database, schema)

    def fetch_routine_parameters_sync(
        self, database: str | None = None, schema: str | None = None, routine_name: str | None = None
    ) -> list[tuple]:
        """Obtiene parámetros de una rutina Snowflake.

        Args:
            database: Nombre de la base de datos
            schema: Nombre del schema
            routine_name: Nombre de la rutina

        Returns:
            list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
        """
        if not self.manager or not database or not schema or not routine_name:
            return []

        conn = self.manager.connection if hasattr(self.manager, "connection") else self.manager.db

        if not conn:
            return []

        return fetch_routine_parameters_sync(conn, database, schema, routine_name)
