"""Vistas y routines de un ``Inspector`` por lotes (``metadata.reflection``, grupo C4 de ADR-003)."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import OperationalError

from util_bbdd._core.exceptions import MetadataIntrospectionError
from util_bbdd.comparar import SchemaComparator
from util_bbdd.metadata.model import Kind, RoutineMeta, SchemaSnapshot
from util_bbdd.metadata.reflection import catalog_source, schema_routines, view_definitions


@pytest.fixture
def engine(tmp_path: Path) -> Any:
    eng = create_engine(f"sqlite:///{(tmp_path / 'v.db').as_posix()}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE VIEW v_a AS SELECT id FROM t"))
        conn.execute(text("CREATE VIEW V_B AS SELECT id + 1 AS x FROM t"))
    yield eng
    eng.dispose()


def test_view_definitions_in_one_query_match_the_inspector(engine: Any) -> None:
    inspector = inspect(engine)
    queries: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda *a: queries.append(a[2]))
    definitions = view_definitions(inspector, None, ["v_a", "v_b", "missing"])
    assert len([q for q in queries if "'view'" in q]) == 1  # antes, una por vista (más la del schema actual)
    assert definitions["v_a"] == inspector.get_view_definition("v_a")
    assert definitions["v_b"].startswith("CREATE VIEW V_B")  # emparejado sin mayúsculas
    assert definitions["missing"] == ""


def test_without_catalog_dialect_reads_view_by_view() -> None:
    inspector = MagicMock()
    inspector.dialect.name = "otro"
    inspector.get_view_definition.side_effect = lambda name, schema=None: f"SELECT '{name}'"
    assert catalog_source(inspector) is None
    assert view_definitions(inspector, "s", ["a"]) == {"a": "SELECT 'a'"}


class _Source:
    def __init__(self, engine_name: str, routines: tuple[RoutineMeta, ...] = (), *, fail: bool = False) -> None:
        self.dialect = MagicMock()
        self.dialect.name = engine_name
        self.routines = routines
        self.fail = fail

    def snapshot(self, schema: str | None = None, *, kinds: Collection[Kind] = ()) -> SchemaSnapshot:
        if self.fail:
            raise OperationalError("SELECT", {}, Exception("sin conexión"))
        return SchemaSnapshot(self.dialect.name, schema or "", {Kind.ROUTINES: self.routines, Kind.VIEWS: ()})


def test_view_batch_failure_falls_back_to_inspector() -> None:
    inspector = MagicMock()
    inspector.get_view_definition.return_value = "SELECT 1"
    assert view_definitions(inspector, "s", ["v"], source=_Source("postgresql", fail=True)) == {"v": "SELECT 1"}  # type: ignore[arg-type]


def test_oracle_routines_without_packages_and_members() -> None:
    routines = (
        RoutineMeta("F", "FUNCTION", definition="CREATE OR REPLACE FUNCTION F ..."),
        RoutineMeta("PKG", "PACKAGE"),
        RoutineMeta("PKG.P", "PROCEDURE", signature="1"),
    )
    result = schema_routines(MagicMock(), "HR", source=_Source("oracle", routines))  # type: ignore[arg-type]
    assert [r.name for r in result or ()] == ["F"]


def test_routine_listing_failure_is_an_introspection_error() -> None:
    with pytest.raises(MetadataIntrospectionError):
        schema_routines(MagicMock(), "s", source=_Source("postgresql", fail=True))  # type: ignore[arg-type]


def test_engine_without_catalog_has_no_routines() -> None:
    inspector = MagicMock()
    inspector.dialect.name = "otro"
    assert schema_routines(inspector, "s") is None


def _inspector(dialect: str) -> MagicMock:
    inspector = MagicMock()
    inspector.engine.dialect.name = dialect
    return inspector


def test_comparator_routines_postgresql_overloads_carry_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    routines = (
        RoutineMeta("f", "FUNCTION", signature="a integer", definition="CREATE FUNCTION f(a integer)"),
        RoutineMeta("f", "FUNCTION", signature="a text", definition="CREATE FUNCTION f(a text)"),
        RoutineMeta("p", "PROCEDURE", definition=None),
    )
    monkeypatch.setattr("util_bbdd.comparar.comparator.schema_routines", lambda inspector, schema: routines)
    result = SchemaComparator._get_routines_safe(_inspector("postgresql"), "public")
    assert result == [
        {
            "name": "f(a integer)",
            "type": "FUNCTION",
            "definition": "CREATE FUNCTION f(a integer)",
            "signature": "f(a integer)",
        },
        {"name": "f(a text)", "type": "FUNCTION", "definition": "CREATE FUNCTION f(a text)", "signature": "f(a text)"},
        {"name": "p", "type": "PROCEDURE", "definition": "", "signature": "p()"},
    ]


def test_comparator_routines_other_engines_and_no_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "util_bbdd.comparar.comparator.schema_routines",
        lambda inspector, schema: (RoutineMeta("p", "PROCEDURE", definition="CREATE PROCEDURE p"),),
    )
    assert SchemaComparator._get_routines_safe(_inspector("mssql"), "dbo") == [
        {"name": "p", "type": "PROCEDURE", "definition": "CREATE PROCEDURE p"}
    ]
    monkeypatch.setattr("util_bbdd.comparar.comparator.schema_routines", lambda inspector, schema: None)
    assert SchemaComparator._get_routines_safe(_inspector("otro"), "s") is None


def test_registered_fetcher_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        SchemaComparator._ROUTINE_FETCHERS, "mydialect", lambda i, s: [{"name": "x", "type": "FUNCTION"}]
    )
    assert SchemaComparator._get_routines_safe(_inspector("mydialect"), "s") == [{"name": "x", "type": "FUNCTION"}]


def test_mssql_rows_are_matched_to_requested_names_ignoring_case() -> None:
    """D2: ``dump`` recibe nombres del usuario; una fila de ``Orders`` sirve para ``ORDERS`` si no hay ambigüedad."""
    from util_bbdd.metadata.reflection import _as_requested, _resolve_requested

    resolved = _resolve_requested(["ORDERS", "items", "dup", "DUP", "missing"], ["Orders", "items", "Dup", "other"])
    assert resolved == {"Orders": "ORDERS", "items": "items"}  # "dup"/"DUP": dos pedidos para la misma tabla
    rows = [("Orders", 1), ("items", 2), ("Dup", 3), ("other", 4)]
    assert _as_requested(rows, resolved) == [("ORDERS", 1), ("items", 2), ("Dup", 3), ("other", 4)]


def test_mssql_names_that_differ_only_in_case_are_not_guessed() -> None:
    """F4 (v0.41.3): con collation sensible a mayúsculas, ``Users`` y ``users`` son tablas distintas."""
    from util_bbdd.metadata.reflection import _resolve_requested

    existing = ["Users", "users"]
    assert _resolve_requested(["users"], existing) == {"users": "users"}
    assert _resolve_requested(["USERS"], existing) == {}  # dos candidatas: tabla a tabla (NoSuchTableError)
