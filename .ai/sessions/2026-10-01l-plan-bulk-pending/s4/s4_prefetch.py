"""S-4: prefetch de bloques (preparar el N+1 mientras se escribe el N, cola de 2) frente a la vía secuencial.

Repite E3 del performance-audit (una medición: +17 % SQL Server, +9 % MySQL, +5 % MariaDB, −18 % Oracle) con 3
repeticiones, sobre el código de v0.25.1 (bloques por tamaño de operación y vía por columnas en las estrategias crudas).
Parche de instancia: los generadores privados ``__record_blocks`` y ``__sql_blocks`` de ``BulkCrud`` pasan por
``dump._source_reader._prefetch``. Sin cambios en ``src/``.

Uso: python s4_prefetch.py <motor,...> [filas] [repeticiones]
"""

from __future__ import annotations

import json
import statistics
import sys
import time

from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402
from util_bbdd.dump._source_reader import _prefetch  # noqa: E402

ENGINES = sys.argv[1].split(",")
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000
REPEAT = int(sys.argv[3]) if len(sys.argv) > 3 else 3


def with_prefetch(crud: BulkCrud, depth: int = 2) -> None:
    for name in ("_BulkCrud__record_blocks", "_BulkCrud__sql_blocks"):
        original: Callable[..., Any] = getattr(crud, name)

        def wrapped(*args: Any, _original: Callable[..., Any] = original) -> Any:
            return _prefetch(_original(*args), depth=depth)

        setattr(crud, name, wrapped)


results: list[dict[str, Any]] = []
for key in ENGINES:
    engine = p.engine_for(key)
    dialect = engine.dialect.name
    df = p.bb.make_dataframe(ROWS, dialect)
    col_a = p.bb.physical_column("a", dialect)
    df_upd = df.copy()
    df_upd[col_a] = df_upd[col_a] + 1
    times: dict[tuple[str, str], list[float]] = {}
    for rep in range(REPEAT):
        for variant in ("secuencial", "prefetch2"):  # alternas para repartir la deriva del servidor
            table = p.fresh(engine)
            crud = BulkCrud(engine, warn_if_audit_disabled=False)
            crud.reflect_table(table.name)
            if variant == "prefetch2":
                with_prefetch(crud)
            t0 = time.perf_counter()
            crud.bulk_insert_from_df(df, table.name, generar_sql=False)
            t_ins = time.perf_counter() - t0
            assert p.count(engine, table) == ROWS
            t0 = time.perf_counter()
            crud.bulk_update_from_df(df_upd, table.name, generar_sql=False)
            t_upd = time.perf_counter() - t0
            assert p.sum_a(engine, table) == int(df[col_a].sum()) + ROWS
            times.setdefault((variant, "insert"), []).append(t_ins)
            times.setdefault((variant, "update"), []).append(t_upd)
            print(json.dumps({"engine": key, "variant": variant, "rep": rep, "insert_s": round(t_ins, 3),
                              "update_s": round(t_upd, 3)}), flush=True)
    for op in ("insert", "update"):
        seq, pre = times[("secuencial", op)], times[("prefetch2", op)]
        ms, mp = statistics.median(seq), statistics.median(pre)
        results.append({"engine": key, "op": op, "secuencial": [round(x, 2) for x in seq],
                        "prefetch2": [round(x, 2) for x in pre], "cambio_pct": round(100 * (mp / ms - 1), 1),
                        "rangos_disjuntos": max(pre) < min(seq) or min(pre) > max(seq)})
    p.bb.drop_table(engine, p.bb.build_table(dialect))
    engine.dispose()
print("RESUMEN", json.dumps(results, ensure_ascii=False))
