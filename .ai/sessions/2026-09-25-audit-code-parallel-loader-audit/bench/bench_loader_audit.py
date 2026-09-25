"""Overhead de la auditoría dentro de ``ParallelBulkLoader`` (FASE 2 MEASURE_OVERHEAD).

Mide, en SQLite (fichero, WAL), cargas paralelas de 4 particiones con y sin ``audit_csv_path``:

- tiempo total (mediana de 3);
- tiempo pasado **dentro** de la escritura del CSV (``AuditCsvRepository.escribir_registros``, lock incluido);
- tiempo de ``BulkPersistenceManager.register_operation`` (acumular en ``_pending`` o escribir);
- nº de aperturas del CSV y de filas escritas;
- pico de memoria de ``_pending`` (tracemalloc no aísla por hilos: se estima con ``sys.getsizeof``).

Ejecutar desde la raíz del repo:  PYTHONPATH=src PYTHONIOENCODING=utf-8 python <este fichero> [--quick]
"""

from __future__ import annotations

import statistics
import sys
import tempfile
import threading

from collections.abc import Iterator
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import sqlalchemy as sa

from util_bbdd.bulk import ParallelBulkLoader
from util_bbdd.bulk._audit.repository import AuditCsvRepository
from util_bbdd.bulk._support.persistence import BulkPersistenceManager

TMP = Path(tempfile.mkdtemp(prefix="bench_loader_audit_"))
WORKERS = 4


class Probe:
    """Acumula tiempos de las funciones instrumentadas (thread-safe)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.write_s = 0.0
        self.write_calls = 0
        self.write_records = 0
        self.register_s = 0.0
        self.register_calls = 0
        self.max_pending = 0


PROBE = Probe()
_orig_write = AuditCsvRepository.escribir_registros
_orig_register = BulkPersistenceManager.register_operation


def _write(self, registros):  # type: ignore[no-untyped-def]
    t0 = perf_counter()
    try:
        return _orig_write(self, registros)
    finally:
        dt = perf_counter() - t0
        with PROBE.lock:
            PROBE.write_s += dt
            PROBE.write_calls += 1
            PROBE.write_records += len(registros)


def _register(self, **kw):  # type: ignore[no-untyped-def]
    t0 = perf_counter()
    try:
        return _orig_register(self, **kw)
    finally:
        dt = perf_counter() - t0
        with PROBE.lock:
            PROBE.register_s += dt
            PROBE.register_calls += 1
            PROBE.max_pending = max(PROBE.max_pending, len(self._pending))


AuditCsvRepository.escribir_registros = _write  # type: ignore[method-assign]
BulkPersistenceManager.register_operation = _register  # type: ignore[method-assign]


def make_engine(db: Path) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{db}", connect_args={"timeout": 120}, pool_size=WORKERS + 2)

    @sa.event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS t"))
        conn.execute(sa.text("CREATE TABLE t (id INTEGER PRIMARY KEY, a INTEGER, b TEXT, c REAL)"))
    return engine


def readers(total: int, reader_chunk: int) -> list:
    per = total // WORKERS

    def reader_for(lo: int, hi: int):  # type: ignore[no-untyped-def]
        def read() -> Iterator[pd.DataFrame]:
            for s in range(lo, hi, reader_chunk):
                e = min(s + reader_chunk, hi)
                ids = np.arange(s, e)
                yield pd.DataFrame({"id": ids, "a": ids % 97, "b": "x" * 12, "c": ids * 0.5})

        return read

    return [reader_for(i * per, (i + 1) * per) for i in range(WORKERS)]


def run(total: int, reader_chunk: int, mode: str, audit: bool, rep: int) -> dict:
    db = TMP / f"db_{total}_{reader_chunk}_{mode}_{audit}_{rep}.sqlite"
    engine = make_engine(db)
    csv_path = TMP / f"audit_{total}_{reader_chunk}_{mode}_{rep}.csv" if audit else None
    kw: dict = {"chunk_size": 5000, "max_workers": WORKERS, "audit_csv_path": csv_path}
    if mode.startswith("commit"):
        kw["commit_every_n_chunks"] = int(mode.removeprefix("commit"))
    if mode == "maint":
        kw["disable_constraints"] = True  # SQLite: sin hoist -> _load_with_maintenance (bulk_insert_from_df por chunk)
    loader = ParallelBulkLoader(engine, **kw)
    PROBE.reset()
    t0 = perf_counter()
    res = loader.load("t", readers(total, reader_chunk))
    elapsed = perf_counter() - t0
    assert not res.partition_errors, res.partition_errors
    assert res.total_rows == total
    csv_rows = sum(1 for _ in open(csv_path, encoding="utf-8")) - 1 if csv_path else 0
    engine.dispose()
    return {
        "elapsed": elapsed,
        "write_s": PROBE.write_s,
        "write_calls": PROBE.write_calls,
        "csv_rows": csv_rows,
        "register_s": PROBE.register_s,
        "register_calls": PROBE.register_calls,
        "max_pending": PROBE.max_pending,
    }


def main() -> None:
    quick = "--quick" in sys.argv
    reps = 1 if quick else 3
    scen = [
        (100_000, 5000, "atomic"),
        (100_000, 500, "atomic"),
        (1_000_000, 5000, "atomic"),
        (1_000_000, 500, "atomic"),
        (1_000_000, 500, "commit2"),
        (1_000_000, 500, "commit10"),
        (1_000_000, 500, "maint"),
    ]
    if quick:
        scen = scen[:2]
    print(f"TMP={TMP}")
    hdr = (
        "| filas | chunk lector | modo | sin audit (s) | con audit (s) | Δ E2E % | en escritura CSV (ms) | aperturas CSV "
        "| filas CSV | en register_operation (ms) | máx. _pending | % en escritura CSV |"
    )
    print(hdr)
    print("|" + "---|" * 12)
    for total, rchunk, mode in scen:
        off = [run(total, rchunk, mode, False, r)["elapsed"] for r in range(reps)]
        on_runs = [run(total, rchunk, mode, True, r) for r in range(reps)]
        on = statistics.median(r["elapsed"] for r in on_runs)
        med = sorted(on_runs, key=lambda r: r["elapsed"])[len(on_runs) // 2]
        off_m = statistics.median(off)
        inside_ms = med["write_s"] * 1e3
        reg_ms = med["register_s"] * 1e3
        # Solo la escritura: con commit_every_n_chunks register_operation puede escribir dentro (tiempos anidados).
        pct_inside = med["write_s"] / med["elapsed"] * 100
        print(
            f"| {total:,} | {rchunk} | {mode} | {off_m:.3f} | {on:.3f} | {(on - off_m) / off_m * 100:+.1f} "
            f"| {inside_ms:.2f} | {med['write_calls']} | {med['csv_rows']} | {reg_ms:.2f} | {med['max_pending']} "
            f"| {pct_inside:.3f} |"
        )
    # Tamaño de un AuditRecord (memoria de _pending)
    from util_bbdd.bulk._audit.record import AuditRecord

    r = AuditRecord("t", "SQLITE", "INSERT", 500, 0.01, False)
    size = sys.getsizeof(r) + sum(sys.getsizeof(getattr(r, f)) for f in r.__dataclass_fields__)
    print(f"\nAuditRecord ≈ {size} B (objeto + atributos, cota superior; cadenas internadas se comparten)")


if __name__ == "__main__":
    main()
