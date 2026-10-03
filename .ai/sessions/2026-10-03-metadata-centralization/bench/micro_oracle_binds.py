"""Micro-benchmark Oracle (H-12): consultas del registry por tabla con literales (como hoy) frente a bind variables.

Recorre N tablas **distintas** (cada literal es un texto SQL nuevo → hard parse) y mide la misma consulta con
``:owner``/``:tabla`` (un único texto SQL → el plan se reutiliza). Mismas filas en ambos casos.

    python micro_oracle_binds.py --volume 500 --tables 30
"""

from __future__ import annotations

import argparse
import json
import re
import time

from pathlib import Path

from sqlalchemy import text

import md_bench

ROOT = Path(__file__).resolve().parents[4]
QUERIES = json.loads((ROOT / "src/util_bbdd/data/sql_queries.json").read_text(encoding="utf-8"))["oracle"]


def _as_binds(template: str) -> str:
    """``'{database}'``/``UPPER('{esquema}')``/``'{tabla}'`` → ``:owner``/``:tabla``."""
    sql = re.sub(r"'\{(database|esquema)\}'", ":owner", template)
    return re.sub(r"'\{tabla\}'", ":tabla", sql)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume", type=int, default=500)
    ap.add_argument("--tables", type=int, default=30)
    ap.add_argument("--offset", type=int, default=100)
    a = ap.parse_args()
    owner = md_bench.schema_name("oracle", a.volume)
    eng = md_bench.sa_engine("oracle", a.volume)
    names_lit = [f"T{i:05d}" for i in range(a.offset, a.offset + a.tables)]
    names_bind = [f"T{i:05d}" for i in range(a.offset + a.tables, a.offset + 2 * a.tables)]
    with eng.connect() as conn:
        for name in ("columnas_tabla", "claves_primarias", "claves_foraneas", "claves_unicas", "indices"):
            t0 = time.perf_counter()
            rows_lit = sum(
                len(conn.execute(text(QUERIES[name].format(database=owner, esquema=owner, tabla=t))).all())
                for t in names_lit
            )
            lit = (time.perf_counter() - t0) / a.tables * 1000
            sql = _as_binds(QUERIES[name])
            t0 = time.perf_counter()
            rows_bind = sum(len(conn.execute(text(sql), {"owner": owner, "tabla": t}).all()) for t in names_bind)
            bind = (time.perf_counter() - t0) / a.tables * 1000
            print(f"  {name:18} literal {lit:8.1f} ms/tabla ({rows_lit} filas)   bind {bind:8.1f} ms/tabla ({rows_bind} filas)")
    eng.dispose()


if __name__ == "__main__":
    main()
