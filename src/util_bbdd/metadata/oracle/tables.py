"""Helpers puros para metadata y DDL de tablas Oracle."""

from __future__ import annotations

from typing import Any

from ...results import Rows


def fetch_schemas_sql() -> str:
    """SQL query parametrizada para obtener esquemas (owners) Oracle.

    Excluye schemas del sistema automáticamente en la query.

    Returns:
        str: SQL query para obtener DISTINCT OWNER de all_tables
    """
    return (
        "SELECT DISTINCT owner "
        "FROM all_tables "
        "WHERE owner NOT IN ('SYS', 'SYSTEM', 'XDB', 'MDSYS', 'ORDDATA', "
        "'SI_INFORMTN_SCHEMA', 'CTXSYS', 'TXNSYS', 'WMSYS', 'OLAPSYS', "
        "'OWBSYS', 'FLOWS_FILES') "
        "AND owner NOT LIKE 'APEX\\_%%' ESCAPE '\\' "
        "AND owner NOT LIKE 'WM%%' "
        "ORDER BY owner"
    )


def fetch_tables_sql() -> str:
    """SQL query parametrizada para obtener tablas de un schema Oracle.

    Parametrizado con :owner para el propietario.

    Returns:
        str: SQL query para table_name, table_type, table_comment
    """
    return (
        "SELECT "
        "t.table_name, "
        "t.table_type, "
        "COALESCE(c.comments, '') AS table_comment "
        "FROM all_tables t "
        "LEFT JOIN all_tab_comments c "
        "  ON c.owner = t.owner "
        "  AND c.table_name = t.table_name "
        "WHERE t.owner = :owner "
        "ORDER BY t.table_name"
    )


def fetch_columns_sql() -> str:
    """SQL query parametrizada para obtener columnas de una tabla Oracle.

    Parametrizado con :owner y :table_name.
    Excluye ROWID pseudo-columnas y detecta LONG.

    Returns:
        str: SQL query para columnas con tipos, nullable, defaults, etc.
    """
    return (
        "SELECT "
        "c.column_name, "
        "c.data_type, "
        "CASE WHEN c.nullable = 'Y' THEN 'YES' ELSE 'NO' END AS is_nullable, "
        "c.column_id AS ordinal_position, "
        "COALESCE(c.data_default, '') AS column_default, "
        "c.data_length, "
        "c.data_precision, "
        "c.data_scale, "
        "COALESCE(d.comments, '') AS column_comment "
        "FROM all_tab_columns c "
        "LEFT JOIN all_col_comments d "
        "  ON d.owner = c.owner "
        "  AND d.table_name = c.table_name "
        "  AND d.column_name = c.column_name "
        "WHERE c.owner = :owner "
        "  AND c.table_name = :table_name "
        "  AND c.column_name != 'ROWID' "
        "ORDER BY c.column_id"
    )


def _normalize_oracle_column_row(row: Any) -> tuple[str, str, str, int, Any, str] | None:
    """Normaliza una fila individual de columna Oracle.

    Excluye LONG/LONG RAW (detecta y filtra). Convierte tipos según Oracle semantics.

    Args:
        row: Tupla/lista de datos de columna (9+ elementos)

    Returns:
        Tupla normalizada (column_name, column_type, is_nullable, ordinal_position,
        column_default, column_comment) o None si es inválida o LONG/LONG RAW
    """
    if not isinstance(row, (tuple, list)) or len(row) < 9:
        return None

    # Detectar LONG/LONG RAW y skipear
    data_type = str(row[1]).upper() if row[1] else "VARCHAR2"
    if data_type in ("LONG", "LONG RAW"):
        return None

    return (
        str(row[0]) if row[0] else "",  # column_name
        str(row[1]) if row[1] else "VARCHAR2",  # data_type
        str(row[2]) if row[2] else "YES",  # is_nullable
        int(row[3]) if row[3] is not None else 0,  # ordinal_position
        str(row[4]).strip() if row[4] else None,  # column_default (puede ser None)
        str(row[8]) if row[8] else "",  # column_comment
    )


def decode_oracle_column_rows(safe_rows: Rows) -> Rows:
    """Decodifica y normaliza filas de columnas Oracle.

    Args:
        safe_rows: Filas del query fetch_columns_sql

    Returns:
        Rows normalizadas con estructura (column_name, column_type, is_nullable,
                                          ordinal_position, column_default, column_comment)
    """
    return [normalized for row in safe_rows if (normalized := _normalize_oracle_column_row(row)) is not None]


