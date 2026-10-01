"""S-3: ¿dónde espera el cliente en el UPDATE paralelo fila a fila de PostgreSQL?

En E7 (performance-audit 2026-10-01h) el UPDATE por executemany con 4 hilos tardó 56,8 s frente a 25,7 s con 1, y el
servidor pasaba el 82 % de las muestras en ``ClientRead``. No era el convoy del GIL (``setswitchinterval`` sin efecto).

Método (D-1: biblioteca estándar): muestreo de las pilas de los hilos de trabajo con ``sys._current_frames()`` cada
5 ms; por cada muestra se anota la función superior de la pila y la primera función de psycopg/SQLAlchemy/util_bbdd
(dónde está el hilo dentro de la librería). Se comparan 1 y 4 hilos con el mismo muestreador. Reproduce el camino sin
``TEMP`` con ``BulkCrud(update_via_staging=False)``. Sin cambios en ``src/``.

Uso: python s3_clientread.py [filas]
"""

from __future__ import annotations

import collections
import json
import sys
import threading
import time

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402

ROWS = int(sys.argv[1]) if len(sys.argv) > 1 else 400_000
KEY = sys.argv[2] if len(sys.argv) > 2 else "postgresql"
DRIVER = sys.argv[3] if len(sys.argv) > 3 else ""  # p.ej. psycopg2: sustituye el driver de la URL
_LIB_MARKERS_EXTRA = ("pymysql", "psycopg2")
_LIB_MARKERS = ("psycopg", "pymysql", "sqlalchemy", "util_bbdd")


def describe(frame: Any) -> tuple[str, str]:
    top = f"{Path(frame.f_code.co_filename).name}:{frame.f_code.co_name}"
    lib = "-"
    f = frame
    while f is not None:
        filename = f.f_code.co_filename.replace("\\", "/")
        if any(marker in filename for marker in _LIB_MARKERS):
            lib = f"{filename.split('site-packages/')[-1].split('src/')[-1]}:{f.f_code.co_name}"
            break
        f = f.f_back
    return top, lib


def run(workers: int) -> dict[str, Any]:
    engine = p.engine_for(KEY, pool_size=8)
    if DRIVER:
        import sqlalchemy as sa

        engine = sa.create_engine(engine.url.set(drivername=f"{engine.dialect.name}+{DRIVER}"), pool_size=8)
    dialect = engine.dialect.name
    df = p.bb.make_dataframe(ROWS, dialect)
    col_a = p.bb.physical_column("a", dialect)
    table = p.fresh(engine)
    BulkCrud(engine, warn_if_audit_disabled=False).bulk_insert_from_df(df, table.name, generar_sql=False)
    df_upd = df.copy()
    df_upd[col_a] = df_upd[col_a] + 1
    bounds = [round(i * ROWS / workers) for i in range(workers + 1)]
    worker_ids: set[int] = set()
    stop = threading.Event()
    tops: collections.Counter[str] = collections.Counter()
    libs: collections.Counter[str] = collections.Counter()

    def work(part: Any) -> None:
        worker_ids.add(threading.get_ident())
        crud = BulkCrud(engine, update_via_staging=False, warn_if_audit_disabled=False)
        crud.reflect_table(table.name)
        crud.bulk_update_from_df(part, table.name, generar_sql=False)

    def sampler() -> None:
        while not stop.is_set():
            frames = sys._current_frames()
            for ident in list(worker_ids):
                frame = frames.get(ident)
                if frame is not None:
                    top, lib = describe(frame)
                    tops[top] += 1
                    libs[lib] += 1
            time.sleep(0.005)

    threads = [threading.Thread(target=work, args=(df_upd.iloc[bounds[i] : bounds[i + 1]],)) for i in range(workers)]
    sampling = threading.Thread(target=sampler, daemon=True)
    t0 = time.perf_counter()
    sampling.start()
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    elapsed = time.perf_counter() - t0
    stop.set()
    sampling.join()
    ok = p.sum_a(engine, table) == int(df[col_a].sum()) + ROWS
    p.bb.drop_table(engine, table)
    engine.dispose()
    total = sum(tops.values()) or 1
    return {
        "engine": f"{engine.dialect.name}+{engine.dialect.driver}",
        "workers": workers,
        "rows": ROWS,
        "seconds": round(elapsed, 2),
        "ok": ok,
        "samples": total,
        "top": [(name, round(100 * n / total, 1)) for name, n in tops.most_common(8)],
        "lib": [(name, round(100 * n / total, 1)) for name, n in libs.most_common(8)],
    }


if __name__ == "__main__":
    for workers in (1, 4):
        print(json.dumps(run(workers), ensure_ascii=False), flush=True)
