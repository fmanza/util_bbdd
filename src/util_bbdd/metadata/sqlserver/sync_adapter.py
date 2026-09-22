"""Adaptador sync de orquestación SQL Server para SyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en SQL Server.
"""

from __future__ import annotations

from .._base_adapter import BaseConnectionAdapter
from ._sqlserver_models import SqlServerParameterDetail, SqlServerRoutineDetail
from .constraints import fetch_foreign_keys_sync, fetch_primary_keys_sync
from .indexes import fetch_indexes_sync
from .routines import fetch_routine_body_sync, fetch_routine_parameters_sync, fetch_routines_sync
from .tables import fetch_columns_sync, fetch_schemas_sync, fetch_tables_sync


class SqlServerSyncAdapter(BaseConnectionAdapter):
    """Implementa SourceAdapter y RoutineAdapter para introspección sync de SQL Server.

    Responsabilidades:
    - Extracción de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def fetch_schemas_sync(self) -> list[tuple]:
        """Obtiene lista de schemas en SQL Server.

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
            schema: Nombre del schema (por defecto 'dbo')

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        conn = self._get_conn()
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
        conn = self._get_conn()
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
        conn = self._get_conn()
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
        conn = self._get_conn()
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
        conn = self._get_conn()
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
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_routines_sync(conn, schema)

    def fetch_routine_parameters_sync(
        self,
        schema: str | None = None,
        routine: str | None = None,
        routine_type: str | None = None,
    ) -> list[tuple]:
        """Obtiene parámetros de un procedimiento/función.

        Implementa RoutineAdapterSync. Resuelve el object_id de SQL Server a partir del nombre
        de la rutina antes de delegar a ``fetch_routine_parameters_by_id_sync`` — MSS-01
        (AUDIT_CODE 2026-09-22): antes tenía la firma ``(object_id: int)``, que no cumplía el
        Protocol (``schema, routine, routine_type``) ni coincidía con la contraparte async.

        Args:
            schema: Nombre del schema (por defecto 'dbo').
            routine: Nombre del procedimiento/función.
            routine_type: Tipo de rutina ('PROCEDURE' o 'FUNCTION', opcional).

        Returns:
            list[tuple]: Filas (param_name, object_id, parameter_id, data_type, is_output,
                               precision, scale)
        """
        conn = self._get_conn()
        if not conn or not routine:
            return []

        all_routines: list[SqlServerRoutineDetail] = fetch_routines_sync(conn, schema)

        routine_upper = routine.strip().upper()
        type_upper = routine_type.strip().upper() if routine_type else None

        matched = next(
            (
                r
                for r in all_routines
                if r.routine_name.upper() == routine_upper
                and (type_upper is None or r.routine_type.upper() == type_upper)
            ),
            None,
        )

        if matched is None:
            return []

        params = self.fetch_routine_parameters_by_id_sync(matched.object_id)

        return [
            (p.param_name, p.object_id, p.parameter_id, p.data_type, p.is_output, p.precision, p.scale) for p in params
        ]

    def fetch_routine_parameters_by_id_sync(self, object_id: int) -> list[SqlServerParameterDetail]:
        """Obtiene parámetros directamente por object_id (API interna SQL Server).

        Útil cuando ya se dispone del object_id (p.ej. desde fetch_routines_sync).

        Args:
            object_id: ID del procedimiento/función en sys.objects.

        Returns:
            list[SqlServerParameterDetail]: Detalles de parámetros
        """
        conn = self._get_conn()
        if not conn:
            return []
        return fetch_routine_parameters_sync(conn, object_id)

    def fetch_routine_definition_sync(self, schema: str, routine: str, routine_type: str) -> str:
        """Obtiene el DDL completo de una rutina (RoutineAdapter).

        Args:
            schema: Nombre del schema (por defecto 'dbo').
            routine: Nombre del procedimiento/función.
            routine_type: Tipo de rutina ('PROCEDURE' o 'FUNCTION', ignorado: la búsqueda de
                sys.sql_modules es por nombre, no distingue tipo).

        Returns:
            str: Definición completa (CREATE PROCEDURE/FUNCTION ...) o ``""`` si no disponible.
        """
        conn = self._get_conn()
        if not conn or not routine:
            return ""
        return fetch_routine_body_sync(conn, schema or "dbo", routine)
