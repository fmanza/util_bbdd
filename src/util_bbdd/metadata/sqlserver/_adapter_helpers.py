"""Helpers para construcción y decodificación de queries SQL Server.

Funciones puras para generar T-SQL sys.* queries y decodificar resultados.
"""

from __future__ import annotations

from typing import Any


def build_sqlserver_schemas_query() -> str:
    """Construye query para obtener esquemas de SQL Server.

    Excluye schemas de sistema: sys, INFORMATION_SCHEMA, etc.

    Returns:
        str: SQL query parameterizado
    """
    sql = """
        SELECT s.name
        FROM sys.schemas s
        WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA', 'msdb_repl', 'msdb')
        AND s.principal_id IN (1, 2, 16384)  -- User-defined schemas
        ORDER BY s.name
    """
    return sql


def build_sqlserver_tables_query() -> str:
    """Construye query para obtener tablas de SQL Server.

    Filtra por schema y excluye tablas de sistema.

    Returns:
        str: SQL query parameterizado
    """
    sql = """
        SELECT t.name, 'TABLE', ISNULL(p.value, '')
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN sys.extended_properties p
            ON p.major_id = t.object_id
            AND p.minor_id = 0
            AND p.class = 1
        WHERE s.name = %(schema_name)s
        AND t.type = 'U'
        ORDER BY t.name
    """
    return sql


def build_sqlserver_columns_query() -> str:
    """Construye query para obtener columnas de una tabla.

    Incluye información de tipos, defaults, identidad y comentarios.

    Returns:
        str: SQL query parameterizado
    """
    sql = """
        SELECT
            c.name,
            t.name,
            CASE WHEN c.is_nullable = 1 THEN 1 ELSE 0 END,
            c.column_id,
            ISNULL(dc.definition, ''),
            ISNULL(p.value, ''),
            CASE WHEN c.is_identity = 1 THEN 1 ELSE 0 END
        FROM sys.columns c
        INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
        INNER JOIN sys.tables tbl ON c.object_id = tbl.object_id
        INNER JOIN sys.schemas s ON tbl.schema_id = s.schema_id
        LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
        LEFT JOIN sys.extended_properties p
            ON p.major_id = c.object_id
            AND p.minor_id = c.column_id
            AND p.class = 1
        WHERE s.name = %(schema_name)s
        AND tbl.name = %(table_name)s
        ORDER BY c.column_id
    """
    return sql


def build_sqlserver_pk_query() -> str:
    """Construye query para obtener claves primarias.

    Uses sys.key_constraints e sys.index_columns.

    Returns:
        str: SQL query parameterizado
    """
    sql = """
        SELECT
            kc.name,
            c.name,
            ic.key_ordinal
        FROM sys.key_constraints kc
        INNER JOIN sys.tables t ON kc.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.objects ko ON kc.unique_index_id = ko.object_id
        INNER JOIN sys.indexes i ON ko.object_id = i.object_id
        INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        WHERE kc.type = 'PK'
        AND s.name = %(schema_name)s
        AND t.name = %(table_name)s
        ORDER BY ic.key_ordinal
    """
    return sql


def build_sqlserver_fk_query() -> str:
    """Construye query para obtener claves foráneas.

    Incluye información de referencias, cascadas y ordinal.

    Returns:
        str: SQL query parameterizado
    """
    sql = """
        SELECT
            fk.name,
            c.name,
            rt.name,
            rc.name,
            fk.delete_referential_action,
            fk.update_referential_action,
            fkc.constraint_column_id
        FROM sys.foreign_keys fk
        INNER JOIN sys.tables t ON fk.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id
        INNER JOIN sys.foreign_key_columns fkc
            ON fk.object_id = fkc.constraint_object_id
        INNER JOIN sys.columns c
            ON fkc.parent_object_id = c.object_id
            AND fkc.parent_column_id = c.column_id
        INNER JOIN sys.columns rc
            ON fkc.referenced_object_id = rc.object_id
            AND fkc.referenced_column_id = rc.column_id
        WHERE s.name = %(schema_name)s
        AND t.name = %(table_name)s
        ORDER BY fk.name, fkc.constraint_column_id
    """
    return sql


def build_sqlserver_indexes_query() -> str:
    """Construye query para obtener índices de una tabla.

    Incluye información de unicidad, tipo y columnas.

    Returns:
        str: SQL query parameterizado
    """
    sql = """
        SELECT
            i.name,
            c.name,
            i.is_unique,
            i.type,
            ic.key_ordinal
        FROM sys.indexes i
        INNER JOIN sys.tables t ON i.object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.index_columns ic
            ON i.object_id = ic.object_id
            AND i.index_id = ic.index_id
        INNER JOIN sys.columns c
            ON ic.object_id = c.object_id
            AND ic.column_id = c.column_id
        WHERE s.name = %(schema_name)s
        AND t.name = %(table_name)s
        AND i.index_id > 0
        ORDER BY i.name, ic.key_ordinal
    """
    return sql


def build_sqlserver_routines_query() -> str:
    """Construye query para obtener procedimientos almacenados.

    Excluye procedimientos de sistema (is_ms_shipped=0).

    Returns:
        str: SQL query parameterizado
    """
    sql = """
        SELECT
            sp.name,
            CASE sp.type WHEN 'P' THEN 'PROCEDURE' WHEN 'FN' THEN 'FUNCTION' ELSE 'UNKNOWN' END,
            sp.object_id,
            (SELECT COUNT(*) FROM sys.parameters WHERE object_id = sp.object_id AND parameter_id > 0)
        FROM sys.procedures sp
        INNER JOIN sys.schemas s ON sp.schema_id = s.schema_id
        WHERE sp.is_ms_shipped = 0
        AND s.name = %(schema_name)s
        ORDER BY sp.name
    """
    return sql


def build_sqlserver_parameters_query() -> str:
    """Construye query para obtener parámetros de un procedimiento.

    Excluye return value (parameter_id = 0).

    Returns:
        str: SQL query parameterizado
    """
    sql = """
        SELECT
            p.name,
            p.object_id,
            p.parameter_id,
            t.name,
            CASE WHEN p.is_output = 1 THEN 1 ELSE 0 END,
            ISNULL(p.precision, 0),
            ISNULL(p.scale, 0)
        FROM sys.parameters p
        INNER JOIN sys.types t ON p.user_type_id = t.user_type_id
        WHERE p.object_id = %(object_id)s
        AND p.parameter_id > 0
        ORDER BY p.parameter_id
    """
    return sql


def decode_sqlserver_cascade_rows(rows: list[Any]) -> list[int]:
    """Extrae códigos de cascade action de resultados de FK.

    Args:
        rows: Resultados de FK query

    Returns:
        list[int]: Lista de códigos de acción (0-4)
    """
    actions: list[int] = []
    for row in rows:
        if not row or len(row) < 5:
            continue
        # Posiciones 4 (delete_action) y 5 (update_action)
        if len(row) > 4 and row[4] is not None:
            actions.append(int(row[4]))
        if len(row) > 5 and row[5] is not None:
            actions.append(int(row[5]))
    return actions
