"""Utilidades SQL compartidas dentro del módulo dump.

Re-exporta el quoting de identificadores de ``bulk`` (fuente única) para ``orchestrator``, ``_constraints`` e
``_indexes``.
"""

from __future__ import annotations

from ..bulk._support.sql_quoting import quote_identifier, quote_table

__all__: list[str] = ["quote_identifier", "quote_table"]
