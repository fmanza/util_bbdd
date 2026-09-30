"""D1 paso 0: coste real de las consultas por tabla de los extractores de migrate frente a consultas por schema.

Por motor origen: crea N tablas (PK, FK a la anterior, índice, 5 columnas) y V vistas en un espacio aislado, mide
``MigrationPlanner.plan()`` contando las consultas del extractor, y mide la alternativa agrupada: las mismas consultas
de la librería sin el filtro por tabla/vista/rutina, una vez cada una. Uso (con las URLs del banco en el entorno):

    python .ai/sessions/2026-09-30-migrate-d1-extract-batching/v0/d1_baseline.py [N] [V]
"""

from __future__ import annotations

import json
import logging
import os
import re
import statistics
import sys
import time

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url

from util_bbdd import SyncDatabaseManager
from util_bbdd.migrate import MigrationPlanner

logging.disable(logging.CRITICAL)
_ARGS = [a for a in sys.argv[1:] if a.isdigit()]
N_TABLES = int(_ARGS[0]) if _ARGS else 200
N_VIEWS = int(_ARGS[1]) if len(_ARGS) > 1 else 20
RUNS = 3
NS = "zz_util_bbdd_d1"
ENV = {
    "mysql": "UTIL_BBDD_TEST_MYSQL_URL",
    "mariadb": "UTIL_BBDD_TEST_MARIADB_URL",
    "postgresql": "UTIL_BBDD_TEST_POSTGRESQL_URL",
    "sqlserver": "UTIL_BBDD_TEST_MSSQL_URL",
    "oracle": "UTIL_BBDD_TEST_ORACLE_URL",
}
TARGET = {"oracle": "postgresql"}  # destino cualquiera: el coste medido es el de extraer
# Filtros por objeto que la versión agrupada no tendría (WHERE ... AND x = <param>  /  WHERE x = <param> AND ...)
_OBJECT_PARAMS = ("table_name", "table", "view_name", "routine_name", "routine_type")
_PARAM = r"(?:%\((?:" + "|".join(_OBJECT_PARAMS) + r")\)s|:(?:" + "|".join(_OBJECT_PARAMS) + r"))"
_AND_FILTER = re.compile(r"\s+AND\s+[\w.\"\[\]]+\s*=\s*" + _PARAM, re.I)
_WHERE_FILTER = re.compile(r"WHERE\s+[\w.\"\[\]]+\s*=\s*" + _PARAM + r"\s+AND\s+", re.I)


def _url(engine: str, database: str | None = None) -> URL:
    url = make_url(os.environ[ENV[engine]])
    return url.set(database=database) if database else url


