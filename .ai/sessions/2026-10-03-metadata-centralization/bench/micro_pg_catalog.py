"""Micro-benchmark PostgreSQL: consultas por tabla de ``sql_queries.json`` frente a las de ``metadata/`` por schema.

Hipótesis H-PG1: las vistas de ``information_schema`` cuestan en función del catálogo **entero** de la base, no del
schema consultado. Se mide cada consulta por tabla del registry (columnas, PK, FK, UK, índices) y la equivalente por
schema de ``metadata.postgresql.tables``.

    python micro_pg_catalog.py --schema zz_md_50 --repeat 5
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time

from pathlib import Path

from sqlalchemy import create_engine, text

from util_bbdd.metadata.postgresql import tables as pg

ROOT = Path(__file__).resolve().parents[4]
QUERIES = json.loads((ROOT / "src/util_bbdd/data/sql_queries.json").read_text(encoding="utf-8"))["postgresql"]


def _time(conn, sql: str, params: dict | None, repeat: int) -> tuple[float, int]:
    samples, n = [], 0
    for _ in range(repeat):
        t0 = time.perf_counter()
        if "%(" in sql:  # estilo pyformat del driver (consultas *_for_schema_sql)
            n = len(conn.exec_driver_sql(sql, params or {}).all())
        else:
            n = len(conn.execute(text(sql), params or {}).all())
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples) * 1000, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default="zz_md_50")
    ap.add_argument("--table", default="t00001")
    ap.add_argument("--repeat", type=int, default=5)
    a = ap.parse_args()
    eng = create_engine(os.environ["UTIL_BBDD_BENCH_POSTGRESQL_URL"])
    params = {"database": a.schema, "esquema": a.schema, "tabla": a.table}
    with eng.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM pg_class WHERE relkind = 'r'")).scalar()
        print(f"catálogo: {total} tablas en la base; schema {a.schema}")
        for name in ("columnas_tabla", "claves_primarias", "claves_foraneas", "claves_unicas", "indices"):
            sql = QUERIES[name]
            sql = sql if isinstance(sql, str) else sql.get("sql") or sql.get("query")
            ms, n = _time(conn, sql.format(**params), None, a.repeat)
            print(f"  registry {name:18} por tabla : {ms:8.1f} ms ({n} filas)")
        for fn in ("fetch_columns_for_schema_sql", "fetch_pk_for_schema_sql", "fetch_fk_for_schema_sql",
                   "fetch_indexes_for_schema_sql"):  # fmt: skip
            sql = getattr(pg, fn)()
            bind = {k: a.schema for k in ("schema", "esquema", "owner", "database") if f":{k}" in sql or f"%({k})s" in sql}
            ms, n = _time(conn, sql, bind, a.repeat)
            print(f"  metadata {fn:32} por schema: {ms:8.1f} ms ({n} filas)")
    eng.dispose()


if __name__ == "__main__":
    main()
