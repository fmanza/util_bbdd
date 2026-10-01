"""R-9: coste de BulkCrud(on_error="isolate") con la API final, INSERT de 1M filas.

Variantes por motor (orden alterno, ``REPEAT`` repeticiones): ``raise`` sin errores, ``isolate`` sin errores e
``isolate`` con 10 PK ya existentes repartidas por la entrada (10 filas rechazadas).

Uso: python bench_isolate.py <motor,...> [filas] [repeticiones]
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402

ENGINES = sys.argv[1].split(",")
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000
REPEAT = int(sys.argv[3]) if len(sys.argv) > 3 else 2
BAD = 10

for key in ENGINES:
    engine = p.engine_for(key)
    dialect = engine.dialect.name
    df = p.bb.make_dataframe(ROWS, dialect)
    bad_positions = [ROWS * (i + 1) // (BAD + 1) for i in range(BAD)]
    times: dict[str, list[float]] = {}
    for _ in range(REPEAT):
        for variant in ("raise", "isolate", "isolate_10"):
            table = p.fresh(engine)
            with tempfile.TemporaryDirectory() as tmp:
                if variant == "isolate_10":
                    BulkCrud(engine, warn_if_audit_disabled=False).bulk_insert_from_df(
                        df.iloc[bad_positions], table.name, generar_sql=False
                    )
                kwargs = {} if variant == "raise" else {"on_error": "isolate", "rejects_csv_path": Path(tmp) / "r.csv"}
                crud = BulkCrud(engine, warn_if_audit_disabled=False, **kwargs)
                crud.reflect_table(table.name)
                t0 = time.perf_counter()
                crud.bulk_insert_from_df(df, table.name, generar_sql=False)
                times.setdefault(variant, []).append(time.perf_counter() - t0)
                assert p.count(engine, table) == ROWS
                assert crud.rows_rejected == (BAD if variant == "isolate_10" else 0)
    base = statistics.median(times["raise"])
    print(
        json.dumps(
            {
                "engine": key,
                **{v: [round(x, 2) for x in t] for v, t in times.items()},
                "isolate_x": round(statistics.median(times["isolate"]) / base, 3),
                "isolate_10_x": round(statistics.median(times["isolate_10"]) / base, 3),
            }
        ),
        flush=True,
    )
    p.bb.drop_table(engine, p.bb.build_table(dialect))
    engine.dispose()
