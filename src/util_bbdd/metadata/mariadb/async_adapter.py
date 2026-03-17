"""Adaptador async de orquestacion MariaDB para AsyncDatabaseManager."""

from __future__ import annotations

from typing import Any

from ...database_exceptions import DatabaseOperationError, QueryError
from ...results import Rows
from .common import escape_mariadb_sql_literal, normalize_mariadb_routine_status_rows
from .routines import (
    build_mariadb_routine_ddl,
    decode_mariadb_routine_detail_rows,
    decode_mariadb_routine_parameter_detail_rows,
    filter_mariadb_routine_parameter_rows,
)
from .tables import build_mariadb_table_ddl, decode_mariadb_safe_column_rows


class MariaDBAsyncAdapter:
    """Extrae la orquestacion MariaDB del manager async."""

    def __init__(self, manager: Any) -> None:
        self.manager = manager

    async def fetch_routines_from_show_status(self, database: str) -> Rows:
        escaped_database: str = escape_mariadb_sql_literal(database)
        procedures_sql: str = f"SHOW PROCEDURE STATUS WHERE Db = '{escaped_database}'"
        functions_sql: str = f"SHOW FUNCTION STATUS WHERE Db = '{escaped_database}'"
        procedures_rows: Rows = await self.manager.execute_custom_many(procedures_sql)
        functions_rows: Rows = await self.manager.execute_custom_many(functions_sql)
        combined_rows: Rows = normalize_mariadb_routine_status_rows(
            procedures_rows, "PROCEDURE"
        ) + normalize_mariadb_routine_status_rows(functions_rows, "FUNCTION")
        return sorted(combined_rows, key=lambda row: (str(row[1]), str(row[0])))

    async def get_routines_detail_rows(self, context_database: str) -> list[dict[str, Any]]:
        cache_key: str = self.manager._cache_context_key(context_database)
        context_label = self.manager._get_query_context_label()

        async def _fetch_rows() -> list[dict[str, Any]]:
            rows: Rows = await self.manager._execute_metadata_many(
                "rutinas_mariadb_detalle",
                params={"database": context_database},
                error_message="Error obteniendo metadata de rutinas MariaDB",
            )
            return decode_mariadb_routine_detail_rows(rows)

        rows = await self.manager._get_cached_rows_async(
            cache_lookup=lambda: self.manager.db_cache._routine_metadata_context_cache.get(cache_key),
            cache_store=lambda items: self.manager.db_cache._routine_metadata_context_cache.__setitem__(
                cache_key, list(items)
            ),
            fetch_rows=_fetch_rows,
            cache_hit_message=f"♻️  Usando metadata detallada de rutinas MariaDB en caché para {context_database}",
            success_message=f"✅ {{count}} rutinas MariaDB detalladas obtenidas para {context_label}: {context_database}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de rutinas MariaDB para {context_label}: {context_database}",
        )
        return [row for row in rows if isinstance(row, dict)]

    async def get_routine_parameters_detail_rows(self, context_database: str) -> list[dict[str, Any]]:
        cache_key: str = self.manager._cache_context_key(context_database)
        context_label = self.manager._get_query_context_label()

        async def _fetch_rows() -> list[dict[str, Any]]:
            rows: Rows = await self.manager._execute_metadata_many(
                "parametros_rutinas_mariadb_detalle",
                params={"database": context_database},
                error_message="Error obteniendo metadata de parámetros de rutinas MariaDB",
            )
            return decode_mariadb_routine_parameter_detail_rows(rows)

        rows = await self.manager._get_cached_rows_async(
            cache_lookup=lambda: self.manager.db_cache._routine_parameters_context_cache.get(cache_key),
            cache_store=lambda items: self.manager.db_cache._routine_parameters_context_cache.__setitem__(
                cache_key, list(items)
            ),
            fetch_rows=_fetch_rows,
            cache_hit_message=f"♻️  Usando metadata detallada de parámetros MariaDB en caché para {context_database}",
            success_message=f"✅ {{count}} parámetros de rutinas MariaDB obtenidos para {context_label}: {context_database}",
            fetch_debug_message=(
                f"🔍 Obteniendo metadata detallada de parámetros de rutinas MariaDB para {context_label}: {context_database}"
            ),
        )
        return [row for row in rows if isinstance(row, dict)]

    async def fetch_columns_safe(self, context_database: str, tabla: str) -> Rows:
        escaped_database: str = escape_mariadb_sql_literal(context_database)
        escaped_table: str = escape_mariadb_sql_literal(tabla)
        sql = (
            "SELECT HEX(COLUMN_NAME) AS column_name_hex, "
            "HEX(COLUMN_TYPE) AS column_type_hex, "
            "IS_NULLABLE, "
            "COLUMN_KEY, "
            "CASE WHEN COLUMN_DEFAULT IS NULL THEN 1 ELSE 0 END AS default_is_null, "
            "HEX(CAST(COLUMN_DEFAULT AS BINARY)) AS column_default_hex, "
            "HEX(COALESCE(EXTRA, '')) AS extra_hex, "
            "HEX(COALESCE(COLUMN_COMMENT, '')) AS column_comment_hex "
            "FROM information_schema.columns "
            f"WHERE table_schema = '{escaped_database}' AND table_name = '{escaped_table}' "
            "ORDER BY ordinal_position"
        )
        safe_rows: Rows = await self.manager.execute_custom_many(sql)
        return decode_mariadb_safe_column_rows(safe_rows)

    async def fetch_view_from_information_schema(self, database: str, view_name: str) -> str:
        escaped_view: str = escape_mariadb_sql_literal(view_name)
        schema_condition: str = f"'{escape_mariadb_sql_literal(database)}'" if database else "DATABASE()"
        sql: str = f"""
            SELECT VIEW_DEFINITION
            FROM information_schema.views
            WHERE TABLE_SCHEMA = {schema_condition}
            AND TABLE_NAME = '{escaped_view}'
            LIMIT 1
        """
        result = await self.manager.execute_custom_one(sql)
        if result and len(result) > 0 and result[0]:
            view_def: str = str(result[0]).strip()
            if view_def:
                return f"CREATE OR REPLACE VIEW `{view_name}` AS\n{view_def}"
        return f"-- View {view_name} definition unavailable\n"

    async def fetch_routine_from_information_schema(self, database: str, routine_name: str, routine_type: str) -> str:
        routine_rows = await self.get_routines_detail_rows(database)
        target_row = next(
            (
                row
                for row in routine_rows
                if str(row.get("routine_type") or "").upper() == routine_type.upper()
                and str(row.get("routine_name") or "").upper() == routine_name.upper()
            ),
            None,
        )
        if target_row and str(target_row.get("routine_definition") or "").strip():
            parameters = await self.fetch_routine_parameters_detailed(
                database=database,
                routine_name=routine_name,
                routine_type=routine_type.upper(),
            )
            return build_mariadb_routine_ddl(
                database=database,
                routine_name=routine_name,
                routine_type=routine_type.upper(),
                routine_definition=str(target_row.get("routine_definition") or "").strip(),
                definer=str(target_row.get("definer") or "").strip(),
                security_type=str(target_row.get("security_type") or "").strip().upper(),
                sql_data_access=str(target_row.get("sql_data_access") or "").strip().upper(),
                is_deterministic=str(target_row.get("is_deterministic") or "").strip().upper(),
                return_type=str(target_row.get("return_type") or "").strip(),
                routine_comment=str(target_row.get("routine_comment") or "").strip(),
                parameters=parameters,
            )
        return f"-- {routine_type} {routine_name} definition unavailable\n"

    async def fetch_routine_parameters_detailed(
        self, *, database: str, routine_name: str, routine_type: str
    ) -> list[dict[str, Any]]:
        detailed_rows = filter_mariadb_routine_parameter_rows(
            await self.get_routine_parameters_detail_rows(database),
            routine_name=routine_name,
            routine_type=routine_type,
        )
        if detailed_rows:
            return detailed_rows

        fallback_rows: list[Any] = list(
            await self.manager._execute_metadata_many(
                "parametros_rutina",
                params={"database": database, "rutina": routine_name, "tipo_rutina": routine_type.upper()},
                error_message="Error obteniendo parámetros de rutina",
                table_name=routine_name,
            )
        )
        return [
            {
                "mode": str(row[0] or "").strip().upper() if len(row) > 0 else "",
                "name": str(row[1] or "").strip() if len(row) > 1 else "",
                "data_type": str(row[2] or "").strip() if len(row) > 2 else "",
                "default_value": str(row[3] or "").strip() if len(row) > 3 and row[3] is not None else "",
                "charset": "",
                "collation": "",
                "ordinal_position": row[4] if len(row) > 4 else 0,
            }
            for row in fallback_rows
            if isinstance(row, (tuple, list))
        ]

    async def build_table_ddl_from_metadata(self, tabla: str) -> str:
        rows: list[Any] = list(await self.manager.get_columns(tabla))
        pk_rows: list[Any] = list(await self.manager.get_primary_keys(tabla))
        return build_mariadb_table_ddl(tabla, rows, pk_rows)

    async def storage_inventory(self, context_database: str) -> dict[str, Any]:
        if not context_database:
            raise ValueError("Para MariaDB debe proporcionar 'database'")

        primary_rows: Rows = await self.manager.execute_query_many("ficheros_fisicos", database=context_database)
        temp_tablespaces_rows: Rows = []

        try:
            temp_tablespaces_rows = await self.manager.execute_query_many("temp_tablespaces")
        except (DatabaseOperationError, QueryError) as error:
            self.manager.logger.warning(
                "Temp tablespaces MariaDB no disponibles para %s. Se devuelve lista vacía. Error: %s",
                context_database,
                error,
            )

        return {
            "primary": primary_rows,
            "temp_tablespaces": temp_tablespaces_rows,
        }
