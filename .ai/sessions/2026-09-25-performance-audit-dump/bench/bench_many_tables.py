#!/usr/bin/env python3
"""Banco de coste fijo por tabla de ``DumpOrchestrator`` (performance-audit de dump, CB5/CB6).

Crea ``N`` tablas pequeñas ``zm_000 … zm_NNN`` (100 filas cada una, cada tabla con FK a la anterior e índice en la FK)
en los esquemas ``dump_src``/``dump_dst`` del banco y vuelca solo esas tablas (``DumpConfig.tables``). Con tan pocas
filas, el tiempo es casi todo coste fijo por tabla: introspección, reflexión, conteos, constraints e informe.

Uso:
    python bench_many_tables.py setup --engines postgresql,mysql,mariadb,mssql,oracle --tables 200
    python bench_many_tables.py run --engines postgresql,... --tables 200 --out results_many.jsonl [--no-counts]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from pathlib import Path
from time import perf_counter
from typing import Any

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench_dump_real as b  # noqa: E402

ROWS = 100
TOPOLOGY = os.environ.get("BENCH_MANY_TOPOLOGY", "chain")  # chain: zm_i → zm_{i-1}; star: zm_i → zm_000


def _names(n: int) -> list[str]:
    return [f"zm_{i:03d}" for i in range(n)]


def _ddl(engine_key: str, schema: str, name: str, prev: str | None) -> list[str]:
    ref_schema = "" if engine_key == "sqlite" else f"{schema}."
    fk = f" REFERENCES {ref_schema}{prev} (id)" if prev else ""
    idx_name = f"{schema}.ix_{name}" if engine_key in ("oracle", "sqlite") else f"ix_{name}"
    on = name if engine_key == "sqlite" else f"{schema}.{name}"
    cols = "ID INT PRIMARY KEY, PARENT_ID INT{fk}, VAL VARCHAR(50)" if engine_key == "mssql" else (
        "id INT PRIMARY KEY, parent_id INT{fk}, val VARCHAR(50)"
    )
    return [f"CREATE TABLE {schema}.{name} ({cols.format(fk=fk)})", f"CREATE INDEX {idx_name} ON {on} (parent_id)"]


def _drop(conn: Any, engine_key: str, schema: str, name: str) -> None:
    if engine_key == "oracle":
        n = conn.execute(
            text("SELECT COUNT(*) FROM all_tables WHERE owner = UPPER(:o) AND table_name = UPPER(:t)"),
            {"o": schema, "t": name},
        ).scalar()
        if n:
            conn.execute(text(f"DROP TABLE {schema}.{name} CASCADE CONSTRAINTS PURGE"))
    elif engine_key == "postgresql":
        conn.execute(text(f"DROP TABLE IF EXISTS {schema}.{name} CASCADE"))
    else:
        conn.execute(text(f"DROP TABLE IF EXISTS {schema}.{name}"))


def setup(engine_key: str, n: int) -> None:
    names = _names(n)
    src_key = b.SOURCE_OF.get(engine_key, engine_key)
    for key, schema, fill in ((src_key, b.SRC, True), (engine_key, b.DST, False)):
        if key == src_key and engine_key != src_key:
            continue  # sqlite: el origen es PostgreSQL, ya preparado por su propio setup
        engine = b.make_engine(key)
        with engine.begin() as conn:
            for name in reversed(names):
                _drop(conn, key, schema, name)
            prev = None
            for name in names:
                ref = prev if TOPOLOGY == "chain" or prev is None else names[0]
                for stmt in _ddl(key, schema, name, ref):
                    conn.execute(text(stmt))
                if fill:
                    conn.execute(
                        text(f"INSERT INTO {schema}.{name} (id, parent_id, val) VALUES (:i, :p, :v)"),
                        [{"i": i, "p": i if prev else None, "v": f"v{i}"} for i in range(1, ROWS + 1)],
                    )
                prev = name
        engine.dispose()
    print(f"setup {engine_key}: {n} tablas", flush=True)


def run_one(engine_key: str, n: int, counts: bool) -> dict[str, Any]:
    b.install_instrumentation(use_prefetch=False)
    from util_bbdd.dump import DumpConfig, DumpOrchestrator

    src = b.make_engine(b.SOURCE_OF.get(engine_key, engine_key))
    dst = b.make_engine(engine_key)
    cfg = DumpConfig(
        source_engine=src,
        target_engine=dst,
        source_schema=b.SRC,
        target_schema=b.DST,
        tables=_names(n),
        output_dir=Path(os.environ.get("BENCH_DUMP_REPORT_DIR", Path.cwd() / "reports")),
        collect_row_counts=counts,
    )
    t0 = perf_counter()
    orch = DumpOrchestrator(cfg)
    result = orch.run()
    total = perf_counter() - t0
    statuses: dict[str, int] = {}
    for r in result.table_results:
        statuses[r.status] = statuses.get(r.status, 0) + 1
    return {
        "engine": engine_key,
        "topology": TOPOLOGY,
        "tables": n,
        "counts": counts,
        "total_s": round(total, 2),
        "per_table_ms": round(total / n * 1000, 1),
        "statuses": statuses,
        "phases": {k: round(v, 2) for k, v in sorted(b.STATS.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["setup", "run", "one"])
    parser.add_argument("--engines", default="postgresql,mysql,mariadb,mssql,oracle,sqlite")
    parser.add_argument("--tables", type=int, default=200)
    parser.add_argument("--no-counts", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.cmd == "setup":
        for e in args.engines.split(","):
            setup(e, args.tables)
    elif args.cmd == "one":
        print(json.dumps(run_one(args.engines, args.tables, not args.no_counts)))
    else:
        for e in args.engines.split(","):
            cmd = [sys.executable, __file__, "one", "--engines", e, "--tables", str(args.tables)]
            if args.no_counts:
                cmd.append("--no-counts")
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            line = next((ln for ln in reversed(proc.stdout.splitlines()) if ln.startswith("{")), None)
            line = line or json.dumps({"engine": e, "crash": proc.stderr[-800:]})
            print(line, flush=True)
            if args.out:
                with args.out.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
