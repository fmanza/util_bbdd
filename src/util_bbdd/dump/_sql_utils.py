"""Utilidades SQL compartidas dentro del módulo dump.

Funciones de quoting de identificadores usadas por ``orchestrator``
y ``_constraints`` para evitar duplicación.
"""

from __future__ import annotations

from sqlalchemy import Engine


def quote_identifier(name: str, engine: Engine) -> str:
    """Devuelve el identificador ``name`` entrecomillado según el dialecto del engine."""
    return engine.dialect.identifier_preparer.quote(name)


def quote_table(table: str, schema: str | None, engine: Engine) -> str:
    """Devuelve ``table`` entrecomillado con prefijo de schema opcional."""
    if schema:
        return f"{quote_identifier(schema, engine)}.{quote_identifier(table, engine)}"
    return quote_identifier(table, engine)
