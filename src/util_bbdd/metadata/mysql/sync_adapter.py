"""Adaptador sync de orquestación MySQL para SyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en MySQL.
"""

from __future__ import annotations

from typing import Any

from ...results import Rows
from .._base_adapter import BaseConnectionAdapter
from ..mariadb.sync_adapter import MariaDBSyncAdapter
from ._mysql_models import MysqlRoutineDetail
from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import (
    fetch_routine_definition_sync,
    fetch_routine_parameters_sync,
    fetch_routines_sync,
)
from .tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class MysqlSyncAdapter(BaseConnectionAdapter):
    """Implementa SourceAdapter y RoutineAdapter para introspección sync de MySQL.

    Responsabilidades:
    - Extracción de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def fetch_schemas_sync(self) -> list[tuple]:
        """Obtiene lista de schemas en MySQL.

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
        """Obtiene claves primarias de una tabla.

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
        """Obtiene claves foráneas de una tabla.

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

    def fetch_routines_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene rutinas (PROCEDURE, FUNCTION) de un schema (RoutineAdapter).

        Convierte ``MysqlRoutineDetail`` (dataclass interno, no cabe en tuple plana —
        ver ``_mysql_models.py``) a tupla en el límite público del adapter, para
        cumplir el Protocol ``RoutineAdapterSync`` (MDC-03, AUDIT_CODE 2026-09-22:
        antes devolvía la dataclass directamente, incompatible con
        ``list[tuple[Any, ...]]`` — invariancia de ``list`` en mypy).

        Args:
            schema: Nombre del schema.

        Returns:
            list[tuple]: Filas (routine_name, routine_type, created_datetime)
        """
        conn = self._get_conn()
        if not conn:
            return []
        details: list[MysqlRoutineDetail] = fetch_routines_sync(conn, schema)
        return [(d.routine_name, d.routine_type, d.created_datetime) for d in details]

    def fetch_routine_parameters_sync(
        self,
        schema: str | None = None,
        routine_name: str | None = None,
        routine_type: str | None = None,
    ) -> list[tuple]:
        """Obtiene parámetros de una rutina (RoutineAdapter).

        Args:
            schema: Nombre del schema.
            routine_name: Nombre de la rutina.
            routine_type: Tipo de rutina (ignorado: information_schema.PARAMETERS
                no filtra por tipo). Aceptado para cumplir el Protocol RoutineAdapterSync
                (MDC-03, AUDIT_CODE 2026-09-22).

        Returns:
            list[tuple]: Filas (parameter_name, parameter_mode, data_type, ordinal_position)
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_routine_parameters_sync(conn, schema, routine_name)

    def fetch_routine_definition_sync(self, schema: str, routine: str, routine_type: str) -> str:
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
        return fetch_routine_definition_sync(conn, schema, routine, routine_type)

    # ==================== Lecturas especializadas (EngineMetadataAdapterSync) ====================
    # MySQL 8 comparte con MariaDB el information_schema que usan estas lecturas (validado contra MySQL 8.4): se
    # delegan en MariaDBSyncAdapter sobre el mismo manager, que las resuelve con el catálogo de queries de "mysql".

    def _engine_metadata(self) -> MariaDBSyncAdapter:
        reader: MariaDBSyncAdapter | None = getattr(self, "_engine_metadata_reader", None)
        if reader is None:
            reader = MariaDBSyncAdapter(self.manager)
            self._engine_metadata_reader = reader
        return reader

    def fetch_routines(self, context_database: str) -> Rows:
        """Rutinas del contexto (nombre, tipo, comentario)."""
        return self._engine_metadata().fetch_routines(context_database)

    def build_table_ddl_from_metadata(self, tabla: str) -> str:
        """DDL de una tabla reconstruido desde columnas y PK."""
        return self._engine_metadata().build_table_ddl_from_metadata(tabla)

    def fetch_view_from_information_schema(self, database: str, view_name: str) -> str:
        """DDL de una vista desde information_schema.views."""
        return self._engine_metadata().fetch_view_from_information_schema(database, view_name)

    def fetch_columns_safe(self, context_database: str, tabla: str) -> Rows:
        """Columnas de una tabla leídas en HEX (seguras frente a problemas de charset)."""
        return self._engine_metadata().fetch_columns_safe(context_database, tabla)

    def fetch_routine_parameters_public_rows(self, *, database: str, routine_name: str, routine_type: str) -> Rows:
        """Parámetros públicos de una rutina."""
        return self._engine_metadata().fetch_routine_parameters_public_rows(
            database=database, routine_name=routine_name, routine_type=routine_type
        )

    def fetch_routine_from_information_schema(self, database: str, routine_name: str, routine_type: str) -> str:
        """DDL de una rutina."""
        return self._engine_metadata().fetch_routine_from_information_schema(database, routine_name, routine_type)

    def storage_inventory(self, context_database: str) -> dict[str, Any]:
        """Inventario de almacenamiento (ficheros por tabla y tablespaces temporales)."""
        return self._engine_metadata().storage_inventory(context_database)
