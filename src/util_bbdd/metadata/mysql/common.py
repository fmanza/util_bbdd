"""Helpers puros compartidos para metadata MySQL.

Proporciona mapeos de tipos MySQL a tipos genéricos, escaping de identificadores,
y funciones de normalización.
"""

from __future__ import annotations


def mysql_type_mapping() -> dict[str, str]:
    """Retorna mapeo completo de tipos MySQL a tipos genéricos.

    Cubre 40+ tipos MySQL comunes incluyendo precisión variable,
    tipos de fecha/hora, JSON, ENUM, SET y tipos especializados.

    Returns:
        dict[str, str]: Mapeo {mysql_type_upper: generic_type}
    """
    return {
        # Integers
        "TINYINT": "tinyint",
        "SMALLINT": "smallint",
        "MEDIUMINT": "integer",
        "INT": "integer",
        "INTEGER": "integer",
        "BIGINT": "bigint",
        # Floating point
        "FLOAT": "float",
        "DOUBLE": "float",
        "DOUBLE PRECISION": "float",
        "REAL": "float",
        # Fixed point
        "DECIMAL": "decimal",
        "DEC": "decimal",
        "NUMERIC": "numeric",
        "FIXED": "numeric",
        # Strings
        "CHAR": "char",
        "VARCHAR": "varchar",
        "BINARY": "binary",
        "VARBINARY": "binary",
        "TINYBLOB": "binary",
        "BLOB": "binary",
        "MEDIUMBLOB": "binary",
        "LONGBLOB": "binary",
        "TINYTEXT": "text",
        "TEXT": "text",
        "MEDIUMTEXT": "text",
        "LONGTEXT": "text",
        # Date/Time
        "DATE": "date",
        "TIME": "time",
        "DATETIME": "datetime",
        "TIMESTAMP": "timestamp",
        "YEAR": "year",
        # Special types
        "JSON": "json",
        "ENUM": "enum",
        "SET": "set",
        "GEOMETRY": "geometry",
        "POINT": "geometry",
        "LINESTRING": "geometry",
        "POLYGON": "geometry",
        "MULTIPOINT": "geometry",
        "MULTILINESTRING": "geometry",
        "MULTIPOLYGON": "geometry",
        "GEOMETRYCOLLECTION": "geometry",
    }


def normalize_mysql_type(mysql_type: str) -> str:
    """Normaliza un tipo MySQL al tipo genérico.

    Para tipos con parámetros (e.g., "VARCHAR(255)", "DECIMAL(10,2)"), extrae la palabra base.
    Si no está en el mapeo, devuelve "object".

    Args:
        mysql_type: Tipo MySQL crudado de information_schema (ej: "VARCHAR", "INT")

    Returns:
        str: Tipo genérico (ej: "varchar", "integer")
    """
    if not mysql_type:
        return "object"

    base_type = mysql_type.strip().upper().split("(")[0].strip()

    mapping = mysql_type_mapping()
    if base_type in mapping:
        return mapping[base_type]

    return "object"


def quote_mysql_identifier(identifier: str) -> str:
    """Escapea un identificador MySQL con backticks.

    Reemplaza backticks internos con doble backtick (estándar SQL).

    Args:
        identifier: Nombre de tabla, columna, schema, etc.

    Returns:
        str: Identificador escapado con backticks (ej: `table_name`)
    """
    if not identifier:
        return "``"

    escaped = identifier.replace("`", "``")
    return f"`{escaped}`"


def escape_mysql_string(value: str) -> str:
    """Escapea un string literal para MySQL.

    Escapa comillas simples y backslashes.

    Args:
        value: String a escapar

    Returns:
        str: String escapado
    """
    if not value:
        return "''"

    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def is_system_schema_mysql(schema_name: str) -> bool:
    """Verifica si es un schema de sistema MySQL a filtrar.

    Schemas excluidos:
    - mysql
    - information_schema
    - performance_schema
    - sys

    Args:
        schema_name: Nombre del schema

    Returns:
        bool: True si es schema de sistema
    """
    excluded = {"mysql", "information_schema", "performance_schema", "sys"}
    return schema_name.lower() in excluded


def decode_mysql_cascade_action(action_code: str | int) -> str:
    """Decodifica el código de acción CASCADE de MySQL.

    Mapeo:
    - 'RESTRICT' -> 'RESTRICT'
    - 'CASCADE' -> 'CASCADE'
    - 'SET NULL' -> 'SET NULL'
    - 'NO ACTION' -> 'NO ACTION'
    - 'SET DEFAULT' -> 'SET DEFAULT'
    - default -> 'RESTRICT'

    Args:
        action_code: Código o nombre de acción (string del information_schema)

    Returns:
        str: Acción normalizada
    """
    action_str = str(action_code).strip().upper()

    action_map = {
        "RESTRICT": "RESTRICT",
        "CASCADE": "CASCADE",
        "SET NULL": "SET NULL",
        "NO ACTION": "NO ACTION",
        "SET DEFAULT": "SET DEFAULT",
    }

    return action_map.get(action_str, "RESTRICT")
