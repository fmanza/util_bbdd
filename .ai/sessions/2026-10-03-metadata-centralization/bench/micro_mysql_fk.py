"""Micro-benchmark MySQL/MariaDB: FK por schema (``metadata.mariadb.tables.fetch_fk_for_schema_sql``) y variantes.

Hipótesis H-MY1: el join ``KEY_COLUMN_USAGE`` ⋈ ``REFERENTIAL_CONSTRAINTS`` sin schema constante en ``rc`` ni
``TABLE_NAME`` en la condición cuesta O(FK²); fijar ``rc.CONSTRAINT_SCHEMA`` y unir también por ``TABLE_NAME`` lo evita.

    python micro_mysql_fk.py --engine mysql --volume 5000
"""

from __future__ import annotations

import argparse
import statistics
import time

from sqlalchemy import text

import md_bench

from util_bbdd.metadata.mariadb.tables import fetch_fk_for_schema_sql

SELECT = (
    "SELECT kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME, kcu.REFERENCED_TABLE_SCHEMA, kcu.REFERENCED_TABLE_NAME, "
    "kcu.REFERENCED_COLUMN_NAME, kcu.ORDINAL_POSITION, rc.DELETE_RULE, rc.UPDATE_RULE "
)
VARIANTS = {
    "actual (metadata)": fetch_fk_for_schema_sql().replace("%(schema)s", ":schema"),
    "rc.schema constante + TABLE_NAME": SELECT
    + "FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
    "ON rc.CONSTRAINT_SCHEMA = :schema AND rc.TABLE_NAME = kcu.TABLE_NAME AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
    "WHERE kcu.TABLE_SCHEMA = :schema AND kcu.REFERENCED_TABLE_NAME IS NOT NULL "
    "ORDER BY kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.ORDINAL_POSITION",
    "dos consultas sin join (kcu)": "SELECT kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME, kcu.REFERENCED_TABLE_SCHEMA, "
    "kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME, kcu.ORDINAL_POSITION FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
    "WHERE kcu.TABLE_SCHEMA = :schema AND kcu.REFERENCED_TABLE_NAME IS NOT NULL",
    "dos consultas sin join (rc)": "SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE, UPDATE_RULE "
    "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = :schema",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="mysql")
    ap.add_argument("--volume", type=int, default=5000)
    ap.add_argument("--repeat", type=int, default=3)
    a = ap.parse_args()
    schema = md_bench.schema_name(a.engine, a.volume)
    eng = md_bench.sa_engine(a.engine, a.volume)
    with eng.connect() as conn:
        for name, sql in VARIANTS.items():
            samples, n = [], 0
            for _ in range(a.repeat):
                t0 = time.perf_counter()
                n = len(conn.execute(text(sql), {"schema": schema}).all())
                samples.append(time.perf_counter() - t0)
            print(f"  {a.engine} {a.volume} {name:34} {statistics.median(samples) * 1000:9.1f} ms ({n} filas)")
    eng.dispose()


if __name__ == "__main__":
    main()
