#!/usr/bin/env python3
"""Banco de rendimiento de la extracción de metadatos de ``util_bbdd`` contra los motores del banco (ADR-003).

Crea, por motor y volumen, un schema aislado con N tablas (PK, UK, FK a la tabla anterior, índice secundario), N/10
vistas y N/50 funciones + N/50 procedures, y mide cada flujo que lee el catálogo contando las sentencias en los dos
caminos de ejecución de la librería:

- ``SyncQueryExecutor`` (managers y adaptadores de ``metadata/``, ``migrate/``, ``doc/``, ``analysis/``; driver nativo).
- Eventos ``before/after_cursor_execute`` de SQLAlchemy (``Inspector``, ``comparar/``, ``dump/``, ``bulk/``).

Cada sentencia se clasifica como de catálogo por su texto y se agrupa por huella (literales y números sustituidos) para
ver los patrones N+1. Por medición: mediana de tiempos, tiempo de catálogo, pico de memoria (``tracemalloc``), nº de
consultas y las huellas más frecuentes y más lentas.

Flujos: ``manager_scan`` (listado + 5 lecturas por tabla con los managers), ``doc_html``, ``comparar``, ``migrate``,
``migrate_extract`` (solo la extracción de ``migrate``), ``dump`` (schema sobre sí mismo con tablas vacías) y ``bulk``
(INSERT de 10 filas).

Aislamiento: PostgreSQL ``zz_md_<N>`` (schema en la base ``bench``), MySQL/MariaDB/SQL Server bases
``zz_util_bbdd_md_<N>``, Oracle usuarios ``ZZ_MD_<N>`` (los crea ``system``), SQLite un fichero por volumen en
``UTIL_BBDD_BENCH_METADATA_SQLITE_DIR`` (por defecto ``<tmp>/util_bbdd_md_bench``).

Credenciales: ``UTIL_BBDD_BENCH_PASSWORD`` (la de ``docker-compose.bench.yml``; vale también codificada para URL).
Puertos: los del banco o ``UTIL_BBDD_BENCH_<MOTOR>_PORT``. Solo 127.0.0.1. **Apunta siempre a los contenedores del
banco**: ``setup`` y ``teardown`` crean y borran esos schemas, bases y usuarios.

Uso:
    python scripts/bench_metadata.py setup --engines postgresql,sqlserver --volumes 50,500
    python scripts/bench_metadata.py run --engines postgresql --volumes 50,500 --flows all --repeat 3
    python scripts/bench_metadata.py run --engines oracle --volumes 5000 --flows manager_scan --limit 20 --repeat 1
    python scripts/bench_metadata.py report > bench_results/metadata/tablas.md
    python scripts/bench_metadata.py teardown --engines all --volumes 50,500,5000

Origen: baseline de la sesión ``2026-10-03-metadata-centralization`` (``02_BASELINE_RENDIMIENTO.md``).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import statistics
import sys
import tempfile
import time
import tracemalloc

from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pandas as pd

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import URL, Engine, make_url

from util_bbdd.executors.sync_query_executor import SyncQueryExecutor

ENGINES = ("sqlite", "postgresql", "mysql", "mariadb", "sqlserver", "oracle")
HOST = "127.0.0.1"
SQLITE_DIR = Path(
    os.environ.get("UTIL_BBDD_BENCH_METADATA_SQLITE_DIR", Path(tempfile.gettempdir()) / "util_bbdd_md_bench")
)

CATALOG_RE = re.compile(
    r"information_schema|\b(all|user|dba)_[a-z_]+\b|dbms_metadata|pg_catalog|\bpg_[a-z_]+|sqlite_(master|schema)"
    r"|\bpragma|\bsys\.[a-z_]+|object_definition|objectproperty|object_id\(|schema_id\(|svv_|pg_table_def"
    r"|^\s*show\s|@@version|\bversion\(\)|serverproperty|v\$|nls_|current_schema|db_name\(\)|database\(\)"
    r"|has_table_privilege|session_privs|col_length|type_name\(",
    re.IGNORECASE,
)


def schema_name(engine: str, volume: int) -> str:
    if engine in ("mysql", "mariadb", "sqlserver"):
        return f"zz_util_bbdd_md_{volume}"
    if engine == "oracle":
        return f"ZZ_MD_{volume}"
    if engine == "postgresql":
        return f"zz_md_{volume}"
    return "main"


def _password() -> str:
    pw = os.environ.get("UTIL_BBDD_BENCH_PASSWORD")
    if not pw:
        raise SystemExit("Define UTIL_BBDD_BENCH_PASSWORD (la de docker-compose.bench.yml)")
    return unquote(pw)


def _port(key: str, default: int) -> int:
    return int(os.environ.get(f"UTIL_BBDD_BENCH_{key.upper()}_PORT", default))


def admin_url(engine: str) -> str:
    """URL del contenedor del banco con el usuario que crea y borra los objetos del banco (siempre 127.0.0.1)."""
    pw = _password()
    urls = {
        "postgresql": URL.create("postgresql+psycopg", "bench", pw, HOST, _port("postgres", 55432), "bench"),
        "mysql": URL.create("mysql+pymysql", "bench", pw, HOST, _port("mysql", 53306), "bench"),
        "mariadb": URL.create("mariadb+pymysql", "bench", pw, HOST, _port("mariadb", 53307), "bench"),
        "sqlserver": URL.create("mssql+pymssql", "sa", pw, HOST, _port("mssql", 51433), "bench"),
        "oracle": URL.create(
            "oracle+oracledb", "bench", pw, HOST, _port("oracle", 51521), None, query={"service_name": "FREEPDB1"}
        ),
    }
    if engine not in urls:
        raise SystemExit(f"Motor no soportado: {engine} (válidos: {', '.join(ENGINES)})")
    return urls[engine].render_as_string(hide_password=False)


def sa_url(engine: str, volume: int) -> str:
    """URL SQLAlchemy que apunta al schema del volumen (``search_path``, base de datos o usuario Oracle)."""
    if engine == "sqlite":
        return f"sqlite:///{(SQLITE_DIR / f'md_{volume}.db').as_posix()}"
    url = make_url(admin_url(engine))
    s = schema_name(engine, volume)
    if engine in ("mysql", "mariadb", "sqlserver"):
        url = url.set(database=s)
    elif engine == "oracle":
        url = url.set(username=s, password=_password())
    return url.render_as_string(hide_password=False)


def sa_engine(engine: str, volume: int) -> Engine:
    kwargs: dict[str, Any] = {}
    if engine == "postgresql":
        kwargs["connect_args"] = {"options": f"-csearch_path={schema_name(engine, volume)}"}
    return create_engine(sa_url(engine, volume), **kwargs)


def manager_args(engine: str, volume: int) -> tuple[str, dict[str, Any]]:
    """``(db_type, conn_params)`` para ``SyncDatabaseManager`` sobre el schema del volumen."""
    if engine == "sqlite":
        return "sqlite", {"database": str(SQLITE_DIR / f"md_{volume}.db")}
    url = make_url(sa_url(engine, volume))
    base = {"host": url.host, "port": url.port, "user": url.username, "password": url.password}
    if engine == "postgresql":
        return "postgresql", {**base, "database": url.database, "schema": schema_name(engine, volume)}
    if engine in ("mysql", "mariadb"):
        return engine, {**base, "database": url.database}
    if engine == "sqlserver":
        return "sqlserver", {**base, "database": url.database, "schema": "dbo"}
    return "oracle", {**base, "service_name": url.query.get("service_name", "FREEPDB1")}


def inspector_schema(engine: str, volume: int) -> str | None:
    if engine == "postgresql":
        return schema_name(engine, volume)
    if engine == "sqlserver":
        return "dbo"
    if engine in ("mysql", "mariadb"):
        return schema_name(engine, volume)
    if engine == "oracle":
        return schema_name(engine, volume).lower()
    return None


# ─── setup / teardown ────────────────────────────────────────────────────────


def _ddl_table(engine: str, i: int) -> list[str]:
    t = f"t{i:05d}"
    parent = f"t{i - 1:05d}" if i > 0 else None
    if engine == "oracle":
        cols = (
            f"id NUMBER(10) CONSTRAINT pk_{t} PRIMARY KEY, code VARCHAR2(30) NOT NULL CONSTRAINT uk_{t} UNIQUE, "
            f"parent_id NUMBER(10), name VARCHAR2(100), amount NUMBER(12,2), created_at DATE"
        )
    elif engine == "sqlite":
        cols = (
            "id INTEGER PRIMARY KEY, code VARCHAR(30) NOT NULL UNIQUE, parent_id INTEGER, name VARCHAR(100), "
            "amount NUMERIC(12,2), created_at DATE"
        )
    else:
        cols = (
            f"id INTEGER NOT NULL, code VARCHAR(30) NOT NULL, parent_id INTEGER, name VARCHAR(100), "
            f"amount NUMERIC(12,2), created_at DATE, CONSTRAINT pk_{t} PRIMARY KEY (id), CONSTRAINT uk_{t} UNIQUE (code)"
        )
    if parent:
        cols += f", CONSTRAINT fk_{t} FOREIGN KEY (parent_id) REFERENCES {parent}(id)"
    return [f"CREATE TABLE {t} ({cols})", f"CREATE INDEX ix_{t}_name ON {t}(name)"]


def _ddl_routines(engine: str, j: int) -> list[str]:
    f, p = f"f{j:04d}", f"p{j:04d}"
    if engine == "postgresql":
        return [
            f"CREATE FUNCTION {f}(x integer) RETURNS integer LANGUAGE sql AS 'SELECT x + 1'",
            f"CREATE PROCEDURE {p}(x integer) LANGUAGE plpgsql AS $$ BEGIN PERFORM x; END $$",
        ]
    if engine in ("mysql", "mariadb"):
        return [
            f"CREATE FUNCTION {f}(x INT) RETURNS INT DETERMINISTIC NO SQL RETURN x + 1",
            f"CREATE PROCEDURE {p}(IN x INT) NO SQL BEGIN DECLARE y INT; SET y = x; END",
        ]
    if engine == "sqlserver":
        return [
            f"CREATE FUNCTION dbo.{f}(@x INT) RETURNS INT AS BEGIN RETURN @x + 1 END",
            f"CREATE PROCEDURE dbo.{p} @x INT AS BEGIN SET NOCOUNT ON; SELECT @x END",
        ]
    if engine == "oracle":
        return [
            f"CREATE OR REPLACE FUNCTION {f}(x NUMBER) RETURN NUMBER IS BEGIN RETURN x + 1; END;",
            f"CREATE OR REPLACE PROCEDURE {p}(x NUMBER) IS y NUMBER; BEGIN y := x; END;",
        ]
    return []


def _create_container(engine: str, volume: int) -> None:
    s = schema_name(engine, volume)
    if engine == "sqlite":
        SQLITE_DIR.mkdir(parents=True, exist_ok=True)
        (SQLITE_DIR / f"md_{volume}.db").unlink(missing_ok=True)
        return
    if engine == "oracle":
        url = make_url(admin_url("oracle")).set(username="system", password=_password())
        stmts = [
            f'CREATE USER {s} IDENTIFIED BY "{_password()}" QUOTA UNLIMITED ON USERS',
            f"GRANT CREATE SESSION, CREATE TABLE, CREATE VIEW, CREATE PROCEDURE TO {s}",
        ]
        eng = create_engine(url)
    else:
        eng = create_engine(admin_url(engine), isolation_level="AUTOCOMMIT")
        stmts = {
            "postgresql": [f"CREATE SCHEMA {s}"],
            "mysql": [f"CREATE DATABASE {s}"],
            "mariadb": [f"CREATE DATABASE {s}"],
            "sqlserver": [f"CREATE DATABASE {s}"],
        }[engine]
    with eng.begin() as conn:
        for st in stmts:
            conn.execute(text(st))
    eng.dispose()


def setup(engine: str, volume: int) -> None:
    started = time.perf_counter()
    _create_container(engine, volume)
    eng = sa_engine(engine, volume)
    n_views = max(1, volume // 10)
    n_routines = max(1, volume // 50)
    skipped: list[str] = []
    with eng.connect() as conn:
        for i in range(volume):
            for st in _ddl_table(engine, i):
                conn.execute(text(st))
            if i % 200 == 199:
                conn.commit()
                print(f"  {engine} {volume}: {i + 1} tablas", flush=True)
        for j in range(n_views):
            conn.execute(text(f"CREATE VIEW v{j:04d} AS SELECT id, code, name FROM t{j * 10:05d}"))
        for j in range(n_routines):
            for st in _ddl_routines(engine, j):
                try:
                    conn.execute(text(st))
                except Exception as exc:  # p.ej. MySQL con binlog sin log_bin_trust_function_creators
                    conn.rollback()
                    skipped.append(f"{st.split('(')[0]}: {str(exc).splitlines()[0][:120]}")
        conn.commit()
    eng.dispose()
    print(f"setup {engine} {volume}: {time.perf_counter() - started:.1f}s; omitidas: {skipped[:3]}", flush=True)


def teardown(engine: str, volume: int) -> None:
    s = schema_name(engine, volume)
    if engine == "sqlite":
        (SQLITE_DIR / f"md_{volume}.db").unlink(missing_ok=True)
        return
    if engine == "oracle":
        url = make_url(admin_url("oracle")).set(username="system", password=_password())
        eng, st = create_engine(url), f"DROP USER {s} CASCADE"
    else:
        eng = create_engine(admin_url(engine), isolation_level="AUTOCOMMIT")
        st = {
            "postgresql": f"DROP SCHEMA IF EXISTS {s} CASCADE",
            "mysql": f"DROP DATABASE IF EXISTS {s}",
            "mariadb": f"DROP DATABASE IF EXISTS {s}",
            "sqlserver": f"DROP DATABASE IF EXISTS {s}",
        }[engine]
    with eng.begin() as conn:
        if engine == "sqlserver":
            conn.execute(
                text(f"IF DB_ID('{s}') IS NOT NULL ALTER DATABASE {s} SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
            )
        conn.execute(text(st))
    eng.dispose()
    print(f"teardown {engine} {volume}", flush=True)


# ─── contador de consultas ───────────────────────────────────────────────────


class QueryCounter:
    """Cuenta y cronometra sentencias de los dos caminos de ejecución de la librería."""

    _NUM = re.compile(r"\b\d+\b")
    _STR = re.compile(r"'(?:[^']|'')*'")
    _WS = re.compile(r"\s+")

    def __init__(self) -> None:
        self.reset()
        self._installed = False

    def reset(self) -> None:
        self.total = 0
        self.catalog = 0
        self.catalog_seconds = 0.0
        self.other_seconds = 0.0
        self.fingerprints: Counter[str] = Counter()
        self.fp_seconds: Counter[str] = Counter()

    def _record(self, sql: str, seconds: float) -> None:
        self.total += 1
        if CATALOG_RE.search(sql or ""):
            self.catalog += 1
            self.catalog_seconds += seconds
            fp = self._WS.sub(" ", self._NUM.sub("N", self._STR.sub("'?'", sql))).strip()[:160]
            self.fingerprints[fp] += 1
            self.fp_seconds[fp] += seconds
        else:
            self.other_seconds += seconds

    def install(self) -> None:
        if self._installed:
            return
        counter = self
        original = SyncQueryExecutor._execute_sql_with_optional_params

        def wrapped(cursor: Any, sql: str, params: Any) -> None:
            t0 = time.perf_counter()
            try:
                return original(cursor, sql, params)
            finally:
                counter._record(str(sql), time.perf_counter() - t0)

        SyncQueryExecutor._execute_sql_with_optional_params = staticmethod(wrapped)  # type: ignore[method-assign]

        @event.listens_for(Engine, "before_cursor_execute")
        def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
            conn.info.setdefault("md_t0", []).append(time.perf_counter())

        @event.listens_for(Engine, "after_cursor_execute")
        def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
            t0 = conn.info["md_t0"].pop()
            counter._record(statement, time.perf_counter() - t0)

        self._installed = True

    def snapshot(self) -> dict[str, Any]:
        return {
            "queries_total": self.total,
            "queries_catalog": self.catalog,
            "catalog_seconds": round(self.catalog_seconds, 3),
            "other_seconds": round(self.other_seconds, 3),
            "top_catalog_fingerprints": self.fingerprints.most_common(8),
            "slowest_catalog_fingerprints": [
                (fp, round(t, 3), self.fingerprints[fp]) for fp, t in self.fp_seconds.most_common(5)
            ],
        }


COUNTER = QueryCounter()


# ─── flujos ──────────────────────────────────────────────────────────────────


def _manager(engine: str, volume: int) -> Any:
    from util_bbdd import SyncDatabaseManager

    db_type, params = manager_args(engine, volume)
    return SyncDatabaseManager(db_type, params, use_pool=False)


def _first(row: Any) -> str:
    if isinstance(row, dict):
        return str(next(iter(row.values())))
    if isinstance(row, (list, tuple)):
        return str(row[0])
    return str(row)


def flow_manager_scan(engine: str, volume: int, limit: int | None) -> dict[str, Any]:
    """Patrón de acceso de ``doc``/``analysis``: listado + 5 lecturas por tabla (columnas, índices, PK, FK, UK)."""
    mgr = _manager(engine, volume)
    try:
        tables = [_first(r) for r in mgr.get_tables()]
        mgr.get_views()
        mgr.get_routines()
        sample = tables[:limit] if limit else tables
        for t in sample:
            mgr.get_columns(t)
            mgr.get_indices(t)
            mgr.get_primary_keys(t)
            mgr.get_foreign_keys(t)
            mgr.get_unique_constraints(t)
        return {"tables_listed": len(tables), "tables_scanned": len(sample)}
    finally:
        mgr.close()


def flow_doc_html(engine: str, volume: int, limit: int | None) -> dict[str, Any]:
    from util_bbdd.doc import DatabaseDocumentation

    mgr = _manager(engine, volume)
    out = Path(tempfile.mkdtemp(prefix="md_doc_"))
    try:
        doc = DatabaseDocumentation(
            db_manager=mgr,
            directorio_salida=out,
            fichero_salida=Path(f"md_{engine}_{volume}"),
            imprimir={
                "tablas": {"imprimir_tablas": True},
                "vistas": {"imprimir_vistas": True},
                "rutinas": {"imprimir_procedures": True, "imprimir_functions": True},
                "grafo": {"enabled": False},
            },
            formatos=["html"],
        )
        doc.generate()
        return {"tables": len(doc.tablas), "views": len(doc.vistas), "routines": len(doc.rutinas)}
    finally:
        mgr.close()


def flow_comparar(engine: str, volume: int, limit: int | None) -> dict[str, Any]:
    from util_bbdd.comparar import SchemaComparator

    eng = sa_engine(engine, volume)
    try:
        s = inspector_schema(engine, volume)
        diff = SchemaComparator().compare(
            inspect(eng), inspect(eng), source_schema=s, target_schema=s, include_routines=engine != "sqlite"
        )
        return {"has_differences": bool(getattr(diff, "has_differences", False))}
    finally:
        eng.dispose()


def flow_migrate(engine: str, volume: int, limit: int | None) -> dict[str, Any]:
    from util_bbdd.migrate import MigrationPlanner

    if engine == "sqlite":
        return {"skipped": "sqlite no es motor origen de migrate"}
    target = "mariadb" if engine == "postgresql" else "postgresql"
    mgr = _manager(engine, volume)
    try:
        schema = {"sqlserver": "dbo", "oracle": schema_name(engine, volume)}.get(engine, schema_name(engine, volume))
        plan = MigrationPlanner(source_engine=engine, target_engine=target).plan(mgr, schema)
        return {"target": target, "tables": len(getattr(plan, "tables", []) or [])}
    finally:
        mgr.close()


def flow_migrate_extract(engine: str, volume: int, limit: int | None) -> dict[str, Any]:
    """Solo la extracción de ``migrate`` (tablas, vistas, routines), sin transpilar vistas (H-14 es cuadrático)."""
    from util_bbdd.migrate import extractors as ex

    classes = {
        "oracle": ex.oracle.OracleSchemaExtractor,
        "postgresql": ex.postgresql.PostgreSQLSchemaExtractor,
        "sqlserver": ex.sqlserver.SQLServerSchemaExtractor,
        "mariadb": ex.mariadb.MariaDBSchemaExtractor,
        "mysql": ex.mysql.MySQLSchemaExtractor,
    }
    if engine not in classes:
        return {"skipped": f"{engine} no es motor origen de migrate"}
    mgr = _manager(engine, volume)
    try:
        schema = {"sqlserver": "dbo"}.get(engine, schema_name(engine, volume))
        extractor = classes[engine](mgr)
        tables = extractor.extract(schema)
        views = extractor.extract_views(schema)
        routines = extractor.extract_routines(schema)
        return {"tables": len(tables), "views": len(views), "routines": len(routines)}
    finally:
        mgr.close()


def flow_dump(engine: str, volume: int, limit: int | None) -> dict[str, Any]:
    """Volcado de un schema sobre sí mismo con tablas vacías: aísla el coste de introspección y de constraints."""
    from util_bbdd.dump import DumpConfig, DumpOrchestrator

    src, dst = sa_engine(engine, volume), sa_engine(engine, volume)
    out = Path(tempfile.mkdtemp(prefix="md_dump_"))
    try:
        s = inspector_schema(engine, volume)
        cfg = DumpConfig(source_engine=src, target_engine=dst, source_schema=s, target_schema=s, output_dir=out)
        result = DumpOrchestrator(cfg).run()
        return {"tables": len(result.table_results), "constraints": len(result.constraint_results)}
    finally:
        src.dispose()
        dst.dispose()


def flow_bulk(engine: str, volume: int, limit: int | None) -> dict[str, Any]:
    """Un INSERT de 10 filas en una tabla: coste fijo de introspección por operación de ``BulkCrud``."""
    from util_bbdd.bulk import BulkCrud

    eng = sa_engine(engine, volume)
    try:
        df = pd.DataFrame(
            {
                "id": range(1, 11),
                "code": [f"c{k}" for k in range(10)],
                "parent_id": [None] * 10,
                "name": ["x"] * 10,
                "amount": [1.5] * 10,
                "created_at": [pd.Timestamp("2026-01-01").date()] * 10,
            }
        )
        crud = BulkCrud(eng, warn_if_audit_disabled=False)
        crud.bulk_insert_from_df(df, "t00001", generar_sql=False)
        crud.bulk_delete_from_df(df[["id"]], "t00001", generar_sql=False) if hasattr(
            crud, "bulk_delete_from_df"
        ) else None
        return {}
    finally:
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM t00001"))
        eng.dispose()


FLOWS = {
    "manager_scan": flow_manager_scan,
    "doc_html": flow_doc_html,
    "comparar": flow_comparar,
    "migrate": flow_migrate,
    "migrate_extract": flow_migrate_extract,
    "dump": flow_dump,
    "bulk": flow_bulk,
}


@contextmanager
def _quiet_logs():
    root = logging.getLogger()
    level = root.level
    root.setLevel(logging.ERROR)
    logging.getLogger("util_bbdd").setLevel(logging.ERROR)
    try:
        yield
    finally:
        root.setLevel(level)


def run_flow(name: str, engine: str, volume: int, repeat: int, limit: int | None) -> dict[str, Any]:
    COUNTER.install()
    runs: list[dict[str, Any]] = []
    info: dict[str, Any] = {}
    error: str | None = None
    for _ in range(repeat):
        COUNTER.reset()
        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            with _quiet_logs():
                info = FLOWS[name](engine, volume, limit)
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:300] if str(exc) else ''}"
        elapsed = time.perf_counter() - t0
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        runs.append({"seconds": round(elapsed, 3), "peak_mb": round(peak / 2**20, 1), **COUNTER.snapshot()})
        if error:
            break
    best = runs[-1]
    return {
        "flow": name,
        "engine": engine,
        "volume": volume,
        "limit": limit,
        "repeat": len(runs),
        "median_seconds": round(statistics.median(r["seconds"] for r in runs), 3),
        "median_catalog_seconds": round(statistics.median(r["catalog_seconds"] for r in runs), 3),
        "peak_mb": max(r["peak_mb"] for r in runs),
        "queries_total": best["queries_total"],
        "queries_catalog": best["queries_catalog"],
        "top_catalog_fingerprints": best["top_catalog_fingerprints"],
        "slowest_catalog_fingerprints": best["slowest_catalog_fingerprints"],
        "info": info,
        "error": error,
    }


VOLUMES = (50, 500, 5000)
REPORT_FLOWS = ("manager_scan", "doc_html", "comparar", "migrate", "migrate_extract", "dump", "bulk")


def _cell(d: dict | None) -> str:
    if d is None:
        return "—"
    if d.get("info", {}).get("skipped"):
        return "n/a"
    if d.get("error"):
        return f"error: {d['error'][:40]}"
    sample = f" (muestra {d['limit']})" if d.get("limit") else ""
    return (
        f"{d['queries_catalog']:,} · {d['median_catalog_seconds']:.2f} / {d['median_seconds']:.2f} s{sample}".replace(
            ",", "."
        )
    )


def report(results: Path) -> None:
    """Tablas Markdown por flujo (motor × volumen) a partir de ``<results>/*.json``.

    Celda: ``consultas de catálogo · tiempo de catálogo / tiempo total``; ``muestra N`` si ``manager_scan`` recorrió solo
    N tablas.
    """
    data = {}
    for f in results.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        data[(d["flow"], d["engine"], d["volume"])] = d
    for flow in REPORT_FLOWS:
        if not any(k[0] == flow for k in data):
            continue
        print(f"\n#### `{flow}`\n")
        print("| Motor | 50 tablas | 500 tablas | 5000 tablas |")
        print("|---|---|---|---|")
        for engine in ENGINES:
            cells = [_cell(data.get((flow, engine, v))) for v in VOLUMES]
            if all(c == "—" for c in cells):
                continue
            print(f"| {engine} | " + " | ".join(cells) + " |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["setup", "run", "teardown", "report"])
    ap.add_argument("--engines", default="sqlite")
    ap.add_argument("--volumes", default="50")
    ap.add_argument("--flows", default="all")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="tablas recorridas en manager_scan (muestra para N grande)")
    ap.add_argument("--out", type=Path, default=Path("bench_results") / "metadata")
    a = ap.parse_args(argv)
    engines = ENGINES if a.engines == "all" else tuple(a.engines.split(","))
    volumes = [int(v) for v in a.volumes.split(",")]
    flows = list(FLOWS) if a.flows == "all" else a.flows.split(",")
    if a.command == "report":
        report(a.out)
        return 0
    for engine in engines:
        for volume in volumes:
            if a.command == "setup":
                setup(engine, volume)
            elif a.command == "teardown":
                teardown(engine, volume)
            else:
                a.out.mkdir(parents=True, exist_ok=True)
                for flow in flows:
                    res = run_flow(flow, engine, volume, a.repeat, a.limit)
                    path = a.out / f"{engine}_{volume}_{flow}.json"
                    path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
                    print(
                        f"{engine:10} {volume:5} {flow:13} t={res['median_seconds']:8.2f}s "
                        f"cat={res['queries_catalog']:6} tot={res['queries_total']:6} "
                        f"tcat={res['median_catalog_seconds']:7.2f}s mem={res['peak_mb']:6.1f}MB {res['error'] or ''}",
                        flush=True,
                    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
