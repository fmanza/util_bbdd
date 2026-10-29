"""PD-08 (performance-audit de dump 2026-09-25): reflexión de tablas encadenadas por FK.

``BulkCrud.reflect_table`` reflejaba también, de forma recursiva, todas las tablas referenciadas por FK (un ``MetaData``
nuevo por llamada): coste cuadrático en cadenas de FK y ``RecursionError`` con ~150 tablas encadenadas, que abortaba
el volcado entero (no es ``SQLAlchemyError``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud
from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = pytest.mark.unit

N_TABLES = 200


def _chain(engine: Engine, n: int) -> None:
    """t0 ← t1 ← … ← t{n-1}: cada tabla referencia a la anterior; una fila por tabla."""
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t0 (id INTEGER PRIMARY KEY, v TEXT)"))
        conn.execute(text("INSERT INTO t0 VALUES (1, 'x')"))
        for i in range(1, n):
            conn.execute(
                text(f"CREATE TABLE t{i} (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES t{i - 1} (id))")
            )
            conn.execute(text(f"INSERT INTO t{i} VALUES (1, 1)"))


def test_reflect_table_does_not_load_referenced_tables(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'chain.db'}")
    _chain(engine, 5)

    table = BulkCrud(engine).reflect_table("t4")

    assert set(table.metadata.tables) == {"t4"}
    assert [c.name for c in table.columns] == ["id", "parent_id"]
    assert [c.name for c in table.primary_key.columns] == ["id"]
    engine.dispose()


def test_dump_of_long_fk_chain_does_not_raise_recursion_error(tmp_path: Path) -> None:
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    dst = create_engine(f"sqlite:///{tmp_path / 'dst.db'}")
    _chain(src, N_TABLES)
    _chain(dst, N_TABLES)

    result = DumpOrchestrator(
        DumpConfig(
            source_engine=src, target_engine=dst, output_dir=tmp_path, collect_row_counts=False, truncate_target=True
        )
    ).run()

    assert len(result.table_results) == N_TABLES
    assert {r.status for r in result.table_results} == {"success"}
    src.dispose()
    dst.dispose()
