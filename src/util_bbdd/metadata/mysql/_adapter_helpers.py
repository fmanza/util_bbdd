"""Constructores de queries SQL Server y decoders para información_schema de MySQL.

Encapsula lógica de SQL parametrizado para evitar inyección y facilitar testing.
"""

from __future__ import annotations


def build_mysql_schemas_query() -> str:
    """Construye query para obtener schemas de MySQL.

    Excluye schemas de sistema (mysql, information_schema, performance_schema, sys).

    Returns:
        str: Query SQL parametrizado
    """
    return """
        SELECT SCHEMA_NAME
        FROM information_schema.SCHEMATA
        WHERE SCHEMA_NAME NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
        ORDER BY SCHEMA_NAME
    """


def build_mysql_tables_query() -> str:
    """Construye query para obtener tablas de un schema.

    Returns:
        str: Query SQL parametrizado con %(schema_name)s
    """
    return """
        SELECT TABLE_NAME, TABLE_TYPE, TABLE_COMMENT
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %(schema_name)s
        ORDER BY TABLE_NAME
    """


def build_mysql_columns_query() -> str:
    """Construye query para obtener columnas de una tabla.

    Incluye información de tipo, nullabilidad, default, y comments.

    Returns:
        str: Query SQL parametrizado con %(schema_name)s, %(table_name)s
    """
    return """
        SELECT
            COLUMN_NAME,
            COLUMN_TYPE,
            IS_NULLABLE,
            ORDINAL_POSITION,
            COLUMN_DEFAULT,
            COLUMN_COMMENT,
            EXTRA
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %(schema_name)s
          AND TABLE_NAME = %(table_name)s
        ORDER BY ORDINAL_POSITION
    """


def build_mysql_pk_query() -> str:
    """Construye query para obtener claves primarias.

    Usa KEY_COLUMN_USAGE de information_schema.

    Returns:
        str: Query SQL parametrizado con %(schema_name)s, %(table_name)s
    """
    return """
        SELECT
            CONSTRAINT_NAME,
            COLUMN_NAME,
            ORDINAL_POSITION
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = %(schema_name)s
          AND TABLE_NAME = %(table_name)s
          AND CONSTRAINT_NAME = 'PRIMARY'
        ORDER BY ORDINAL_POSITION
    """


def build_mysql_fk_query() -> str:
    """Construye query para obtener claves foráneas.

    Combina KEY_COLUMN_USAGE con REFERENTIAL_CONSTRAINTS para obtener
    información completa de FK incluyendo acciones.

    Returns:
        str: Query SQL parametrizado con %(schema_name)s, %(table_name)s
    """
    return """
        SELECT
            k.CONSTRAINT_NAME,
            k.COLUMN_NAME,
            k.REFERENCED_TABLE_NAME,
            k.REFERENCED_COLUMN_NAME,
            r.UPDATE_RULE,
            r.DELETE_RULE,
            k.ORDINAL_POSITION
        FROM information_schema.KEY_COLUMN_USAGE k
        LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS r
            ON k.CONSTRAINT_SCHEMA = r.CONSTRAINT_SCHEMA
            AND k.CONSTRAINT_NAME = r.CONSTRAINT_NAME
        WHERE k.TABLE_SCHEMA = %(schema_name)s
          AND k.TABLE_NAME = %(table_name)s
          AND k.REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY k.ORDINAL_POSITION
    """


def build_mysql_indexes_query() -> str:
    """Construye query para obtener índices.

    Usa information_schema.STATISTICS (evita claves primarias que ya se obtienen por separado).

    Returns:
        str: Query SQL parametrizado con %(schema_name)s, %(table_name)s
    """
    return """
        SELECT
            INDEX_NAME,
            COLUMN_NAME,
            SEQ_IN_INDEX,
            NON_UNIQUE
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %(schema_name)s
          AND TABLE_NAME = %(table_name)s
          AND INDEX_NAME != 'PRIMARY'
        ORDER BY INDEX_NAME, SEQ_IN_INDEX
    """


def build_mysql_routines_query() -> str:
    """Construye query para obtener rutinas (PROCEDURE, FUNCTION).

    Returns:
        str: Query SQL parametrizado con %(schema_name)s
    """
    return """
        SELECT
            ROUTINE_NAME,
            ROUTINE_TYPE,
            CREATED
        FROM information_schema.ROUTINES
        WHERE ROUTINE_SCHEMA = %(schema_name)s
        ORDER BY ROUTINE_NAME
    """


def build_mysql_routine_parameters_query() -> str:
    """Construye query para obtener parámetros de una rutina.

    Returns:
        str: Query SQL parametrizado con %(schema_name)s, %(routine_name)s
    """
    return """
        SELECT
            PARAMETER_NAME,
            PARAMETER_MODE,
            DATA_TYPE,
            ORDINAL_POSITION
        FROM information_schema.PARAMETERS
        WHERE SPECIFIC_SCHEMA = %(schema_name)s
          AND SPECIFIC_NAME = %(routine_name)s
        ORDER BY ORDINAL_POSITION
    """
