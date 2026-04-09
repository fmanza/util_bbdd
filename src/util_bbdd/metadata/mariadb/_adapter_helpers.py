"""Helpers puros compartidos por los adaptadores sync y async de MariaDB.

Responsabilidad: encapsular construcción de SQL y procesamiento de resultados
que son idénticos entre MariaDBSyncAdapter y MariaDBAsyncAdapter. Los adaptadores
solo coordinan la parte sync/async (await vs directa).
"""

from __future__ import annotations

from ...results import RowOrNone, Rows
from ._routine_models import MariaDBRoutineDetail, MariaDBRoutineParameterDetail
from .common import escape_mariadb_sql_literal
from .routines import build_mariadb_routine_ddl


def build_columns_safe_sql(context_database: str, tabla: str) -> str:
    """Construye la consulta HEX-safe para columnas de una tabla MariaDB.

    Usa HEX(...) para evitar corrupción de charset en information_schema.
    """
    escaped_database: str = escape_mariadb_sql_literal(context_database)
    escaped_table: str = escape_mariadb_sql_literal(tabla)
    return (
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


def build_view_definition_sql(database: str, view_name: str) -> str:
    """Construye la consulta para obtener VIEW_DEFINITION desde information_schema."""
    escaped_view: str = escape_mariadb_sql_literal(view_name)
    schema_condition: str = f"'{escape_mariadb_sql_literal(database)}'" if database else "DATABASE()"
    return (
        "SELECT VIEW_DEFINITION "
        "FROM information_schema.views "
        f"WHERE TABLE_SCHEMA = {schema_condition} "
        f"AND TABLE_NAME = '{escaped_view}' "
        "LIMIT 1"
    )


def process_view_result(result: RowOrNone, view_name: str) -> str:
    """Convierte la fila de VIEW_DEFINITION al DDL completo o un comentario de fallback."""
    if result and len(result) > 0 and result[0]:
        view_def: str = str(result[0]).strip()
        if view_def:
            return f"CREATE OR REPLACE VIEW `{view_name}` AS\n{view_def}"
    return f"-- View {view_name} definition unavailable\n"


def build_routine_ddl_from_detail(
    *,
    database: str,
    routine_name: str,
    routine_type: str,
    target_row: MariaDBRoutineDetail,
    parameters: list[MariaDBRoutineParameterDetail],
) -> str:
    """Ensambla el DDL completo de una rutina MariaDB a partir del modelo IR."""
    return build_mariadb_routine_ddl(
        database=database,
        routine_name=routine_name,
        routine_type=routine_type.upper(),
        routine_definition=target_row.routine_definition,
        definer=target_row.definer,
        security_type=target_row.security_type,
        sql_data_access=target_row.sql_data_access,
        is_deterministic=target_row.is_deterministic,
        return_type=target_row.return_type,
        routine_comment=target_row.routine_comment,
        parameters=[entry.to_dict() for entry in parameters],
    )


def routine_entries_to_rows(routine_rows: list[MariaDBRoutineDetail]) -> Rows:
    """Convierte entradas de rutinas MariaDB al formato de fila pública (nombre, tipo, comentario)."""
    return sorted(
        [
            (entry.routine_name, entry.routine_type, entry.routine_comment)
            for entry in routine_rows
            if entry.routine_name.strip()
        ],
        key=lambda row: (str(row[1]), str(row[0])),
    )


__all__: list[str] = [
    "build_columns_safe_sql",
    "build_routine_ddl_from_detail",
    "build_view_definition_sql",
    "process_view_result",
    "routine_entries_to_rows",
]
