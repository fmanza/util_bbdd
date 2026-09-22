"""Adaptador async de orquestacion MariaDB para AsyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en MariaDB/MySQL con soporte asíncrono.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ...results import Rows
from ._adapter_helpers import (
    build_columns_safe_sql,
    build_routine_ddl_from_detail,
    build_view_definition_sql,
    process_view_result,
    routine_entries_to_rows,
)
from ._manager_protocol import MariaDBAsyncManagerProtocol
from ._routine_models import MariaDBRoutineDetail, MariaDBRoutineParameterDetail
from .routines import (
    build_public_mariadb_routine_parameter_entry_rows,
    decode_mariadb_routine_detail_entries,
    decode_mariadb_routine_parameter_detail_entries,
    filter_mariadb_routine_parameter_entries,
)
from .tables import build_mariadb_table_ddl, decode_mariadb_safe_column_rows


class MariaDBAsyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección async de MariaDB.

    Responsabilidades:
    - Extracción asíncrona de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].
    """

    """Extrae la orquestacion MariaDB del manager async."""

    def __init__(self, manager: MariaDBAsyncManagerProtocol) -> None:
        self.manager = manager

    async def _get_cached_entries(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_entries: Callable[[], Awaitable[list[Any]]],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str,
    ) -> list[Any]:
        return list(
            await self.manager._get_cached_rows_async(
                cache_lookup=cache_lookup,
                cache_store=cache_store,
                fetch_rows=fetch_entries,
                cache_hit_message=cache_hit_message,
                success_message=success_message,
                fetch_debug_message=fetch_debug_message,
            )
        )

    async def get_routine_details(self, context_database: str) -> list[MariaDBRoutineDetail]:
        cache_key: str = self.manager._cache_context_key(context_database)
        context_label = self.manager._get_query_context_label()

        async def _fetch_rows() -> list[MariaDBRoutineDetail]:
            rows: Rows = await self.manager._execute_metadata_many(
                "rutinas_mariadb_detalle",
                params={"database": context_database},
                error_message="Error obteniendo metadata de rutinas MariaDB",
            )
            return decode_mariadb_routine_detail_entries(rows)

        rows = await self._get_cached_entries(
            cache_lookup=lambda: self.manager.db_cache._routine_metadata_context_cache.get(cache_key),
            cache_store=lambda items: self.manager.db_cache._routine_metadata_context_cache.__setitem__(
                cache_key, list(items)
            ),
            fetch_entries=_fetch_rows,
            cache_hit_message=f"♻️  Usando metadata detallada de rutinas MariaDB en caché para {context_database}",
            success_message=f"✅ {{count}} rutinas MariaDB detalladas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de rutinas MariaDB para {context_label}: {context_database}",
        )
        return [row for row in rows if isinstance(row, MariaDBRoutineDetail)]

    async def get_routine_parameters_details(self, context_database: str) -> list[MariaDBRoutineParameterDetail]:
        cache_key: str = self.manager._cache_context_key(context_database)
        context_label = self.manager._get_query_context_label()

        async def _fetch_rows() -> list[MariaDBRoutineParameterDetail]:
            rows: Rows = await self.manager._execute_metadata_many(
                "parametros_rutinas_mariadb_detalle",
                params={"database": context_database},
                error_message="Error obteniendo metadata de parámetros de rutinas MariaDB",
            )
            return decode_mariadb_routine_parameter_detail_entries(rows)

        rows = await self._get_cached_entries(
            cache_lookup=lambda: self.manager.db_cache._routine_parameters_context_cache.get(cache_key),
            cache_store=lambda items: self.manager.db_cache._routine_parameters_context_cache.__setitem__(
                cache_key, list(items)
            ),
            fetch_entries=_fetch_rows,
            cache_hit_message=f"♻️  Usando metadata detallada de parámetros MariaDB en caché para {context_database}",
            success_message=f"✅ {{count}} parámetros de rutinas MariaDB obtenidos para {context_label}: {context_database}",
            fetch_debug_message=(
                f"🔍 Obteniendo metadata detallada de parámetros de rutinas MariaDB para {context_label}: {context_database}"
            ),
        )
        return [row for row in rows if isinstance(row, MariaDBRoutineParameterDetail)]

    async def fetch_columns_safe(self, context_database: str, tabla: str) -> Rows:
        sql, params = build_columns_safe_sql(context_database, tabla)
        return decode_mariadb_safe_column_rows(await self.manager.execute_custom_many(sql, params))

    async def fetch_view_from_information_schema(self, database: str, view_name: str) -> str:
        sql, params = build_view_definition_sql(database, view_name)
        return process_view_result(await self.manager.execute_custom_one(sql, params), view_name)

    async def fetch_routine_from_information_schema(self, database: str, routine_name: str, routine_type: str) -> str:
        routine_rows = await self.get_routine_details(database)
        target_row = next(
            (row for row in routine_rows if row.matches(routine_name=routine_name, routine_type=routine_type)),
            None,
        )
        if target_row and target_row.routine_definition:
            parameters = await self.fetch_routine_parameters_detailed(
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

    async def fetch_routine_parameters_detailed(
        self, *, database: str, routine_name: str, routine_type: str
    ) -> list[MariaDBRoutineParameterDetail]:
        return filter_mariadb_routine_parameter_entries(
            await self.get_routine_parameters_details(database),
            routine_name=routine_name,
            routine_type=routine_type,
        )

    async def fetch_routine_parameters_public_rows(
        self, *, database: str, routine_name: str, routine_type: str
    ) -> Rows:
        return build_public_mariadb_routine_parameter_entry_rows(
            await self.fetch_routine_parameters_detailed(
                database=database,
                routine_name=routine_name,
                routine_type=routine_type,
            )
        )

    async def fetch_routines(self, context_database: str) -> Rows:
        return routine_entries_to_rows(await self.get_routine_details(context_database))

    async def build_table_ddl_from_metadata(self, tabla: str) -> str:
        rows: list[Any] = list(await self.manager.get_columns(tabla))
        pk_rows: list[Any] = list(await self.manager.get_primary_keys(tabla))
        return build_mariadb_table_ddl(tabla, rows, pk_rows)

    async def storage_inventory(self, context_database: str) -> dict[str, Any]:
        if not context_database:
            raise ValueError("Para MariaDB debe proporcionar 'database'")

        primary_rows: Rows = await self.manager.execute_query_many("ficheros_fisicos", database=context_database)
        temp_tablespaces_rows: Rows = await self.manager.execute_query_many("temp_tablespaces")

        return {
            "primary": primary_rows,
            "temp_tablespaces": temp_tablespaces_rows,
        }

    # ==================== SourceAdapter Protocol ====================
    # MEO-03 (AUDIT_CODE 2026-09-22): firma alineada con SourceAdapterAsync (los otros 8 motores
    # aceptan schema/table explícitos). El manager de MariaDB está ligado a una única database
    # por instancia (sin parámetro de schema en get_tables()/get_columns()/...), así que aquí
    # `schema` se acepta por conformidad de contrato pero se ignora: se usa siempre el contexto
    # ya vinculado al manager, igual que ya documentaban los métodos de RoutineAdapter de abajo.

    async def fetch_tables_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en modo asíncrono (SourceAdapter).

        Args:
            schema: Ignorado; MariaDB usa la database ya vinculada al manager.

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment, ...)
        """
        return list(await self.manager.get_tables())

    async def fetch_columns_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla en modo asíncrono (SourceAdapter).

        Args:
            schema: Ignorado; MariaDB usa la database ya vinculada al manager.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable, ...)
        """
        return list(await self.manager.get_columns(table))

    async def fetch_primary_keys_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves primarias en modo asíncrono (SourceAdapter).

        Args:
            schema: Ignorado; MariaDB usa la database ya vinculada al manager.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, ordinal_position, ...)
        """
        return list(await self.manager.get_primary_keys(table))

    async def fetch_foreign_keys_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves foráneas en modo asíncrono (SourceAdapter).

        Args:
            schema: Ignorado; MariaDB usa la database ya vinculada al manager.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ...)
        """
        return list(await self.manager.get_foreign_keys(table))

    async def fetch_indexes_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene índices de una tabla en modo asíncrono (SourceAdapter).

        Args:
            schema: Ignorado; MariaDB usa la database ya vinculada al manager.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, column_name, seq_in_index, ...)
        """
        return list(await self.manager.get_indices(table))

    # ==================== RoutineAdapter Protocol ====================

    async def fetch_routines_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de routines en modo asíncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema/database (ignorado para MariaDB).

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_comment, ...)
        """
        return list(await self.fetch_routines(schema or self.manager._get_query_context_database()))

    async def fetch_routine_parameters_async(self, schema: str, routine: str, routine_type: str) -> list[tuple]:
        """Obtiene parámetros de una routine en modo asíncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (ignorado).
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            list[tuple]: Filas (parameter_name, parameter_type, data_type, ...)
        """
        return list(
            await self.fetch_routine_parameters_public_rows(
                database=schema or self.manager._get_query_context_database(),
                routine_name=routine,
                routine_type=routine_type,
            )
        )

    async def fetch_routine_definition_async(self, schema: str, routine: str, routine_type: str) -> str:
        """Obtiene el DDL completo de una routine en modo asíncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (ignorado).
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            str: DDL de la routine (p.ej. 'CREATE PROCEDURE ...').
        """
        return await self.fetch_routine_from_information_schema(
            database=schema or self.manager._get_query_context_database(),
            routine_name=routine,
            routine_type=routine_type,
        )
