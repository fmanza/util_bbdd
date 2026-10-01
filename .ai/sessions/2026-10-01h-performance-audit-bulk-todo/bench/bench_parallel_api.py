"""R-5 (AUDIT_PLAN): ParallelBulkLoader.load/update/delete (API de la Fase 2) con 1/2/4 hilos, 1M filas, repeticiones.

Uso: python bench_parallel_api.py <motor,...> [filas] [repeticiones]
"""

from __future__ import annotations

import json
import sys
import time

from pathlib import Path

import pandas as pd
import sqlalchemy as sa

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import ParallelBulkLoader  # noqa: E402

ENGINES = sys.argv[1].split(",")
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000
REPEAT = int(sys.argv[3]) if len(sys.argv) > 3 else 2
WORKERS = (1, 2, 4)


def readers(df: pd.DataFrame, workers: int) -> list:
    bounds = [round(i * len(df) / workers) for i in range(workers + 1)]
    parts = [df.iloc[bounds[i] : bounds[i + 1]] for i in range(workers)]
    return [(lambda part=part: (part.iloc[s : s + 5000] for s in range(0, len(part), 5000))) for part in parts]


for key in ENGINES:
    engine = p.engine_for(key, pool_size=8)
    dialect = engine.dialect.name
    df = p.bb.make_dataframe(ROWS, dialect)
    col_a, col_id = p.bb.physical_column("a", dialect), p.bb.physical_column("id", dialect)
    df_upd = df.copy()
    df_upd[col_a] = df_upd[col_a] + 1
    expected = int(df[col_a].sum()) + ROWS
    for rep in range(REPEAT):
        for workers in WORKERS:
            table = p.fresh(engine)
            loader = ParallelBulkLoader(engine, chunk_size=5000, max_workers=workers)
            out = {"engine": key, "workers": workers, "rep": rep, "rows": ROWS}
            t0 = time.perf_counter()
            r = loader.load(table.name, readers(df, workers))
            out["insert_s"] = round(time.perf_counter() - t0, 3)
            ok = not r.partition_errors and p.count(engine, table) == ROWS
            t0 = time.perf_counter()
            r = loader.update(table.name, readers(df_upd, workers))
            out["update_s"] = round(time.perf_counter() - t0, 3)
            ok = ok and not r.partition_errors and p.sum_a(engine, table) == expected
            t0 = time.perf_counter()
            r = loader.delete(table.name, readers(df[[col_id]], workers))
            out["delete_s"] = round(time.perf_counter() - t0, 3)
            out["ok"] = ok and not r.partition_errors and p.count(engine, table) == 0
            print(json.dumps(out), flush=True)
    p.bb.drop_table(engine, p.bb.build_table(dialect))
    engine.dispose()
