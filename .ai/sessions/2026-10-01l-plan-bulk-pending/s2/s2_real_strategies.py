"""AUDIT_PLAN de on_error="isolate": ¿las estrategias reales de bulk se recuperan tras fallar dentro de un SAVEPOINT?

Por motor: en una transacción, SAVEPOINT → estrategia real con un lote que falla → ROLLBACK TO SAVEPOINT → la misma
estrategia con un lote bueno → COMMIT. Se verifica el estado final. Estrategias: INSERT (la resuelta por BulkCrud, por
columnas si la admite), UPDATE por staging (MySQL/MariaDB/PostgreSQL) y DELETE (la resuelta; OPENJSON en SQL Server).
"""

from __future__ import annotations

import json
import sys

from pathlib import Path
from typing import Any

import pandas as pd
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402
from util_bbdd.bulk._execution.delete_strategies import DeleteStrategyResolver  # noqa: E402
from util_bbdd.bulk._execution.staging_update import STAGING_UPDATE_DIALECTS, StagingUpdateStrategy  # noqa: E402
from util_bbdd.bulk._support.sql_helpers import SqlColumns  # noqa: E402
from util_bbdd.bulk.normalize import dataframe_to_sql_columns, dataframe_to_sql_records  # noqa: E402


def ids_of(engine: sa.Engine, tabla: sa.Table, column: str) -> list[int]:
    """Lee los ids y cierra la conexión (una conexión abierta retiene el bloqueo de metadatos en MySQL)."""
    with engine.connect() as conn:
        return sorted(r[0] for r in conn.execute(sa.select(tabla.c[column])))


def check(key: str) -> dict[str, Any]:
    engine = p.engine_for(key)
    dialect = engine.dialect.name
    n = lambda c: p.bb.physical_column(c, dialect)  # noqa: E731
    table = p.fresh(engine)
    crud = BulkCrud(engine, warn_if_audit_disabled=False)
    tabla = crud.reflect_table(table.name)
    executor = crud._batch_statement_executor
    strategy = executor.insert_strategy
    out: dict[str, Any] = {"engine": key, "insert_strategy": type(strategy).__name__}

    def frame(ids: list[int], a: int = 0) -> pd.DataFrame:
        df = p.bb.make_dataframe(len(ids), dialect)
        df[n("id")] = ids
        df[n("a")] = a
        return df

    def insert(conn: Any, df: pd.DataFrame) -> None:
        if getattr(strategy, "supports_columns", False):
            strategy.execute_columns(connection=conn, stmt=sa.insert(tabla), block=SqlColumns(*dataframe_to_sql_columns(df)))
        else:
            strategy.execute(connection=conn, stmt=sa.insert(tabla), records=dataframe_to_sql_records(df))

    # INSERT: lote con PK duplicada dentro de un SAVEPOINT, luego lote bueno
    with engine.begin() as conn:
        insert(conn, frame([1, 2]))
        sp = conn.begin_nested()
        try:
            insert(conn, frame([3, 1]))
            out["insert_error"] = "no falló"
        except sa.exc.DBAPIError as exc:
            out["insert_error"] = type(exc).__name__
            sp.rollback()
        insert(conn, frame([4, 5]))
    out["insert_ok"] = ids_of(engine, tabla, n("id")) == [1, 2, 4, 5]

    # UPDATE por staging: valor demasiado largo para s1 (String(50)) dentro de un SAVEPOINT
    if dialect in STAGING_UPDATE_DIALECTS:
        staging = StagingUpdateStrategy(table=tabla, pk_cols=[n("id")], update_cols=[n("a"), n("s1")], loader=strategy)
        stmt = sa.update(tabla)  # no se usa: staging no denegado
        with engine.begin() as conn:
            sp = conn.begin_nested()
            try:
                staging.execute(connection=conn, stmt=stmt, records=[{n("id"): 1, n("a"): 7, n("s1"): "x" * 80}])
                out["update_error"] = "no falló"
            except sa.exc.DBAPIError as exc:
                out["update_error"] = type(exc).__name__
                sp.rollback()
            staging.execute(connection=conn, stmt=stmt, records=[{n("id"): 2, n("a"): 9, n("s1"): "ok"}])
        with engine.connect() as c:
            vals = dict(c.execute(sa.select(tabla.c[n("id")], tabla.c[n("a")])).all())
        out["update_ok"] = vals.get(1) == 0 and vals.get(2) == 9

    # DELETE: estrategia resuelta; el error se provoca con una FK que referencia la fila 4
    child = sa.Table(
        f"{table.name}_child",
        sa.MetaData(),
        sa.Column("cid", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("pid", sa.Integer, sa.ForeignKey(tabla.c[n("id")])),
    )
    child.drop(engine, checkfirst=True)
    child.create(engine)
    with engine.begin() as conn:
        conn.execute(sa.insert(child), [{"cid": 1, "pid": 4}])
    delete = DeleteStrategyResolver().resolve(dialect)
    with engine.begin() as conn:
        sp = conn.begin_nested()
        try:
            delete.execute(connection=conn, table=tabla, batch_df=pd.DataFrame({n("id"): [4, 5]}), pk_cols=[n("id")])
            out["delete_error"] = "no falló"
        except sa.exc.DBAPIError as exc:
            out["delete_error"] = type(exc).__name__
            sp.rollback()
        delete.execute(connection=conn, table=tabla, batch_df=pd.DataFrame({n("id"): [5]}), pk_cols=[n("id")])
    out["delete_strategy"] = type(delete).__name__
    out["delete_ok"] = ids_of(engine, tabla, n("id")) == [1, 2, 4]
    child.drop(engine, checkfirst=True)
    p.bb.drop_table(engine, p.bb.build_table(dialect))
    engine.dispose()
    return out


for key in sys.argv[1].split(","):
    try:
        print(json.dumps(check(key)), flush=True)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"engine": key, "fallo_del_script": f"{type(exc).__name__}: {str(exc)[:200]}"}), flush=True)
