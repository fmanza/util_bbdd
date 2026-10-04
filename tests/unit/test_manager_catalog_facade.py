"""``get_*`` de metadatos de los managers sobre el snapshot (E2 de ADR-003).

Los managers devuelven modelos neutros leídos de ``get_schema_metadata`` (una consulta por tipo para todo el schema),
no tuplas por motor leídas con una consulta por tabla. Aquí se prueba la fachada con un ``get_schema_metadata`` falso;
la lectura real del catálogo la cubren los tests de ``metadata/`` y la caracterización de integración.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

import pytest

from util_bbdd._core.exceptions import QueryNotFoundError
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


class _Executor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        self.calls.append((sql, dict(params)))
        return self.rows


class _Source:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.executor = _Executor(rows)

    def current_schema(self) -> str:
        return "public"


class _AsyncExecutor(_Executor):
    async def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:  # type: ignore[override]
        return super().fetch_all(sql, params)


class _AsyncSource:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.executor = _AsyncExecutor(rows)

    async def current_schema(self) -> str:
        return "public"


class _SyncManager(SyncCatalogFacade):
    def __init__(
        self, data: dict[Kind, tuple[Any, ...]] = DATA, db_type: str = "postgresql", rows: list[Any] | None = None
    ) -> None:
        self.data = data
        self.db_type = db_type
        self.metadata_source = _Source(rows or [])
        self.calls: list[frozenset[Kind]] = []

    def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind]) -> SchemaSnapshot:
        self.calls.append(frozenset(kinds))
        return _snapshot(kinds, self.data)


class _AsyncManager(AsyncCatalogFacade):
    def __init__(
        self, data: dict[Kind, tuple[Any, ...]] = DATA, db_type: str = "postgresql", rows: list[Any] | None = None
    ) -> None:
        self.data = data
        self.db_type = db_type
        self.metadata_source = _AsyncSource(rows or [])

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


def test_native_table_ddl_is_read_once_per_table_and_cleared_with_the_catalog() -> None:
    manager = _SyncManager(rows=[("CREATE TABLE public.emp (id integer);",)])
    assert manager.get_ddl("emp") == "CREATE TABLE public.emp (id integer);"
    assert manager.get_ddl("emp") == "CREATE TABLE public.emp (id integer);"
    ((sql, params),) = manager.metadata_source.executor.calls
    assert "quote_ident" in sql and params == {"schema": "public", "table_name": "emp"}
    manager.__dict__.pop("_table_ddl_cache")  # lo que hace _invalidate_catalog() con clear_cache()
    manager.get_ddl("emp")
    assert len(manager.metadata_source.executor.calls) == 2


def test_native_table_ddl_of_missing_table_is_empty() -> None:
    assert _SyncManager(rows=[]).get_ddl("nope") == ""


def test_mysql_table_ddl_comes_from_the_snapshot() -> None:
    manager = _SyncManager(db_type="mariadb")
    assert manager.get_ddl("emp").startswith("CREATE TABLE `emp` (\n  `ID` integer NOT NULL")
    assert manager.metadata_source.executor.calls == []


def test_columns_charset_collation_lists_columns_with_their_own_collation() -> None:
    data = DATA | {
        Kind.COLUMNS: (
            ColumnMeta("t", "a", 1, "varchar(5)", "varchar", True, collation="utf8mb4_bin"),
            ColumnMeta("t", "b", 2, "int", "int", True),
        )
    }
    assert _SyncManager(data, db_type="mysql").get_columns_charset_collation("t") == [("a", "utf8mb4", "utf8mb4_bin")]
    assert _SyncManager(data).get_columns_charset_collation("t") == [("a", None, "utf8mb4_bin")]


def test_storage_rows_and_inventory() -> None:
    manager = _SyncManager(db_type="mariadb", rows=[("db", "emp", "InnoDB", 1.0, 0.5, 1.5)])
    assert manager.get_storage_rows("ficheros_fisicos") == [("db", "emp", "InnoDB", 1.0, 0.5, 1.5)]
    assert manager.metadata_source.executor.calls[-1][1]["schema"] == "public"
    inventory = manager.get_storage_inventory()
    assert set(inventory) == {"primary", "temp_tablespaces"}
    with pytest.raises(QueryNotFoundError):
        manager.get_storage_rows("sqlite_file_summary")


def test_storage_inventory_requires_tablespace_where_needed() -> None:
    with pytest.raises(ValueError, match="tablespace"):
        _SyncManager().get_storage_inventory()
    assert _SyncManager(db_type="hsqldb").get_storage_inventory() == {"primary": []}


@pytest.mark.asyncio
async def test_async_ddl_charset_and_storage() -> None:
    manager = _AsyncManager(rows=[("CREATE TABLE x ();",)])
    assert await manager.get_ddl("x") == "CREATE TABLE x ();"
    assert await manager.get_columns_charset_collation("emp") == []
    assert await manager.get_storage_rows("temp_tablespaces") == [("CREATE TABLE x ();",)]
    assert set(await manager.get_storage_inventory("pg_default")) == {"primary", "temp_tablespaces"}
    assert (await _AsyncManager(db_type="mysql").get_ddl("emp")).startswith("CREATE TABLE `emp`")
