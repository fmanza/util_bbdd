#!/usr/bin/env python3
"""Banco de los modos de índices (ninguno / secundarios / todos) en la carga de ``BulkCrud`` contra motores reales.

G0 de la sesión ``.ai/sessions/2026-10-18b-index-modes-bulk-dump``: mide, **antes de implementarlo en la librería**,
cuánto gana desactivar los índices del destino durante un INSERT masivo y reconstruirlos al final. Los índices se
desactivan y reconstruyen con DDL directo de este script (modo autónomo: conexión propia, como ``dump.IndexManager``);
la carga es la de la API pública (``BulkCrud.bulk_insert_from_df``, en serie o con ``ParallelOptions``).

Modos (``--modes``):

- ``none``: no se toca ningún índice (referencia de cada grupo).
- ``secondary``: índices secundarios no únicos.
- ``all``: además, UNIQUE y PK, salvo lo que el motor no permite quitar sin rehacer la tabla (PK clustered de SQL
  Server, PK de MariaDB/MySQL, PK de SQLite).

Ejes por grupo (cada grupo compara sus modos con ``none``):

- ``--profiles``: ``sec0`` (solo PK), ``sec2`` (PK + 2 secundarios), ``sec2u`` (+ 1 UNIQUE), ``sec5u`` (PK + 5
  secundarios + 1 UNIQUE), ``fk1``/``fk2`` (``sec2`` + 1/2 FK hacia una tabla padre de 1000 filas).
- ``--order``: filas en orden de PK o barajadas.
- ``--workers``: 1 = en serie; N = ``ParallelOptions(mode="manual", max_workers=N)``.
- ``--constraints``: ``on`` o ``off`` (``off`` = ``maintenance_scope(disable_constraints=True)`` en serie o
  ``ParallelOptions(disable_constraints=True)``; en MariaDB/MySQL es ``FOREIGN_KEY_CHECKS=0``).
- ``--unique-checks off`` (solo MariaDB/MySQL): ``SET SESSION unique_checks=0`` en cada conexión del pool.
- ``--storage myisam`` (solo MariaDB/MySQL): tabla MyISAM; ``secondary`` es ``DISABLE KEYS``/``ENABLE KEYS``.

Protocolo (el de ``scripts/bench_parallel.py``): tandas de calentamiento descartadas, modos en orden alterno en cada
repetición, mediana y rango intercuartílico. Veredicto (decisión D3 de la sesión): un modo **gana** si su total
(desactivar + cargar + reconstruir) es al menos un 5 % menor que el de ``none`` y su p75 es menor que el p25 de
``none``. Después de cada tanda se comprueba que los índices y constraints vuelven a estar como al crear la tabla.

``--probes`` ejecuta además comprobaciones de corrección (no de tiempo) pendientes del AUDIT_PLAN:

- SQL Server: en un heap con PK NONCLUSTERED, qué pasa con las FK entrantes tras ``ALTER INDEX ALL … DISABLE`` y
  ``REBUILD`` (lo que hace hoy ``maintenance_scope(disable_indexes=True)``).
- MariaDB/MySQL: si se puede borrar un índice requerido por una FK, con y sin ``FOREIGN_KEY_CHECKS=0``.

Motores y URLs como ``scripts/bench_bulk.py`` (``UTIL_BBDD_BENCH_<MOTOR>_URL``; ver ``scripts/bench_env.example.sh``);
SQL Server con pyodbc + ODBC Driver 18 como ``scripts/bench_parallel.py``. **Apunta siempre a una base de datos de
pruebas**: solo crea y elimina las tablas ``zz_util_bbdd_bench_ix`` y ``zz_util_bbdd_bench_ixp``. No muestra contraseñas.

Uso:
    python scripts/bench_index_modes.py --engines oracle,mssql --rows 1000000 --profiles sec2u --repeat 3
    python scripts/bench_index_modes.py --engines mysql,mariadb --profiles fk2 --constraints on,off --unique-checks on,off
    python scripts/bench_index_modes.py --engines mssql,mysql,mariadb --probes-only
    python scripts/bench_index_modes.py --out build/logs/bench_index_modes.md --csv build/logs/bench_index_modes.csv
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import logging
import sys
import time

from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from sqlalchemy import (
    Column,
    Engine,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_bulk  # noqa: E402  (mismo directorio: columnas, datos, nombres físicos y URLs del banco)
import bench_parallel  # noqa: E402  (orden alterno, estadísticos y URL pyodbc de SQL Server)

from util_bbdd.bulk import AuditOptions, BulkCrud, ParallelOptions  # noqa: E402

ENGINES: tuple[str, ...] = ("postgresql", "mysql", "mariadb", "mssql", "oracle", "sqlite")
MODES: tuple[str, ...] = ("none", "secondary", "all")
MYSQL_FAMILY: frozenset[str] = frozenset({"mysql", "mariadb"})
TABLE_NAME = "zz_util_bbdd_bench_ix"
PARENT_NAME = "zz_util_bbdd_bench_ixp"
PARENT_ROWS = 1000  # bench_bulk.make_dataframe genera a, b y c en [0, 1000)
SEED = bench_bulk.SEED
#: Decisión D3 de la sesión: ganancia mínima del total frente a ``none`` (en %).
MIN_GAIN_PCT: float = 5.0
#: Columnas lógicas de los índices secundarios, en orden (``sec2`` usa las dos primeras).
SECONDARY_COLUMNS: tuple[str, ...] = ("a", "b", "c", "f1", "d")
UNIQUE_COLUMN = "s1"  # bench_bulk.make_dataframe: "name_<i>", único

Kind = Literal["pk", "unique", "secondary"]

_log = logging.getLogger("bench_index_modes")


# ---------------------------------------------------------------------------
# Perfiles y DDL (funciones puras, testeadas en tests/unit/test_bench_index_modes_script.py)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Profile:
    """Índices y FK de la tabla medida."""

    secondary: int
    unique: bool
    fks: int


PROFILES: dict[str, Profile] = {
    "sec0": Profile(0, False, 0),
    "sec2": Profile(2, False, 0),
    "sec2u": Profile(2, True, 0),
    "sec5u": Profile(5, True, 0),
    "fk1": Profile(2, False, 1),
    "fk2": Profile(2, False, 2),
}


@dataclass(frozen=True)
class IndexSpec:
    """Un índice de la tabla medida: nombre, tipo, columnas lógicas y si lo necesita una FK (columnas de la FK)."""

    name: str
    kind: Kind
    columns: tuple[str, ...]
    fk_required: bool = False


def index_specs(profile: Profile) -> list[IndexSpec]:
    """Índices del perfil: PK, UNIQUE opcional y secundarios; las FK van sobre las primeras columnas secundarias."""
    specs = [IndexSpec("pk_zz_bench_ix", "pk", ("id",))]
    if profile.unique:
        specs.append(IndexSpec("uq_zz_bench_ix_s1", "unique", (UNIQUE_COLUMN,)))
    specs.extend(
        IndexSpec(f"ix_zz_bench_ix_{col}", "secondary", (col,), fk_required=pos < profile.fks)
        for pos, col in enumerate(SECONDARY_COLUMNS[: profile.secondary])
    )
    return specs


@dataclass
class DdlPlan:
    """DDL de un modo: sentencias para desactivar y para restaurar, índices tocados y omitidos (con el motivo)."""

    disable: list[str] = field(default_factory=list)
    restore: list[str] = field(default_factory=list)
    touched: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def _never_reason(dialect: str, spec: IndexSpec, storage: str) -> str | None:
    """Motivo por el que un índice no se toca nunca en ``dialect`` (``None`` si se puede tocar)."""
    if spec.kind == "pk":
        if dialect == "mssql":
            return "PK clustered (es la tabla)"
        if dialect in MYSQL_FAMILY:
            return "PK (clustered en InnoDB)" if storage == "innodb" else "PK"
        if dialect == "sqlite":
            return "PK de SQLite (no se puede quitar)"
    if dialect in MYSQL_FAMILY and spec.fk_required:
        return "requerido por una FK"
    return None


def plan_ddl(
    dialect: str,
    mode: str,
    specs: Sequence[IndexSpec],
    *,
    table_sql: str,
    quote: Callable[[str], str],
    column: Callable[[str], str],
    storage: str = "innodb",
) -> DdlPlan:
    """DDL para desactivar y restaurar los índices de ``specs`` en ``mode``.

    Args:
        dialect: Nombre del dialecto de SQLAlchemy.
        mode: ``none``, ``secondary`` o ``all``.
        specs: Índices de la tabla (:func:`index_specs`).
        table_sql: Tabla ya citada.
        quote: Cita un nombre de índice o constraint.
        column: Nombre lógico de columna → nombre físico citado.
        storage: Motor de almacenamiento en MariaDB/MySQL (``innodb`` o ``myisam``).

    Returns:
        Plan con el DDL en orden: al restaurar, PK → UNIQUE → secundarios.
    """
    plan = DdlPlan()
    if mode == "none":
        return plan
    kinds: set[Kind] = {"secondary"} if mode == "secondary" else {"secondary", "unique", "pk"}
    selected: list[IndexSpec] = []
    for spec in (s for s in specs if s.kind in kinds):
        reason = _never_reason(dialect, spec, storage)
        if reason is None:
            selected.append(spec)
        else:
            plan.skipped.append((spec.name, reason))
    order = {"pk": 0, "unique": 1, "secondary": 2}
    selected.sort(key=lambda s: order[s.kind])
    plan.touched = [s.name for s in selected]
    if not selected:
        return plan
    sql = _SqlParts(table_sql, quote, column)
    if dialect in MYSQL_FAMILY:
        _plan_mysql(plan, selected, sql, storage)
        return plan
    per_index = _PER_INDEX_DDL.get(dialect)
    if per_index is None:
        raise ValueError(f"dialecto no soportado por el banco: {dialect!r}")
    for spec in selected:
        disable, restore = per_index(spec, sql)
        plan.disable.append(disable)
        plan.restore.append(restore)
    return plan


@dataclass(frozen=True)
class _SqlParts:
    """Tabla citada y funciones de cita de :func:`plan_ddl`."""

    table: str
    quote: Callable[[str], str]
    column: Callable[[str], str]

    def cols(self, spec: IndexSpec) -> str:
        return ", ".join(self.column(c) for c in spec.columns)


def _plan_mysql(plan: DdlPlan, selected: Sequence[IndexSpec], sql: _SqlParts, storage: str) -> None:
    """MariaDB/MySQL: InnoDB con un ALTER para borrar y otro para crear; MyISAM con ``DISABLE KEYS`` para secundarios."""
    if storage == "myisam":
        secondary = [s for s in selected if s.kind == "secondary"]
        others = [s for s in selected if s.kind != "secondary"]
        if secondary:
            plan.disable.append(f"ALTER TABLE {sql.table} DISABLE KEYS")
        if others:
            plan.disable.append(
                f"ALTER TABLE {sql.table} " + ", ".join(f"DROP INDEX {sql.quote(s.name)}" for s in others)
            )
            plan.restore.append(
                f"ALTER TABLE {sql.table} "
                + ", ".join(f"ADD UNIQUE INDEX {sql.quote(s.name)} ({sql.cols(s)})" for s in others)
            )
        if secondary:
            plan.restore.append(f"ALTER TABLE {sql.table} ENABLE KEYS")
        return
    # InnoDB: una sola pasada por la tabla al reconstruir todos los índices.
    plan.disable.append(f"ALTER TABLE {sql.table} " + ", ".join(f"DROP INDEX {sql.quote(s.name)}" for s in selected))
    adds = (f"ADD {'UNIQUE ' if s.kind == 'unique' else ''}INDEX {sql.quote(s.name)} ({sql.cols(s)})" for s in selected)
    plan.restore.append(f"ALTER TABLE {sql.table} " + ", ".join(adds))


def _ddl_mssql(spec: IndexSpec, sql: _SqlParts) -> tuple[str, str]:
    name = sql.quote(spec.name)
    return f"ALTER INDEX {name} ON {sql.table} DISABLE", f"ALTER INDEX {name} ON {sql.table} REBUILD"


def _ddl_oracle(spec: IndexSpec, sql: _SqlParts) -> tuple[str, str]:
    name = sql.quote(spec.name)
    if spec.kind == "secondary":
        return f"ALTER INDEX {name} UNUSABLE", f"ALTER INDEX {name} REBUILD"
    # PK/UNIQUE: desactivar la constraint borra su índice; ENABLE VALIDATE lo recrea y valida los datos.
    return (
        f"ALTER TABLE {sql.table} DISABLE CONSTRAINT {name}",
        f"ALTER TABLE {sql.table} ENABLE VALIDATE CONSTRAINT {name}",
    )


def _ddl_postgresql(spec: IndexSpec, sql: _SqlParts) -> tuple[str, str]:
    name = sql.quote(spec.name)
    if spec.kind == "secondary":
        return f"DROP INDEX {name}", f"CREATE INDEX {name} ON {sql.table} ({sql.cols(spec)})"
    definition = "PRIMARY KEY" if spec.kind == "pk" else "UNIQUE"
    return (
        f"ALTER TABLE {sql.table} DROP CONSTRAINT {name}",
        f"ALTER TABLE {sql.table} ADD CONSTRAINT {name} {definition} ({sql.cols(spec)})",
    )


def _ddl_sqlite(spec: IndexSpec, sql: _SqlParts) -> tuple[str, str]:
    name = sql.quote(spec.name)
    unique = "UNIQUE " if spec.kind == "unique" else ""
    return f"DROP INDEX {name}", f"CREATE {unique}INDEX {name} ON {sql.table} ({sql.cols(spec)})"


_PER_INDEX_DDL: dict[str, Callable[[IndexSpec, _SqlParts], tuple[str, str]]] = {
    "mssql": _ddl_mssql,
    "oracle": _ddl_oracle,
    "postgresql": _ddl_postgresql,
    "sqlite": _ddl_sqlite,
}


def gain_pct(base_median: float, mode_median: float) -> float:
    """Ganancia del total frente a ``none`` en % (positiva = más rápido)."""
    return (base_median - mode_median) / base_median * 100 if base_median > 0 else 0.0


def wins(base: bench_parallel.Stats, mode: bench_parallel.Stats) -> bool:
    """Criterio D3: gana ≥ 5 % de mediana y los rangos intercuartílicos no se solapan."""
    return gain_pct(base.median, mode.median) >= MIN_GAIN_PCT and mode.p75 < base.p25


# ---------------------------------------------------------------------------
# Tablas
# ---------------------------------------------------------------------------


def build_tables(dialect: str, profile: Profile, storage: str) -> tuple[Table, Table | None]:
    """Tabla medida (columnas de ``bench_bulk``) con los índices del perfil y, si hay FK, la tabla padre."""
    metadata = MetaData()
    phys = bench_bulk.physical_column
    kwargs: dict[str, Any] = {"mysql_engine": "MyISAM"} if dialect in MYSQL_FAMILY and storage == "myisam" else {}
    parent: Table | None = None
    if profile.fks:
        parent = Table(
            bench_bulk.physical_name(PARENT_NAME, dialect),
            metadata,
            Column(phys("id", dialect), Integer, primary_key=True, autoincrement=False),
            **kwargs,
        )
    specs = index_specs(profile)
    items: list[Any] = [
        Column(phys(name, dialect), col_type, autoincrement=False) for name, col_type in bench_bulk.COLUMNS
    ]
    items.append(PrimaryKeyConstraint(phys("id", dialect), name=specs[0].name))
    for spec in specs[1:]:
        columns = [phys(c, dialect) for c in spec.columns]
        if spec.kind == "unique" and dialect != "sqlite":
            items.append(UniqueConstraint(*columns, name=spec.name))
        else:  # SQLite: el UNIQUE como índice único, para poder borrarlo
            items.append(Index(spec.name, *columns, unique=spec.kind == "unique"))
    if parent is not None:
        for pos in range(profile.fks):
            col = SECONDARY_COLUMNS[pos]
            items.append(
                ForeignKeyConstraint(
                    [phys(col, dialect)], [parent.c[phys("id", dialect)]], name=f"fk_zz_bench_ix_{col}"
                )
            )
    table = Table(bench_bulk.physical_name(TABLE_NAME, dialect), metadata, *items, **kwargs)
    return table, parent


def drop_tables(engine: Engine) -> None:
    """Elimina (si existen) la tabla medida y la padre. Solo actúa sobre ``TABLE_NAME`` y ``PARENT_NAME``."""
    dialect = engine.dialect.name
    metadata = MetaData()
    for logical in (TABLE_NAME, PARENT_NAME):  # primero la hija
        Table(bench_bulk.physical_name(logical, dialect), metadata).drop(engine, checkfirst=True)


def reset_tables(engine: Engine, table: Table, parent: Table | None) -> None:
    """Recrea las tablas y carga la padre con ``PARENT_ROWS`` filas (ids 0…999)."""
    if table.name.lower() != TABLE_NAME or (parent is not None and parent.name.lower() != PARENT_NAME):
        raise ValueError(f"Tablas inesperadas: {table.name!r}, {getattr(parent, 'name', None)!r}")
    drop_tables(engine)
    if parent is not None:
        parent.create(engine)
        pk = parent.c[bench_bulk.physical_column("id", engine.dialect.name)].name
        with engine.begin() as conn:
            conn.execute(parent.insert(), [{pk: i} for i in range(PARENT_ROWS)])
    table.create(engine)


def index_state(engine: Engine, table: Table) -> tuple[Any, ...]:
    """Huella de índices y constraints de la tabla y número de objetos deshabilitados o no válidos (debe ser 0)."""
    insp = inspect(engine)  # nuevo en cada llamada: sin caché
    pk = insp.get_pk_constraint(table.name)
    indexes = sorted((str(i["name"]).lower(), bool(i["unique"])) for i in insp.get_indexes(table.name))
    try:
        uniques = sorted(str(u["name"]).lower() for u in insp.get_unique_constraints(table.name) if u.get("name"))
    except NotImplementedError:  # SQL Server: el dialecto no lo implementa; los UNIQUE ya salen en get_indexes
        uniques = []
    fks = sorted(str(f["name"]).lower() for f in insp.get_foreign_keys(table.name) if f.get("name"))
    pk_cols = tuple(sorted(str(c).lower() for c in pk.get("constrained_columns") or []))
    return pk_cols, tuple(indexes), tuple(uniques), tuple(fks), _bad_objects(engine, table)


def _bad_objects(engine: Engine, table: Table) -> int:
    """Índices deshabilitados/``UNUSABLE``/no válidos y constraints deshabilitadas o no confiables."""
    dialect = engine.dialect.name
    queries: list[tuple[str, dict[str, Any]]] = []
    if dialect == "oracle":
        name = {"t": table.name.upper()}
        queries = [
            ("SELECT COUNT(*) FROM user_indexes WHERE table_name = :t AND status NOT IN ('VALID', 'N/A')", name),
            ("SELECT COUNT(*) FROM user_constraints WHERE table_name = :t AND status <> 'ENABLED'", name),
        ]
    elif dialect == "mssql":
        name = {"t": table.name}
        queries = [
            ("SELECT COUNT(*) FROM sys.indexes WHERE object_id = OBJECT_ID(:t) AND is_disabled = 1", name),
            (
                "SELECT COUNT(*) FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID(:t) "
                "AND (is_disabled = 1 OR is_not_trusted = 1)",
                name,
            ),
        ]
    elif dialect == "postgresql":
        queries = [
            (
                "SELECT COUNT(*) FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid "
                "WHERE c.relname = :t AND NOT i.indisvalid",
                {"t": table.name},
            )
        ]
    if not queries:
        return 0
    with engine.connect() as conn:
        return sum(int(conn.execute(text(sql), params).scalar() or 0) for sql, params in queries)


# ---------------------------------------------------------------------------
# Medición
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Group:
    """Una combinación de ejes en la que se comparan los modos."""

    profile: str
    order: str
    workers: int
    constraints: str
    unique_checks: str
    storage: str

    @property
    def extra(self) -> str:
        parts: list[str] = []
        if self.unique_checks == "off":
            parts.append("uc0")
        if self.storage != "innodb":
            parts.append(self.storage)
        return "+".join(parts) or "-"


@dataclass
class Run:
    """Tiempos de una tanda (segundos) y su comprobación."""

    disable: float = 0.0
    load: float = 0.0
    restore: float = 0.0
    restored_ok: bool = True
    error: str | None = None

    @property
    def total(self) -> float:
        return self.disable + self.load + self.restore


def _short_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc).splitlines()[0][:160] if str(exc) else ''}"


@contextlib.contextmanager
def unique_checks_off(engine: Engine, enabled: bool) -> Generator[None, None, None]:
    """``SET SESSION unique_checks=0`` en cada conexión que sale del pool y ``=1`` al devolverla (como ``dump``)."""
    if not enabled:
        yield
        return

    def _set(dbapi_conn: Any, value: int) -> None:
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute(f"SET SESSION unique_checks = {value}")
        finally:
            cursor.close()

    def off(dbapi_conn: Any, _rec: Any, _proxy: Any) -> None:
        _set(dbapi_conn, 0)

    def on(dbapi_conn: Any, _rec: Any) -> None:
        if dbapi_conn is not None:
            _set(dbapi_conn, 1)

    event.listen(engine, "checkout", off)
    event.listen(engine, "checkin", on)
    try:
        yield
    finally:
        event.remove(engine, "checkout", off)
        event.remove(engine, "checkin", on)


def _execute_ddl(engine: Engine, statements: Sequence[str]) -> float:
    start = time.perf_counter()
    if statements:
        with engine.begin() as conn:
            for sql in statements:
                conn.execute(text(sql))
    return time.perf_counter() - start


def run_once(
    engine: Engine, table: Table, parent: Table | None, df: pd.DataFrame, group: Group, mode: str
) -> tuple[Run, DdlPlan]:
    """Tablas recién creadas → desactivar (modo) → cargar → reconstruir → comprobar que todo vuelve a su estado."""
    dialect = engine.dialect.name
    reset_tables(engine, table, parent)
    before = index_state(engine, table)
    preparer = engine.dialect.identifier_preparer
    plan = plan_ddl(
        dialect,
        mode,
        index_specs(PROFILES[group.profile]),
        table_sql=preparer.format_table(table),
        quote=preparer.quote,
        column=lambda c: preparer.quote(bench_bulk.physical_column(c, dialect)),
        storage=group.storage,
    )
    constraints_off = group.constraints == "off"
    parallel = (
        None
        if group.workers == 1
        else ParallelOptions(mode="manual", max_workers=group.workers, disable_constraints=constraints_off)
    )
    crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False), parallel=parallel)
    crud.reflect_table(table.name)  # antes del DDL: la carga usa la tabla tal como es (con su PK)
    run = Run()
    try:
        run.disable = _execute_ddl(engine, plan.disable)
        start = time.perf_counter()
        with unique_checks_off(engine, group.unique_checks == "off"):
            if group.workers == 1 and constraints_off:
                with crud.bulk_session(), crud.maintenance_scope(table.name, disable_constraints=True):
                    crud.bulk_insert_from_df(df, table.name, generar_sql=False)
            else:
                crud.bulk_insert_from_df(df, table.name, generar_sql=False)
        run.load = time.perf_counter() - start
        run.restore = _execute_ddl(engine, plan.restore)
        after = index_state(engine, table)
        run.restored_ok = after == before and after[-1] == 0
        if not run.restored_ok:
            _log.warning("%s %s %s: estado tras reconstruir distinto: %s → %s", dialect, group, mode, before, after)
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        run.error = _short_error(exc)
        _log.warning("%s %s %s: %s", dialect, group, mode, run.error)
    return run, plan


def groups_for(dialect: str, args: argparse.Namespace) -> list[Group]:
    """Combinaciones de ejes válidas para el motor (``unique_checks`` y ``storage`` solo en MariaDB/MySQL)."""
    mysql = dialect in MYSQL_FAMILY
    unique_checks = args.unique_checks if mysql else ["on"]
    storages = args.storage if mysql else ["innodb"]
    out: list[Group] = []
    for profile in args.profiles:
        for storage in storages:
            if storage == "myisam" and PROFILES[profile].fks:
                continue  # MyISAM no tiene FK
            for order in args.order:
                for workers in args.workers:
                    for constraints in args.constraints:
                        out.extend(Group(profile, order, workers, constraints, uc, storage) for uc in unique_checks)
    return out


def ordered_frame(df: pd.DataFrame, order: str) -> pd.DataFrame:
    """``df`` en orden de PK o barajado con la semilla del banco."""
    return df if order == "pk" else df.sample(frac=1, random_state=SEED).reset_index(drop=True)


HEADER: tuple[str, ...] = (
    "| Motor | Filas | Perfil | Orden | Hilos | Constraints | Extra | Modo | Desactivar s | Carga s | Reconstruir s | "
    "Total: mediana (p25–p75) s | Δ total vs none | Gana (≥ 5 % sin solape) | Restaurado | Omitidos |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
)


def bench_engine(key: str, url: str, args: argparse.Namespace, csv_rows: list[dict[str, Any]]) -> list[str]:
    """Filas de la tabla de resultados de un motor."""
    engine = create_engine(url, pool_size=max(args.workers) + 1, max_overflow=10)
    dialect = engine.dialect.name
    lines: list[str] = []
    _log.info("%s: servidor %s", key, bench_bulk.server_version(engine) or "?")
    try:
        for rows in args.rows:
            base_df = bench_bulk.make_dataframe(rows, dialect)
            groups = groups_for(dialect, args)
            for index, group in enumerate(groups):
                table, parent = build_tables(dialect, PROFILES[group.profile], group.storage)
                df = ordered_frame(base_df, group.order)
                if index == 0:
                    for _ in range(args.warmup):
                        run_once(engine, table, parent, df, group, args.modes[0])
                runs: dict[str, list[Run]] = {mode: [] for mode in args.modes}
                plans: dict[str, DdlPlan] = {}
                for order in bench_parallel.schedule(args.modes, args.repeat):
                    for mode in order:
                        run, plans[mode] = run_once(engine, table, parent, df, group, mode)
                        runs[mode].append(run)
                        csv_rows.append(
                            {
                                "engine": key,
                                "rows": rows,
                                **{k: getattr(group, k) for k in ("profile", "order", "workers", "constraints")},
                                "unique_checks": group.unique_checks,
                                "storage": group.storage,
                                "mode": mode,
                                "disable_s": round(run.disable, 4),
                                "load_s": round(run.load, 4),
                                "restore_s": round(run.restore, 4),
                                "total_s": round(run.total, 4),
                                "restored_ok": run.restored_ok,
                                "error": run.error or "",
                            }
                        )
                lines.extend(_group_lines(key, rows, group, args.modes, runs, plans))
    finally:
        drop_tables(engine)
        engine.dispose()
    return lines


def _group_lines(
    key: str, rows: int, group: Group, modes: Sequence[str], runs: dict[str, list[Run]], plans: dict[str, DdlPlan]
) -> list[str]:
    ok_runs = {mode: [r for r in rs if r.error is None] for mode, rs in runs.items()}
    base = bench_parallel.Stats.of([r.total for r in ok_runs["none"]]) if ok_runs.get("none") else None
    lines: list[str] = []
    for mode in modes:
        prefix = (
            f"| {key} | {rows} | {group.profile} | {group.order} | {group.workers} | {group.constraints} | "
            f"{group.extra} | {mode} |"
        )
        good = ok_runs[mode]
        if not good:
            errors = sorted({r.error or "" for r in runs[mode]})
            lines.append(f"{prefix} – | – | – | error | – | – | – | {'; '.join(errors)} |")
            print(lines[-1], flush=True)
            continue
        stats = bench_parallel.Stats.of([r.total for r in good])
        med = bench_parallel.Stats.of
        delta = "–" if base is None or mode == "none" else f"{gain_pct(base.median, stats.median):+.1f} %"
        verdict = "–" if base is None or mode == "none" else ("sí" if wins(base, stats) else "no")
        restored = "sí" if all(r.restored_ok for r in good) else "**no**"
        plan = plans.get(mode, DdlPlan())
        skipped = ", ".join(f"{name} ({reason})" for name, reason in plan.skipped) or "–"
        lines.append(
            f"{prefix} {med([r.disable for r in good]).median:.2f} | {med([r.load for r in good]).median:.2f} | "
            f"{med([r.restore for r in good]).median:.2f} | {stats.median:.2f} ({stats.p25:.2f}–{stats.p75:.2f}) | "
            f"{delta} | {verdict} | {restored} | {skipped} |"
        )
        print(lines[-1], flush=True)
    return lines


# ---------------------------------------------------------------------------
# Comprobaciones de corrección (--probes)
# ---------------------------------------------------------------------------


def _probe_mssql_heap_pk(engine: Engine) -> list[str]:
    """Heap con PK NONCLUSTERED y FK entrante: estado de la FK tras ``ALTER INDEX ALL … DISABLE`` y ``REBUILD``."""
    parent, child = "ZZ_UTIL_BBDD_BENCH_IXP", "ZZ_UTIL_BBDD_BENCH_IX"

    def fk_state(conn: Any) -> str:
        row = conn.execute(
            text(
                "SELECT is_disabled, is_not_trusted FROM sys.foreign_keys "
                "WHERE name = 'fk_probe' AND parent_object_id = OBJECT_ID(:t)"
            ),
            {"t": child},
        ).first()
        return "sin FK" if row is None else f"is_disabled={row[0]}, is_not_trusted={row[1]}"

    def pk_state(conn: Any) -> str:
        row = conn.execute(
            text("SELECT is_disabled FROM sys.indexes WHERE object_id = OBJECT_ID(:t) AND is_primary_key = 1"),
            {"t": parent},
        ).first()
        return "sin PK" if row is None else f"PK is_disabled={row[0]}"

    drop_tables(engine)
    out: list[str] = []
    with engine.begin() as conn:
        conn.execute(
            text(f"CREATE TABLE [{parent}] (id INT NOT NULL, CONSTRAINT pk_probe PRIMARY KEY NONCLUSTERED (id))")
        )
        conn.execute(
            text(
                f"CREATE TABLE [{child}] (id INT NOT NULL PRIMARY KEY, a INT NULL, "
                f"CONSTRAINT fk_probe FOREIGN KEY (a) REFERENCES [{parent}] (id))"
            )
        )
        conn.execute(text(f"INSERT INTO [{parent}] (id) VALUES (1), (2)"))
        conn.execute(text(f"INSERT INTO [{child}] (id, a) VALUES (1, 1)"))
    try:
        with engine.begin() as conn:
            out.append(f"| mssql | heap PK NONCLUSTERED: inicial | {pk_state(conn)}; FK entrante {fk_state(conn)} |")
            conn.execute(text(f"ALTER INDEX ALL ON [{parent}] DISABLE"))
            out.append(f"| mssql | tras ALTER INDEX ALL … DISABLE | {pk_state(conn)}; FK entrante {fk_state(conn)} |")
        try:
            with engine.begin() as conn:
                conn.execute(text(f"INSERT INTO [{parent}] (id) VALUES (1)"))
            out.append(
                "| mssql | INSERT de PK duplicada con el índice deshabilitado | aceptado (sin control de unicidad) |"
            )
            with engine.begin() as conn:  # quitar el duplicado: si no, el REBUILD de la PK falla
                conn.execute(text(f"DELETE TOP (1) FROM [{parent}] WHERE id = 1"))
        except SQLAlchemyError as exc:
            out.append(
                f"| mssql | INSERT de PK duplicada con el índice deshabilitado | rechazado: {_short_error(exc)} |"
            )
        with engine.begin() as conn:
            conn.execute(text(f"ALTER INDEX ALL ON [{parent}] REBUILD"))
            out.append(f"| mssql | tras ALTER INDEX ALL … REBUILD | {pk_state(conn)}; FK entrante {fk_state(conn)} |")
    except SQLAlchemyError as exc:
        out.append(f"| mssql | error en la prueba | {_short_error(exc)} |")
        with contextlib.suppress(SQLAlchemyError), engine.begin() as conn:
            conn.execute(text(f"ALTER INDEX ALL ON [{parent}] REBUILD"))
    finally:
        drop_tables(engine)
    return out


def _probe_mysql_fk_index(key: str, engine: Engine) -> list[str]:
    """¿Se puede borrar el índice que usa una FK, con ``FOREIGN_KEY_CHECKS=1`` y con ``=0``?"""
    out: list[str] = []
    for fkc in (1, 0):
        drop_tables(engine)
        with engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE {PARENT_NAME} (id INT NOT NULL PRIMARY KEY) ENGINE=InnoDB"))
            conn.execute(
                text(
                    f"CREATE TABLE {TABLE_NAME} (id INT NOT NULL PRIMARY KEY, a INT NULL, INDEX ix_probe_a (a), "
                    f"CONSTRAINT fk_probe FOREIGN KEY (a) REFERENCES {PARENT_NAME} (id)) ENGINE=InnoDB"
                )
            )
        with engine.connect() as conn:
            conn.execute(text(f"SET SESSION FOREIGN_KEY_CHECKS = {fkc}"))
            try:
                conn.execute(text(f"ALTER TABLE {TABLE_NAME} DROP INDEX ix_probe_a"))
                indexes = sorted(str(i["name"]) for i in inspect(conn).get_indexes(TABLE_NAME))
                out.append(
                    f"| {key} | DROP INDEX requerido por FK con FOREIGN_KEY_CHECKS={fkc} | permitido; índices "
                    f"después: {', '.join(indexes) or 'ninguno'} |"
                )
            except SQLAlchemyError as exc:
                out.append(
                    f"| {key} | DROP INDEX requerido por FK con FOREIGN_KEY_CHECKS={fkc} | rechazado: {_short_error(exc)} |"
                )
            finally:
                conn.execute(text("SET SESSION FOREIGN_KEY_CHECKS = 1"))
    drop_tables(engine)
    return out


def run_probes(key: str, url: str) -> list[str]:
    """Comprobaciones de corrección del motor (solo SQL Server y MariaDB/MySQL)."""
    engine = create_engine(url)
    try:
        dialect = engine.dialect.name
        if dialect == "mssql":
            return _probe_mssql_heap_pk(engine)
        if dialect in MYSQL_FAMILY:
            return _probe_mysql_fk_index(key, engine)
        return []
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _csv_ints(value: str) -> list[int]:
    return bench_parallel._csv_ints(value)  # noqa: SLF001 — mismo directorio de scripts


def _choices(allowed: Sequence[str]) -> Callable[[str], list[str]]:
    return lambda value: bench_parallel._csv_choice(value, allowed)  # noqa: SLF001


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engines", default="postgresql,mysql,mariadb,mssql,oracle", type=_choices(ENGINES))
    parser.add_argument("--rows", default="1000000", type=_csv_ints, help="Filas por tanda (lista)")
    parser.add_argument("--profiles", default="sec2u", type=_choices(tuple(PROFILES)))
    parser.add_argument("--modes", default=",".join(MODES), type=_choices(MODES))
    parser.add_argument("--order", default="pk", type=_choices(("pk", "random")))
    parser.add_argument("--workers", default="1", type=_csv_ints, help="Hilos (1 = en serie; lista)")
    parser.add_argument("--constraints", default="on", type=_choices(("on", "off")))
    parser.add_argument("--unique-checks", default="on", type=_choices(("on", "off")), help="Solo MariaDB/MySQL")
    parser.add_argument("--storage", default="innodb", type=_choices(("innodb", "myisam")), help="Solo MariaDB/MySQL")
    parser.add_argument("--repeat", type=int, default=3, help="Repeticiones medidas por modo")
    parser.add_argument("--warmup", type=int, default=1, help="Tandas de calentamiento descartadas por motor y filas")
    parser.add_argument("--probes", action="store_true", help="Ejecuta también las comprobaciones de corrección")
    parser.add_argument("--probes-only", action="store_true", help="Solo las comprobaciones de corrección")
    parser.add_argument("--mssql-driver", choices=("pyodbc", "url"), default="pyodbc")
    parser.add_argument("--out", type=Path, default=None, help="Fichero Markdown con las tablas de resultados")
    parser.add_argument("--csv", type=Path, default=None, help="Fichero CSV con una fila por tanda")
    parser.add_argument("-v", "--verbose", action="store_true", help="Muestra también los logs de util_bbdd")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.repeat < 1 or args.warmup < 0:
        raise SystemExit("--repeat debe ser ≥ 1 y --warmup ≥ 0")
    if "none" not in args.modes:
        args.modes = ["none", *args.modes]  # referencia de la comparación
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.verbose:
        logging.getLogger("util_bbdd").setLevel(logging.ERROR)
    urls: dict[str, str] = {}
    for key in args.engines:
        url = bench_bulk.resolve_engine_url(key)
        if url is None:
            _log.warning("SKIP %s: sin URL (UTIL_BBDD_BENCH_%s_URL)", key, key.upper())
            continue
        urls[key] = bench_parallel.to_pyodbc_url(url) if key == "mssql" and args.mssql_driver == "pyodbc" else url
    output: list[str] = []
    csv_rows: list[dict[str, Any]] = []
    if not args.probes_only:
        print("\n".join(HEADER))
        output.extend(HEADER)
        for key, url in urls.items():
            output.extend(bench_engine(key, url, args, csv_rows))
    if args.probes or args.probes_only:
        probe_lines = ["", "| Motor | Comprobación | Resultado |", "|---|---|---|"]
        for key, url in urls.items():
            probe_lines.extend(run_probes(key, url))
        print("\n".join(probe_lines))
        output.extend(probe_lines)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(f"{line}\n" for line in output), encoding="utf-8")
    if args.csv is not None and csv_rows:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(csv_rows[0]))
            writer.writeheader()
            writer.writerows(csv_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
