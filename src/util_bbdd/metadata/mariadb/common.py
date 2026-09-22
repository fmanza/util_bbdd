"""Helpers puros compartidos para metadata MariaDB."""

from __future__ import annotations

from typing import Any


def mariadb_type_mapping() -> dict[str, str]:
    """Retorna mapeo completo de tipos MariaDB a tipos genéricos.

    MEO-07 (AUDIT_CODE 2026-09-22): MariaDB no tenía ninguna función de
    normalización propia — MariaDBSyncAdapter/AsyncAdapter.fetch_columns_sync/async
    exponían el tipo nativo crudo (p.ej. "varchar(255)") como ``column_type``, a
    diferencia del resto de motores (mysql, postgresql, sqlserver, oracle, sqlite),
    que devuelven un tipo genérico normalizado. Mapeo alineado con
    ``mysql_type_mapping()`` (MariaDB es históricamente compatible con el sistema
    de tipos de MySQL en ``information_schema``).

    Returns:
        dict[str, str]: Mapeo {mariadb_type_upper: generic_type}
    """
    return {
        # Integers
        "TINYINT": "tinyint",
        "SMALLINT": "smallint",
        "MEDIUMINT": "integer",
        "INT": "integer",
        "INTEGER": "integer",
        "BIGINT": "bigint",
        "BIT": "bit",
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


def normalize_mariadb_type(mariadb_type: str) -> str:
    """Normaliza un tipo MariaDB al tipo genérico.

    Para tipos con parámetros (e.g., "VARCHAR(255)", "DECIMAL(10,2)"), extrae la
    palabra base. Si no está en el mapeo, devuelve "object".

    Args:
        mariadb_type: Tipo MariaDB crudo de information_schema (ej: "varchar(255)")

    Returns:
        str: Tipo genérico (ej: "varchar", "integer")
    """
    if not mariadb_type:
        return "object"

    base_type = mariadb_type.strip().upper().split("(")[0].strip()

    mapping = mariadb_type_mapping()
    if base_type in mapping:
        return mapping[base_type]

    return "object"


def escape_mariadb_sql_literal(value: str) -> str:
    """Escapa comillas simples para SQL literal MariaDB."""
    return str(value).replace("'", "''")


def decode_mariadb_hex_text(value: Any) -> str:
    """Decodifica texto HEX de MariaDB con fallback latin-1."""
    if value is None:
        return ""
    raw_hex: str = str(value).strip()
    if not raw_hex:
        return ""
    try:
        raw_bytes = bytes.fromhex(raw_hex)
    except ValueError:
        return str(value)
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1")


def quote_mariadb_identifier(identifier: str) -> str:
    """Quote de identificadores MariaDB con backticks."""
    from ..adapters.shared.identifier_utils import quote_backtick_identifier

    return quote_backtick_identifier(identifier)


def format_mariadb_default(default_value: Any) -> str:
    """Renderiza DEFAULT MariaDB preservando expresiones conocidas."""
    raw = str(default_value)
    upper_raw = raw.upper()
    if upper_raw == "NULL":
        return "NULL"
    if upper_raw in {"CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP()"}:
        return raw
    if upper_raw.endswith("()"):
        return raw
    try:
        float(raw)
        return raw
    except ValueError:
        escaped = raw.replace("\\", "\\\\").replace("'", "''")
        return f"'{escaped}'"


def parse_mariadb_column_charset_collation_row(
    row: tuple[Any, ...], column_name: str
) -> tuple[str, str | None, str | None]:
    """Parsea fila MariaDB de charset/collation de columna."""
    charset: str | None = str(row[1]) if len(row) > 1 else None
    collation: str | None = str(row[2]) if len(row) > 2 else None
    return (column_name, charset, collation)


def parse_mariadb_db_charset(result: tuple[Any, ...]) -> dict[str, Any]:
    """Parsea charset/collation de base de datos MariaDB."""
    if not result:
        return {}
    charset: str = str(result[0])
    if len(result) > 1:
        return {"charset": charset, "collation": str(result[1])}
    return {"charset": charset}
