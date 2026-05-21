"""Utilidades compartidas para quoting de identificadores SQL.

Funciones reutilizadas por múltiples motores que usan el mismo delimitador.
"""

from __future__ import annotations

__all__: list[str] = ["quote_backtick_identifier"]


def quote_backtick_identifier(identifier: str) -> str:
    """Escapa un identificador SQL con backticks (MySQL / MariaDB).

    Reemplaza backticks internos con doble backtick (estándar SQL).

    Args:
        identifier: Nombre de tabla, columna, schema, etc.

    Returns:
        str: Identificador escapado (ej: `table_name`, `user``name`)
    """
    if not identifier:
        return "``"
    escaped = str(identifier).replace("`", "``")
    return f"`{escaped}`"
