"""Q8: coste de la etapa pandas del volcado frente a una ruta con tuplas, sin escribir (origen real, datos large).

Por tabla y motor de origen mide, en CPU del proceso (una pasada completa):
  fetch   fetchmany → tuplas (suelo común a las dos rutas)
  df      + DataFrame(rows, dtype=object)              (hoy: hilo lector)
  rebatch + _rebatch a write_batch                      (hoy: hilo principal; solo si write_batch > chunk)
  records + dataframe_to_sql_records(strip_strings=False)   (hoy: hilo principal)
  tuples  alternativa sin pandas: [dict(zip(keys, row))]
"""

import sys
from time import perf_counter

import pandas as pd

sys.path.insert(0, "scripts")
import bench_dump as b  # noqa: E402

from util_bbdd.bulk.normalize import dataframe_to_sql_records  # noqa: E402
from util_bbdd.dump.orchestrator import _execute_read, _rebatch  # noqa: E402

CHUNK = 5000
engines = sys.argv[1].split(",") if len(sys.argv) > 1 else ["postgresql"]
WRITE = {"postgresql": 20_000}


def rows_iter(conn, sql):
    res = _execute_read(conn, sql, CHUNK, None)
    keys = list(res.keys())
    while rows := res.fetchmany(CHUNK):
        yield keys, rows


for key in engines:
    eng = b.make_engine(key)
    wb = WRITE.get(key, CHUNK)
    for table in b.TABLES:
        sql = f"SELECT * FROM {b.SRC}.{table}" if key != "sqlite" else f"SELECT * FROM {b.SRC}.{table}"
        t = {"fetch": 0.0, "df": 0.0, "rebatch": 0.0, "records": 0.0, "tuples": 0.0}
        n = 0
        with eng.connect() as conn:
            dfs = []
            it = rows_iter(conn, sql)
            while True:
                s = perf_counter()
                try:
                    keys, rows = next(it)
                except StopIteration:
                    t["fetch"] += perf_counter() - s
                    break
                t["fetch"] += perf_counter() - s
                n += len(rows)
                s = perf_counter()
                recs_t = [dict(zip(keys, r)) for r in rows]
                t["tuples"] += perf_counter() - s
                del recs_t
                s = perf_counter()
                dfs.append(pd.DataFrame(rows, columns=keys, dtype=object))
                t["df"] += perf_counter() - s
                if len(dfs) * CHUNK >= 200_000:  # procesar por tandas para no retener la tabla entera
                    s = perf_counter()
                    batches = list(_rebatch(iter(dfs), wb))
                    t["rebatch"] += perf_counter() - s
                    s = perf_counter()
                    for df in batches:
                        dataframe_to_sql_records(df, strip_strings=False)
                    t["records"] += perf_counter() - s
                    dfs = []
            if dfs:
                s = perf_counter()
                batches = list(_rebatch(iter(dfs), wb))
                t["rebatch"] += perf_counter() - s
                s = perf_counter()
                for df in batches:
                    dataframe_to_sql_records(df, strip_strings=False)
                t["records"] += perf_counter() - s
        pandas_cost = t["df"] + t["rebatch"] + t["records"]
        print(
            f"{key:18} {table:12} rows={n:>8} fetch={t['fetch']:6.2f} df={t['df']:5.2f} rebatch={t['rebatch']:5.2f} "
            f"records={t['records']:5.2f} | pandas={pandas_cost:5.2f} tuples={t['tuples']:5.2f} "
            f"ahorro={pandas_cost - t['tuples']:5.2f}s",
            flush=True,
        )
    eng.dispose()
