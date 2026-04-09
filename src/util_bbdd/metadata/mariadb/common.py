"""Helpers puros compartidos para metadata MariaDB."""

from __future__ import annotations

from typing import Any


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
    safe_identifier = str(identifier).replace("`", "``")
    return f"`{safe_identifier}`"


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
