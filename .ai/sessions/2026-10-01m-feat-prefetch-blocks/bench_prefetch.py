"""R-5: BulkCrud(prefetch_blocks=True) frente a False con la API final, 1M filas, 3 repeticiones alternas.

Uso: python bench_prefetch.py <motor,...> [filas] [repeticiones]
"""

from __future__ import annotations

import json
import statistics
import sys
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402

ENGINES = sys.argv[1].split(",")
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000
REPEAT = int(sys.argv[3]) if len(sys.argv) > 3 else 3

for key in ENGINES:
    engine = p.engine_for(key)
    dialect = engine.dialect.name
    df = p.bb.make_dataframe(ROWS, dialect)
    col_a = p.bb.physical_column("a", dialect)
    df_upd = df.copy()
    df_upd[col_a] = df_upd[col_a] + 1
    times: dict[tuple[bool, str], list[float]] = {}
    for _ in range(REPEAT):
        for prefetch in (False, True):
            table = p.fresh(engine)
            crud = BulkCrud(engine, prefetch_blocks=prefetch, warn_if_audit_disabled=False)
            crud.reflect_table(table.name)
            t0 = time.perf_counter()
            crud.bulk_insert_from_df(df, table.name, generar_sql=False)
            times.setdefault((prefetch, "insert"), []).append(time.perf_counter() - t0)
            assert p.count(engine, table) == ROWS
            t0 = time.perf_counter()
            crud.bulk_update_from_df(df_upd, table.name, generar_sql=False)
            times.setdefault((prefetch, "update"), []).append(time.perf_counter() - t0)
            assert p.sum_a(engine, table) == int(df[col_a].sum()) + ROWS
    for op in ("insert", "update"):
        off, on = times[(False, op)], times[(True, op)]
        print(json.dumps({"engine": key, "op": op, "off": [round(x, 2) for x in off], "on": [round(x, 2) for x in on],
                          "cambio_pct": round(100 * (statistics.median(on) / statistics.median(off) - 1), 1),
                          "disjuntos": max(on) < min(off) or min(on) > max(off)}), flush=True)
    p.bb.drop_table(engine, p.bb.build_table(dialect))
    engine.dispose()
