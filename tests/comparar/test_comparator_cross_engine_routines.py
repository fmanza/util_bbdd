"""Comparación entre motores (case de vistas, routines, columnas de índices y FKs) y fallos al listar routines.

Cubre los hallazgos B1, B4, B5 y B7 de la auditoría de ``comparar/`` (2026-10-02).
"""

from __future__ import annotations

import logging

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("sqlalchemy")


from util_bbdd._core.exceptions import MetadataIntrospectionError
from util_bbdd.comparar.comparator import SchemaComparator


class _FakeInspector:
    """Inspector mínimo: tablas sin columnas salvo que se indiquen, vistas y un dialect para las routines."""

    def __init__(
        self,
        *,
        tables: list[str] | None = None,
        views: dict[str, str] | None = None,
        indexes: list[dict[str, Any]] | None = None,
        fks: list[dict[str, Any]] | None = None,
        dialect: str = "sqlite",
    ) -> None:
        self._tables = tables or []
        self._views = views or {}
        self._indexes = indexes or []
        self._fks = fks or []
        self.engine = MagicMock()
        self.engine.dialect.name = dialect
        self.engine.url = None
        self.view_definition_calls: list[str] = []

    def get_table_names(self, schema: str | None = None) -> list[str]:
        return self._tables

    def get_view_names(self, schema: str | None = None) -> list[str]:
        return list(self._views)

    def get_view_definition(self, view: str, schema: str | None = None) -> str:
        self.view_definition_calls.append(view)
        return self._views[view]

    def get_columns(self, table: str, schema: str | None = None) -> list[dict[str, Any]]:
        return []

    def get_pk_constraint(self, table: str, schema: str | None = None) -> dict[str, Any]:
        return {}

    def get_indexes(self, table: str, schema: str | None = None) -> list[dict[str, Any]]:
        return self._indexes

    def get_foreign_keys(self, table: str, schema: str | None = None) -> list[dict[str, Any]]:
        return self._fks

    def get_table_comment(self, table: str, schema: str | None = None) -> dict[str, Any]:
        return {}


@pytest.fixture
def comparator() -> SchemaComparator:
    return SchemaComparator()


# ---------------------------------------------------------------------------
# B4 — case-insensitive en vistas, columnas de índices y FKs
# ---------------------------------------------------------------------------


class TestViewsCaseInsensitive:
    def test_same_view_with_different_case_is_not_added_and_removed(self, comparator: SchemaComparator) -> None:
        source = _FakeInspector(views={"V_EMP": "SELECT 1"})
        target = _FakeInspector(views={"v_emp": "select 1"})

        diff = comparator.compare(source, target, include_tables=False)

        assert diff.view_diffs == ()
        # Cada lado consulta la definición con su propio nombre
        assert source.view_definition_calls == ["V_EMP"]
        assert target.view_definition_calls == ["v_emp"]

    def test_modified_view_keeps_source_name(self, comparator: SchemaComparator) -> None:
        source = _FakeInspector(views={"V_EMP": "SELECT 1"})
        target = _FakeInspector(views={"v_emp": "SELECT 2"})

        diff = comparator.compare(source, target, include_tables=False)

        assert [(v.view_name, v.status) for v in diff.view_diffs] == [("V_EMP", "modified")]


