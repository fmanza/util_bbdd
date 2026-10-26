"""Argumento ``schema`` explícito en ``DatabaseDocumentation`` y ``GraphvizRelationshipGraphExt`` (web G22, 4.1.0).

Hasta 4.0 los dos sacaban el schema del contexto del manager (``conn_params``): para documentar otro schema había que
saber qué clave usa cada motor (``schema`` o ``database``) y copiar los ``conn_params``. SQLite solo lee ``main``: con
otro schema el snapshot está vacío, lo que basta para comprobar que todas las lecturas van al schema pedido.
"""

from __future__ import annotations

import sqlite3

from pathlib import Path
from typing import Any

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.doc.infrastructure.adapters.sync_database_manager_adapter import SyncDatabaseManagerAdapter

pytestmark = pytest.mark.unit

IMPRIMIR = {"tablas": {"imprimir_tablas": True, "columnas": True, "ddl": True}}


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    path = tmp_path / "demo.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id));
        """
    )
    con.close()
    return path


@pytest.mark.parametrize(("schema", "tables"), [(None, 2), ("main", 2), ("otro", 0)])
def test_documentation_reads_the_requested_schema(
    sqlite_db: Path, tmp_path: Path, schema: str | None, tables: int
) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager,
            directorio_salida=tmp_path / "out",
            fichero_salida=Path("demo"),
            imprimir=IMPRIMIR,
            formatos=["excel"],
            schema=schema,
        ).generate()

    assert result.tables == tables


@pytest.mark.parametrize(("schema", "related"), [(None, True), ("otro", False)])
def test_graph_reads_the_requested_schema(sqlite_db: Path, schema: str | None, related: bool) -> None:
    pytest.importorskip("graphviz")
    from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt

    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        generator = GraphvizRelationshipGraphExt(manager, schema=schema)
        relations = generator.analyze_table_relations("orders")

    assert bool(relations) is related
    assert generator.schema == schema


class _RecordingManager:
    db_type = "oracle"
    database = "ORCL"
    conn_params: dict[str, Any] = {"user": "bench"}

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def get_query_context_database(self) -> str:
        return "BENCH"

    def get_schema_metadata(self, schema: str | None = None, **kwargs: Any) -> Any:
        self.calls.append(("snapshot", schema))
        return type("_Snapshot", (), {"schema": (schema or "BENCH").upper()})()

    def get_ddl(self, table_name: str, /, *, schema: str | None = None) -> str:
        self.calls.append(("ddl", schema))
        return ""

    def get_columns_charset_collation(self, table_name: str, /, *, schema: str | None = None) -> Any:
        self.calls.append(("charset", schema))
        return []

    def get_storage_rows(self, query_name: str, **params: Any) -> Any:
        self.calls.append(("storage", params.get("schema")))
        return []


def test_adapter_routes_every_read_to_the_schema() -> None:
    manager = _RecordingManager()
    adapter = SyncDatabaseManagerAdapter(manager, {}, schema="hr")  # type: ignore[arg-type]

    assert adapter.get_query_context_database() == "HR"  # normalizado por el dialecto, sin consultar
    adapter.get_schema_metadata(kinds=frozenset())
    adapter.get_ddl("T")
    adapter.get_columns_charset_collation("T")
    adapter.get_storage_rows("table_sizes")

    assert ("ddl", "hr") in manager.calls
    assert ("charset", "hr") in manager.calls
    assert ("storage", "HR") in manager.calls
    assert all(schema is not None for _, schema in manager.calls)


def test_adapter_without_schema_keeps_the_manager_context() -> None:
    manager = _RecordingManager()
    adapter = SyncDatabaseManagerAdapter(manager, {})  # type: ignore[arg-type]

    assert adapter.get_query_context_database() == "BENCH"
    adapter.get_ddl("T")
    adapter.get_storage_rows("table_sizes")

    assert manager.calls == [("ddl", None), ("storage", None)]
