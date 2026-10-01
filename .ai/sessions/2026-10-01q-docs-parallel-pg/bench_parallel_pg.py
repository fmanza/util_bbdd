"""Escalado de ParallelBulkLoader.load con la API de v0.26.0 (lotes por motor), 1 frente a 4 hilos.

Uso: python bench_parallel_pg.py <motor,...> <filas,...> [repeticiones]
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

from util_bbdd.bulk import ParallelBulkLoader  # noqa: E402

ENGINES = sys.argv[1].split(",")
SIZES = [int(x) for x in sys.argv[2].split(",")]
REPEAT = int(sys.argv[3]) if len(sys.argv) > 3 else 3

for key in ENGINES:
    engine = p.engine_for(key)
    for rows in SIZES:
        df = p.bb.make_dataframe(rows, engine.dialect.name)
        times: dict[int, list[float]] = {}
        for _ in range(REPEAT):
            for workers in (1, 4):
                table = p.fresh(engine)
                bounds = [round(i * rows / 4) for i in range(5)]
                readers = [lambda a=a, b=b: iter([df.iloc[a:b]]) for a, b in zip(bounds, bounds[1:], strict=False)]
                t0 = time.perf_counter()
                result = ParallelBulkLoader(engine, max_workers=workers).load(table.name, readers)
                times.setdefault(workers, []).append(time.perf_counter() - t0)
                assert not result.partition_errors and p.count(engine, table) == rows
        one, four = statistics.median(times[1]), statistics.median(times[4])
        print(
            json.dumps(
                {
                    "engine": key,
                    "driver": engine.url.drivername,
                    "rows": rows,
                    "1": [round(x, 2) for x in times[1]],
                    "4": [round(x, 2) for x in times[4]],
                    "speedup": round(one / four, 2),
                }
            ),
            flush=True,
        )
    p.bb.drop_table(engine, p.bb.build_table(engine.dialect.name))
    engine.dispose()
