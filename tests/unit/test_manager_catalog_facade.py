"""``get_*`` de metadatos de los managers sobre el snapshot (E2 de ADR-003).

Los managers devuelven modelos neutros leídos de ``get_schema_metadata`` (una consulta por tipo para todo el schema),
no tuplas por motor leídas con una consulta por tabla. Aquí se prueba la fachada con un ``get_schema_metadata`` falso;
la lectura real del catálogo la cubren los tests de ``metadata/`` y la caracterización de integración.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

import pytest

from util_bbdd.managers._catalog_facade import AsyncCatalogFacade, SyncCatalogFacade
from util_bbdd.metadata.model import (
    ColumnMeta,
    DatabaseMeta,
    ForeignKeyMeta,
    IndexMeta,
    Kind,
    PrimaryKeyMeta,
    RoutineKey,
    RoutineMeta,
    RoutineParameterMeta,
    SchemaSnapshot,
    TableMeta,
    UniqueMeta,
    ViewMeta,
)

_PROC = RoutineMeta("Alta", "PROCEDURE", "(integer)", definition="  CREATE PROCEDURE Alta(p integer) ...  ")
_FUNC_1 = RoutineMeta("calc", "FUNCTION", "(integer)", definition="CREATE FUNCTION calc(a integer) ...")
_FUNC_2 = RoutineMeta("calc", "FUNCTION", "(text)", definition="CREATE FUNCTION calc(a text) ...")

DATA: dict[Kind, tuple[Any, ...]] = {
    Kind.TABLES: (TableMeta("EMP", "empleados"), TableMeta("dept")),
    Kind.VIEWS: (
        ViewMeta("v_emp", " SELECT id FROM emp "),
        ViewMeta("v_full", "CREATE VIEW v_full AS SELECT 1"),
        ViewMeta("v_secret", None),
    ),
    Kind.COLUMNS: (
        ColumnMeta("EMP", "ID", 1, "integer", "integer", False),
        ColumnMeta("EMP", "DEPT_ID", 2, "integer", "integer", True),
    ),
    Kind.PRIMARY_KEYS: (PrimaryKeyMeta("EMP", "pk_emp", ("ID",)),),
    Kind.FOREIGN_KEYS: (ForeignKeyMeta("EMP", "fk_emp_dept", ("DEPT_ID",), "", "dept", ("id",)),),
    Kind.UNIQUES: (UniqueMeta("EMP", "uq_emp", ("DEPT_ID",)),),
    Kind.INDEXES: (IndexMeta("EMP", "ix_emp", ("DEPT_ID",), False),),
    Kind.ROUTINES: (_PROC, _FUNC_1, _FUNC_2),
    Kind.ROUTINE_PARAMETERS: (
        RoutineParameterMeta(_FUNC_1.key, 1, "a", "IN", "integer"),
        RoutineParameterMeta(_FUNC_2.key, 1, "a", "IN", "text"),
        RoutineParameterMeta(RoutineKey("otra", ""), 1, "x", "IN", "integer"),
    ),
    Kind.DATABASE: (DatabaseMeta("PostgreSQL 16.4", "UTF8", None),),
}


def _snapshot(kinds: Collection[Kind], data: dict[Kind, tuple[Any, ...]]) -> SchemaSnapshot:
    return SchemaSnapshot("postgresql", "public", {k: data.get(k, ()) for k in kinds})


class _SyncManager(SyncCatalogFacade):
    def __init__(self, data: dict[Kind, tuple[Any, ...]] = DATA) -> None:
        self.data = data
        self.calls: list[frozenset[Kind]] = []

    def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind]) -> SchemaSnapshot:
        self.calls.append(frozenset(kinds))
        return _snapshot(kinds, self.data)


class _AsyncManager(AsyncCatalogFacade):
    def __init__(self, data: dict[Kind, tuple[Any, ...]] = DATA) -> None:
        self.data = data

    async def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind]) -> SchemaSnapshot:
        return _snapshot(kinds, self.data)


def test_listings_return_models() -> None:
    manager = _SyncManager()
    assert manager.get_tables() == [TableMeta("EMP", "empleados"), TableMeta("dept")]
    assert [v.name for v in manager.get_views()] == ["v_emp", "v_full", "v_secret"]
    assert manager.get_routines() == [_PROC, _FUNC_1, _FUNC_2]


def test_per_table_reads_ignore_case_and_ask_only_their_kind() -> None:
    manager = _SyncManager()
    assert [c.name for c in manager.get_columns("emp")] == ["ID", "DEPT_ID"]
    assert manager.get_primary_keys("Emp") == PrimaryKeyMeta("EMP", "pk_emp", ("ID",))
    assert manager.get_foreign_keys("EMP")[0].ref_table == "dept"
    assert manager.get_unique_constraints("emp")[0].columns == ("DEPT_ID",)
    assert manager.get_indices("emp")[0].name == "ix_emp"
    assert manager.calls == [
        frozenset({Kind.COLUMNS}),
        frozenset({Kind.PRIMARY_KEYS}),
        frozenset({Kind.FOREIGN_KEYS}),
        frozenset({Kind.UNIQUES}),
        frozenset({Kind.INDEXES}),
    ]


def test_missing_table_gives_empty_results() -> None:
    manager = _SyncManager()
    assert manager.get_columns("nope") == []
    assert manager.get_primary_keys("nope") is None


@pytest.mark.parametrize(
    ("view", "expected"),
    [
        ("V_EMP", "CREATE VIEW v_emp AS\nSELECT id FROM emp"),
        ("v_full", "CREATE VIEW v_full AS SELECT 1"),
        ("v_secret", ""),
        ("nope", ""),
    ],
)
def test_view_ddl(view: str, expected: str) -> None:
    assert _SyncManager().get_view_ddl(view) == expected


def test_routine_ddl_matches_name_and_type() -> None:
    manager = _SyncManager()
    assert manager.get_routine_ddl("alta", "procedure") == "CREATE PROCEDURE Alta(p integer) ..."
    assert manager.get_routine_ddl("alta", "FUNCTION") == ""
    assert manager.get_routine_ddl("calc", "FUNCTION") == "CREATE FUNCTION calc(a integer) ..."


def test_routine_parameters_include_every_overload() -> None:
    parameters = _SyncManager().get_routine_parameters("CALC", "FUNCTION")
    assert [(p.routine.signature, p.data_type) for p in parameters] == [("(integer)", "integer"), ("(text)", "text")]


def test_database_metadata() -> None:
    manager = _SyncManager()
    assert manager.get_database_version() == "PostgreSQL 16.4"
    assert manager.get_database_charset_collation() == {"charset": "UTF8"}


def test_database_metadata_unavailable() -> None:
    manager = _SyncManager(data={})
    assert manager.get_database_metadata() is None
    assert manager.get_database_version() == "Unknown"
    assert manager.get_database_charset_collation() == {}


@pytest.mark.asyncio
async def test_async_facade_mirrors_sync() -> None:
    sync, manager = _SyncManager(), _AsyncManager()
    assert await manager.get_tables() == sync.get_tables()
    assert await manager.get_views() == sync.get_views()
    assert await manager.get_routines() == sync.get_routines()
    assert await manager.get_columns("emp") == sync.get_columns("emp")
    assert await manager.get_primary_keys("emp") == sync.get_primary_keys("emp")
    assert await manager.get_foreign_keys("emp") == sync.get_foreign_keys("emp")
    assert await manager.get_unique_constraints("emp") == sync.get_unique_constraints("emp")
    assert await manager.get_indices("emp") == sync.get_indices("emp")
    assert await manager.get_view_ddl("v_emp") == sync.get_view_ddl("v_emp")
    assert await manager.get_routine_ddl("calc", "function") == sync.get_routine_ddl("calc", "function")
    assert await manager.get_routine_parameters("calc", "FUNCTION") == sync.get_routine_parameters("calc", "FUNCTION")
    assert await manager.get_database_version() == "PostgreSQL 16.4"
    assert await manager.get_database_charset_collation() == {"charset": "UTF8"}
