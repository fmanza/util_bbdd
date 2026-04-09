"""Helpers puros compartidos para metadata Snowflake.

Proporciona mapeos de tipos Snowflake a tipos genéricos, escaping de identificadores,
y funciones de normalización.

Snowflake soporta tipos SQL estándar más tipos semi-estructurados (OBJECT, ARRAY, VARIANT).
Caso: identifiers UPPERCASE por defecto; comillas dobles preservan case.
"""

from __future__ import annotations


def snowflake_type_mapping() -> dict[str, str]:
    """Retorna mapeo completo de tipos Snowflake a tipos genéricos.

    Snowflake soporta más de 30 tipos nativos:
    - Numeric: INT, BIGINT, SMALLINT, TINYINT, FLOAT, DOUBLE, NUMBER(p,s) DECIMAL
    - String: VARCHAR, CHAR, TEXT, STRING
    - Date/Time: DATE, TIME, DATETIME, TIMESTAMP variants
    - Binary: BINARY, VARBINARY
    - Semi-structured: OBJECT, ARRAY, VARIANT (parsed como "object")
    - Geography: GEOGRAPHY, GEOMETRY

    Fallback: "object" para tipos no reconocidos.

    Returns:
        dict[str, str]: Mapeo {snowflake_type_upper: generic_type}
    """
    return {
        # Integer types
        "INT": "integer",
        "INTEGER": "integer",
        "INT2": "smallint",
        "INT4": "integer",
        "INT8": "bigint",
        "SMALLINT": "smallint",
        "TINYINT": "smallint",
        "BIGINT": "bigint",
        "BYTEINT": "smallint",
        # Floating point
        "FLOAT": "float",
        "FLOAT4": "float",
        "FLOAT8": "float",
        "DOUBLE": "float",
        "DOUBLE PRECISION": "float",
        "REAL": "float",
        # Fixed point / Numeric
        "DECIMAL": "decimal",
        "NUMERIC": "numeric",
        "NUMBER": "numeric",
        # String types
        "CHAR": "char",
        "CHARACTER": "char",
        "VARCHAR": "varchar",
        "CHARACTER VARYING": "varchar",
        "TEXT": "text",
        "STRING": "text",
        # Binary
        "BINARY": "binary",
        "VARBINARY": "binary",
        # Date / Time (Snowflake has many variants)
        "DATE": "date",
        "TIME": "time",
        "TIME WITHOUT TIME ZONE": "time",
        "TIMETZ": "time",
        "TIME WITH TIME ZONE": "time",
        "DATETIME": "timestamp",
        "TIMESTAMP": "timestamp",
        "TIMESTAMP WITHOUT TIME ZONE": "timestamp",
        "TIMESTAMP_NTZ": "timestamp",
        "TIMESTAMP WITH TIME ZONE": "timestamp",
        "TIMESTAMP_TZ": "timestamp",
        "TIMESTAMP_LTZ": "timestamp",
        "TIMESTAMPTZ": "timestamp",
        "TIMESTAMPNTZ": "timestamp",
        # Boolean
        "BOOLEAN": "boolean",
        "BOOL": "boolean",
        # Semi-structured (parsed as object)
        "OBJECT": "object",
        "ARRAY": "object",
        "VARIANT": "object",
        # Geography
        "GEOGRAPHY": "object",
        "GEOMETRY": "object",
    }


def normalize_snowflake_type(column_type: str) -> str:
    """Normaliza un tipo Snowflake a tipo genérico.

    Extrae tipo base y parámetros (p.ej. NUMBER(10,2) -> numeric).
    Normaliza a UPPERCASE per Snowflake default case sensitivity.

    Args:
        column_type: Tipo Snowflake con/sin parámetros

    Returns:
        str: Tipo genérico normalizado o "object" si no se reconoce
    """
    if not column_type:
        return "object"

    # Limpiar espacios y convertir a mayúsculas
    ct = column_type.strip().upper()

    # Remover parámetros (p.ej. VARCHAR(255) -> VARCHAR, NUMBER(10,2) -> NUMBER)
    base_type = ct.split("(")[0].strip()

    # Usar mapeo
    mapping = snowflake_type_mapping()
    return mapping.get(base_type, "object")


def quote_snowflake_identifier(name: str) -> str:
    """Cita un identificador Snowflake (schema, tabla, columna, etc.).

    Snowflake es case-insensitive por defecto (identifiers UPPERCASE);
    comillas dobles preservan case.

    Args:
        name: Identificador sin comillas

    Returns:
        str: Identificador citado con comillas dobles y caracteres especiales escapados
    """
    if not name:
        return '""'

    # Escapar comillas dobles duplicándolas
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def escape_snowflake_string(value: str) -> str:
    """Escapa un literal de string para Snowflake.

    Usa comillas simples Y duplica apóstrofos (estándar SQL).

    Args:
        value: String a escapar

    Returns:
        str: String escapado listo para SQL
    """
    if not value:
        return "''"

    # Duplicar comillas simples (estándar SQL)
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def normalize_snowflake_identifier(name: str | None) -> str:
    """Normaliza un identificador Snowflake a UPPERCASE (default case).

    Snowflake almacena identifiers no-quoted en UPPERCASE internamente.

    Args:
        name: Identificador original

    Returns:
        str: Identificador normalizado a UPPERCASE
    """
    if not name:
        return ""

    # Si está entre comillas, preservar case y remover comillas
    if name.startswith('"') and name.endswith('"'):
        return name[1:-1]

    # Si no está entre comillas, normalizar a UPPERCASE
    return name.strip().upper()


def is_system_schema_snowflake(schema_name: str | None) -> bool:
    """Determina si un schema debe excluirse por ser de sistema Snowflake.

    Sistema schemas: INFORMATION_SCHEMA, SNOWFLAKE (algunos objetos).

    Args:
        schema_name: Nombre del schema

    Returns:
        bool: True si es schema de sistema
    """
    if not schema_name:
        return False

    s = schema_name.strip().upper()
    return s in ("INFORMATION_SCHEMA", "SNOWFLAKE")


def parse_snowflake_database_schema_table(full_name: str) -> tuple[str, str, str]:
    """Parsea un nombre de objeto Snowflake en componentes DATABASE.SCHEMA.TABLE.

    Snowflake usa tres niveles: DATABASE.SCHEMA.TABLE (CURRENT_DATABASE si no especificado).

    Args:
        full_name: Nombre completo (puede ser "TABLE", "SCHEMA.TABLE", "DB.SCHEMA.TABLE")

    Returns:
        tuple[str, str, str]: (database, schema, table) — vacío si no especificado
    """
    if not full_name:
        return ("", "", "")

    name = full_name.strip()
    parts = name.split(".")

    if len(parts) == 1:
        # Solo tabla
        return ("", "", parts[0])
    elif len(parts) == 2:
        # SCHEMA.TABLE
        return ("", parts[0], parts[1])
    elif len(parts) >= 3:
        # DATABASE.SCHEMA.TABLE (o más, usar últimos 3)
        return (parts[-3], parts[-2], parts[-1])

    return ("", "", "")