def fetch_pk_constraint_sql() -> str:
    """SQL query parametrizada para obtener claves primarias Oracle.

    Parametrizado con :owner y :table_name.

    Returns:
        str: SQL query para constraint_name, column_name, ordinal_position
    """
    return (
        "SELECT "
        "cc.constraint_name, "
        "cc.column_name, "
        "cc.position AS ordinal_position "
        "FROM all_constraints con "
        "JOIN all_cons_columns cc "
        "  ON con.constraint_name = cc.constraint_name "
        "  AND con.owner = cc.owner "
        "WHERE con.owner = :owner "
        "  AND con.table_name = :table_name "
        "  AND con.constraint_type = 'P' "
        "ORDER BY con.constraint_name, cc.position"
    )


def fetch_fk_constraint_sql() -> str:
    """SQL query parametrizada para obtener claves foráneas Oracle.

    Parametrizado con :owner y :table_name.
    Decodifica acciones ON DELETE desde DELETE_RULE.

    Returns:
        str: SQL query para (constraint_name, column_name, ref_owner, ref_table,
                               ref_column, on_delete_action, on_update_action, ordinal_position)
    """
    return (
        "SELECT "
        "con.constraint_name, "
        "cc.column_name, "
        "rcon.owner AS ref_owner, "
        "rcon.table_name AS ref_table, "
        "rcc.column_name AS ref_column, "
        "con.delete_rule, "
        "'' AS on_update_action, "
        "cc.position AS ordinal_position "
        "FROM all_constraints con "
        "JOIN all_cons_columns cc "
        "  ON con.constraint_name = cc.constraint_name "
        "  AND con.owner = cc.owner "
        "JOIN all_constraints rcon "
        "  ON con.r_constraint_id = rcon.constraint_id "
        "JOIN all_cons_columns rcc "
        "  ON rcon.constraint_name = rcc.constraint_name "
        "  AND rcon.owner = rcc.owner "
        "WHERE con.owner = :owner "
        "  AND con.table_name = :table_name "
        "  AND con.constraint_type = 'R' "
        "ORDER BY con.constraint_name, cc.position"
    )


def fetch_indexes_sql() -> str:
    """SQL query parametrizada para obtener índices Oracle.

    Parametrizado con :owner y :table_name.

    Returns:
        str: SQL query para (index_name, column_name, order_direction, uniqueness, ordinal_position)
    """
    return (
        "SELECT "
        "i.index_name, "
        "ic.column_name, "
        "COALESCE(ic.descend, 'ASC') AS order_direction, "
        "i.uniqueness, "
        "ic.column_position AS ordinal_position "
        "FROM all_indexes i "
        "JOIN all_ind_columns ic "
        "  ON i.index_name = ic.index_name "
        "  AND i.owner = ic.index_owner "
        "WHERE i.owner = :owner "
        "  AND i.table_name = :table_name "
        "ORDER BY i.index_name, ic.column_position"
    )


def fetch_routines_sql() -> str:
    """SQL query parametrizada para obtener rutinas (procedures/functions) Oracle.

    Parametrizado con :owner.

    Returns:
        str: SQL query para procedure_name, object_type, object_id del schema
    """
    return (
        "SELECT procedure_name, object_type, object_id FROM all_procedures WHERE owner = :owner ORDER BY procedure_name"
    )


def fetch_routine_parameters_sql() -> str:
    """SQL query parametrizada para obtener parámetros de rutinas Oracle.

    Parametrizado con :owner y :routine_name.

    Returns:
        str: SQL query para parámetros (argument_name, in_out, data_type, etc)
    """
    return (
        "SELECT "
        "argument_name, "
        "position, "
        "in_out, "
        "data_type, "
        "data_length, "
        "data_precision, "
        "data_scale, "
        "object_id, "
        "argument_id "
        "FROM all_arguments "
        "WHERE owner = :owner "
        "  AND object_name = :routine_name "
        "  AND argument_name IS NOT NULL "
        "ORDER BY position"
    )


__all__: list[str] = [
    "fetch_schemas_sql",
    "fetch_tables_sql",
    "fetch_columns_sql",
    "decode_oracle_column_rows",
    "fetch_pk_constraint_sql",
    "fetch_fk_constraint_sql",
    "fetch_indexes_sql",
    "fetch_routines_sql",
    "fetch_routine_parameters_sql",
]
