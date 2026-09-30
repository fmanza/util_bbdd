"""E2 (0.22.0): comentarios de vistas desde PostgreSQL y SQL Server y hacia PostgreSQL, Oracle y SQL Server.

MySQL/MariaDB no tienen comentarios de vistas: como origen no hay nada que leer y como destino el comentario queda
como ``--`` en el script, con un aviso ``COMMENT``. Los emisores se prueban en ``test_views_{postgresql,sqlserver}.py``
y ``test_emitter_oracle.py``; el recorrido completo, en ``tests/integration/test_migrate_views_e2e.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
from util_bbdd.migrate.emitters.mysql import MySQLDDLEmitter
from util_bbdd.migrate.emitters.oracle import OracleDDLEmitter
from util_bbdd.migrate.emitters.sqlserver import SQLServerDDLEmitter
from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor
from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor
from util_bbdd.migrate.ir.models import CanonicalView, MigrationPlan


def _manager(view_rows: list[tuple[Any, ...]]) -> MagicMock:
    manager = MagicMock()

    def side_effect(sql: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        if "VIEW_DEFINITION" in sql or "OBJECT_DEFINITION" in sql:
            return view_rows
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


@pytest.mark.parametrize(
    ("extractor", "definition"),
    [(PostgreSQLSchemaExtractor, "SELECT 1"), (SQLServerSchemaExtractor, "CREATE VIEW v AS SELECT 1")],
    ids=["postgresql", "sqlserver"],
)
class TestExtractors:
    def test_comment_is_read(self, extractor: Any, definition: str) -> None:
        [view] = extractor(_manager([("v", definition, " Vista ñ ")])).extract_views("s")
        assert view.comment == "Vista ñ"

    @pytest.mark.parametrize("row_tail", [(None,), ()], ids=["null", "sin-columna"])
    def test_no_comment(self, extractor: Any, definition: str, row_tail: tuple[Any, ...]) -> None:
        [view] = extractor(_manager([("v", definition, *row_tail)])).extract_views("s")
        assert view.comment == ""


@pytest.mark.parametrize("emitter", [MariaDBDDLEmitter, MySQLDDLEmitter], ids=["mariadb", "mysql"])
def test_mysql_targets_keep_the_script_comment_and_warn(emitter: Any) -> None:
    view = CanonicalView("v", "v", "s", "SELECT 1", [], "Vista\nde prueba", [])
    plan = MigrationPlan(
        tables=[],
        warnings=[],
        source_schema="s",
        source_engine="postgresql",
        target_engine="mariadb",
        emitter=emitter("utf8mb4", "utf8mb4_unicode_ci"),
        views=[view],
    )
    ddl = plan.emit_ddl()
    plan.emit_statements()  # una segunda emisión no duplica el aviso
    assert "-- COMMENT: Vista de prueba" in ddl
    assert [(w.table, w.category, w.severity) for w in plan.warnings] == [("v", "COMMENT", "WARNING")]
    assert view.warnings == plan.warnings


@pytest.mark.parametrize(
    ("emitter", "comment"),
    [
        (MariaDBDDLEmitter("utf8mb4", "utf8mb4_unicode_ci"), "Vista"),
        (MySQLDDLEmitter("utf8mb4", "utf8mb4_unicode_ci"), "Vista"),
        (OracleDDLEmitter(), "x" * 5000),  # recorte a 4000 bytes → aviso COMMENT durante la emisión
        (SQLServerDDLEmitter(), "x" * 5000),  # recorte a 3750 unidades UTF-16
    ],
    ids=["mariadb", "mysql", "oracle", "sqlserver"],
)
def test_emitting_twice_gives_the_same_script(emitter: Any, comment: str) -> None:
    """L1 (auditoría 0.22.0): el aviso de la emisión no puede añadir la nota de revisión solo en la segunda."""
    view = CanonicalView("v", "v", "s", "SELECT 1", [], comment, [])
    first = emitter.emit([], views=[view])
    assert first == emitter.emit([], views=[view])
    assert "-- NOTE: requires manual review" in first
    assert [w.category for w in view.warnings] == ["COMMENT"]


def test_view_without_comment_has_no_warning() -> None:
    view = CanonicalView("v", "v", "s", "SELECT 1", [], "", [])
    MariaDBDDLEmitter("utf8mb4", "utf8mb4_unicode_ci").emit([], views=[view])
    assert view.warnings == []
