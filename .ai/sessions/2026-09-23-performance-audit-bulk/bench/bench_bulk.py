"""Benchmark por fases de util_bbdd.bulk sobre SQLite (coste Python agnóstico de motor)."""

from __future__ import annotations

import gc
import sys
import tempfile
import tracemalloc

from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from sqlalchemy import create_engine, text

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk.normalize import normalize_records_for_sql

DDL = """
CREATE TABLE t (
  id INTEGER PRIMARY KEY, a INTEGER, b INTEGER, c INTEGER,
  f1 REAL, f2 REAL, s1 TEXT, s2 TEXT, s3 TEXT, d TIMESTAMP
)
"""


def make_df(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    f2 = rng.random(n)
    f2[::7] = np.nan
    s3 = np.array([f" val {i} " for i in range(n)], dtype=object)
    s3[::11] = None
    return pd.DataFrame(
        {
            "id": np.arange(1, n + 1),
            "a": rng.integers(0, 1000, n),
            "b": rng.integers(0, 1000, n),
            "c": rng.integers(0, 1000, n),
            "f1": rng.random(n),
            "f2": f2,
            "s1": [f"name_{i}" for i in range(n)],
            "s2": ["x" * 20] * n,
            "s3": s3,
            "d": pd.date_range("2026-01-01", periods=n, freq="s"),
        }
    )


def vectorized_records(df: pd.DataFrame) -> list[dict]:
    """Prototipo: normalización por columna + to_dict (misma semántica que normalize_sql_literal)."""
    out = {}
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_datetime64_any_dtype(s.dtype):
            arr = np.array(s.dt.to_pydatetime(), dtype=object)
            arr[s.isna().to_numpy()] = None
            out[col] = arr
        elif pd.api.types.is_bool_dtype(s.dtype) or pd.api.types.is_integer_dtype(s.dtype) and not s.hasnans:
            out[col] = s.to_numpy().tolist()
        elif pd.api.types.is_float_dtype(s.dtype):
            arr = s.to_numpy(dtype=object)
            arr[s.isna().to_numpy()] = None
            out[col] = arr.tolist()
        else:  # object / str: fallback celda a celda (strip, bytes, json...)
            from util_bbdd.bulk.normalize import normalize_sql_literal

            out[col] = [normalize_sql_literal(v) for v in s.to_numpy(dtype=object)]
    cols = list(out)
    return [dict(zip(cols, row)) for row in zip(*(out[c] for c in cols))]


def t(fn, *a, **k):
    gc.collect()
    s = perf_counter()
    r = fn(*a, **k)
    return perf_counter() - s, r


def main(sizes: list[int]) -> None:
    tmp = Path(tempfile.mkdtemp())
    print(f"python {sys.version.split()[0]} pandas {pd.__version__}")
    hdr = "n;copy;to_dict;normalize;vect_records;insert_total;insert_exec_only;update_total;delete_total"
    print(hdr)
    for n in sizes:
        df = make_df(n)
        tc, _ = t(df.copy)
        td, recs = t(df.to_dict, orient="records")
        tn, norm = t(normalize_records_for_sql, recs)
        tv, vect = t(vectorized_records, df)
        # equivalencia del prototipo
        assert len(norm) == len(vect)
        for i in (0, 7, 11, n - 1):
            if i < n:
                assert norm[i] == vect[i], (norm[i], vect[i])
        del recs, norm, vect

        db = tmp / f"b{n}.db"
        eng = create_engine(f"sqlite:///{db}")
        with eng.begin() as c:
            c.execute(text(DDL))
        bc = BulkCrud(eng, chunk_size=5000)
        ti, _ = t(bc.bulk_insert_from_df, df, "t", generar_sql=False)
        # exec-only: reinsert into fresh table with pre-normalized records
        with eng.begin() as c:
            c.execute(text("DELETE FROM t"))
        from sqlalchemy import insert

        tab = bc.reflect_table("t")
        recs2 = normalize_records_for_sql(df.to_dict(orient="records"))
        te, _ = t(bc._batch_statement_executor.execute, records=recs2, stmt=insert(tab))
        del recs2
        dfu = df.copy()
        dfu["a"] = dfu["a"] + 1
        tu, _ = t(bc.bulk_update_from_df, dfu, "t", generar_sql=False)
        tdl, _ = t(bc.bulk_delete_from_df, df[["id"]], "t", generar_sql=False)
        eng.dispose()
        print(f"{n};{tc:.3f};{td:.3f};{tn:.3f};{tv:.3f};{ti:.3f};{te:.3f};{tu:.3f};{tdl:.3f}", flush=True)

    # generación SQL (por fila) — 10K
    n = 10_000
    df = make_df(n)
    eng = create_engine(f"sqlite:///{tmp / 'g.db'}")
    with eng.begin() as c:
        c.execute(text(DDL))
    bc = BulkCrud(eng)
    tg, _ = t(bc.bulk_insert_from_df, df, "t", generar_sql=True, path_sql=tmp)
    tgu, _ = t(bc.bulk_update_from_df, df, "t", generar_sql=True, path_sql=tmp)
    print(f"generar_sql INSERT 10K: {tg:.2f}s ({tg / n * 1e6:.0f} us/fila); UPDATE 10K: {tgu:.2f}s")

    # memoria pico 100K insert
    n = 100_000
    df = make_df(n)
    eng = create_engine(f"sqlite:///{tmp / 'm.db'}")
    with eng.begin() as c:
        c.execute(text(DDL))
    bc = BulkCrud(eng)
    base = df.memory_usage(deep=True).sum()
    tracemalloc.start()
    bc.bulk_insert_from_df(df, "t", generar_sql=False)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"mem 100K: df={base / 1e6:.1f}MB pico_traced={peak / 1e6:.1f}MB ratio={peak / base:.1f}x")


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]] or [1_000, 10_000, 100_000])
