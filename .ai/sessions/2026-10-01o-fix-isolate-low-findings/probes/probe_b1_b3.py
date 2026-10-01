"""B-1: SQL Server con XACT_ABORT ON; B-3: SQLite con autocommit=True (Python >= 3.12)."""

import logging
import os
import pathlib
import sqlite3
import sys
import tempfile
import uuid

import pandas as pd

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, event, text

from util_bbdd.bulk import BulkCrud

logging.disable(logging.CRITICAL)


def run(eng, label):
    name = f"zz_probe_{uuid.uuid4().hex[:6]}"
    t = Table(name, MetaData(), Column("id", Integer, primary_key=True, autoincrement=False), Column("v", String(5)))
    t.create(eng)
    try:
        BulkCrud(eng, warn_if_audit_disabled=False).bulk_insert_from_df(pd.DataFrame({"id": [2], "v": ["x"]}), name, False)
        d = pathlib.Path(tempfile.mkdtemp())
        crud = BulkCrud(eng, chunk_size=4, on_error="isolate", rejects_csv_path=d / "r.csv", warn_if_audit_disabled=False)
        try:
            crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2, 3, 4], "v": list("abcd")}), name, False)
            outcome = "ok"
        except Exception as exc:
            ctx = exc.__context__
            outcome = f"{type(exc).__name__}: {str(exc).splitlines()[0][:150]} || contexto: {type(ctx).__name__ if ctx else None}"
        with eng.connect() as c:
            ids = [r[0] for r in c.execute(text(f"select id from {name} order by id"))]
        print(f"{label}: {outcome} | filas={ids} | rows_rejected={crud.rows_rejected}")
    finally:
        t.drop(eng, checkfirst=True)


if "mssql" in sys.argv:
    eng = create_engine(os.environ["UTIL_BBDD_TEST_MSSQL_URL"])

    @event.listens_for(eng, "connect")
    def _xact_abort(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("SET XACT_ABORT ON")
        cur.close()

    run(eng, "mssql XACT_ABORT ON")
    eng.dispose()

if "sqlite" in sys.argv:
    d = pathlib.Path(tempfile.mkdtemp())
    eng = create_engine(f"sqlite:///{d / 'a.db'}", connect_args={"autocommit": True})
    run(eng, f"sqlite autocommit=True (py {sys.version_info[:2]}, LEGACY={sqlite3.LEGACY_TRANSACTION_CONTROL})")
    # ¿queda una transacción abierta que bloquea a otra conexión?
    other = sqlite3.connect(d / "a.db", timeout=1)
    try:
        other.execute("create table zz_lock_probe (x int)")
        other.commit()
        print("sqlite autocommit=True: sin bloqueo residual")
    except Exception as exc:
        print(f"sqlite autocommit=True: bloqueo residual -> {exc}")
    eng.dispose()
