"""Normalización agnóstica de tipos SQL a tipos genéricos."""

from __future__ import annotations

__all__: list[str] = [
    "normalize_column_type",
    "build_generic_columns_hint",
]


# Mapeos genéricos de tipos SQL a tipos normalizado
_SQL_TYPE_MAPPING: dict[str, str] = {
    # Strings
    "char": "string",
    "varchar": "string",
    "text": "string",
    "tinytext": "string",
    "mediumtext": "string",
    "longtext": "string",
    "binary": "string",
    "varbinary": "string",
    # Numbers
    "tinyint": "integer",
    "smallint": "integer",
    "mediumint": "integer",
    "int": "integer",
    "integer": "integer",
    "bigint": "integer",
    "float": "float",
    "double": "float",
    "decimal": "decimal",
    "numeric": "decimal",
    # Temporal
    "date": "date",
    "time": "time",
    "datetime": "datetime",
    "timestamp": "datetime",
    "year": "year",
    # JSON
    "json": "json",
    "jsonb": "jsonb",
    # Boolean
    "bool": "boolean",
    "boolean": "boolean",
    # Spatial (MySQL/PostGIS)
    "geometry": "geometry",
    "point": "geometry",
    "linestring": "geometry",
    "polygon": "geometry",
}


def normalize_column_type(raw_type: str, db_type: str = "generic") -> str:
    """Mapea un tipo SQL nativo a un tipo genérico normalizado.

    Args:
        raw_type: Tipo nativo de la BD (p.ej. 'VARCHAR(255)', 'DATETIME', 'BIGINT').
        db_type: Tipo de BD (p.ej. 'mariadb', 'postgresql', 'sqlite').
                 Usado solo para contexto; el mapeo es agnóstico.

    Returns:
        str: Tipo normalizado (p.ej. 'string', 'integer', 'datetime').
             Si no hay mapeo, devuelve el tipo en minúsculas como fallback.

    Ejemplo:
        >>> normalize_column_type('VARCHAR(100)', 'mariadb')
        'string'
        >>> normalize_column_type('BIGINT UNSIGNED', 'mariadb')
        'integer'
        >>> normalize_column_type('TIMESTAMP', 'postgresql')
        'datetime'
    """
    # Extrae el tipo base sin parámetros ni modificadores
    base_type = raw_type.split("(")[0].strip().lower()
    # Remove common modifiers
    base_type = base_type.replace("unsigned", "").replace("signed", "").strip()

    # Busca en el mapeo
    return _SQL_TYPE_MAPPING.get(base_type, base_type)


def build_generic_columns_hint() -> str:
    """Genera un hint genérico de columnas para documentación.

    Sirve como recomendación en la documentación de cuáles columnas suelen
    devolver los adaptadores de modo agnóstico.

    Returns:
        str: Descripción simple de columnas genéricas esperadas.

    Ejemplo:
        >>> build_generic_columns_hint()
        'column_name, column_type, is_nullable, column_key, ...'
    """
    return "column_name, column_type, is_nullable, column_key, column_default, extra, column_comment"
