"""Banco de overhead de AuditManager (FASE 2 MEASURE_OVERHEAD).

A) Micro: coste por llamada de AuditManager.registrar_operacion (logging por defecto y con INFO a fichero).
B) Contención: 8 hilos escribiendo al mismo CSV.
C) E2E SQLite: bulk_insert_from_df y bulk_insert_from_chunks con/sin auditoría (1K/100K/1M, 3 reps, mediana).
D) Memoria: pico tracemalloc de registrar_operacion x10k y del CSV leído.
"""

from __future__ import annotations

import logging
import statistics
import sys
import tempfile
import threading
import tracemalloc

from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import sqlalchemy as sa

from util_bbdd.bulk import AuditManager, BulkCrud

TMP = Path(tempfile.mkdtemp(prefix="bench_audit_"))


def micro(n: int, label: str) -> float:
    csv_path = TMP / f"micro_{label}.csv"
    mgr = AuditManager(csv_path)
    for _ in range(200):  # warmup
        mgr.registrar_operacion("t", "SQLITE", "INSERT", 5000, 0.1)
    samples = []
    for _ in range(3):
        t0 = perf_counter()
        for _ in range(n):
            mgr.registrar_operacion("t", "SQLITE", "INSERT", 5000, 0.1)
        samples.append((perf_counter() - t0) / n * 1e6)
    return statistics.median(samples)


def contention(threads: int, per_thread: int) -> float:
    csv_path = TMP / "contention.csv"
    mgrs = [AuditManager(csv_path) for _ in range(threads)]

    def work(m: AuditManager) -> None:
        for _ in range(per_thread):
            m.registrar_operacion("t", "SQLITE", "INSERT", 5000, 0.1)

    ts = [threading.Thread(target=work, args=(m,)) for m in mgrs]
    t0 = perf_counter()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    total = threads * per_thread
    lines = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1
    assert lines == total, (lines, total)
    return (perf_counter() - t0) / total * 1e6


def make_df(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "id": np.arange(n, dtype=np.int64),
            "a": rng.integers(0, 1_000_000, n),
            "f": rng.random(n),
            "s": [f"txt{i % 1000}" for i in range(n)],
        }
    )


def e2e(n: int, audit: bool, mode: str, chunk: int = 5000, reps: int = 3) -> float:
    df = make_df(n)
    samples = []
    for r in range(reps):
        db = TMP / f"e2e_{n}_{audit}_{mode}_{r}.db"
        eng = sa.create_engine(f"sqlite:///{db}")
        with eng.begin() as c:
            c.exec_driver_sql("CREATE TABLE t (id BIGINT PRIMARY KEY, a BIGINT, f FLOAT, s VARCHAR(20))")
        crud = BulkCrud(eng, chunk_size=chunk, audit_csv_path=(TMP / f"e2e_{r}_{mode}.csv") if audit else None)
        t0 = perf_counter()
        if mode == "df":
            crud.bulk_insert_from_df(df, "t", generar_sql=False)
        else:
            crud.bulk_insert_from_chunks((df.iloc[i : i + chunk] for i in range(0, n, chunk)), "t")
        samples.append(perf_counter() - t0)
        eng.dispose()
    return statistics.median(samples)


def memory() -> tuple[float, float]:
    csv_path = TMP / "mem.csv"
    mgr = AuditManager(csv_path)
    tracemalloc.start()
    for _ in range(10_000):
        mgr.registrar_operacion("t", "SQLITE", "INSERT", 5000, 0.1)
    _, peak_write = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    tracemalloc.start()
    mgr.leer_auditoria()
    _, peak_read = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak_write / 1024, peak_read / 1024 / 1024


if __name__ == "__main__":
    part = sys.argv[1] if len(sys.argv) > 1 else "all"
    logging.basicConfig(level=logging.WARNING)  # como una app que no configura logging
    if part in ("micro", "all"):
        print(f"A1 micro (root WARNING, sin handler de INFO): {micro(5000, 'warn'):.1f} us/llamada")
        fh = logging.FileHandler(TMP / "app.log", encoding="utf-8")
        logging.getLogger().addHandler(fh)
        logging.getLogger().setLevel(logging.INFO)
        print(f"A2 micro (root INFO + FileHandler):        {micro(5000, 'info'):.1f} us/llamada")
        logging.getLogger().removeHandler(fh)
        logging.getLogger().setLevel(logging.WARNING)
        disabled = AuditManager(None)
        t0 = perf_counter()
        for _ in range(5000):
            disabled.registrar_operacion("t", "SQLITE", "INSERT", 5000, 0.1)
        print(f"A3 micro (audit_csv_path=None):             {(perf_counter() - t0) / 5000 * 1e6:.1f} us/llamada")
    if part in ("contention", "all"):
        print(f"B  contención 8 hilos x 1000:              {contention(8, 1000):.1f} us/llamada (efectivo)")
    if part in ("memory", "all"):
        w, r = memory()
        print(f"D  memoria: pico escritura x10k = {w:.1f} KiB ; pico lectura 10k filas = {r:.2f} MiB")
    if part in ("e2e", "all"):
        logging.disable(logging.CRITICAL)  # sin ruido de log en el E2E: medimos el I/O de auditoría
        sizes = [1_000, 100_000, 1_000_000]
        print("C  E2E SQLite (mediana de 3, s)")
        print("modo | n | chunk | sin audit | con audit | delta % | filas CSV")
        for mode, chunk in (("df", 5000), ("chunks", 5000), ("chunks", 500)):
            for n in sizes:
                if chunk == 500 and n == 1_000_000:
                    continue
                reps = 1 if n == 1_000_000 else 3
                a = e2e(n, False, mode, chunk, reps)
                b = e2e(n, True, mode, chunk, reps)
                rows = 1 if mode == "df" else -(-n // chunk)
                print(f"{mode} | {n} | {chunk} | {a:.3f} | {b:.3f} | {(b - a) / a * 100:+.1f} | {rows}")
