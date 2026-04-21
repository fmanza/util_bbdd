"""Adaptador sync de orquestacion MariaDB para SyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en MariaDB/MySQL.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...results import Rows
from ._adapter_helpers import (
    build_columns_safe_sql,
    build_routine_ddl_from_detail,
    build_view_definition_sql,
    process_view_result,
    routine_entries_to_rows,
)
from ._manager_protocol import MariaDBSyncManagerProtocol
from ._routine_models import MariaDBRoutineDetail, MariaDBRoutineParameterDetail
from .routines import (
    build_public_mariadb_routine_parameter_entry_rows,
    decode_mariadb_routine_detail_entries,
    decode_mariadb_routine_parameter_detail_entries,
    filter_mariadb_routine_parameter_entries,
)
from .tables import build_mariadb_table_ddl, decode_mariadb_safe_column_rows


class MariaDBSyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección sync de MariaDB.

    Responsabilidades:
    - Extracción de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].
    """

    """Extrae la orquestacion MariaDB del manager sync."""

    def __init__(self, manager: MariaDBSyncManagerProtocol) -> None:
        self.manager = manager

    def _get_cached_entries(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_entries: Callable[[], list[Any]],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str,
    ) -> list[Any]:
        return list(
            self.manager._get_cached_rows(
                cache_lookup=cache_lookup,
                cache_store=cache_store,
                fetch_rows=fetch_entries,
                cache_hit_message=cache_hit_message,
                success_message=success_message,
                fetch_debug_message=fetch_debug_message,
            )
        )

    def get_routine_details(self, context_database: str) -> list[MariaDBRoutineDetail]:
        cache_key: str = self.manager._cache_context_key(context_database)
        context_label: str = self.manager._get_query_context_label()
        entries = self._get_cached_entries(
            cache_lookup=lambda: self.manager.db_cache._routine_metadata_context_cache.get(cache_key),
            cache_store=lambda items: self.manager.db_cache._routine_metadata_context_cache.__setitem__(
                cache_key, list(items)
            ),
            fetch_entries=lambda: decode_mariadb_routine_detail_entries(
                self.manager._execute_metadata_many(
                    "rutinas_mariadb_detalle",
                    params={"database": context_database},
                    error_message="Error obteniendo metadata de rutinas MariaDB",
                )
            ),
            cache_hit_message=f"♻️  Usando metadata detallada de rutinas MariaDB en caché para {context_database}",
            success_message=f"✅ {{count}} rutinas MariaDB detalladas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=(
                f"🔍 Obteniendo metadata detallada de rutinas MariaDB para {context_label}: {context_database}"
            ),
        )
        return [entry for entry in entries if isinstance(entry, MariaDBRoutineDetail)]

    def get_routine_parameters_details(self, context_database: str) -> list[MariaDBRoutineParameterDetail]:
        cache_key: str = self.manager._cache_context_key(context_database)
        context_label: str = self.manager._get_query_context_label()
        entries = self._get_cached_entries(
            cache_lookup=lambda: self.manager.db_cache._routine_parameters_context_cache.get(cache_key),
            cache_store=lambda items: self.manager.db_cache._routine_parameters_context_cache.__setitem__(
                cache_key, list(items)
            ),
            fetch_entries=lambda: decode_mariadb_routine_parameter_detail_entries(
                self.manager._execute_metadata_many(
                    "parametros_rutinas_mariadb_detalle",
                    params={"database": context_database},
                    error_message="Error obteniendo metadata de parámetros de rutinas MariaDB",
                )
            ),
            cache_hit_message=f"♻️  Usando metadata detallada de parámetros MariaDB en caché para {context_database}",
            success_message=f"✅ {{count}} parámetros de rutinas MariaDB obtenidos para {context_label}: {context_database}",
            fetch_debug_message=(
                f"🔍 Obteniendo metadata detallada de parámetros de rutinas MariaDB para {context_label}: {context_database}"
            ),
        )
        return [entry for entry in entries if isinstance(entry, MariaDBRoutineParameterDetail)]

    def fetch_columns_safe(self, context_database: str, tabla: str) -> Rows:
        sql = build_columns_safe_sql(context_database, tabla)
        return decode_mariadb_safe_column_rows(self.manager.execute_custom_many(sql))

    def fetch_view_from_information_schema(self, database: str, view_name: str) -> str:
        sql = build_view_definition_sql(database, view_name)
        return process_view_result(self.manager.execute_custom_one(sql), view_name)

    def fetch_routine_from_information_schema(self, database: str, routine_name: str, routine_type: str) -> str:
        routine_rows = self.get_routine_details(database)
        target_row = next(
            (row for row in routine_rows if row.matches(routine_name=routine_name, routine_type=routine_type)),
            None,
        )
        if target_row and target_row.routine_definition:
            parameters = self.fetch_routine_parameters_detailed(
                database=database,
                routine_name=routine_name,
                routine_type=routine_type.upper(),
            )
            return build_routine_ddl_from_detail(
                database=database,
                routine_name=routine_name,
                routine_type=routine_type,
                target_row=target_row,
                parameters=parameters,
            )
        return f"-- {routine_type} {routine_name} definition unavailable\n"

    def fetch_routine_parameters_detailed(
        self, *, database: str, routine_name: str, routine_type: str
    ) -> list[MariaDBRoutineParameterDetail]:
        return filter_mariadb_routine_parameter_entries(
            self.get_routine_parameters_details(database),
            routine_name=routine_name,
            routine_type=routine_type,
        )

    def fetch_routine_parameters_public_rows(self, *, database: str, routine_name: str, routine_type: str) -> Rows:
        return build_public_mariadb_routine_parameter_entry_rows(
            self.fetch_routine_parameters_detailed(
                database=database,
                routine_name=routine_name,
                routine_type=routine_type,
            )
        )

    def fetch_routines(self, context_database: str) -> Rows:
        return routine_entries_to_rows(self.get_routine_details(context_database))

    def build_table_ddl_from_metadata(self, tabla: str) -> str:
        rows: list[Any] = list(self.manager.get_columns(tabla))
        pk_rows: list[Any] = list(self.manager.get_primary_keys(tabla))
        return build_mariadb_table_ddl(tabla, rows, pk_rows)

    def storage_inventory(self, context_database: str) -> dict[str, Any]:
        if not context_database:
            raise ValueError("Para MariaDB debe proporcionar 'database'")

        primary_rows: Rows = self.manager.execute_query_many("ficheros_fisicos", database=context_database)
        temp_tablespaces_rows: Rows = self.manager.execute_query_many("temp_tablespaces")

        return {
            "primary": primary_rows,
            "temp_tablespaces": temp_tablespaces_rows,
        }

    # ==================== SourceAdapter Protocol ====================

    def fetch_tables_sync(self) -> list[tuple]:
        """Obtiene lista de tablas en modo síncrono (SourceAdapter).

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment, ...)
        """
        return list(self.manager.get_tables())

    def fetch_columns_sync(self, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla en modo síncrono (SourceAdapter).

        Args:
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable, ...)
        """
        return list(self.manager.get_columns(table))

    def fetch_primary_keys_sync(self, table: str) -> list[tuple]:
        """Obtiene claves primarias en modo síncrono (SourceAdapter).

        Args:
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, ordinal_position, ...)
        """
        return list(self.manager.get_primary_keys(table))

    def fetch_foreign_keys_sync(self, table: str) -> list[tuple]:
        """Obtiene claves foráneas en modo síncrono (SourceAdapter).

        Args:
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ...)
        """
        return list(self.manager.get_foreign_keys(table))

    def fetch_indexes_sync(self, table: str) -> list[tuple]:
        """Obtiene índices de una tabla en modo síncrono (SourceAdapter).

        Args:
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, column_name, seq_in_index, ...)
        """
        return list(self.manager.get_indices(table))

    # ==================== RoutineAdapter Protocol ====================

    def fetch_routines_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de routines en modo síncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema/database (ignorado para MariaDB).

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_comment, ...)
        """
        return list(self.fetch_routines(schema or self.manager._get_query_context_database()))

    def fetch_routine_parameters_sync(self, schema: str, routine: str, routine_type: str) -> list[tuple]:
        """Obtiene parámetros de una routine en modo síncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (ignorado).
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            list[tuple]: Filas (parameter_name, parameter_type, data_type, ...)
        """
        return list(
            self.fetch_routine_parameters_public_rows(
                database=schema or self.manager._get_query_context_database(),
                routine_name=routine,
                routine_type=routine_type,
            )
        )

    def fetch_routine_definition_sync(self, schema: str, routine: str, routine_type: str) -> str:
        """Obtiene el DDL completo de una routine en modo síncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (ignorado).
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            str: DDL de la routine (p.ej. 'CREATE PROCEDURE ...').
        """
        return self.fetch_routine_from_information_schema(
            database=schema or self.manager._get_query_context_database(),
            routine_name=routine,
            routine_type=routine_type,
        )