def _raw(url: URL, statements: list[str]) -> None:
    eng = create_engine(url, isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        cur = conn.connection.dbapi_connection.cursor()
        for statement in statements:
            try:
                cur.execute(statement)
            except Exception:  # noqa: BLE001 - limpieza tolerante
                if not statement.startswith(("DROP", "BEGIN", "IF")):
                    raise
    eng.dispose()


def _schema_objects(engine: str) -> list[str]:
    i, v, d, n = ("NUMBER(10)", "VARCHAR2(50)", "DATE", "NUMBER(10,2)") if engine == "oracle" else (
        "INT", "VARCHAR(50)", "DATE", "DECIMAL(10,2)")
    p = "ZZD1_" if engine == "oracle" else ""
    out: list[str] = []
    for k in range(N_TABLES):
        fk = f", CONSTRAINT {p}fk_{k} FOREIGN KEY (parent_id) REFERENCES {p}t{k - 1:03d} (id)" if k else ""
        out.append(f"CREATE TABLE {p}t{k:03d} (id {i} PRIMARY KEY, parent_id {i}, name {v}, created {d}, amount {n}{fk})")
        out.append(f"CREATE INDEX {p}ix_{k} ON {p}t{k:03d} (name)")
    out += [f"CREATE VIEW {p}v{k:03d} AS SELECT id, name FROM {p}t{k:03d}" for k in range(N_VIEWS)]
    return out


def _setup(engine: str) -> tuple[dict[str, Any], str]:
    base = _url(engine)
    params: dict[str, Any] = {"host": base.host, "port": base.port, "user": base.username, "password": base.password}
    if engine in ("mysql", "mariadb"):
        _raw(base, [f"DROP DATABASE IF EXISTS {NS}", f"CREATE DATABASE {NS}"])
        _raw(_url(engine, NS), _schema_objects(engine))
        return params | {"database": NS}, NS
    if engine == "sqlserver":
        _teardown(engine)
        _raw(base.set(database="master"), [f"CREATE DATABASE {NS}"])
        _raw(_url(engine, NS), _schema_objects(engine))
        return params | {"database": NS}, "dbo"
    if engine == "postgresql":
        _raw(base, [f"DROP SCHEMA IF EXISTS {NS} CASCADE", f"CREATE SCHEMA {NS}", f"SET search_path = {NS}"])
        _raw(base.set(query={"options": f"-csearch_path={NS}"}), _schema_objects(engine))
        return params | {"database": base.database}, NS
    _teardown(engine)
    _raw(base, _schema_objects(engine))
    return params | {"service_name": base.query.get("service_name")}, str(base.username).upper()


def _teardown(engine: str) -> None:
    base = _url(engine)
    if engine in ("mysql", "mariadb"):
        _raw(base, [f"DROP DATABASE IF EXISTS {NS}"])
    elif engine == "sqlserver":
        _raw(base.set(database="master"), [
            f"IF DB_ID('{NS}') IS NOT NULL BEGIN ALTER DATABASE {NS} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"DROP DATABASE {NS}; END"])
    elif engine == "postgresql":
        _raw(base, [f"DROP SCHEMA IF EXISTS {NS} CASCADE"])
    else:
        _raw(base, [
            "BEGIN FOR v IN (SELECT view_name FROM user_views WHERE view_name LIKE 'ZZD1%') LOOP "
            "EXECUTE IMMEDIATE 'DROP VIEW \"' || v.view_name || '\"'; END LOOP; END;",
            "BEGIN FOR t IN (SELECT table_name FROM user_tables WHERE table_name LIKE 'ZZD1%') LOOP "
            "EXECUTE IMMEDIATE 'DROP TABLE \"' || t.table_name || '\" CASCADE CONSTRAINTS'; END LOOP; END;"])


class CountingManager:
    """Envuelve el manager: cuenta y cronometra las consultas del extractor y guarda una muestra por SQL."""

    def __init__(self, manager: SyncDatabaseManager) -> None:
        self._manager = manager
        self.calls = 0
        self.seconds = 0.0
        self.samples: dict[str, dict[str, Any]] = {}

    def execute_custom_many(self, sql: str, params: dict[str, Any]) -> Any:
        self.calls += 1
        self.samples.setdefault(sql, dict(params))
        start = time.perf_counter()
        try:
            return self._manager.execute_custom_many(sql, params)
        finally:
            self.seconds += time.perf_counter() - start


def _batched_cost(manager: SyncDatabaseManager, samples: dict[str, dict[str, Any]]) -> tuple[float, int, list[str]]:
    """Ejecuta una vez cada SQL distinto sin su filtro por objeto: coste de la versión agrupada."""
    seconds, queries, unconvertible = 0.0, 0, []
    for sql, params in samples.items():
        stripped = _WHERE_FILTER.sub("WHERE ", _AND_FILTER.sub("", sql))
        remaining = {k: v for k, v in params.items() if k not in _OBJECT_PARAMS}
        if re.search(_PARAM, stripped):
            unconvertible.append(sql[:80])
            continue
        start = time.perf_counter()
        manager.execute_custom_many(stripped, remaining)
        seconds += time.perf_counter() - start
        queries += 1
    return seconds, queries, unconvertible


def main() -> None:
    results: dict[str, Any] = {"tables": N_TABLES, "views": N_VIEWS, "engines": {}}
    for engine in [e for e in os.environ.get("D1_ENGINES", ",".join(ENV)).split(",") if e]:
        print(f"== {engine}: creando {N_TABLES} tablas y {N_VIEWS} vistas…", flush=True)
        conn_params, schema = _setup(engine)
        manager = SyncDatabaseManager(engine, conn_params, use_pool=False)
        try:
            plan_times, extract_times, calls = [], [], 0
            counting = CountingManager(manager)
            for _ in range(RUNS):
                counting.calls, counting.seconds = 0, 0.0
                start = time.perf_counter()
                plan = MigrationPlanner(
                    source_engine=engine, target_engine=TARGET.get(engine, "oracle"), view_strategy="passthrough"
                ).plan(counting, schema)
                plan_times.append(time.perf_counter() - start)
                extract_times.append(counting.seconds)
                calls = counting.calls
            batched = [_batched_cost(manager, counting.samples) for _ in range(RUNS)]
        finally:
            manager.close()
            _teardown(engine)
        batched_seconds = statistics.median(b[0] for b in batched)
        row = {
            "tables_extracted": len(plan.tables),
            "views_extracted": len(plan.views),
            "queries_per_table_design": calls,
            "plan_seconds": round(statistics.median(plan_times), 3),
            "extract_seconds": round(statistics.median(extract_times), 3),
            "ms_per_query": round(1000 * statistics.median(extract_times) / calls, 2),
            "batched_queries": batched[0][1],
            "batched_seconds": round(batched_seconds, 3),
            "unconvertible": batched[0][2],
        }
        results["engines"][engine] = row
        print(json.dumps(row, ensure_ascii=False), flush=True)
    out = Path(__file__).with_name(f"results_{N_TABLES}{os.environ.get('D1_SUFFIX', '')}.json")
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"guardado en {out}")


if __name__ == "__main__":
    main()
