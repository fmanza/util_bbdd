"""Helpers puros compartidos para metadata MariaDB."""

from __future__ import annotations

from typing import Any


def quote_mariadb_identifier(identifier: str) -> str:
    """Identificador entre backticks (los backticks internos, duplicados)."""
    if not identifier:
        return "``"
    escaped = str(identifier).replace("`", "``")
    return f"`{escaped}`"


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
    # MariaDB ≥ 10.2.7 devuelve los literales ya entrecomillados ('x', 'it''s'): volver a entrecomillarlos producía
    # '''x'''. MySQL los devuelve sin comillas y siguen el camino de abajo.
    if len(raw) >= 2 and raw.startswith("'") and raw.endswith("'") and "'" not in raw[1:-1].replace("''", ""):
        return raw
    try:
        float(raw)
        return raw
    except ValueError:
        escaped = raw.replace("\\", "\\\\").replace("'", "''")
        return f"'{escaped}'"
