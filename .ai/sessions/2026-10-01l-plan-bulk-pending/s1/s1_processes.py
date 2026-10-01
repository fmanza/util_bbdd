"""S-1: INSERT paralelo con procesos frente a hilos (prototipo; sin cambios en ``src/``).

S-3 mostró que el cliente de PostgreSQL (psycopg 3) está limitado por el GIL con varios hilos. ¿Escala el INSERT si cada
partición va en su propio proceso?

- Hilos: ``ParallelBulkLoader.load`` (la API actual), 1/2/4 hilos.
- Procesos: ``ProcessPoolExecutor`` (``spawn`` en Windows) con una función de nivel de módulo; cada proceso crea su engine
  desde ``UTIL_BBDD_BENCH_<MOTOR>_URL`` del entorno heredado (la contraseña no viaja por argumentos ni serializada),
  genera su partición del DataFrame determinista y la inserta con ``BulkCrud.bulk_insert_from_chunks``.
- Se mide el tiempo de pared total (incluye arrancar los procesos e importar pandas/SQLAlchemy) y el de inserción.

Uso: python s1_processes.py <motor,...> [filas]
"""

from __future__ import annotations

import json
import os
import sys
import time

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))


def _partition(key: str, rows: int, start: int, end: int, table_name: str) -> dict[str, float]:
    """Trabajo de un proceso: genera su partición e inserta. Nivel de módulo: serializable con ``spawn``."""
    t_import = time.perf_counter()
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))
    import proto_bulk_todo as p

    from util_bbdd.bulk import BulkCrud

    engine = p.engine_for(key, pool_size=2)
    part = p.bb.make_dataframe(rows, engine.dialect.name).iloc[start:end]
    ready = time.perf_counter()
    crud = BulkCrud(engine, warn_if_audit_disabled=False)
    crud.bulk_insert_from_chunks((part.iloc[s : s + 20_000] for s in range(0, len(part), 20_000)), table_name)
    done = time.perf_counter()
    engine.dispose()
    return {"setup_s": ready - t_import, "insert_s": done - ready}


def main() -> None:
    import proto_bulk_todo as p

    from util_bbdd.bulk import ParallelBulkLoader

    engines = sys.argv[1].split(",")
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000
    for key in engines:
        engine = p.engine_for(key, pool_size=8)
        df = p.bb.make_dataframe(rows, engine.dialect.name)
        for workers in (1, 2, 4):
            bounds = [round(i * rows / workers) for i in range(workers + 1)]
            # Hilos (API actual)
            table = p.fresh(engine)
            parts = [df.iloc[bounds[i] : bounds[i + 1]] for i in range(workers)]
            readers = [(lambda part=part: (part.iloc[s : s + 20_000] for s in range(0, len(part), 20_000))) for part in parts]
            t0 = time.perf_counter()
            result = ParallelBulkLoader(engine, max_workers=workers).load(table.name, readers)
            t_threads = time.perf_counter() - t0
            ok_threads = not result.partition_errors and p.count(engine, table) == rows
            # Procesos
            table = p.fresh(engine)
            t0 = time.perf_counter()
            with ProcessPoolExecutor(max_workers=workers) as pool:
                stats = list(
                    pool.map(
                        _partition,
                        [key] * workers,
                        [rows] * workers,
                        bounds[:-1],
                        bounds[1:],
                        [table.name] * workers,
                    )
                )
            t_procs = time.perf_counter() - t0
            ok_procs = p.count(engine, table) == rows
            print(
                json.dumps(
                    {
                        "engine": key,
                        "workers": workers,
                        "threads_s": round(t_threads, 2),
                        "threads_ok": ok_threads,
                        "processes_wall_s": round(t_procs, 2),
                        "processes_insert_max_s": round(max(s["insert_s"] for s in stats), 2),
                        "processes_setup_max_s": round(max(s["setup_s"] for s in stats), 2),
                        "processes_ok": ok_procs,
                    }
                ),
                flush=True,
            )
        p.bb.drop_table(engine, p.bb.build_table(engine.dialect.name))
        engine.dispose()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
