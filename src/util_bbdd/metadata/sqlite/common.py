"""Helpers puros compartidos para metadata SQLite.

Proporciona mapeos de tipos SQLite a tipos genéricos, escaping de identificadores,
y funciones de normalización.
"""

from __future__ import annotations

from ..adapters.shared import normalize_column_type


def sqlite_type_mapping() -> dict[str, str]:
    """Retorna mapeo completo de tipos SQLite a tipos genéricos.

    SQLite tiene 5 tipos de almacenamiento: NULL, INTEGER, REAL, TEXT, BLOB.
    Se incluyen affinities y tipos comunes compatibles.

    Returns:
        dict[str, str]: Mapeo {sqlite_type_upper: generic_type}
    """
    return {
        "NULL": "null",
        "INTEGER": "integer",
        "INT": "integer",
        "TINYINT": "integer",
        "SMALLINT": "smallint",
        "MEDIUMINT": "integer",
        "BIGINT": "bigint",
        "UNSIGNED BIG INT": "bigint",
        "INT2": "integer",
        "INT4": "integer",
        "INT8": "bigint",
        "REAL": "float",
        "DOUBLE": "float",
        "DOUBLE PRECISION": "float",
        "FLOAT": "float",
        "NUMERIC": "numeric",
        "DECIMAL": "decimal",
        "BOOLEAN": "boolean",
        "TEXT": "varchar",
        "VARCHAR": "varchar",
        "CHARACTER": "char",
        "CHAR": "char",
        "VARYING CHARACTER": "varchar",
        "NCHAR": "varchar",
        "NATIVE CHARACTER": "varchar",
        "NVARCHAR": "varchar",
        "CLOB": "clob",
        "BLOB": "binary",
        "DATE": "date",
        "TIME": "time",
        "DATETIME": "datetime",
        "TIMESTAMP": "timestamp",
        "JSON": "object",
        "UUID": "varchar",
    }


def normalize_sqlite_type(sqlite_type: str) -> str:
    """Normaliza un tipo SQLite al tipo genérico.

    Para tipos con parámetros (e.g., "VARCHAR(255)"), extrae la palabra base.
    Si no está en el mapeo, devuelve "object".

    Args:
        sqlite_type: Tipo SQLite crudado del PRAGMA table_info (ej: "VARCHAR", "INTEGER")

    Returns:
        str: Tipo genérico normalizado o "object" si no se mapea
    """
    if not sqlite_type:
        return "object"

    sqlite_type_clean = str(sqlite_type).strip().upper()

    # Extraer tipo base (remover parámetros en paréntesis)
    if "(" in sqlite_type_clean:
        base_type = sqlite_type_clean.split("(")[0].strip()
    else:
        base_type = sqlite_type_clean

    # Buscar en mapeo
    mapping = sqlite_type_mapping()
    if base_type in mapping:
        return mapping[base_type]

    # Tipos compuestos (ej: "DOUBLE PRECISION", "VARYING CHARACTER")
    if " " in sqlite_type_clean:
        clean_full = sqlite_type_clean.split("(")[0].strip()
        if clean_full in mapping:
            return mapping[clean_full]

    # Fallback
    return normalize_column_type(base_type, db_type="sqlite") or "object"


def quote_sqlite_identifier(identifier: str) -> str:
    """Escapa identificadores SQLite con comillas dobles.

    SQLite acepta comillas dobles, corchetes y backticks para delimitar identificadores.
    Se usa comillas dobles por compatibilidad con SQL estándar.

    Args:
        identifier: Identificador a escapar (nombre de tabla, columna, schema)

    Returns:
        str: Identificador escapado con comillas dobles
    """
    if not identifier:
        return '""'

    identifier_str = str(identifier).strip()

    # Escapar comillas dobles internas duplicándolas
    escaped = identifier_str.replace('"', '""')

    return f'"{escaped}"'


def is_system_schema_sqlite(schema: str | None) -> bool:
    """Determina si un schema es sistema en SQLite.

    SQLite no tiene schemas de sistema en el sentido tradicional.
    Solo tiene "main" (por defecto) y "temp" (temporal).
    Retorna False siempre, ya que estos no se consideran "sistema".

    Args:
        schema: Nombre del schema

    Returns:
        bool: False (no hay schemas de sistema en SQLite)
    """
    return False


def escape_sqlite_string(value: str) -> str:
    """Escapa strings para uso en SQL dinámico SQLite.

    Duplica comillas simples para evitar inyección SQL.

    Args:
        value: String a escapar

    Returns:
        str: String escapado entre comillas simples
    """
    if not value:
        return "''"

    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"
