"""Constructores de queries SQL Redshift y decoders para pg_catalog e information_schema.

Encapsula lógica de SQL parametrizado para evitar inyección y facilitar testing.

Redshift difiere de PostgreSQL en:
- No supporta arrays, ranges, user-defined types (UDTs)
- Constraints (PK/FK/CHECK) son metadata-only, NO ENFORCED
- Usa mezcla de pg_catalog e information_schema
"""

from __future__ import annotations


def build_redshift_schemas_query() -> str:
    """Construye query para obtener schemas de Redshift via pg_catalog.

    Excluye schemas de sistema (pg_*, information_schema).

    Returns:
        str: Query SQL sin parámetros
    """
    return """
        SELECT n.nspname
        FROM pg_catalog.pg_namespace n
        WHERE n.nspname NOT LIKE 'pg\\_%%'
          AND n.nspname != 'information_schema'
        ORDER BY n.nspname
    """


def build_redshift_tables_query() -> str:
    """Construye query para obtener tablas de un schema via pg_catalog.pg_tables.

    Returns:
        str: Query SQL parametrizado con :schema_name
    """
    return """
        SELECT tablename, 'TABLE' AS table_type, ''
        FROM pg_catalog.pg_tables
        WHERE schemaname = :schema_name
        ORDER BY tablename
    """


def build_redshift_columns_query() -> str:
    """Construye query para obtener columnas de una tabla via information_schema.columns.

    (Redshift usa information_schema para columnas, contrario a PostgreSQL)

    Returns:
        str: Query SQL parametrizado con :schema_name, :table_name
    """
    return """
        SELECT
            column_name,
            udt_name,
            is_nullable,
            ordinal_position,
            column_default,
            ''
        FROM information_schema.columns
        WHERE table_schema = :schema_name
          AND table_name = :table_name
        ORDER BY ordinal_position
    """


def build_redshift_pk_query() -> str:
    """Construye query para obtener claves primarias via information_schema.

    IMPORTANTE: Redshift PK son ADVISORY, no enforced.

    Returns:
        str: Query SQL parametrizado con :schema_name, :table_name
    """
    return """
        SELECT
            constraint_name,
            column_name,
            ordinal_position
        FROM information_schema.key_column_usage
        WHERE table_schema = :schema_name
          AND table_name = :table_name
          AND constraint_type = 'PRIMARY KEY'
        ORDER BY ordinal_position
    """


def build_redshift_fk_query() -> str:
    """Construye query para obtener claves foráneas via information_schema.

    IMPORTANTE: Redshift FK son ADVISORY, no enforced.

    Combina key_column_usage con referential_constraints.

    Returns:
        str: Query SQL parametrizado con :schema_name, :table_name
    """
    return """
        SELECT
            k.constraint_name,
            k.column_name,
            k.referenced_table_name,
            k.referenced_column_name,
            r.update_rule,
            r.delete_rule,
            k.ordinal_position
        FROM information_schema.key_column_usage k
        LEFT JOIN information_schema.referential_constraints r
            ON k.constraint_schema = r.constraint_schema
           AND k.constraint_name = r.constraint_name
        WHERE k.table_schema = :schema_name
          AND k.table_name = :table_name
          AND k.referenced_table_name IS NOT NULL
        ORDER BY k.ordinal_position
    """


def build_redshift_indexes_query() -> str:
    """Construye query para obtener índices de una tabla via pg_catalog.

    Redshift tiene soporte limitado para índices; principalmente para uso interno.

    Returns:
        str: Query SQL parametrizado con :schema_name, :table_name
    """
    return """
        SELECT
            indexname,
            'INDEX' AS index_type,
            ''
        FROM pg_catalog.pg_indexes
        WHERE schemaname = :schema_name
          AND tablename = :table_name
        ORDER BY indexname
    """


def build_redshift_routines_query() -> str:
    """Construye query para obtener rutinas (UDFs) via information_schema.

    Redshift soporta principalmente UDFs (funciones), no procedimientos.

    Returns:
        str: Query SQL parametrizado con :schema_name
    """
    return """
        SELECT
            routine_name,
            routine_type,
            created,
            routine_schema
        FROM information_schema.routines
        WHERE routine_schema = :schema_name
        ORDER BY routine_name
    """
