"""E5b: DELETE de Oracle — executemany (actual, GenericDeleteStrategy) vs una sentencia por lote con SYS.ODCINUMBERLIST."""

from __future__ import annotations

import json
import sys
import time

from pathlib import Path

import sqlalchemy as sa

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402


def main(rows: int, repeat: int) -> None:
    engine = p.engine_for("oracle")
    df = p.bb.make_dataframe(rows, "oracle")
    for variant in ("executemany", "odcinumberlist"):
        for rep in range(repeat):
            table = p.fresh(engine)
            crud = BulkCrud(engine, chunk_size=5000, warn_if_audit_disabled=False)
            crud.bulk_insert_from_df(df, table.name, generar_sql=False)
            if variant == "executemany":
                t0 = time.perf_counter()
                crud.bulk_delete_from_df(df[["id"]], table.name, generar_sql=False)
                t = time.perf_counter() - t0
            else:
                quoted = engine.dialect.identifier_preparer.format_table(table)
                t0 = time.perf_counter()
                with engine.begin() as c:
                    raw = c.connection.dbapi_connection
                    list_type = raw.gettype("SYS.ODCINUMBERLIST")
                    cur = raw.cursor()
                    for s in range(0, rows, 5000):
                        ids = list_type.newobject(df["id"].iloc[s : s + 5000].tolist())
                        cur.execute(f"DELETE FROM {quoted} WHERE id IN (SELECT column_value FROM TABLE(:ids))", ids=ids)
                    cur.close()
                t = time.perf_counter() - t0
            p.record("oracle_delete", "oracle", variant, rows, t, p.count(engine, table) == 0, rep=rep)
    p.bb.drop_table(engine, p.bb.build_table("oracle"))
    engine.dispose()
    print(json.dumps(p.RESULTS))


if __name__ == "__main__":
    for n in (10_000, 100_000, 1_000_000):
        main(n, 2)
