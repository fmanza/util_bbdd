#!/usr/bin/env python3
"""Banco de pruebas de rendimiento de ``util_bbdd.bulk`` contra motores reales.

Mide ``bulk_insert_from_df``, ``bulk_update_from_df`` y ``bulk_delete_from_df`` (API pública, ``generar_sql=False``)
para cada motor × variante × tamaño × repetición, verifica el resultado con SQL después de cada operación y escribe:

    <out>/results.csv       una fila por medición (incluye errores: una operación que falla no detiene el banco)
    <out>/summary.md        mediana por motor × variante × operación × tamaño
    <out>/environment.json  versiones de Python, pandas, SQLAlchemy, driver y servidor (sin contraseñas)

Motores: se activan con una URL SQLAlchemy en ``UTIL_BBDD_BENCH_<MOTOR>_URL`` (o, si no existe, en la convención de los
tests de integración ``UTIL_BBDD_TEST_<MOTOR>_URL``). SQLite no necesita URL: usa un fichero temporal. Un motor sin URL
se salta con un aviso. Motores: sqlite, postgresql, mysql, mariadb, mssql, oracle.

**Apunta siempre a una base de datos de pruebas.** El banco solo crea y elimina la tabla ``zz_util_bbdd_bench``.

Variantes A/B (hallazgos de .ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md):

    baseline                           BulkCrud por defecto (todos los motores)
    mysql-multirow-legacy              MySQL/MariaDB con la vía multi-fila anterior a P-02 (la actual usa executemany)
    mysql-update-executemany-legacy    MySQL/MariaDB con el UPDATE fila a fila anterior a P-04 (update_via_staging=False)
    p01-mssql-engine-fast-executemany  SQL Server + pyodbc con create_engine(fast_executemany=True)

Uso:
    python scripts/bench_bulk.py                                   # todos los motores con URL, 1K..1M, 3 repeticiones
    python scripts/bench_bulk.py --engines sqlite,postgresql --sizes 1000,10000 --repeat 1
    python scripts/bench_bulk.py --variants baseline --ops insert --memory
    python scripts/bench_bulk.py --list-variants
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import platform
import statistics
import sys
import tempfile
import traceback
import tracemalloc

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import sqlalchemy as sa

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Engine,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    cast,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import make_url

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.batch import InsertStrategyResolver, MySQLMultiRowInsertStrategy
from util_bbdd.bulk._support.validation import normalize_identifier

ROOT = Path(__file__).resolve().parent.parent

ENGINES: tuple[str, ...] = ("sqlite", "postgresql", "mysql", "mariadb", "mssql", "oracle")
OPS: tuple[str, ...] = ("insert", "update", "delete")
DEFAULT_SIZES: tuple[int, ...] = (1_000, 10_000, 100_000, 1_000_000)
TABLE_NAME = "zz_util_bbdd_bench"
SEED = 42

# (nombre lógico, tipo) — el nombre físico sigue la convención de BulkCrud para cada dialecto (ver physical_name).
COLUMNS: tuple[tuple[str, Any], ...] = (
    ("id", Integer),
    ("a", Integer),
    ("b", Integer),
    ("c", Integer),
    ("f1", Float),
    ("f2", Float),
    ("s1", String(50)),
    ("s2", String(50)),
    ("s3", String(50)),
    ("d", DateTime),
)

_log = logging.getLogger("bench_bulk")


# ---------------------------------------------------------------------------
# Motores
# ---------------------------------------------------------------------------


def resolve_engine_url(engine_key: str, environ: dict[str, str] | None = None) -> str | None:
    """Devuelve la URL configurada para ``engine_key`` o ``None`` si el motor no está disponible.

    Orden: ``UTIL_BBDD_BENCH_<MOTOR>_URL`` → ``UTIL_BBDD_TEST_<MOTOR>_URL``. SQLite sin URL usa un fichero temporal.
    """
    env = os.environ if environ is None else environ
    key = engine_key.upper()
    url = env.get(f"UTIL_BBDD_BENCH_{key}_URL") or env.get(f"UTIL_BBDD_TEST_{key}_URL")
    if url:
        warn_if_standard_port(engine_key, url)
        return url
    if engine_key == "sqlite":
        return f"sqlite:///{Path(tempfile.mkdtemp(prefix='util_bbdd_bench_')) / 'bench.db'}"
    return None


# Puertos estándar por motor. Los contenedores del banco (docker-compose.bench.yml) usan otros a propósito, para no
# tocar nunca un servidor que ya use el estándar (p.ej. un PostgreSQL de desarrollo en el 5432).
_STANDARD_PORTS: dict[str, int] = {"postgresql": 5432, "mysql": 3306, "mariadb": 3306, "mssql": 1433, "oracle": 1521}


def warn_if_standard_port(engine_key: str, url: str) -> bool:
    """Registra un WARNING si ``url`` usa el puerto estándar del motor (o ninguno, que equivale a él).

    Solo avisa: un servidor de pruebas real puede estar en el puerto estándar. Devuelve si ha avisado.
    """
    standard = _STANDARD_PORTS.get(engine_key)
    if standard is None:
        return False
    try:
        port = make_url(url).port or standard
    except Exception:  # URL no analizable: que falle después al conectar, con su propio error
        return False
    if port != standard:
        return False
    _log.warning(
        "%s: la URL usa el puerto estándar %d; los servidores del banco (docker-compose.bench.yml) usan puertos propios. "
        "Comprueba que no apunta a otro servidor (el banco crea y borra tablas zz_util_bbdd_*).",
        engine_key,
        standard,
    )
    return True


def physical_name(logical: str, dialect_name: str) -> str:
    """Nombre físico de tabla/columna según la convención de ``BulkCrud`` (MySQL/MariaDB no se normalizan)."""
    if dialect_name in ("mysql", "mariadb"):
        return logical
    return normalize_identifier(logical, dialect_name)


def physical_column(logical: str, dialect_name: str) -> str:
    """Nombre físico de columna. En SQL Server, en minúsculas: desde PD-01 ``BulkCrud`` casa las columnas sin distinguir
    mayúsculas, y crearlas en MAYÚSCULAS (como las tablas) ocultaba justo ese fallo (sesión 2026-09-25-performance-audit-dump)."""
    if dialect_name == "mssql":
        return logical
    return physical_name(logical, dialect_name)


def build_table(dialect_name: str) -> Table:
    """Tabla de benchmark con PK explícita (sin autoincremento) y nombres según el dialecto."""
    metadata = MetaData()
    columns = [
        Column(physical_column(name, dialect_name), col_type, primary_key=(name == "id"), autoincrement=False)
        for name, col_type in COLUMNS
    ]
    return Table(physical_name(TABLE_NAME, dialect_name), metadata, *columns)


def reset_table(engine: Engine, table: Table) -> None:
    """Elimina (si existe) y crea la tabla de benchmark. Solo actúa sobre ``TABLE_NAME``."""
    if table.name.lower() != TABLE_NAME:
        raise ValueError(f"Tabla inesperada: {table.name!r}")
    table.drop(engine, checkfirst=True)
    table.create(engine)


def drop_table(engine: Engine, table: Table) -> None:
    """Elimina la tabla de benchmark al terminar con un motor."""
    if table.name.lower() == TABLE_NAME:
        table.drop(engine, checkfirst=True)


def server_version(engine: Engine) -> str:
    """Versión del servidor tal como la informa el dialecto (vacía si no se puede leer)."""
    try:
        with engine.connect() as conn:  # la primera conexión inicializa el dialecto y lee la versión
            info = conn.dialect.server_version_info
        return ".".join(str(part) for part in info) if info else ""
    except sa.exc.SQLAlchemyError:
        return ""


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------


def make_dataframe(rows: int, dialect_name: str) -> pd.DataFrame:
    """DataFrame determinista de ``rows`` filas con ints, floats con NaN, textos con None y fechas.

    Los textos llevan espacios en los extremos a propósito: ``normalize_sql_literal`` los recorta.
    """
    rng = np.random.default_rng(SEED)
    f2 = rng.random(rows)
    f2[::7] = np.nan
    s3 = np.array([f" val {i} " for i in range(rows)], dtype=object)
    s3[::11] = None
    data: dict[str, Any] = {
        "id": np.arange(1, rows + 1),
        "a": rng.integers(0, 1000, rows),
        "b": rng.integers(0, 1000, rows),
        "c": rng.integers(0, 1000, rows),
        "f1": rng.random(rows),
        "f2": f2,
        "s1": [f"name_{i}" for i in range(rows)],
        "s2": ["x" * 20] * rows,
        "s3": s3,
        "d": pd.date_range("2026-01-01", periods=rows, freq="s"),
    }
    return pd.DataFrame({physical_column(name, dialect_name): values for name, values in data.items()})


# ---------------------------------------------------------------------------
# Variantes A/B
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Variant:
    """Configuración alternativa de engine/BulkCrud que se compara contra ``baseline``."""

    name: str
    description: str
    finding: str = ""
    # Dialectos a los que aplica la variante; sin valor, aplica a todos.
    dialects: frozenset[str] | None = None
    # Subcadena exigida en el driver de la URL (p.ej. "pyodbc"); vacía, cualquier driver.
    driver_contains: str = ""
    engine_kwargs: dict[str, Any] = field(default_factory=dict)
    crud_kwargs: Callable[[], dict[str, Any]] = field(default=dict)

    def applies_to(self, dialect_name: str, drivername: str) -> bool:
        if self.dialects is not None and dialect_name not in self.dialects:
            return False
        return not self.driver_contains or self.driver_contains in drivername.lower()


VARIANTS: dict[str, Variant] = {
    variant.name: variant
    for variant in (
        Variant(name="baseline", description="BulkCrud por defecto"),
        Variant(
            name="mysql-multirow-legacy",
            description="MySQL/MariaDB: vía multi-fila con text() (la de por defecto antes de P-02)",
            finding="P-02",
            dialects=frozenset({"mysql", "mariadb"}),
            crud_kwargs=lambda: {
                "insert_resolver": InsertStrategyResolver(mysql_strategy=MySQLMultiRowInsertStrategy())
            },
        ),
        Variant(
            name="mysql-update-executemany-legacy",
            description="MySQL/MariaDB: UPDATE fila a fila (update_via_staging=False, el de por defecto antes de P-04)",
            finding="P-04",
            dialects=frozenset({"mysql", "mariadb"}),
            crud_kwargs=lambda: {"update_via_staging": False},
        ),
        Variant(
            name="p01-mssql-engine-fast-executemany",
            description="SQL Server + pyodbc: create_engine(fast_executemany=True) (desactiva insertmanyvalues)",
            finding="P-01",
            dialects=frozenset({"mssql"}),
            driver_contains="pyodbc",
            engine_kwargs={"fast_executemany": True},
        ),
    )
}


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------


@dataclass
class Measurement:
    """Una medición de una operación bulk."""

    engine: str
    driver: str
    variant: str
    op: str
    rows: int
    repeat: int
    seconds: float | None
    rows_per_second: float | None
    ok: bool
    error: str = ""
    peak_mb: float | None = None


def _count(engine: Engine, table: Table) -> int:
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(table)).scalar_one())


def _sum_a(engine: Engine, table: Table) -> int:
    col = table.c[physical_column("a", engine.dialect.name)]
    with engine.connect() as conn:
        # CAST a BIGINT: en SQL Server SUM(INT) desborda por encima de 2^31 (tamaños > ~2M filas).
        total = func.coalesce(func.sum(cast(col, BigInteger)), 0)
        return int(conn.execute(select(total).select_from(table)).scalar_one())


def _short_error(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}".replace("\n", " ")
    return text[:300]


def timed(fn: Callable[[], None], *, memory: bool) -> tuple[float, float | None]:
    """Ejecuta ``fn`` y devuelve (segundos, pico_MB). Con ``memory`` usa tracemalloc (penaliza el tiempo)."""
    if memory:
        tracemalloc.start()
    start = perf_counter()
    try:
        fn()
    finally:
        elapsed = perf_counter() - start
        peak: float | None = None
        if memory:
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peak = peak_bytes / 1e6
    return elapsed, peak


@dataclass(frozen=True)
class BenchConfig:
    """Parámetros comunes a todas las mediciones de una ejecución."""

    sizes: Sequence[int]
    ops: Sequence[str]
    repeat: int
    chunk_size: int
    audit_csv: Path | None
    memory: bool = False


Step = tuple[Callable[[], None], Callable[[], bool]]


def _build_steps(engine: Engine, table: Table, crud: BulkCrud, df: pd.DataFrame) -> dict[str, Step]:
    """Acción y verificación SQL de cada operación sobre ``df`` ya cargado en memoria."""
    dialect = engine.dialect.name
    rows = len(df)
    col_a = physical_column("a", dialect)
    col_id = physical_column("id", dialect)
    df_update = df.copy()
    df_update[col_a] = df_update[col_a] + 1
    expected_sum_a = int(df[col_a].sum()) + rows
    return {
        "insert": (
            lambda: crud.bulk_insert_from_df(df, table.name, generar_sql=False),
            lambda: _count(engine, table) == rows,
        ),
        "update": (
            lambda: crud.bulk_update_from_df(df_update, table.name, generar_sql=False),
            lambda: _sum_a(engine, table) == expected_sum_a,
        ),
        "delete": (
            lambda: crud.bulk_delete_from_df(df[[col_id]], table.name, generar_sql=False),
            lambda: _count(engine, table) == 0,
        ),
    }


def _measure_step(step: Step, base: Measurement, *, memory: bool) -> Measurement:
    """Ejecuta y verifica un paso; cualquier excepción queda registrada en la medición."""
    run, check = step
    try:
        seconds, peak = timed(run, memory=memory)
        ok = check()
    except Exception as exc:  # noqa: BLE001
        # Se registra cualquier fallo del motor o del driver (p.ej. P-05) sin detener el banco.
        _log.debug("Fallo en %s/%s/%s/%d: %s", base.engine, base.variant, base.op, base.rows, traceback.format_exc())
        base.error = _short_error(exc)
        return base
    base.seconds = round(seconds, 4)
    base.rows_per_second = round(base.rows / seconds, 1) if seconds > 0 else None
    base.peak_mb = round(peak, 1) if peak is not None else None
    base.ok = ok
    base.error = "" if ok else "verificación SQL fallida (filas o valores inesperados)"
    return base


def run_cycle(
    *, engine: Engine, engine_key: str, variant: Variant, rows: int, repeat: int, config: BenchConfig
) -> list[Measurement]:
    """Ejecuta INSERT → UPDATE → DELETE (los seleccionados) sobre una tabla recién creada.

    Si no se mide INSERT pero sí UPDATE o DELETE, los datos se cargan sin cronometrar. Una operación fallida corta el
    ciclo, porque las siguientes dependerían de un estado incierto.
    """
    table = build_table(engine.dialect.name)
    reset_table(engine, table)
    crud = BulkCrud(engine, chunk_size=config.chunk_size, audit_csv_path=config.audit_csv, **variant.crud_kwargs())
    crud.reflect_table(table.name)  # la reflexión (1 vez por instancia) queda fuera de la medición
    steps = _build_steps(engine, table, crud, make_dataframe(rows, engine.dialect.name))

    if "insert" not in config.ops and {"update", "delete"} & set(config.ops):
        steps["insert"][0]()  # carga previa sin medir

    results: list[Measurement] = []
    for op in (op for op in OPS if op in config.ops):
        base = Measurement(engine_key, engine.dialect.driver, variant.name, op, rows, repeat, None, None, False)
        measurement = _measure_step(steps[op], base, memory=config.memory)
        results.append(measurement)
        if not measurement.ok:
            break
    return results


def _run_variant(
    engine_key: str, url: str, variant: Variant, config: BenchConfig, env_info: dict[str, Any]
) -> list[Measurement]:
    """Todas las mediciones de un motor con una variante; un fallo al preparar el motor lo salta."""
    measurements: list[Measurement] = []
    engine: Engine | None = None
    try:
        engine = create_engine(url, **variant.engine_kwargs)
        env_info["engines"][engine_key] = {
            "status": "ok",
            "url": engine.url.render_as_string(hide_password=True),
            "driver": engine.url.drivername,
            "server_version": server_version(engine),
        }
        for rows in config.sizes:
            for rep in range(1, config.repeat + 1):
                _log.info("> %s · %s · %d filas · rep %d", engine_key, variant.name, rows, rep)
                cycle = run_cycle(
                    engine=engine, engine_key=engine_key, variant=variant, rows=rows, repeat=rep, config=config
                )
                for m in cycle:
                    _log.info(
                        "   %s: %s", m.op, f"{m.seconds:.3f}s" if m.ok and m.seconds is not None else f"ERROR {m.error}"
                    )
                measurements.extend(cycle)
        drop_table(engine, build_table(engine.dialect.name))
    except Exception as exc:  # noqa: BLE001
        # Driver ausente, servidor caído o DDL rechazado: se registra y se pasa al siguiente motor.
        _log.error("ERROR %s · %s: no se pudo preparar el motor: %s", engine_key, variant.name, _short_error(exc))
        env_info["engines"][engine_key] = {"status": "error", "error": _short_error(exc)}
    finally:
        if engine is not None:
            engine.dispose()
    return measurements


def run_benchmark(
    *,
    engines: Sequence[str],
    sizes: Sequence[int],
    ops: Sequence[str],
    variants: Sequence[str],
    repeat: int,
    chunk_size: int,
    out_dir: Path,
    memory: bool = False,
    environ: dict[str, str] | None = None,
) -> list[Measurement]:
    """Ejecuta el banco completo y escribe ``results.csv``, ``summary.md`` y ``environment.json`` en ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    config = BenchConfig(
        sizes=sizes, ops=ops, repeat=repeat, chunk_size=chunk_size, audit_csv=out_dir / "audit.csv", memory=memory
    )
    measurements: list[Measurement] = []
    env_info: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "sqlalchemy": sa.__version__,
        "chunk_size": chunk_size,
        "repeat": repeat,
        "memory": memory,
        "engines": {},
    }

    for engine_key in engines:
        url = resolve_engine_url(engine_key, environ)
        if url is None:
            _log.warning("SKIP %s: sin URL (UTIL_BBDD_BENCH_%s_URL); se salta", engine_key, engine_key.upper())
            env_info["engines"][engine_key] = {"status": "skipped"}
            continue
        parsed = sa.engine.make_url(url)
        dialect_name = parsed.get_dialect().name
        for variant in (VARIANTS[name] for name in variants):
            if variant.applies_to(dialect_name, parsed.drivername):
                measurements.extend(_run_variant(engine_key, url, variant, config, env_info))

    write_results(measurements, out_dir / "results.csv")
    (out_dir / "summary.md").write_text(render_summary(measurements, env_info), encoding="utf-8")
    (out_dir / "environment.json").write_text(json.dumps(env_info, indent=2, ensure_ascii=False), encoding="utf-8")
    return measurements


# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------


def write_results(measurements: Sequence[Measurement], path: Path) -> None:
    """CSV con una fila por medición."""
    names = list(Measurement.__dataclass_fields__)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for m in measurements:
            writer.writerow(asdict(m))


def summarize(measurements: Sequence[Measurement]) -> list[dict[str, Any]]:
    """Mediana de segundos por (motor, variante, operación, filas); cuenta errores aparte."""
    groups: dict[tuple[str, str, str, int], list[Measurement]] = {}
    for m in measurements:
        groups.setdefault((m.engine, m.variant, m.op, m.rows), []).append(m)
    summary: list[dict[str, Any]] = []
    for (engine_key, variant, op, rows), items in groups.items():
        times = [m.seconds for m in items if m.ok and m.seconds is not None]
        errors = [m.error for m in items if not m.ok]
        median = statistics.median(times) if times else None
        summary.append(
            {
                "engine": engine_key,
                "variant": variant,
                "op": op,
                "rows": rows,
                "median_s": median,
                "rows_per_s": round(rows / median, 1) if median else None,
                "runs_ok": len(times),
                "runs_error": len(errors),
                "error": errors[0] if errors else "",
            }
        )
    order = {op: i for i, op in enumerate(OPS)}
    summary.sort(key=lambda r: (r["engine"], order.get(r["op"], len(order)), r["rows"], r["variant"] != "baseline"))
    return summary