class TestIndexAndForeignKeyColumnsCaseInsensitive:
    def test_index_columns_differing_only_in_case_are_equal(self, comparator: SchemaComparator) -> None:
        source = _FakeInspector(tables=["T"], indexes=[{"name": "IX", "column_names": ["ID"], "unique": False}])
        target = _FakeInspector(tables=["t"], indexes=[{"name": "ix", "column_names": ["id"], "unique": False}])

        diff = comparator.compare(source, target, include_views=False)

        assert diff.table_diffs == ()

    def test_index_column_change_still_detected(self, comparator: SchemaComparator) -> None:
        source = _FakeInspector(tables=["t"], indexes=[{"name": "ix", "column_names": ["ID"], "unique": False}])
        target = _FakeInspector(tables=["t"], indexes=[{"name": "ix", "column_names": ["name"], "unique": False}])

        diff = comparator.compare(source, target, include_views=False)

        idx = diff.table_diffs[0].index_diffs[0]
        assert (idx.status, idx.source_columns, idx.target_columns) == ("modified", "ID", "name")

    def test_fk_columns_and_referred_table_differing_only_in_case_are_equal(self, comparator: SchemaComparator) -> None:
        fk_src = {"name": "FK_A", "constrained_columns": ["B_ID"], "referred_table": "B", "referred_columns": ["ID"]}
        fk_tgt = {"name": "fk_a", "constrained_columns": ["b_id"], "referred_table": "b", "referred_columns": ["id"]}
        source = _FakeInspector(tables=["A"], fks=[fk_src])
        target = _FakeInspector(tables=["a"], fks=[fk_tgt])

        diff = comparator.compare(source, target, include_views=False)

        assert diff.table_diffs == ()


# ---------------------------------------------------------------------------
# B1/B5/B7 — routines: fallos al listar, sobrecargas, case y MySQL
# ---------------------------------------------------------------------------


def _routine(name: str, definition: str = "def", rtype: str = "FUNCTION", **extra: str) -> dict[str, str]:
    return {"name": name, "type": rtype, "definition": definition, **extra}


