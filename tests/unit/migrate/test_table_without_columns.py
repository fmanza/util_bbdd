"""H2 (auditoría 0.21.0): una tabla sin columnas activas es un ERROR del plan y ``execute()`` no empieza.

Antes, los emisores escribían ``-- ERROR: tabla sin columnas activas`` dentro de un ``CREATE TABLE`` inválido, sin
ningún aviso en el plan: ``execute()`` lo intentaba y fallaba a mitad. Pasa si no se extrae ninguna columna (p. ej. un
desajuste de nombres en el catálogo) o si todas se omiten por tipos incompatibles (``ROWID`` de Oracle).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate import MigrationPlanner

_ID = ("ID", "NUMBER", "NO", 1, None, None, 10, 0, "")
_RID = ("RID", "ROWID", "YES", 1, None, None, None, None, "")


def _oracle_manager(columns_by_table: dict[str, list[tuple]]) -> MagicMock:
    manager = MagicMock()

    def side_effect(sql: str, params: dict) -> list:
        if "all_tables" in sql:
            return [(name, "TABLE", "") for name in columns_by_table]
        if "all_tab_columns" in sql and "all_col_comments" in sql:
            return [(name, *row) for name, rows in columns_by_table.items() for row in rows]
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


@pytest.mark.parametrize(
    ("columns", "reason"),
    [([], "sin columnas extraídas"), ([_RID], "todas omitidas (ROWID)")],
    ids=["sin-columnas", "todas-omitidas"],
)
def test_table_without_active_columns_is_an_error(columns: list[tuple], reason: str) -> None:
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
