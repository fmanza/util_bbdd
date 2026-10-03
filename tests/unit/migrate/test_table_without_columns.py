"""H2 (auditoría 0.21.0): una tabla sin columnas activas es un ERROR del plan y ``execute()`` no empieza.

Antes, los emisores escribían ``-- ERROR: tabla sin columnas activas`` dentro de un ``CREATE TABLE`` inválido, sin
ningún aviso en el plan: ``execute()`` lo intentaba y fallaba a mitad. Pasa si no se extrae ninguna columna (p. ej. un
desajuste de nombres en el catálogo) o si todas se omiten por tipos incompatibles (``ROWID`` de Oracle).
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from util_bbdd.metadata.model import ColumnMeta
from util_bbdd.migrate import MigrationPlanner

from ._snapshot_source import col, fake_manager, table

_ID = col("", "ID", 1, "NUMBER(10)", "NUMBER", precision=10, scale=0, nullable=False)
_RID = col("", "RID", 1, "ROWID")


def _oracle_manager(columns_by_table: dict[str, list[ColumnMeta]]) -> MagicMock:
    objects: list[object] = []
    for name, columns in columns_by_table.items():
        objects += [table(name), *(replace(c, table=name) for c in columns)]
    return fake_manager("oracle", *objects)


@pytest.mark.parametrize(
    ("columns", "reason"),
    [([], "sin columnas extraídas"), ([_RID], "todas omitidas (ROWID)")],
    ids=["sin-columnas", "todas-omitidas"],
)
def test_table_without_active_columns_is_an_error(columns: list[ColumnMeta], reason: str) -> None:
    plan = MigrationPlanner(source_engine="oracle", target_engine="postgresql").plan(
        _oracle_manager({"OK": [_ID], "VACIA": columns}), "S"
    )
    errors = [w for w in plan.warnings if w.category == "TABLE" and w.severity == "ERROR"]
    assert [w.table.lower() for w in errors] == ["vacia"], reason
    target = MagicMock()
    with pytest.raises(ValueError, match="ERROR"):
        plan.execute(target)
    target.get_sqlalchemy_engine.assert_not_called()


def test_tables_with_columns_have_no_table_error() -> None:
    plan = MigrationPlanner(source_engine="oracle", target_engine="postgresql").plan(
        _oracle_manager({"OK": [_ID]}), "S"
    )
    assert not any(w.category == "TABLE" for w in plan.warnings)
