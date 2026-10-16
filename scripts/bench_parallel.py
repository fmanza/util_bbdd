#!/usr/bin/env python3
"""Banco de la carga paralela de ``BulkCrud`` (``ParallelOptions``) contra motores reales.

Mide ``bulk_insert_from_df`` → ``bulk_update_from_df`` → ``bulk_delete_from_df`` con 1 hilo (en serie) y con N hilos
(``ParallelOptions(mode="manual", max_workers=N)``) para validar o actualizar las reglas de ``ParallelPlanner.RULES``
(``src/util_bbdd/bulk/_execution/parallel_planner.py``). Protocolo (deuda D5, sesión 2026-10-16g):

- una tanda de calentamiento por motor y volumen, descartada;
- en cada repetición se ejecutan **todas** las configuraciones de hilos en orden alterno (1, N…, y al revés en la
  siguiente), para que la deriva del servidor (caché, checkpoints) no favorezca a ninguna;
- por configuración: mediana y rango intercuartílico (p25–p75);
- veredicto con el criterio del planificador: gana si la mediana da ≥ 1,5× **y** el p75 en paralelo es menor que el
  p25 en serie (los rangos intercuartílicos no se solapan).

Motores y URLs como ``scripts/bench_bulk.py`` (``UTIL_BBDD_BENCH_<MOTOR>_URL``; ver ``scripts/bench_env.example.sh``).
SQL Server se mide con pyodbc + ODBC Driver 18 (el driver de las reglas) aunque la URL del banco sea pymssql; con
``--mssql-driver url`` se usa la URL tal cual. **Apunta siempre a una base de datos de pruebas**: solo crea y elimina la
tabla ``zz_util_bbdd_bench``. No muestra contraseñas.

Uso:
    python scripts/bench_parallel.py --engines oracle --rows 200000,1000000 --workers 2,4 --repeat 5
    python scripts/bench_parallel.py --engines postgresql --rows 50000 --ops insert --repeat 1 --warmup 0
    python scripts/bench_parallel.py --engines mssql --out build/logs/bench_parallel.md   # solo la tabla en el fichero
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
import time

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from sqlalchemy import Engine, Table, create_engine, make_url

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_bulk  # noqa: E402  (mismo directorio: tabla, datos y URLs del banco)

from util_bbdd.bulk import AuditOptions, BulkCrud, ParallelOptions  # noqa: E402

OPS: tuple[str, ...] = ("insert", "update", "delete")
ENGINES: tuple[str, ...] = ("postgresql", "mysql", "mariadb", "mssql", "oracle", "sqlite")
#: Criterio de ParallelPlanner: aceleración mínima de la mediana para considerar que el paralelo gana.
MIN_SPEEDUP: float = 1.5

_log = logging.getLogger("bench_parallel")


# ---------------------------------------------------------------------------
# Funciones puras (testeadas en tests/unit/test_bench_parallel_script.py)
# ---------------------------------------------------------------------------


def to_pyodbc_url(url: str) -> str:
    """URL de SQL Server con pyodbc + ODBC Driver 18 (``TrustServerCertificate=yes``), conservando host y credenciales."""
    parsed = make_url(url).set(drivername="mssql+pyodbc")
    query = dict(parsed.query)
    query.setdefault("driver", "ODBC Driver 18 for SQL Server")
    query.setdefault("TrustServerCertificate", "yes")
    return parsed.set(query=query).render_as_string(hide_password=False)


def schedule(configs: Sequence[int], repeat: int) -> list[list[int]]:
    """Orden de las configuraciones de hilos en cada repetición: alterno (ABAB…, y BA… en las impares)."""
    return [list(configs) if rep % 2 == 0 else list(reversed(configs)) for rep in range(repeat)]


@dataclass(frozen=True)
class Stats:
    """Mediana y cuartiles de una serie de tiempos (segundos)."""

    median: float
    p25: float
    p75: float
    n: int

    @classmethod
    def of(cls, times: Sequence[float]) -> Stats:
        if not times:
            raise ValueError("sin tiempos")
        if len(times) == 1:
            return cls(times[0], times[0], times[0], 1)
        q1, _, q3 = statistics.quantiles(times, n=4, method="inclusive")
        return cls(statistics.median(times), q1, q3, len(times))


def verdict(serial: Stats, parallel: Stats) -> tuple[float, bool]:
    """Aceleración de la mediana y si el paralelo **gana** con el criterio del planificador (ver el docstring)."""
    speedup = serial.median / parallel.median if parallel.median > 0 else 0.0
    return speedup, speedup >= MIN_SPEEDUP and parallel.p75 < serial.p25


# ---------------------------------------------------------------------------
# Medición
# ---------------------------------------------------------------------------


@dataclass
class Series:
    """Tiempos de una configuración (motor, filas, hilos, operación)."""

    times: list[float] = field(default_factory=list)


def _crud(engine: Engine, workers: int) -> BulkCrud:
    parallel = None if workers == 1 else ParallelOptions(mode="manual", max_workers=workers)
    return BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False), parallel=parallel)


def _timed(fn: Callable[[], None]) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def run_cycle(engine: Engine, table: Table, df: pd.DataFrame, workers: int, ops: Sequence[str]) -> dict[str, float]:
    """Tabla recién creada; INSERT (si se mide o lo necesitan los demás) → UPDATE → DELETE. Devuelve los tiempos."""
    dialect = engine.dialect.name
    bench_bulk.reset_table(engine, table)
    crud = _crud(engine, workers)
    serial = _crud(engine, 1)
    pk = bench_bulk.physical_column("id", dialect)
    out: dict[str, float] = {}
    inserter = crud if "insert" in ops else serial
    elapsed = _timed(lambda: inserter.bulk_insert_from_df(df, table.name, generar_sql=False))
    if "insert" in ops:
        out["insert"] = elapsed
    if "update" in ops:
        column = bench_bulk.physical_column("a", dialect)
        updated = df.assign(**{column: df[column] + 1})
        out["update"] = _timed(lambda: crud.bulk_update_from_df(updated, table.name, generar_sql=False))
    if "delete" in ops:
        out["delete"] = _timed(lambda: crud.bulk_delete_from_df(df[[pk]], table.name, generar_sql=False))
    return out


def bench_engine(key: str, url: str, args: argparse.Namespace) -> list[str]:
    """Filas de la tabla de resultados de un motor."""
    engine = create_engine(url, pool_size=max(args.workers) + 1, max_overflow=10)
    dialect = engine.dialect.name
    table = bench_bulk.build_table(dialect)
    configs = [1, *args.workers]
    lines: list[str] = []
    try:
        for rows in args.rows:
            df = bench_bulk.make_dataframe(rows, dialect)
            for _ in range(args.warmup):
                run_cycle(engine, table, df, 1, args.ops)
            series: dict[tuple[int, str], Series] = {(w, op): Series() for w in configs for op in args.ops}
            for order in schedule(configs, args.repeat):
                for workers in order:
                    for op, seconds in run_cycle(engine, table, df, workers, args.ops).items():
                        series[(workers, op)].times.append(seconds)
            auto = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False), parallel=ParallelOptions(mode="auto"))
            for op in args.ops:
                base = Stats.of(series[(1, op)].times)
                plan = auto.parallel_plan(op, rows)  # type: ignore[arg-type]
                for workers in args.workers:
                    par = Stats.of(series[(workers, op)].times)
                    speedup, wins = verdict(base, par)
                    lines.append(
                        f"| {key} | {rows} | {op} | {base.median:.2f} ({base.p25:.2f}–{base.p75:.2f}) | {workers} | "
                        f"{par.median:.2f} ({par.p25:.2f}–{par.p75:.2f}) | {speedup:.2f}× | {'sí' if wins else 'no'} | "
                        f"{plan.workers} | {base.n} |"
                    )
                    print(lines[-1], flush=True)
    finally:
        bench_bulk.drop_table(engine, table)
        engine.dispose()
    return lines


def _csv_ints(value: str) -> list[int]:
    numbers = [int(part) for part in value.split(",") if part.strip()]
    if not numbers or any(n < 1 for n in numbers):
        raise argparse.ArgumentTypeError(f"lista de enteros ≥ 1 separados por comas, recibido: {value!r}")
    return numbers


def _csv_choice(value: str, allowed: Sequence[str]) -> list[str]:
    items = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [item for item in items if item not in allowed]
    if not items or unknown:
        raise argparse.ArgumentTypeError(f"valores no válidos: {unknown or value!r}; posibles: {', '.join(allowed)}")
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--engines", default="postgresql,mysql,mariadb,mssql,oracle", type=lambda v: _csv_choice(v, ENGINES)
    )
    parser.add_argument("--rows", default="1000000", type=_csv_ints, help="Filas por tanda (lista)")
    parser.add_argument("--workers", default="2,4", type=_csv_ints, help="Hilos a comparar con 1 (lista)")
    parser.add_argument("--ops", default=",".join(OPS), type=lambda v: _csv_choice(v, OPS))
    parser.add_argument("--repeat", type=int, default=5, help="Repeticiones medidas por configuración")
    parser.add_argument("--warmup", type=int, default=1, help="Tandas de calentamiento descartadas (en serie)")
    parser.add_argument("--mssql-driver", choices=("pyodbc", "url"), default="pyodbc")
    parser.add_argument("--out", type=Path, default=None, help="Fichero donde escribir solo la tabla de resultados")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra también los logs de util_bbdd")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repeat < 1 or args.warmup < 0:
        raise SystemExit("--repeat debe ser ≥ 1 y --warmup ≥ 0")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.verbose:
        logging.getLogger("util_bbdd").setLevel(logging.ERROR)
    header = [
        "| Motor | Filas | Operación | 1 hilo: mediana (p25–p75) s | Hilos | Paralelo: mediana (p25–p75) s | "
        "Aceleración | Gana (≥ 1,5× sin solape) | `auto` (hilos) | Repeticiones |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for line in header:
        print(line)
    table: list[str] = list(header)
    for key in args.engines:
        url = bench_bulk.resolve_engine_url(key)
        if url is None:
            _log.warning("SKIP %s: sin URL (UTIL_BBDD_BENCH_%s_URL)", key, key.upper())
            continue
        if key == "mssql" and args.mssql_driver == "pyodbc":
            url = to_pyodbc_url(url)
        table.extend(bench_engine(key, url, args))
    if args.out is not None:
        # La salida estándar lleva además los tiempos que imprime medir_tiempo (util.timing) si está instalado.
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(f"{line}\n" for line in table), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
