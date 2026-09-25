#!/usr/bin/env python3
"""Banco de pruebas de la generación de ficheros SQL de ``util_bbdd.bulk`` (``generar_sql=True``), sin servidor.

Mide por dialecto y operación las tres etapas del camino ``generar_sql=True`` sobre el dataset de ``bench_bulk.py``:

    normalización   DataFrame → bloque por columnas (``dataframe_to_sql_columns``; DELETE usa ``to_dict``, como
                    ``BulkCrud``)
    render          registros → líneas SQL (``generate_insert_sql`` / ``generate_update_sql`` / ``generate_delete_sql``)
    escritura       líneas → fichero (``BulkPersistenceManager.persist_sql``)

en bloques de ``--chunk-size`` filas, como ``BulkCrud``. Los dialectos se crean con ``create_engine(url).dialect`` (no
conecta); un dialecto cuyo driver no está instalado se salta con un aviso. Con ``--e2e`` mide además la API pública
(``bulk_*_from_df(..., generar_sql=True)``) con SQLite en un fichero temporal.

Salida: tabla en consola (mediana de ``--repeat`` repeticiones) y, con ``--out``, un CSV con una fila por medición.
Hallazgos: .ai/audit/audit_report_bulk_sql_serialization_20260925.md (P-30 a P-36).

Uso:
    python scripts/bench_sqlgen.py                                  # 100K filas, 5 dialectos, 3 repeticiones
    python scripts/bench_sqlgen.py --rows 10000 --dialects sqlite,postgresql --repeat 1
    python scripts/bench_sqlgen.py --rows 1000000 --e2e --repeat 1 --out bench_results/sqlgen.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import statistics
import sys
import tempfile

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from bench_bulk import build_table, make_dataframe, physical_name
from sqlalchemy import Table, create_engine, insert

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._support.persistence import BulkPersistenceManager
from util_bbdd.bulk._support.sql_helpers import (
    SqlColumns,
    generate_delete_sql,
    generate_insert_sql,
    generate_update_sql,
    restore_binary_values,
)
from util_bbdd.bulk.normalize import dataframe_to_sql_columns

DIALECT_URLS: dict[str, str] = {
    "sqlite": "sqlite://",
    "postgresql": "postgresql+psycopg2://",
    "mysql": "mysql+pymysql://",
    "oracle": "oracle+oracledb://",
    "mssql": "mssql+pyodbc://",
}
OPS: tuple[str, ...] = ("insert", "update", "delete")

_log = logging.getLogger("bench_sqlgen")


@dataclass
class Measurement:
    """Una repetición de una operación en un dialecto (tiempos en segundos)."""

    dialect: str
    op: str
    rows: int
    repeat: int
    normalize_s: float
    render_s: float
    write_s: float
    file_mb: float

    @property
    def total_s(self) -> float:
        return self.normalize_s + self.render_s + self.write_s


def _pk_alias(pk_cols: Sequence[str]) -> dict[str, str]:
    return {column: f"{column}_pk" for column in pk_cols}


def _generate(op: str, table: Table, records: Sequence[dict[str, Any]], dialect: Any) -> list[str]:
    pk_cols = [column.name for column in table.primary_key.columns]
    if op == "insert":
        return generate_insert_sql(insert(table), records, dialect)
    if op == "update":
        update_cols = [column.name for column in table.columns if column.name not in pk_cols]
        return generate_update_sql(
            table=table,
            records=records,
            update_cols=update_cols,
            pk_param_map=_pk_alias(pk_cols),
            pk_cols=pk_cols,
            dialect=dialect,
        )
    return generate_delete_sql(records=records, table=table, pk_cols=pk_cols, dialect=dialect)


def measure(dialect_name: str, dialect: Any, op: str, rows: int, chunk_size: int, repeat: int) -> Measurement:
    """Mide las tres etapas de ``op`` en bloques de ``chunk_size`` filas."""
    table = build_table(dialect_name)
    df = make_dataframe(rows, dialect_name)
    pk_cols = [column.name for column in table.primary_key.columns]
    alias = _pk_alias(pk_cols)
    normalize_s = render_s = 0.0
    lines: list[str] = []
    for start in range(0, rows, chunk_size):
        block = df.iloc[start : start + chunk_size]
        t0 = perf_counter()
        if op == "delete":
            records = [{str(k): v for k, v in record.items()} for record in block[pk_cols].to_dict(orient="records")]
        else:  # como BulkCrud al generar SQL: bloque por columnas (P-34)
            records = SqlColumns(*dataframe_to_sql_columns(block))
            restore_binary_values(records, table)
            if op == "update":
                for original, pk_alias in alias.items():
                    records.add_alias(pk_alias, original)
        t1 = perf_counter()
        lines.extend(_generate(op, table, records, dialect))
        normalize_s += t1 - t0
        render_s += perf_counter() - t1
    persistence = BulkPersistenceManager(
        engine_url="sqlite://",
        logger=_log,
        audit_manager=None,  # type: ignore[arg-type]  # persist_sql no lo usa
        db_info=dialect_name,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "out.sql"
        t0 = perf_counter()
        persistence.persist_sql(iter(lines), path)
        write_s = perf_counter() - t0
        file_mb = path.stat().st_size / 1e6
    return Measurement(dialect_name, op, rows, repeat, normalize_s, render_s, write_s, file_mb)


def measure_e2e(rows: int, chunk_size: int, repeat: int) -> list[Measurement]:
    """API pública con SQLite: una medición por operación (solo total en ``render_s``)."""
    logging.getLogger("util_bbdd").setLevel(logging.CRITICAL)
    results: list[Measurement] = []
    table = build_table("sqlite")
    df = make_dataframe(rows, "sqlite")
    id_col = physical_name("id", "sqlite")
    with tempfile.TemporaryDirectory() as tmp:
        engine = create_engine(f"sqlite:///{tmp}/bench.db")
        try:
            table.create(engine)
            crud = BulkCrud(engine, chunk_size=chunk_size, warn_if_audit_disabled=False)
            calls = {
                "insert": lambda out: crud.bulk_insert_from_df(df, table.name, generar_sql=True, path_sql=out),
                "update": lambda out: crud.bulk_update_from_df(df, table.name, generar_sql=True, path_sql=out),
                "delete": lambda out: crud.bulk_delete_from_df(
                    df[[id_col]], table.name, generar_sql=True, path_sql=out
                ),
            }
            for op, call in calls.items():
                out = Path(tmp) / f"{op}_{repeat}"  # carpeta propia: el nombre del fichero lleva la hora al segundo
                out.mkdir()
                t0 = perf_counter()
                call(out)
                elapsed = perf_counter() - t0
                size = sum(path.stat().st_size for path in out.iterdir()) / 1e6
                results.append(Measurement("sqlite-e2e", op, rows, repeat, 0.0, elapsed, 0.0, size))
        finally:
            engine.dispose()
    return results


def load_dialects(names: Sequence[str]) -> dict[str, Any]:
    """Dialectos por nombre; se salta (con aviso) el que no tenga driver instalado."""
    dialects: dict[str, Any] = {}
    for name in names:
        try:
            dialects[name] = create_engine(DIALECT_URLS[name]).dialect
        except ImportError as error:
            _log.warning("Se salta %s: driver no instalado (%s)", name, error)
    return dialects


def render_table(measurements: Sequence[Measurement]) -> str:
    """Mediana por dialecto × operación, en µs/fila."""
    groups: dict[tuple[str, str], list[Measurement]] = {}
    for measurement in measurements:
        groups.setdefault((measurement.dialect, measurement.op), []).append(measurement)
    header = f"{'dialecto':<12}{'op':<8}{'norm µs/f':>10}{'render µs/f':>12}{'write µs/f':>11}{'total s':>9}{'MB':>8}"
    lines = [header, "-" * len(header)]
    for (dialect, op), group in groups.items():
        rows = group[0].rows

        def med(attr: str, items: list[Measurement] = group) -> float:
            return statistics.median(getattr(item, attr) for item in items)

        lines.append(
            f"{dialect:<12}{op:<8}{med('normalize_s') / rows * 1e6:>10.2f}{med('render_s') / rows * 1e6:>12.2f}"
            f"{med('write_s') / rows * 1e6:>11.2f}{med('total_s'):>9.2f}{med('file_mb'):>8.1f}"
        )
    return "\n".join(lines)


def write_csv(measurements: Sequence[Measurement], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*asdict(measurements[0]), "total_s"])
        writer.writeheader()
        for measurement in measurements:
            writer.writerow({**asdict(measurement), "total_s": measurement.total_s})


def _csv_list(value: str, allowed: Sequence[str]) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in items if item not in allowed]
    if unknown:
        raise argparse.ArgumentTypeError(f"desconocido(s): {', '.join(unknown)}. Válidos: {', '.join(allowed)}")
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--dialects", default=",".join(DIALECT_URLS), type=lambda v: _csv_list(v, tuple(DIALECT_URLS)))
    parser.add_argument("--ops", default=",".join(OPS), type=lambda v: _csv_list(v, OPS))
    parser.add_argument("--chunk-size", type=int, default=5000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--e2e", action="store_true", help="Mide también la API pública con SQLite")
    parser.add_argument("--out", type=Path, default=None, help="CSV con una fila por medición")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    measurements: list[Measurement] = []
    for name, dialect in load_dialects(args.dialects).items():
        for op in args.ops:
            for repeat in range(args.repeat):
                measurements.append(measure(name, dialect, op, args.rows, args.chunk_size, repeat))
    if args.e2e:
        for repeat in range(args.repeat):
            measurements.extend(m for m in measure_e2e(args.rows, args.chunk_size, repeat) if m.op in args.ops)
    if not measurements:
        print("Sin mediciones (¿ningún driver instalado?)", file=sys.stderr)
        return 1
    print(f"rows={args.rows} chunk_size={args.chunk_size} repeat={args.repeat}")
    print(render_table(measurements))
    if args.out is not None:
        write_csv(measurements, args.out)
        print(f"CSV: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
