"""Helpers puros compartidos para metadata Redshift.

Proporciona mapeos de tipos Redshift a tipos genéricos, escaping de identificadores,
y funciones de normalización.

Redshift soporta un subconjunto de tipos PostgreSQL (sin arrays, ranges, UDTs).
"""

from __future__ import annotations


def redshift_type_mapping() -> dict[str, str]:
    """Retorna mapeo completo de tipos Redshift a tipos genéricos.

    Redshift soporta: integer, varchar, char, decimal, numeric, float, double,
    boolean, date, timestamp, time, smallint, bigint, real, int, integer.

    Fallback: "object" para tipos no reconocidos.

    Returns:
        dict[str, str]: Mapeo {redshift_type_upper: generic_type}
    """
    return {
        # Integers
        "SMALLINT": "smallint",
        "INT2": "smallint",
        "INT": "integer",
        "INTEGER": "integer",
        "INT4": "integer",
        "BIGINT": "bigint",
        "INT8": "bigint",
        # Floating point
        "FLOAT": "float",
        "FLOAT4": "float",
        "FLOAT8": "float",
        "DOUBLE": "float",
        "DOUBLE PRECISION": "float",
        "REAL": "float",
        # Fixed point
        "DECIMAL": "decimal",
        "NUMERIC": "numeric",
        # Strings
        "CHAR": "char",
        "CHARACTER": "char",
        "BPCHAR": "char",
        "VARCHAR": "varchar",
        "CHARACTER VARYING": "varchar",
        "TEXT": "text",
        # Binary (Redshift tiene limitado soporte)
        "BYTEA": "binary",
        # Date/Time
        "DATE": "date",
        "TIME": "time",
        "TIME WITHOUT TIME ZONE": "time",
        "TIMETZ": "time",
        "TIME WITH TIME ZONE": "time",
        "TIMESTAMP": "timestamp",
        "TIMESTAMP WITHOUT TIME ZONE": "timestamp",
        "TIMESTAMPTZ": "timestamp",
        "TIMESTAMP WITH TIME ZONE": "timestamp",
        # Boolean
        "BOOLEAN": "boolean",
        "BOOL": "boolean",
        # Geometry (soporte limitado)
        "GEOMETRY": "object",
        # JSON
        "JSON": "text",
        "JSONB": "text",
    }


def normalize_redshift_type(column_type: str) -> str:
    """Normaliza un tipo Redshift a tipo genérico.

    Extrae tipo base y parámetros (p.ej. VARCHAR(50) -> varchar).

    Args:
        column_type: Tipo Redshift con/sin parámetros

    Returns:
        str: Tipo genérico normalizado o "object" si no se reconoce
    """
    if not column_type:
        return "object"

    # Limpiar espacios y convertir a mayúsculas
    ct = column_type.strip().upper()

    # Remover parámetros (p.ej. VARCHAR(255) -> VARCHAR)
    base_type = ct.split("(")[0].strip()

    # Usar mapeo
    mapping = redshift_type_mapping()
    return mapping.get(base_type, "object")


def quote_redshift_identifier(name: str) -> str:
    """Cita un identificador Redshift (schema, tabla, columna, etc.).

    Redshift es case-insensitive por defecto; las comillas dobles preservan case.

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


def escape_redshift_string(value: str) -> str:
    """Escapa un literal de string untuk Redshift.

    Usa comillas simples Y duplica apóstrofos.

    Args:
        value: String a escapar

    Returns:
        str: String escapado listo para SQL
    """
    if not value:
        return "''"

    # Duplicar comillas simples
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def is_system_schema_redshift(schema_name: str | None) -> bool:
    """Determina si un schema debe excluirse por ser de sistema Redshift.

    Sistema schemas: pg_*, information_schema.

    Args:
        schema_name: Nombre del schema

    Returns:
        bool: True si es schema de sistema
    """
    if not schema_name:
        return False

    s = schema_name.strip().lower()
    return s.startswith("pg_") or s == "information_schema"
