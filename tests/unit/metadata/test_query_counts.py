"""Las consultas de catálogo de cada flujo no crecen con el número de tablas (ADR-003, guarda contra N+1).

Cada test ejecuta un flujo sobre un schema SQLite con 10 y con 100 tablas (PK, UK, FK a la tabla anterior, índice) y
cuenta las sentencias de catálogo en los dos caminos de ejecución de la librería: ``SyncQueryExecutor`` (managers,
driver nativo), ``DbapiCatalogExecutor`` (lectura por lotes de los managers) y los eventos de SQLAlchemy (``Inspector``, ``comparar``, ``dump``, ``bulk``).

Excepción registrada en ADR-003: con SQLite, SQLAlchemy refleja cada tabla con ``PRAGMA`` y ``sqlite_master`` por
nombre (en proceso, sin red). ``comparar`` (``Inspector``) y ``dump`` (cada ``Table`` que carga) la usan; en esos flujos
se descuenta esa reflexión y el resto no puede crecer. La lectura por lotes de los servidores la cubren
``tests/integration/test_comparar_prefetch_engines.py`` y el banco (``scripts/bench_metadata.py``).
"""

from __future__ import annotations

import logging
import re

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine

from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.metadata.source import DbapiCatalogExecutor

CATALOG_RE = re.compile(
    r"information_schema|sqlite_(master|schema|temp_master)|\bpragma|\bpg_|\bsys\.|\ball_[a-z_]+\b",
    re.IGNORECASE,
)


# Reflexión de SQLAlchemy de una tabla SQLite (``SQLiteDialect.get_columns``/``get_indexes``/``get_foreign_keys``…)
SQLITE_TABLE_REFLECTION_RE = re.compile(
    r"\bpragma\s+(main\.)?\"?(table_x?info|index_list|index_info|index_xinfo|foreign_key_list)\b|"
    r"\bfrom\s+\(?\s*select\b.*\bsqlite_(master|temp_master|schema)\b|\bsqlite_(master|temp_master|schema)\b.*\bname\s*=",
    re.IGNORECASE | re.DOTALL,
)


class _Counter:
    def __init__(self) -> None:
        self.catalog = 0
        self.sqlite_reflection = 0

    def record(self, sql: str) -> None:
        if CATALOG_RE.search(sql or ""):
            self.catalog += 1
            if SQLITE_TABLE_REFLECTION_RE.search(sql):
                self.sqlite_reflection += 1


@pytest.fixture
def counter(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Counter]:
    c = _Counter()
    original = SyncQueryExecutor._execute_sql_with_optional_params

    def wrapped(cursor: Any, sql: str, params: Any) -> None:
        c.record(str(sql))
        return original(cursor, sql, params)

    monkeypatch.setattr(SyncQueryExecutor, "_execute_sql_with_optional_params", staticmethod(wrapped))

    # Lectura por lotes de los managers (get_schema_metadata → ManagerCatalogExecutor → DbapiCatalogExecutor)
    original_fetch = DbapiCatalogExecutor.fetch_all

    def fetch_all(executor: Any, sql: str, params: Any) -> Any:
        c.record(sql)
        return original_fetch(executor, sql, params)

    monkeypatch.setattr(DbapiCatalogExecutor, "fetch_all", fetch_all)

    def on_execute(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        c.record(statement)

    event.listen(Engine, "before_cursor_execute", on_execute)
    try:
        yield c
    finally:
        event.remove(Engine, "before_cursor_execute", on_execute)


def _build(path: Path, n: int) -> Path:
    eng = create_engine(f"sqlite:///{path.as_posix()}")
    with eng.begin() as conn:
        for i in range(n):
            fk = f", parent_id INTEGER REFERENCES t{i - 1:03d}(id)" if i else ", parent_id INTEGER"
            conn.execute(
                text(f"CREATE TABLE t{i:03d} (id INTEGER PRIMARY KEY, code VARCHAR(20) UNIQUE, name TEXT{fk})")
            )
            conn.execute(text(f"CREATE INDEX ix_t{i:03d}_name ON t{i:03d}(name)"))
        conn.execute(text("CREATE VIEW v000 AS SELECT id, code FROM t000"))
    eng.dispose()
    return path


def _manager(db: Path) -> Any:
    from util_bbdd import SyncDatabaseManager

    return SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False)


