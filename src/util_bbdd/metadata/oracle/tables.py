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
    # MEO-06 (AUDIT_CODE 2026-09-22): "NOT LIKE 'WM%'" excluía por error cualquier
    # schema de usuario que empezara por "WM" (p.ej. WMHOLDINGS, WM_REPORTS); WMSYS
    # (el único schema de sistema real con ese prefijo) ya está cubierto por el
    # NOT IN exacto de abajo, así que el filtro por prefijo era redundante y demasiado
    # amplio a la vez. Retirado.
    return (
        "SELECT DISTINCT owner "
        "FROM all_tables "
        "WHERE owner NOT IN ('SYS', 'SYSTEM', 'XDB', 'MDSYS', 'ORDDATA', "
        "'SI_INFORMTN_SCHEMA', 'CTXSYS', 'TXNSYS', 'WMSYS', 'OLAPSYS', "
        "'OWBSYS', 'FLOWS_FILES') "
        "AND owner NOT LIKE 'APEX\\_%%' ESCAPE '\\' "
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
        "'TABLE' AS table_type, "
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
        "c.data_default AS column_default, "
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


#: Tipos Oracle sin mapeo genérico fiable (deprecados por Oracle desde 9i en favor de
#: CLOB/BLOB). MEO-05 (AUDIT_CODE 2026-09-22): antes se descartaban en silencio (la
#: columna desaparecía del resultado sin ningún indicio); ahora se conservan con un
#: marcador explícito en el comentario en vez de desaparecer sin avisar.
_UNSUPPORTED_ORACLE_COLUMN_TYPES: frozenset[str] = frozenset({"LONG", "LONG RAW"})


def _normalize_oracle_column_row(row: Any) -> tuple[str, str, str, int, Any, str] | None:
    """Normaliza una fila individual de columna Oracle.

    Las columnas LONG/LONG RAW se conservan (no se descartan) con un marcador
    explícito ``[TIPO NO SOPORTADO]`` antepuesto al comentario — ver MEO-05.

    Args:
        row: Tupla/lista de datos de columna (9+ elementos)

    Returns:
        Tupla normalizada (column_name, column_type, is_nullable, ordinal_position,
        column_default, column_comment) o None si la fila es inválida.
    """
    if not isinstance(row, (tuple, list)) or len(row) < 9:
        return None

    data_type = str(row[1]).upper() if row[1] else "VARCHAR2"
    comment = str(row[8]) if row[8] else ""
    if data_type in _UNSUPPORTED_ORACLE_COLUMN_TYPES:
        comment = f"[TIPO NO SOPORTADO: {data_type}] {comment}".strip()

    return (
        str(row[0]) if row[0] else "",  # column_name
        str(row[1]) if row[1] else "VARCHAR2",  # data_type
        str(row[2]) if row[2] else "YES",  # is_nullable
        int(row[3]) if row[3] is not None else 0,  # ordinal_position
        str(row[4]).strip() if row[4] else None,  # column_default (puede ser None)
        comment,  # column_comment
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
        "  ON con.r_owner = rcon.owner "
        "  AND con.r_constraint_name = rcon.constraint_name "
        "JOIN all_cons_columns rcc "
        "  ON rcon.constraint_name = rcc.constraint_name "
        "  AND rcon.owner = rcc.owner "
        "  AND rcc.position = cc.position "  # la n-ésima columna de la FK referencia la n-ésima de la clave
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


def fetch_views_sql() -> str:
    """SQL query parametrizada para obtener vistas de un schema Oracle.

    Parametrizado con :owner.
    ``ALL_VIEWS.text`` es tipo LONG; cx_Oracle/python-oracledb lo devuelven
    como ``str`` completo. Para Oracle < 12.2 el comportamiento depende de
    la configuración del driver.

    Returns:
        str: SQL query para (view_name, text, comments)
    """
    return (
        "SELECT v.view_name, v.text, c.comments "
        "FROM all_views v "
        "LEFT JOIN all_tab_comments c "
        "  ON c.owner = v.owner "
        "  AND c.table_name = v.view_name "
        "  AND c.table_type = 'VIEW' "
        "WHERE v.owner = :owner "
        "ORDER BY v.view_name"
    )


def fetch_view_columns_sql() -> str:
    """SQL query parametrizada para obtener columnas de una vista Oracle.

    Parametrizado con :owner y :view_name.

    Returns:
        str: SQL query para column_name ordenado por column_id
    """
    return "SELECT column_name FROM all_tab_columns WHERE owner = :owner AND table_name = :view_name ORDER BY column_id"


def fetch_routines_sql() -> str:
    """SQL query parametrizada para obtener rutinas (procedures/functions) Oracle (uso: adaptadores de metadatos).

    Parametrizado con :owner. Columnas en el orden de ``decode_oracle_routine_rows``.

    Hotfix 0.23.1: en ``ALL_PROCEDURES`` el nombre de una rutina suelta (y el de cada package) está en ``object_name``
    y ``procedure_name`` es NULL; ``procedure_name`` solo lo tienen los miembros de un package. Antes se devolvía
    ``(procedure_name, object_type, object_id)``: nombre vacío y el ``object_id`` leído como owner.

    0.23.2: solo ``PROCEDURE`` y ``FUNCTION``, como el listado de rutinas del resto de motores. ``ALL_PROCEDURES``
    incluye también packages (y sus subprogramas), disparadores y tipos con métodos, que no son rutinas sueltas.

    Returns:
        str: SQL query para (routine_name, object_type, owner, object_id) del schema.
    """
    return (
        "SELECT COALESCE(procedure_name, object_name), object_type, owner, object_id "
        "FROM all_procedures WHERE owner = :owner AND object_type IN ('PROCEDURE', 'FUNCTION') "
        "ORDER BY COALESCE(procedure_name, object_name)"
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


def fetch_routine_body_sql() -> str:
    """SQL query parametrizada para obtener el cuerpo de una rutina Oracle.

    Parametrizado con :owner, :routine_name y :routine_type.
    Concatena todas las líneas de ALL_SOURCE ordenadas por ``line``.

    Returns:
        str: SQL query para (line, text) de la rutina indicada.
    """
    return (
        "SELECT line, text "
        "FROM all_source "
        "WHERE owner = :owner "
        "  AND name = :routine_name "
        "  AND type = :routine_type "
        "ORDER BY line"
    )


def fetch_identity_generation_sql(*, with_owner: bool) -> str:
    """SQL con el tipo de generación de una columna identity (``ALWAYS`` / ``BY DEFAULT``) y su ``DEFAULT_ON_NULL``.

    Lo usa ``PKSequenceSyncer`` para repetir el mismo tipo al modificar la identity (``ALTER TABLE … MODIFY … GENERATED
    … AS IDENTITY (START WITH n)``); la secuencia de una identity no admite ``ALTER SEQUENCE`` (ORA-32793).

    Args:
        with_owner: ``True`` consulta ``ALL_TAB_IDENTITY_COLS`` filtrando por ``:owner``; ``False``, las vistas
            ``USER_*``.

    Parámetros: ``:tbl``, ``:col`` y, con ``with_owner``, ``:owner``, con los nombres como en el catálogo.

    Returns:
        str: SQL para (generation_type, default_on_null).
    """
    if with_owner:
        return (
            "SELECT i.generation_type, c.default_on_null FROM all_tab_identity_cols i "
            "JOIN all_tab_columns c ON c.owner = i.owner AND c.table_name = i.table_name "
            "AND c.column_name = i.column_name "
            "WHERE i.owner = :owner AND i.table_name = :tbl AND i.column_name = :col"
        )
    return (
        "SELECT i.generation_type, c.default_on_null FROM user_tab_identity_cols i "
        "JOIN user_tab_columns c ON c.table_name = i.table_name AND c.column_name = i.column_name "
        "WHERE i.table_name = :tbl AND i.column_name = :col"
    )


# ─── migrate/extractors: una consulta por schema y tipo de objeto (D1, 0.21.0) ─────────────
# Mismo SQL que las consultas por tabla de arriba (que siguen usando los adaptadores de metadatos), sin el filtro de
# tabla y con ``table_name`` como primera columna; filas ordenadas por tabla y después por el orden propio del objeto.
# 200 tablas: 823 consultas (7,3 s en el banco) → 8 (0,18 s). Sesión 2026-09-30-migrate-d1-extract-batching.


def fetch_columns_for_schema_sql() -> str:
    """Columnas de todas las tablas de un owner (uso: migrate/extractors). Parametrizado con :owner.

    Returns:
        str: SQL query para (table_name, + las 9 columnas de :func:`fetch_columns_sql`).
    """
    return (
        "SELECT "
        "c.table_name, "
        "c.column_name, "
        "c.data_type, "
        "CASE WHEN c.nullable = 'Y' THEN 'YES' ELSE 'NO' END AS is_nullable, "
        "c.column_id AS ordinal_position, "
        "c.data_default AS column_default, "
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
        "  AND c.column_name != 'ROWID' "
        "ORDER BY c.table_name, c.column_id"
    )


def fetch_pk_for_schema_sql() -> str:
    """Columnas de PK de todas las tablas de un owner (uso: migrate/extractors). Parametrizado con :owner.

    Returns:
        str: SQL query para (table_name, constraint_name, column_name, ordinal_position).
    """
    return (
        "SELECT "
        "con.table_name, "
        "cc.constraint_name, "
        "cc.column_name, "
        "cc.position AS ordinal_position "
        "FROM all_constraints con "
        "JOIN all_cons_columns cc "
        "  ON con.constraint_name = cc.constraint_name "
        "  AND con.owner = cc.owner "
        "WHERE con.owner = :owner "
        "  AND con.constraint_type = 'P' "
        "ORDER BY con.table_name, con.constraint_name, cc.position"
    )


def fetch_fk_for_schema_sql() -> str:
    """Claves foráneas de todas las tablas de un owner (uso: migrate/extractors). Parametrizado con :owner.

    Returns:
        str: SQL query para (table_name, + las 8 columnas de :func:`fetch_fk_constraint_sql`).
    """
    return (
        "SELECT "
        "con.table_name, "
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
        "  ON con.r_owner = rcon.owner "
        "  AND con.r_constraint_name = rcon.constraint_name "
        "JOIN all_cons_columns rcc "
        "  ON rcon.constraint_name = rcc.constraint_name "
        "  AND rcon.owner = rcc.owner "
        "  AND rcc.position = cc.position "  # la n-ésima columna de la FK referencia la n-ésima de la clave
        "WHERE con.owner = :owner "
        "  AND con.constraint_type = 'R' "
        "ORDER BY con.table_name, con.constraint_name, cc.position"
    )


def fetch_indexes_for_schema_sql() -> str:
    """Índices de todas las tablas de un owner (uso: migrate/extractors). Parametrizado con :owner.

    Returns:
        str: SQL query para (table_name, + las 5 columnas de :func:`fetch_indexes_sql`).
    """
    return (
        "SELECT "
        "i.table_name, "
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
        "ORDER BY i.table_name, i.index_name, ic.column_position"
    )


def fetch_view_columns_for_schema_sql() -> str:
    """Columnas de todas las tablas y vistas de un owner (uso: migrate/extractors). Parametrizado con :owner.

    Returns:
        str: SQL query para (table_name, column_name) ordenado por tabla y column_id.
    """
    return "SELECT table_name, column_name FROM all_tab_columns WHERE owner = :owner ORDER BY table_name, column_id"


def fetch_routines_for_schema_sql() -> str:
    """Rutinas sueltas y miembros de package de un owner (uso: migrate/extractors, hotfix R4 0.23.1).

    En ``ALL_PROCEDURES`` el nombre de una rutina suelta está en ``object_name`` y ``procedure_name`` es NULL;
    ``procedure_name`` solo lo tienen los miembros de un package (``object_name`` = el package). :func:`fetch_routines_sql`
    (la de los adaptadores) lee solo ``procedure_name`` y no sirve para las rutinas sueltas.

    Parametrizado con :owner.

    Returns:
        str: SQL query para (object_name, object_type, procedure_name).
    """
    return (
        "SELECT object_name, object_type, procedure_name "
        "FROM all_procedures "
        "WHERE owner = :owner AND object_type IN ('PROCEDURE', 'FUNCTION', 'PACKAGE') "
        "ORDER BY object_name, subprogram_id"
    )


def fetch_routine_bodies_for_schema_sql() -> str:
    """Código de todas las rutinas y cuerpos de package de un owner (uso: migrate/extractors).

    Parametrizado con :owner. Solo los tipos que lee el extractor: PROCEDURE, FUNCTION y PACKAGE BODY.

    Returns:
        str: SQL query para (name, type, line, text) ordenado por nombre, tipo y línea.
    """
    return (
        "SELECT name, type, line, text "
        "FROM all_source "
        "WHERE owner = :owner "
        "  AND type IN ('PROCEDURE', 'FUNCTION', 'PACKAGE BODY') "
        "ORDER BY name, type, line"
    )


def fetch_standalone_routine_sources_for_schema_sql() -> str:
    """Código de las procedures y functions sueltas de un owner, en una consulta (uso: comparar).

    Como :func:`fetch_routine_bodies_for_schema_sql` pero sin ``PACKAGE BODY``: quien solo compara rutinas sueltas
    no transfiere el código de los packages, que puede ser de miles de líneas.

    Parametrizado con :owner.

    Returns:
        str: SQL query para (name, type, line, text) ordenado por nombre, tipo y línea.
    """
    return (
        "SELECT name, type, line, text "
        "FROM all_source "
        "WHERE owner = :owner "
        "  AND type IN ('PROCEDURE', 'FUNCTION') "
        "ORDER BY name, type, line"
    )


__all__: list[str] = [
    "fetch_schemas_sql",
    "fetch_tables_sql",
    "fetch_columns_sql",
    "decode_oracle_column_rows",
    "fetch_pk_constraint_sql",
    "fetch_fk_constraint_sql",
    "fetch_indexes_sql",
    "fetch_views_sql",
    "fetch_view_columns_sql",
    "fetch_routines_sql",
    "fetch_routine_parameters_sql",
    "fetch_routine_body_sql",
    "fetch_identity_generation_sql",
    "fetch_columns_for_schema_sql",
    "fetch_pk_for_schema_sql",
    "fetch_fk_for_schema_sql",
    "fetch_indexes_for_schema_sql",
    "fetch_view_columns_for_schema_sql",
    "fetch_routine_bodies_for_schema_sql",
    "fetch_standalone_routine_sources_for_schema_sql",
    "fetch_routines_for_schema_sql",
]
