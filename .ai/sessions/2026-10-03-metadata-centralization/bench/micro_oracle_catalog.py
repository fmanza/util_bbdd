"""Micro-benchmark Oracle: registry por tabla frente a consultas por owner (``ALL_*``) y frente a ``USER_*``.

Hipótesis H-ORA1: con owner = usuario conectado, ``USER_*`` es más barato que ``ALL_*`` filtrado por ``OWNER`` (no
evalúa privilegios sobre objetos de otros esquemas). Se conecta como el usuario del volumen (``ZZ_MD_<N>``).

    python micro_oracle_catalog.py --volume 500 --repeat 3
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

from pathlib import Path

from sqlalchemy import create_engine, text

import md_bench

from util_bbdd.metadata.oracle import tables as ora

ROOT = Path(__file__).resolve().parents[4]
QUERIES = json.loads((ROOT / "src/util_bbdd/data/sql_queries.json").read_text(encoding="utf-8"))["oracle"]

COLS = "table_name, column_name, data_type, data_length, data_precision, data_scale, nullable, column_id"
USER_VS_ALL = {
    "columnas": (
        f"SELECT {COLS} FROM all_tab_columns WHERE owner = :owner ORDER BY table_name, column_id",
        f"SELECT {COLS} FROM user_tab_columns ORDER BY table_name, column_id",
    ),
    "constraints+cols": (
        "SELECT c.table_name, c.constraint_name, c.constraint_type, cc.column_name, cc.position FROM all_constraints c "
        "JOIN all_cons_columns cc ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name "
        "WHERE c.owner = :owner AND c.constraint_type IN ('P','U','R')",
        "SELECT c.table_name, c.constraint_name, c.constraint_type, cc.column_name, cc.position FROM user_constraints c "
        "JOIN user_cons_columns cc ON cc.constraint_name = c.constraint_name WHERE c.constraint_type IN ('P','U','R')",
    ),
    "indices": (
        "SELECT i.table_name, i.index_name, i.uniqueness, ic.column_name, ic.column_position FROM all_indexes i "
        "JOIN all_ind_columns ic ON ic.index_owner = i.owner AND ic.index_name = i.index_name WHERE i.table_owner = :owner",
        "SELECT i.table_name, i.index_name, i.uniqueness, ic.column_name, ic.column_position FROM user_indexes i "
        "JOIN user_ind_columns ic ON ic.index_name = i.index_name",
    ),
}


def _time(conn, sql: str, params: dict, repeat: int) -> tuple[float, int]:
    samples, n = [], 0
    for _ in range(repeat):
        t0 = time.perf_counter()
        n = len(conn.execute(text(sql), params).all())
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples) * 1000, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume", type=int, default=500)
    ap.add_argument("--table", default="T00001")
    ap.add_argument("--repeat", type=int, default=3)
    a = ap.parse_args()
    owner = md_bench.schema_name("oracle", a.volume)
    eng = create_engine(md_bench.sa_url("oracle", a.volume))
    fmt = {"database": owner, "esquema": owner, "tabla": a.table}
    with eng.connect() as conn:
        print(f"owner {owner}")
        for name in ("columnas_tabla", "claves_primarias", "claves_foraneas", "claves_unicas", "indices"):
            ms, n = _time(conn, QUERIES[name].format(**fmt), {}, a.repeat)
            print(f"  registry {name:18} por tabla : {ms:8.1f} ms ({n} filas)")
        for fn in ("fetch_columns_for_schema_sql", "fetch_pk_for_schema_sql", "fetch_fk_for_schema_sql",
                   "fetch_indexes_for_schema_sql"):  # fmt: skip
            ms, n = _time(conn, getattr(ora, fn)(), {"owner": owner}, a.repeat)
            print(f"  metadata {fn:32} por owner: {ms:8.1f} ms ({n} filas)")
        for name, (all_sql, user_sql) in USER_VS_ALL.items():
            ms_all, n_all = _time(conn, all_sql, {"owner": owner}, a.repeat)
            ms_user, n_user = _time(conn, user_sql, {}, a.repeat)
            print(f"  {name:18} ALL_* {ms_all:8.1f} ms ({n_all})  USER_* {ms_user:8.1f} ms ({n_user})")
    eng.dispose()


if __name__ == "__main__":
    main()
