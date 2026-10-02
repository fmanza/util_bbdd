#!/usr/bin/env python3
"""Banco de pruebas de rendimiento de ``util_bbdd.comparar.SchemaComparator.compare()`` contra motores reales.

Crea dos esquemas en el mismo servidor (``cmp_src`` y ``cmp_tgt``) y mide ``compare()`` entre ellos con todas las
opciones (tablas, columnas, índices, FKs, comentarios, vistas) sin y con ``include_routines``: el mejor tiempo de
``--repeat`` ejecuciones y el número de sentencias que llegan al driver (``before_cursor_execute``). Cada ejecución usa
Inspectors nuevos, así que no hay caché de reflexión entre repeticiones. También imprime el número de diferencias
encontradas, para que una optimización que cambie el resultado se vea en la misma tabla.

Esquema (N tablas por esquema, ``--tables``):
    t<i>(id PK, name VARCHAR(50) NOT NULL, ref FK → t0.id, [extra]) con índice en name y comentario de tabla
    v<i>: N/10 vistas sobre t<i>; f<i>: N/10 funciones
En ``cmp_tgt`` el 10 % de las tablas tiene una columna ``extra``, el 20 % de las vistas y de las funciones cambia: con
200 tablas, el resultado esperado son 20 tablas con diferencias, 40 diferencias de columna/comentario... y 20 vistas
modificadas (la definición incluye el nombre del esquema).

Subcomandos:
    setup       borra y crea ``cmp_src``/``cmp_tgt`` (esquemas en PostgreSQL y SQL Server, bases en MySQL/MariaDB, usuarios
                en Oracle) con N tablas
    run         mide compare() y escribe una tabla Markdown; con ``--out``, añade una línea JSON por medición
    teardown    borra ``cmp_src``/``cmp_tgt``

Credenciales: ``UTIL_BBDD_BENCH_PASSWORD`` (la de ``docker-compose.bench.yml``). Puertos: los del banco o
``UTIL_BBDD_BENCH_<MOTOR>_PORT``. Solo 127.0.0.1. **Apunta siempre a los contenedores del banco**: ``setup`` y
``teardown`` borran ``cmp_src``/``cmp_tgt`` con todo su contenido. Usuarios: ``root`` en MySQL/MariaDB (``bench`` solo
tiene permisos sobre su base), ``system`` en Oracle (crea los usuarios) y ``sa`` en SQL Server.

Uso:
    python scripts/bench_compare.py setup --engines postgresql,mssql,oracle --tables 200
    python scripts/bench_compare.py run --engines postgresql,mssql,oracle --repeat 3 --out bench_results/compare
    python scripts/bench_compare.py teardown
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import URL, Engine, create_engine, event, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.comparar import SchemaComparator

_log = logging.getLogger("bench_compare")

ENGINES: tuple[str, ...] = ("postgresql", "mysql", "mariadb", "mssql", "oracle")
MSSQL_DRIVERS: tuple[str, ...] = ("pymssql", "pyodbc")
HOST = "127.0.0.1"


@dataclass
class Measurement:
    """Una medición de ``compare()`` (el mejor tiempo de ``repeat`` ejecuciones)."""

    engine: str
    tables: int
    routines: bool
    seconds: float
    statements: int
    table_diffs: int
    leaf_diffs: int
    view_diffs: int
    routine_diffs: int


def _port(engine_key: str, default: int) -> int:
    return int(os.environ.get(f"UTIL_BBDD_BENCH_{engine_key.upper()}_PORT", default))


def make_url(engine_key: str, *, mssql_driver: str = "pymssql") -> URL:
    """URL del contenedor del banco para ``engine_key`` (siempre 127.0.0.1)."""
    pw = os.environ.get("UTIL_BBDD_BENCH_PASSWORD")
    if not pw:
        raise SystemExit("Define UTIL_BBDD_BENCH_PASSWORD (la de docker-compose.bench.yml)")
    if engine_key == "postgresql":
        return URL.create("postgresql+psycopg", "bench", pw, HOST, _port("postgres", 55432), "bench")
    if engine_key == "mysql":
        return URL.create("mysql+pymysql", "root", pw, HOST, _port("mysql", 53306), None)
    if engine_key == "mariadb":
        return URL.create("mariadb+pymysql", "root", pw, HOST, _port("mariadb", 53307), None)
    if engine_key == "mssql":
        if mssql_driver == "pyodbc":
            return URL.create(
                "mssql+pyodbc",
                "sa",
                pw,
                HOST,
                _port("mssql", 51433),
                "bench",
                query={"driver": "ODBC Driver 18 for SQL Server", "TrustServerCertificate": "yes"},
            )
        return URL.create("mssql+pymssql", "sa", pw, HOST, _port("mssql", 51433), "bench")
    if engine_key == "oracle":
        return URL.create(
            "oracle+oracledb", "system", pw, HOST, _port("oracle", 51521), None, query={"service_name": "FREEPDB1"}
        )
    raise SystemExit(f"Motor no soportado: {engine_key} (válidos: {', '.join(ENGINES)})")


def schemas(engine_key: str) -> tuple[str, str]:
    """Esquemas origen y destino (en Oracle, usuarios en mayúsculas)."""
    return ("CMP_SRC", "CMP_TGT") if engine_key == "oracle" else ("cmp_src", "cmp_tgt")


def ddl(engine_key: str, schema: str, *, tables: int, target: bool) -> list[str]:
    """Sentencias que crean las tablas, índices, comentarios, vistas y funciones de un esquema.

    ``target=True`` introduce las diferencias del destino: columna ``extra`` en el 10 % de las tablas y cambios en el
    20 % de las vistas y de las funciones.
    """
    varchar = "VARCHAR2(50)" if engine_key == "oracle" else "VARCHAR(50)"
    index_schema = f"{schema}." if engine_key == "oracle" else ""  # solo Oracle admite el esquema en el índice
    out: list[str] = []
    for i in range(tables):
        extra = f", extra {varchar}" if target and i % 10 == 0 else ""
        ref = f", ref INT REFERENCES {schema}.t0(id)" if i else ", ref INT"
        out.append(f"CREATE TABLE {schema}.t{i} (id INT PRIMARY KEY, name {varchar} NOT NULL{ref}{extra})")
        out.append(f"CREATE INDEX {index_schema}ix_t{i} ON {schema}.t{i}(name)")
        if engine_key in ("postgresql", "oracle"):
            out.append(f"COMMENT ON TABLE {schema}.t{i} IS 'tabla {i}'")
        elif engine_key in ("mysql", "mariadb"):
            out.append(f"ALTER TABLE {schema}.t{i} COMMENT = 'tabla {i}'")
    for i in range(max(tables // 10, 1)):
        columns = "id" if target and i % 5 == 0 else "id, name"
        out.append(f"CREATE VIEW {schema}.v{i} AS SELECT {columns} FROM {schema}.t{i}")
        value = i + (100 if target and i % 5 == 0 else 0)
        if engine_key == "postgresql":
            out.append(f"CREATE FUNCTION {schema}.f{i}() RETURNS int LANGUAGE sql AS 'select {value}'")
        elif engine_key in ("mysql", "mariadb"):
            out.append(f"CREATE FUNCTION {schema}.f{i}() RETURNS INT DETERMINISTIC RETURN {value}")
        elif engine_key == "mssql":
            out.append(f"CREATE FUNCTION {schema}.f{i}() RETURNS INT AS BEGIN RETURN {value} END")
        elif engine_key == "oracle":
            out.append(f"CREATE FUNCTION {schema}.f{i} RETURN NUMBER AS BEGIN RETURN {value}; END;")
    return out


def setup(engine: Engine, engine_key: str, *, tables: int) -> None:
    """Borra y crea ``cmp_src``/``cmp_tgt`` con ``tables`` tablas cada uno."""
    teardown(engine, engine_key)
    pw = os.environ["UTIL_BBDD_BENCH_PASSWORD"]
    with engine.connect() as conn:
        for target, schema in enumerate(schemas(engine_key)):
            if engine_key in ("mysql", "mariadb"):
                conn.exec_driver_sql(f"CREATE DATABASE {schema}")
            elif engine_key == "oracle":
                conn.exec_driver_sql(f'CREATE USER {schema} IDENTIFIED BY "{pw}" QUOTA UNLIMITED ON USERS')
            else:
                conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
            conn.commit()
            for statement in ddl(engine_key, schema, tables=tables, target=bool(target)):
                conn.exec_driver_sql(statement)
            conn.commit()
    _log.info("%s: %s y %s creados con %d tablas", engine_key, *schemas(engine_key), tables)


def teardown(engine: Engine, engine_key: str) -> None:
    """Borra ``cmp_src``/``cmp_tgt`` si existen (sin error si no)."""
    with engine.connect() as conn:
        for schema in schemas(engine_key):
            try:
                if engine_key in ("mysql", "mariadb"):
                    conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {schema}")
                elif engine_key == "postgresql":
                    conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
                elif engine_key == "oracle":
                    exists = conn.execute(text("SELECT COUNT(*) FROM all_users WHERE username = :u"), {"u": schema})
                    if exists.scalar():
                        conn.exec_driver_sql(f"DROP USER {schema} CASCADE")
                elif engine_key == "mssql":
                    _drop_mssql_schema(conn, schema)
                conn.commit()
            except SQLAlchemyError as exc:
                conn.rollback()
                _log.warning("teardown %s/%s: %s", engine_key, schema, exc)


def _drop_mssql_schema(conn: Any, schema: str) -> None:
    """SQL Server no tiene DROP SCHEMA … CASCADE: vistas, funciones, FKs y tablas antes que el esquema."""
    params = {"s": schema}
    for kind, query in (
        ("VIEW", "SELECT name FROM sys.views WHERE schema_id = SCHEMA_ID(:s)"),
        ("FUNCTION", "SELECT name FROM sys.objects WHERE type IN ('FN', 'IF', 'TF') AND schema_id = SCHEMA_ID(:s)"),
    ):
        for (name,) in conn.execute(text(query), params).all():
            conn.exec_driver_sql(f"DROP {kind} {schema}.{name}")
    fks = conn.execute(
        text("SELECT OBJECT_NAME(parent_object_id), name FROM sys.foreign_keys WHERE schema_id = SCHEMA_ID(:s)"),
        params,
    ).all()
    for table, fk in fks:
        conn.exec_driver_sql(f"ALTER TABLE {schema}.{table} DROP CONSTRAINT {fk}")
    for (table,) in conn.execute(text("SELECT name FROM sys.tables WHERE schema_id = SCHEMA_ID(:s)"), params).all():
        conn.exec_driver_sql(f"DROP TABLE {schema}.{table}")
    conn.exec_driver_sql(f"IF SCHEMA_ID('{schema}') IS NOT NULL DROP SCHEMA {schema}")


def measure(engine: Engine, engine_key: str, *, routines: bool, repeat: int) -> Measurement:
    """Mejor tiempo de ``repeat`` ejecuciones de compare() entre ``cmp_src`` y ``cmp_tgt``."""
    counter = {"n": 0}

    def count(*_args: Any, **_kwargs: Any) -> None:
        counter["n"] += 1

    source_schema, target_schema = schemas(engine_key)
    best: tuple[float, int, Any] | None = None
    event.listen(engine, "before_cursor_execute", count)
    try:
        for _ in range(max(repeat, 1)):
            counter["n"] = 0
            start = time.perf_counter()
            diff = SchemaComparator().compare(
                inspect(engine),
                inspect(engine),
                source_schema=source_schema,
                target_schema=target_schema,
                include_routines=routines,
            )
            elapsed = time.perf_counter() - start
            if best is None or elapsed < best[0]:
                best = (elapsed, counter["n"], diff)
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert best is not None
    elapsed, statements, diff = best
    tables = len(inspect(engine).get_table_names(schema=source_schema))
    return Measurement(
        engine=engine_key,
        tables=tables,
        routines=routines,
        seconds=round(elapsed, 3),
        statements=statements,
        table_diffs=len(diff.table_diffs),
        leaf_diffs=diff.total_leaf_differences,
        view_diffs=len(diff.view_diffs),
        routine_diffs=len(diff.routine_diffs),
    )


def to_markdown(results: list[Measurement]) -> str:
    """Tabla Markdown de las mediciones."""
    lines = [
        "| Motor | Tablas | Routines | Tiempo | Sentencias | Tablas con dif. | Dif. hoja | Vistas | Routines con dif. |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {m.engine} | {m.tables} | {'sí' if m.routines else 'no'} | {m.seconds:.2f} s | {m.statements} | "
        f"{m.table_diffs} | {m.leaf_diffs} | {m.view_diffs} | {m.routine_diffs} |"
        for m in results
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("setup", "run", "teardown"):
        p = sub.add_parser(name)
        p.add_argument("--engines", default=",".join(ENGINES))
        p.add_argument("--mssql-driver", choices=MSSQL_DRIVERS, default="pymssql")
        if name == "setup":
            p.add_argument("--tables", type=int, default=200)
        if name == "run":
            p.add_argument("--repeat", type=int, default=3)
            p.add_argument("--out", type=Path, help="directorio donde añadir results.jsonl")
    args = parser.parse_args(argv)

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")  # consola cp1252 en Windows
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    _log.setLevel(logging.INFO)

    results: list[Measurement] = []
    for engine_key in args.engines.split(","):
        engine = create_engine(make_url(engine_key, mssql_driver=args.mssql_driver))
        try:
            if args.cmd == "setup":
                setup(engine, engine_key, tables=args.tables)
            elif args.cmd == "teardown":
                teardown(engine, engine_key)
            else:
                results.extend(measure(engine, engine_key, routines=r, repeat=args.repeat) for r in (False, True))
        finally:
            engine.dispose()

    if args.cmd == "run":
        print(to_markdown(results))
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            with (args.out / "results.jsonl").open("a", encoding="utf-8") as fh:
                for m in results:
                    fh.write(json.dumps(asdict(m)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
