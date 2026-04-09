"""Constructores de queries SQL Snowflake y decoders para information_schema.

Encapsula lógica de SQL parametrizado para evitar inyección y facilitar testing.

Snowflake usa INFORMATION_SCHEMA (estándar SQL) para metadatos:
- DATABASES: información de bases de datos
- SCHEMATA: schemas en una base de datos
- TABLES: tablas en un schema
- COLUMNS: columnas en una tabla
- TABLE_CONSTRAINTS: constraints definidos (ADVISORY, no enforced)
- KEY_COLUMN_USAGE: columnas part of constraints
- ROUTINES: funciones y procedimientos almacenados
"""

from __future__ import annotations


def build_snowflake_databases_query() -> str:
    """Construye query para obtener bases de datos Snowflake via INFORMATION_SCHEMA.

    Excluye databases de sistema y compartidas si aplica.

    Returns:
        str: Query SQL sin parámetros
    """
    return """
        SELECT DATABASE_NAME
        FROM INFORMATION_SCHEMA.DATABASES
        WHERE DATABASE_NAME NOT IN ('SNOWFLAKE_SAMPLE_DATA')
        ORDER BY DATABASE_NAME
    """


def build_snowflake_schemas_query() -> str:
    """Construye query para obtener schemas de Snowflake via INFORMATION_SCHEMA.

    Excluye schemas de sistema (INFORMATION_SCHEMA, SNOWFLAKE).

    Returns:
        str: Query SQL parametrizado con :database_name
    """
    return """
        SELECT SCHEMA_NAME
        FROM INFORMATION_SCHEMA.SCHEMATA
        WHERE CATALOG_NAME = :database_name
          AND SCHEMA_NAME NOT IN ('INFORMATION_SCHEMA', 'SNOWFLAKE')
        ORDER BY SCHEMA_NAME
    """


def build_snowflake_tables_query() -> str:
    """Construye query para obtener tablas de un schema via INFORMATION_SCHEMA.TABLES.

    Returns:
        str: Query SQL parametrizado con :database_name, :schema_name
    """
    return """
        SELECT
            TABLE_NAME,
            TABLE_TYPE,
            COALESCE(COMMENT, '') AS table_comment
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_CATALOG = :database_name
          AND TABLE_SCHEMA = :schema_name
          AND TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA', 'SNOWFLAKE')
        ORDER BY TABLE_NAME
    """


def build_snowflake_columns_query() -> str:
    """Construye query para obtener columnas de una tabla via INFORMATION_SCHEMA.COLUMNS.

    Snowflake mantiene tipos en DATA_TYPE y parámetros en CHARACTER_MAXIMUM_LENGTH, etc.

    Returns:
        str: Query SQL parametrizado con :database_name, :schema_name, :table_name
    """
    return """
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            ORDINAL_POSITION,
            COLUMN_DEFAULT,
            COALESCE(COMMENT, '') AS column_comment
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_CATALOG = :database_name
          AND TABLE_SCHEMA = :schema_name
          AND TABLE_NAME = :table_name
        ORDER BY ORDINAL_POSITION
    """


def build_snowflake_pk_query() -> str:
    """Construye query para obtener claves primarias via INFORMATION_SCHEMA.

    IMPORTANTE: Snowflake PK son ADVISORY, no enforced.

    Returns:
        str: Query SQL parametrizado con :database_name, :schema_name, :table_name
    """
    return """
        SELECT
            tc.CONSTRAINT_NAME,
            kcu.COLUMN_NAME,
            kcu.ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            ON tc.TABLE_CATALOG = kcu.TABLE_CATALOG
           AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
           AND tc.TABLE_NAME = kcu.TABLE_NAME
           AND tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
        WHERE tc.TABLE_CATALOG = :database_name
          AND tc.TABLE_SCHEMA = :schema_name
          AND tc.TABLE_NAME = :table_name
          AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        ORDER BY kcu.ORDINAL_POSITION
    """


def build_snowflake_fk_query() -> str:
    """Construye query para obtener claves foráneas via INFORMATION_SCHEMA.

    IMPORTANTE: Snowflake FK son ADVISORY, no enforced.

    Returns:
        str: Query SQL parametrizado con :database_name, :schema_name, :table_name
    """
    return """
        SELECT
            rc.CONSTRAINT_NAME,
            kcu.COLUMN_NAME,
            kcu.REFERENCED_TABLE_NAME,
            kcu.REFERENCED_COLUMN_NAME,
            rc.UPDATE_RULE,
            rc.DELETE_RULE,
            kcu.ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
        LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            ON rc.CONSTRAINT_CATALOG = kcu.TABLE_CATALOG
           AND rc.CONSTRAINT_SCHEMA = kcu.TABLE_SCHEMA
           AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
        WHERE kcu.TABLE_CATALOG = :database_name
          AND kcu.TABLE_SCHEMA = :schema_name
          AND kcu.TABLE_NAME = :table_name
        ORDER BY kcu.ORDINAL_POSITION
    """


def build_snowflake_indexes_query() -> str:
    """Construye query para obtener índices de una tabla (stub).

    IMPORTANTE: Snowflake NO tiene índices nativos.
    Usa CLUSTERING KEY para optimización de query en columnas específicas.

    Retorna vacío; los índices lógicos se documentan desde CLUSTERING KEY.

    Returns:
        str: Query vacío
    """
    # Snowflake no tiene concepto de índices como otros DB
    # CLUSTERING KEY es la única forma de optimizar query en columnas
    return """
        SELECT NULL WHERE 1 = 0
    """


def build_snowflake_routines_query() -> str:
    """Construye query para obtener rutinas (UDFs, SPs) via INFORMATION_SCHEMA.

    Snowflake soporta:
    - FUNCTION (UDF en SQL, JavaScript, etc.)
    - PROCEDURE (stored procedure)

    Returns:
        str: Query SQL parametrizado con :database_name, :schema_name
    """
    return """
        SELECT
            ROUTINE_NAME,
            ROUTINE_TYPE,
            CREATED,
            ROUTINE_DEFINITION,
            LANGUAGE
        FROM INFORMATION_SCHEMA.ROUTINES
        WHERE ROUTINE_CATALOG = :database_name
          AND ROUTINE_SCHEMA = :schema_name
          AND ROUTINE_SCHEMA NOT IN ('INFORMATION_SCHEMA', 'SNOWFLAKE')
        ORDER BY ROUTINE_NAME
    """


def build_snowflake_routine_parameters_query() -> str:
    """Construye query para obtener parámetros de una rutina.

    Snowflake INFORMATION_SCHEMA.PARAMETERS lista parameters de funciones/procedures.

    Returns:
        str: Query SQL parametrizado con :database_name, :schema_name, :routine_name
    """
    return """
        SELECT
            PARAMETER_NAME,
            PARAMETER_MODE,
            DATA_TYPE,
            ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.PARAMETERS
        WHERE ROUTINE_CATALOG = :database_name
          AND ROUTINE_SCHEMA = :schema_name
          AND ROUTINE_NAME = :routine_name
        ORDER BY ORDINAL_POSITION
    """
