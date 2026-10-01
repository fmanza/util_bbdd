"""Reproduce el ok=false de MySQL con 2 hilos (R-5): UPDATE y DELETE paralelos, captura partition_errors."""

from __future__ import annotations

import json
import sys

from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader  # noqa: E402

KEY = sys.argv[1] if len(sys.argv) > 1 else "mysql"
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 200_000
CYCLES = int(sys.argv[3]) if len(sys.argv) > 3 else 10
WORKERS = int(sys.argv[4]) if len(sys.argv) > 4 else 2



def readers(df, workers):  # noqa: ANN001, ANN201  (copia de bench_parallel_api: importarlo ejecutaría su banco)
    bounds = [round(i * len(df) / workers) for i in range(workers + 1)]
    parts = [df.iloc[bounds[i] : bounds[i + 1]] for i in range(workers)]
    return [(lambda part=part: (part.iloc[s : s + 5000] for s in range(0, len(part), 5000))) for part in parts]


engine = p.engine_for(KEY, pool_size=8)
dialect = engine.dialect.name
df = p.bb.make_dataframe(ROWS, dialect)
col_a, col_id = p.bb.physical_column("a", dialect), p.bb.physical_column("id", dialect)
df_upd = df.copy()
df_upd[col_a] = df_upd[col_a] + 1
for cycle in range(CYCLES):
    table = p.fresh(engine)
    BulkCrud(engine, warn_if_audit_disabled=False).bulk_insert_from_df(df, table.name, False)
    loader = ParallelBulkLoader(engine, chunk_size=5000, max_workers=WORKERS)
    upd = loader.update(table.name, readers(df_upd, WORKERS))
    dele = loader.delete(table.name, readers(df[[col_id]], WORKERS))
    print(json.dumps({"engine": KEY, "workers": WORKERS, "cycle": cycle,
                      "update_retries": sum(r.retries for r in upd.partition_results),
                      "delete_retries": sum(r.retries for r in dele.partition_results), "update_errors": [e[:300] for e in upd.partition_errors],
                      "delete_errors": [e[:300] for e in dele.partition_errors], "left": p.count(engine, table)}),
          flush=True)
p.bb.drop_table(engine, p.bb.build_table(dialect))
engine.dispose()