def render_summary(measurements: Sequence[Measurement], env_info: dict[str, Any]) -> str:
    """Resumen Markdown con mediana por grupo y comparación contra ``baseline``."""
    rows = summarize(measurements)
    base = {(r["engine"], r["op"], r["rows"]): r["median_s"] for r in rows if r["variant"] == "baseline"}
    lines = [
        "# Banco de pruebas bulk",
        "",
        f"- Fecha: {env_info['timestamp']} · Python {env_info['python']} · pandas {env_info['pandas']} · "
        f"SQLAlchemy {env_info['sqlalchemy']} · chunk_size {env_info['chunk_size']} · repeticiones {env_info['repeat']}",
        "",
        "| Motor | Servidor | Driver |",
        "|---|---|---|",
    ]
    for key, info in env_info["engines"].items():
        lines.append(f"| {key} | {info.get('server_version', info['status'])} | {info.get('driver', '')} |")
    lines += [
        "",
        "| Motor | Operación | Filas | Variante | Mediana (s) | Filas/s | vs baseline | OK/Error | Error |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        median = f"{r['median_s']:.3f}" if r["median_s"] is not None else "—"
        rate = f"{r['rows_per_s']:,.0f}" if r["rows_per_s"] else "—"
        ref = base.get((r["engine"], r["op"], r["rows"]))
        if r["variant"] != "baseline" and ref and r["median_s"]:
            delta = f"{ref / r['median_s']:.2f}×"
        else:
            delta = ""
        error = r["error"].replace("|", "\\|")[:120]
        lines.append(
            f"| {r['engine']} | {r['op']} | {r['rows']:,} | {r['variant']} | {median} | {rate} | {delta} | "
            f"{r['runs_ok']}/{r['runs_error']} | {error} |"
        )
    lines.append("")
    lines.append("`vs baseline` > 1 significa que la variante es más rápida que `baseline`.")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _csv_list(value: str, allowed: Sequence[str], label: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in items if item not in allowed]
    if unknown:
        raise argparse.ArgumentTypeError(f"{label} desconocido(s): {', '.join(unknown)}. Válidos: {', '.join(allowed)}")
    return items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engines", default=",".join(ENGINES), type=lambda v: _csv_list(v, ENGINES, "motor"))
    parser.add_argument(
        "--sizes",
        default=",".join(str(s) for s in DEFAULT_SIZES),
        type=lambda v: [int(s) for s in v.split(",") if s.strip()],
    )
    parser.add_argument("--ops", default=",".join(OPS), type=lambda v: _csv_list(v, OPS, "operación"))
    parser.add_argument(
        "--variants", default=",".join(VARIANTS), type=lambda v: _csv_list(v, list(VARIANTS), "variante")
    )
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--chunk-size", type=int, default=5000)
    parser.add_argument("--out", type=Path, default=None, help="Directorio de salida (default: bench_results/<fecha>)")
    parser.add_argument("--memory", action="store_true", help="Mide el pico de memoria con tracemalloc (más lento)")
    parser.add_argument("--list-variants", action="store_true", help="Lista las variantes y termina")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra también los logs de util_bbdd")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # consolas Windows (cp1252): la salida lleva caracteres no ASCII
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.list_variants:
        for variant in VARIANTS.values():
            scope = ", ".join(sorted(variant.dialects)) if variant.dialects else "todos"
            print(f"{variant.name:36} [{variant.finding or '—'}] ({scope}) {variant.description}")
        return 0
    if args.repeat < 1 or args.chunk_size < 1 or any(size < 1 for size in args.sizes):
        print("--repeat, --chunk-size y --sizes deben ser ≥ 1", file=sys.stderr)
        return 2

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    logging.getLogger("util_bbdd").setLevel(logging.INFO if args.verbose else logging.ERROR)
    logging.getLogger("util").setLevel(logging.INFO if args.verbose else logging.ERROR)

    out_dir = args.out or ROOT / "bench_results" / datetime.now().strftime("%Y%m%d_%H%M%S")
    measurements = run_benchmark(
        engines=args.engines,
        sizes=args.sizes,
        ops=args.ops,
        variants=args.variants,
        repeat=args.repeat,
        chunk_size=args.chunk_size,
        out_dir=out_dir,
        memory=args.memory,
    )
    print((out_dir / "summary.md").read_text(encoding="utf-8"))
    print(f"Resultados en {out_dir}")
    return 0 if measurements else 1


if __name__ == "__main__":
    sys.exit(main())
