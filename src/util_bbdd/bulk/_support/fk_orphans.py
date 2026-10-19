"""Comprobación de filas huérfanas de una FK tras cargar con las FK desactivadas (común a bulk y dump).

Una consulta ``NOT EXISTS`` por FK que devuelve la primera fila de la tabla hija sin fila referenciada (con
``MATCH SIMPLE``: una columna de la FK a ``NULL`` exime a la fila). La usan ``BulkCrud.maintenance_scope``
(PostgreSQL siempre, H-01; MariaDB/MySQL con ``validate_fks_after``, v3.3.0) y ``dump.ConstraintManager``
(``DumpConfig.validate_fks_after``, MariaDB/MySQL).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def orphan_check_sql(dialect: str, prep: Any, child: str, fk: Mapping[str, Any]) -> str | None:
    """SQL de la primera fila huérfana de ``fk`` en ``child`` (ya citada); ``None`` si la FK está mal formada.

    Args:
        dialect: Nombre del dialecto (límite de filas: ``LIMIT``, ``TOP`` o ``FETCH FIRST``).
        prep: ``identifier_preparer`` del dialecto.
        child: Tabla hija citada.
        fk: ``constrained_columns``, ``referred_schema``, ``referred_table`` y ``referred_columns`` (como
            ``Inspector.get_foreign_keys``).
    """
    child_cols: Sequence[str] = fk.get("constrained_columns") or []
    parent_cols: Sequence[str] = fk.get("referred_columns") or []
    parent_table: str = fk.get("referred_table") or ""
    if not child_cols or not parent_cols or not parent_table or len(child_cols) != len(parent_cols):
        return None
    not_null = " AND ".join(f"c.{prep.quote(col)} IS NOT NULL" for col in child_cols)
    match = " AND ".join(
        f"p.{prep.quote(pc)} = c.{prep.quote(cc)}" for cc, pc in zip(child_cols, parent_cols, strict=True)
    )
    parent_schema: str | None = fk.get("referred_schema")
    parent = (
        f"{prep.quote_identifier(parent_schema)}.{prep.quote_identifier(parent_table)}"
        if parent_schema
        else prep.quote_identifier(parent_table)
    )
    body = f"FROM {child} c WHERE {not_null} AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE {match})"
    if dialect == "mssql":
        return f"SELECT TOP 1 1 {body}"
    if dialect == "oracle":
        return f"SELECT 1 {body} FETCH FIRST 1 ROWS ONLY"
    return f"SELECT 1 {body} LIMIT 1"


__all__: list[str] = ["orphan_check_sql"]
