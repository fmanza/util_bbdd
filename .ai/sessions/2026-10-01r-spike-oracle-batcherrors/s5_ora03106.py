"""S-5: qué combinación da ORA-03106 con batcherrors (oracledb thin). Driver puro, sin SQLAlchemy en el envío."""

from __future__ import annotations

import itertools
import sys

from pathlib import Path

import oracledb
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))

import proto_bulk_todo as p  # noqa: E402

engine = p.engine_for("oracle")
print("oracledb", oracledb.__version__, "thin" if oracledb.is_thin_mode() else "thick")
for op, lob, bad, batcherrors in itertools.product(("insert", "update"), (100, 3999, 4001, 9000), (False, True), (False, True)):
    raw = engine.raw_connection()
    cur = raw.cursor()
    try:
        cur.execute("BEGIN EXECUTE IMMEDIATE 'DROP TABLE zz_s5_lob'; EXCEPTION WHEN OTHERS THEN NULL; END;")
        cur.execute("CREATE TABLE zz_s5_lob (id NUMBER PRIMARY KEY, s VARCHAR2(10), c CLOB)")
        cur.executemany("INSERT INTO zz_s5_lob (id, s, c) VALUES (:1, :2, :3)", [(i, "v", "x") for i in range(10)])
        raw.commit()
        cur.setinputsizes(None, None, oracledb.DB_TYPE_CLOB if lob > 4000 else None)
        rows = [(i, "u", "y" * lob) for i in range(10)]
        if bad:
            rows[4] = (4, "demasiado largo", "y" * lob)
        if op == "insert":
            rows = [(i + 100, s, c) for i, s, c in rows]
            sql = "INSERT INTO zz_s5_lob (id, s, c) VALUES (:1, :2, :3)"
        else:
            rows = [(s, c, i) for i, s, c in rows]
            sql = "UPDATE zz_s5_lob SET s = :1, c = :2 WHERE id = :3"
        try:
            cur.executemany(sql, rows, batcherrors=batcherrors)
            errs = [e.full_code for e in cur.getbatcherrors()] if batcherrors else []
            out = f"ok errores={errs}"
        except oracledb.DatabaseError as exc:
            out = f"EXC {str(exc).splitlines()[0][:70]}"
        raw.rollback()
    except Exception as exc:
        out = f"FALLO CONEXIÓN {str(exc).splitlines()[0][:60]}"
    finally:
        try:
            raw.close()
        except Exception:
            pass
    print(f"{op:6} lob={lob:5} fila_mala={bad!s:5} batcherrors={batcherrors!s:5} → {out}", flush=True)
engine.dispose()
with sa.create_engine(engine.url).begin() as c:
    c.exec_driver_sql("BEGIN EXECUTE IMMEDIATE 'DROP TABLE zz_s5_lob'; EXCEPTION WHEN OTHERS THEN NULL; END;")