def _manager_scan(db: Path) -> None:
    with _manager(db) as mgr:
        for table_meta in mgr.get_tables():
            table = table_meta.name
            mgr.get_columns(table)
            mgr.get_indices(table)
            mgr.get_primary_keys(table)
            mgr.get_foreign_keys(table)
            mgr.get_unique_constraints(table)


def _analysis(db: Path) -> None:
    from util_bbdd.analysis.base import DatabaseRelationshipGraphBase

    with _manager(db) as mgr:
        DatabaseRelationshipGraphBase(mgr).analyze_table_relations("t000")


def _doc(db: Path) -> None:
    from util_bbdd.doc import DatabaseDocumentation

    with _manager(db) as mgr:
        DatabaseDocumentation(
            db_manager=mgr,
            directorio_salida=db.parent / "doc",
            fichero_salida=Path("doc"),
            imprimir={
                "tablas": {
                    "imprimir_tablas": True,
                    "columnas": True,
                    "pk": True,
                    "fk": True,
                    "unicas": True,
                    "indices": True,
                },
                "grafo": {"enabled": False},
            },  # fmt: skip
            formatos=["html"],
        ).generate()


def _comparar(db: Path) -> None:
    from util_bbdd.comparar import SchemaComparator

    eng = create_engine(f"sqlite:///{db.as_posix()}")
    try:
        SchemaComparator().compare(inspect(eng), inspect(eng))
    finally:
        eng.dispose()


def _dump(db: Path) -> None:
    from util_bbdd.dump import DumpConfig, DumpOrchestrator

    src = create_engine(f"sqlite:///{db.as_posix()}")
    dst = create_engine(f"sqlite:///{db.as_posix()}")
    try:
        DumpOrchestrator(DumpConfig(source_engine=src, target_engine=dst, output_dir=db.parent / "dump")).run()
    finally:
        src.dispose()
        dst.dispose()


def _bulk(db: Path) -> None:
    from util_bbdd.bulk import BulkCrud

    eng = create_engine(f"sqlite:///{db.as_posix()}")
    try:
        df = pd.DataFrame({"id": [1, 2], "code": ["a", "b"], "name": ["x", "y"], "parent_id": [None, None]})
        BulkCrud(eng, warn_if_audit_disabled=False).bulk_insert_from_df(df, "t000", generar_sql=False)
    finally:
        eng.dispose()


def _snapshot(db: Path) -> None:
    from util_bbdd.metadata import CatalogSource

    eng = create_engine(f"sqlite:///{db.as_posix()}")
    try:
        CatalogSource.from_engine(eng).snapshot()
    finally:
        eng.dispose()


FLOWS: list[Any] = [
    pytest.param(_manager_scan, False, id="manager_scan"),  # E2: get_* tipados sobre el snapshot
    pytest.param(_analysis, False, id="analysis"),  # C2: índice de relaciones desde el snapshot
    pytest.param(_doc, False, id="doc"),  # D1: catálogo por lotes (CatalogRows)
    # C4 + H-29 / D2: por lotes en los servidores; con SQLite, SQLAlchemy refleja cada tabla (excepción de ADR-003)
    pytest.param(_comparar, True, id="comparar"),
    pytest.param(_dump, True, id="dump"),
    pytest.param(_bulk, False, id="bulk"),
    pytest.param(_snapshot, False, id="snapshot"),  # lectura por lotes (ADR-003): la referencia
]


@pytest.mark.parametrize(("flow", "sqlite_reflection"), FLOWS)
def test_catalog_queries_do_not_grow_with_tables(
    flow: Callable[[Path], None],
    sqlite_reflection: bool,
    counter: _Counter,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    (tmp_path / "small").mkdir()
    (tmp_path / "large").mkdir()
    small = _build(tmp_path / "small" / "db.sqlite", 10)
    large = _build(tmp_path / "large" / "db.sqlite", 100)

    counter.catalog = counter.sqlite_reflection = 0
    flow(small)
    with_10 = counter.catalog - (counter.sqlite_reflection if sqlite_reflection else 0)
    counter.catalog = counter.sqlite_reflection = 0
    flow(large)
    with_100 = counter.catalog - (counter.sqlite_reflection if sqlite_reflection else 0)

    assert with_10 > 0, "el flujo no leyó el catálogo: el contador no está viendo sus consultas"
    assert with_100 <= with_10, f"consultas de catálogo: {with_10} con 10 tablas, {with_100} con 100"
