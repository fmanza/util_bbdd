"""1.4: DELETE SQL Server con PK compuesta — estrategia anterior (executemany por fila) vs OPENJSON … WITH (implementada)."""

from __future__ import annotations

import json
import os
import sys
import time

import pandas as pd
import sqlalchemy as sa

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.batch import MSSQLOpenJsonDeleteStrategy, SqlBasedDeleteStrategy

ROWS = [int(x) for x in sys.argv[1:]] or [10_000, 100_000, 1_000_000]
engine = sa.create_engine(os.environ["UTIL_BBDD_BENCH_MSSQL_URL"])
BulkCrud(engine, warn_if_audit_disabled=False)  # fast_executemany como la librería
results = []
for rows in ROWS:
    df = pd.DataFrame({"a": [i // 10 for i in range(rows)], "b": [i % 10 for i in range(rows)]})
    for name, strategy in (("anterior", SqlBasedDeleteStrategy()), ("openjson", MSSQLOpenJsonDeleteStrategy())):
        for rep in range(2 if rows >= 1_000_000 else 3):
            table = sa.Table(
                "zz_util_bbdd_bench_pk2", sa.MetaData(),
                sa.Column("a", sa.Integer, primary_key=True, autoincrement=False),
                sa.Column("b", sa.Integer, primary_key=True, autoincrement=False),
            )
            table.drop(engine, checkfirst=True)
            table.create(engine)
            BulkCrud(engine, warn_if_audit_disabled=False).bulk_insert_from_df(df, table.name, False)
            t0 = time.perf_counter()
            with engine.begin() as conn:
                for start in range(0, rows, 5000):
                    strategy.execute(connection=conn, table=table, batch_df=df.iloc[start : start + 5000], pk_cols=["a", "b"])
            elapsed = time.perf_counter() - t0
            with engine.connect() as conn:
                left = conn.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()
            results.append({"rows": rows, "variant": name, "rep": rep, "seconds": round(elapsed, 3), "ok": left == 0})
            print(json.dumps(results[-1]), flush=True)
            table.drop(engine, checkfirst=True)
engine.dispose()