class TestRoutineComparison:
    def test_listing_failure_skips_routine_comparison(
        self, comparator: SchemaComparator, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def failing(_inspector: Any, _schema: str | None) -> list[dict[str, str]]:
            raise MetadataIntrospectionError("No se pudieron listar las routines Fake", operation="get_routines")

        monkeypatch.setitem(SchemaComparator._ROUTINE_FETCHERS, "fake_fail", failing)
        monkeypatch.setitem(SchemaComparator._ROUTINE_FETCHERS, "fake_ok", lambda _i, _s: [_routine("p1")])

        with caplog.at_level(logging.WARNING):
            diff = comparator.compare(
                _FakeInspector(dialect="fake_ok"),
                _FakeInspector(dialect="fake_fail"),
                include_tables=False,
                include_views=False,
                include_routines=True,
            )

        # Sin la omisión, "p1" saldría como añadida aunque el destino no se haya podido leer
        assert diff.routine_diffs == ()
        assert any("Se omite la comparación de routines" in r.message for r in caplog.records)

    def test_overload_matched_by_signature_when_only_one_side_has_overloads(
        self, comparator: SchemaComparator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = [_routine("f", "d1", signature="f(integer)")]
        target = [
            _routine("f(integer)", "d1", signature="f(integer)"),
            _routine("f(text)", "d2", signature="f(text)"),
        ]
        monkeypatch.setitem(SchemaComparator._ROUTINE_FETCHERS, "fake_src", lambda _i, _s: source)
        monkeypatch.setitem(SchemaComparator._ROUTINE_FETCHERS, "fake_tgt", lambda _i, _s: target)

        diff = comparator.compare(
            _FakeInspector(dialect="fake_src"),
            _FakeInspector(dialect="fake_tgt"),
            include_tables=False,
            include_views=False,
            include_routines=True,
        )

        assert [(r.routine_name, r.status) for r in diff.routine_diffs] == [("f(text)", "removed")]

    def test_signature_ignored_when_only_one_side_provides_it(
        self, comparator: SchemaComparator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A1: PostgreSQL (con signature) frente a MariaDB (sin ella) se empareja por nombre."""
        pg = [_routine("calc", "d", signature="calc(integer)")]
        maria = [_routine("calc", "d")]
        monkeypatch.setitem(SchemaComparator._ROUTINE_FETCHERS, "fake_pg", lambda _i, _s: pg)
        monkeypatch.setitem(SchemaComparator._ROUTINE_FETCHERS, "fake_maria", lambda _i, _s: maria)

        diff = comparator.compare(
            _FakeInspector(dialect="fake_pg"),
            _FakeInspector(dialect="fake_maria"),
            include_tables=False,
            include_views=False,
            include_routines=True,
        )

        assert diff.routine_diffs == ()

    def test_routine_names_compared_case_insensitive(
        self, comparator: SchemaComparator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(SchemaComparator._ROUTINE_FETCHERS, "fake_up", lambda _i, _s: [_routine("MY_PROC")])
        monkeypatch.setitem(SchemaComparator._ROUTINE_FETCHERS, "fake_low", lambda _i, _s: [_routine("my_proc")])

        diff = comparator.compare(
            _FakeInspector(dialect="fake_up"),
            _FakeInspector(dialect="fake_low"),
            include_tables=False,
            include_views=False,
            include_routines=True,
        )

        assert diff.routine_diffs == ()


class TestForeignKeyNoneAttributes:
    def test_none_referred_table_and_columns_do_not_crash(self, comparator: SchemaComparator) -> None:
        fk_none = {"name": "fk", "constrained_columns": None, "referred_table": None, "referred_columns": [None]}
        fk_full = {"name": "fk", "constrained_columns": ["a"], "referred_table": "r", "referred_columns": ["id"]}

        diff = comparator.compare(
            _FakeInspector(tables=["t"], fks=[fk_none]),
            _FakeInspector(tables=["t"], fks=[fk_full]),
            include_views=False,
        )

        fk = diff.table_diffs[0].fk_diffs[0]
        assert (fk.status, fk.source_columns, fk.source_referred_table, fk.target_referred_table) == (
            "modified",
            "",
            "",
            "r",
        )

    def test_none_attributes_in_added_fk(self, comparator: SchemaComparator) -> None:
        fk_none = {"name": "fk", "constrained_columns": None, "referred_table": None, "referred_columns": None}

        diff = comparator.compare(
            _FakeInspector(tables=["t"], fks=[fk_none]), _FakeInspector(tables=["t"]), include_views=False
        )

        fk = diff.table_diffs[0].fk_diffs[0]
        assert (fk.status, fk.source_columns, fk.source_referred_table, fk.source_referred_columns) == (
            "added",
            "",
            "",
            "",
        )


# ---------------------------------------------------------------------------
# FKs con nombre generado por el motor: se emparejan por estructura
# ---------------------------------------------------------------------------


def _fk(name: str | None, cols: list[str], ref: str = "p", ref_cols: list[str] | None = None) -> dict[str, Any]:
    return {"name": name, "constrained_columns": cols, "referred_table": ref, "referred_columns": ref_cols or ["id"]}


class TestGeneratedForeignKeyNames:
    def _fk_diffs(self, comparator: SchemaComparator, source: list[Any], target: list[Any]) -> list[tuple[str, str]]:
        diff = comparator.compare(
            _FakeInspector(tables=["t"], fks=source), _FakeInspector(tables=["t"], fks=target), include_views=False
        )
        return [(fk.fk_name, fk.status) for td in diff.table_diffs for fk in td.fk_diffs]

    @pytest.mark.parametrize(
        ("source_name", "target_name"),
        [
            ("SYS_C008123", "SYS_C009456"),  # Oracle
            ("FK__t__ref__39D3E0C8", "FK__t__ref__5B1A2C3D"),  # SQL Server
            ("t_ref_fkey", "t_ref_fkey1"),  # PostgreSQL
            ("t_ibfk_1", "t_ibfk_2"),  # MySQL/MariaDB
            ("FK__t__ref__39D3E0C8", "t_ref_fkey"),  # SQL Server frente a PostgreSQL
            (None, "SYS_C000001"),  # SQLite (anónima) frente a Oracle
        ],
    )
    def test_same_fk_with_generated_names_is_not_a_difference(
        self, comparator: SchemaComparator, source_name: str | None, target_name: str
    ) -> None:
        assert self._fk_diffs(comparator, [_fk(source_name, ["REF"])], [_fk(target_name, ["ref"])]) == []

    def test_generated_names_with_different_structure_still_differ(self, comparator: SchemaComparator) -> None:
        diffs = self._fk_diffs(comparator, [_fk("SYS_C1", ["a"])], [_fk("SYS_C2", ["b"])])

        assert diffs == [("SYS_C1", "added"), ("SYS_C2", "removed")]

    def test_user_named_fk_is_not_matched_by_structure(self, comparator: SchemaComparator) -> None:
        """Un nombre puesto por el usuario que cambia es una diferencia real (renombrado)."""
        diffs = self._fk_diffs(comparator, [_fk("fk_pedido_cliente", ["a"])], [_fk("SYS_C2", ["a"])])

        assert diffs == [("fk_pedido_cliente", "added"), ("SYS_C2", "removed")]

    def test_duplicate_structures_are_matched_one_to_one(self, comparator: SchemaComparator) -> None:
        source = [_fk("SYS_C1", ["a"]), _fk("SYS_C2", ["a"])]
        target = [_fk("SYS_C7", ["a"])]

        assert self._fk_diffs(comparator, source, target) == [("SYS_C2", "added")]


def _ix(name: str, cols: list[str], *, unique: bool = True) -> dict[str, Any]:
    return {"name": name, "column_names": cols, "unique": unique}


class TestGeneratedIndexNames:
    """Nombres reales de un UNIQUE sin nombre, tomados del banco (SQL Server 2022, Oracle 23ai, PostgreSQL 17)."""

    def _idx_diffs(self, comparator: SchemaComparator, source: list[Any], target: list[Any]) -> list[tuple[str, str]]:
        diff = comparator.compare(
            _FakeInspector(tables=["t"], indexes=source),
            _FakeInspector(tables=["t"], indexes=target),
            include_views=False,
        )
        return [(i.index_name, i.status) for td in diff.table_diffs for i in td.index_diffs]

    @pytest.mark.parametrize(
        ("source_name", "target_name"),
        [
            ("UQ__zzix6f6b__3BD0198F43553E7D", "UQ__zzix6f6b__D86D1817E4458CE6"),  # SQL Server
            ("sys_c0021957", "sys_c0034001"),  # Oracle (SQLAlchemy normaliza a minúsculas)
            ("UQ__zzix6f6b__3BD0198F43553E7D", "t_a_key"),  # SQL Server frente a PostgreSQL
        ],
    )
    def test_same_unique_index_with_generated_names_is_not_a_difference(
        self, comparator: SchemaComparator, source_name: str, target_name: str
    ) -> None:
        assert self._idx_diffs(comparator, [_ix(source_name, ["A"])], [_ix(target_name, ["a"])]) == []

    def test_uniqueness_is_part_of_the_structure(self, comparator: SchemaComparator) -> None:
        diffs = self._idx_diffs(comparator, [_ix("SYS_C1", ["a"], unique=True)], [_ix("SYS_C2", ["a"], unique=False)])

        assert diffs == [("SYS_C1", "added"), ("SYS_C2", "removed")]

    def test_user_named_index_is_not_matched_by_structure(self, comparator: SchemaComparator) -> None:
        diffs = self._idx_diffs(comparator, [_ix("uq_cliente_email", ["a"])], [_ix("SYS_C2", ["a"])])

        assert diffs == [("uq_cliente_email", "added"), ("SYS_C2", "removed")]

    def test_mysql_column_named_indexes_are_not_treated_as_generated(self, comparator: SchemaComparator) -> None:
        """MySQL/MariaDB nombran el índice como su columna: indistinguible de un nombre puesto a mano."""
        diffs = self._idx_diffs(comparator, [_ix("a", ["a"])], [_ix("a_2", ["a"])])

        assert diffs == [("a", "added"), ("a_2", "removed")]
