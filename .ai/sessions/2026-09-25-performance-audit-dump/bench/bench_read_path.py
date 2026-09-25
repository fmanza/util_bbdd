#!/usr/bin/env python3
"""Microbanco de la ruta de lectura de ``dump`` (performance-audit de dump, propuesta de ruta sin pandas).

Mide, sobre ``dump_src.order_items`` (2M filas en el volumen ``large`` de ``bench_dump_real.py``), el coste de producir
las filas listas para el INSERT por tres vías:

    pandas        pd.read_sql(chunksize) + rename + dataframe_to_sql_records   (la ruta actual de dump + bulk)
    raw           cursor DBAPI fetchmany(chunk) → tuplas                         (sin DataFrame ni dicts)
    raw_tuned     como raw, con cursor de servidor (stream_results) y, en Oracle, arraysize = chunk

Solo lee: no escribe en ninguna base. Cada vía en un subproceso para medir la memoria pico por separado.

Uso:
    python bench_read_path.py --engines postgresql,mysql,mariadb,mssql,oracle --out results_read.jsonl
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from pathlib import Path
from time import perf_counter

import pandas as pd

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench_dump_real import SRC, make_engine, peak_rss_mb  # noqa: E402

COLS = ["item_id", "order_id", "product_name", "quantity", "unit_price"]
CHUNK = 5000


def run(engine_key: str, mode: str) -> dict[str, object]:
    from util_bbdd.bulk.normalize import dataframe_to_sql_records

    tuned = mode == "raw_tuned"
    engine = make_engine(engine_key, arraysize=CHUNK if tuned else None)
    sql = f"SELECT {', '.join(COLS)} FROM {SRC}.order_items"
    rows = 0
    t0 = perf_counter()
    first_chunk_s = None
    if mode == "pandas":
        with engine.connect() as conn:
            for chunk in pd.read_sql(text(sql), conn, chunksize=CHUNK):
                if first_chunk_s is None:
                    first_chunk_s = perf_counter() - t0
                recs = dataframe_to_sql_records(chunk[COLS].rename(columns=dict(zip(COLS, COLS, strict=True))))
                rows += len(recs)
    else:
        opts = {"stream_results": True, "max_row_buffer": CHUNK} if tuned else {}
        with engine.connect().execution_options(**opts) as conn:
            result = conn.execute(text(sql))
            while batch := result.fetchmany(CHUNK):
                if first_chunk_s is None:
                    first_chunk_s = perf_counter() - t0
                data = [tuple(r) for r in batch]
                rows += len(data)
    total = perf_counter() - t0
    engine.dispose()
    return {
        "engine": engine_key,
        "mode": mode,
        "rows": rows,
        "total_s": round(total, 2),
        "first_chunk_s": round(first_chunk_s or 0, 2),
        "rows_per_s": round(rows / total),
        "peak_rss_mb": round(peak_rss_mb(), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engines", default="postgresql,mysql,mariadb,mssql,oracle")
    parser.add_argument("--modes", default="pandas,raw,raw_tuned")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--one", nargs=2, metavar=("ENGINE", "MODE"))
    args = parser.parse_args()
    if args.one:
        print(json.dumps(run(*args.one)))
        return 0
    for engine_key in args.engines.split(","):
        for mode in args.modes.split(","):
            proc = subprocess.run(
                [sys.executable, __file__, "--one", engine_key, mode], capture_output=True, text=True, check=False
            )
            line = next((ln for ln in reversed(proc.stdout.splitlines()) if ln.startswith("{")), None)
            line = line or json.dumps({"engine": engine_key, "mode": mode, "crash": proc.stderr[-800:]})
            print(line, flush=True)
            if args.out:
                with args.out.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
