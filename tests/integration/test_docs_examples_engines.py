"""Los ejemplos de ``docs/examples/`` que necesitan un servidor, ejecutados contra el banco (docker-compose.bench.yml).

Cada ejemplo lee su conexión de ``UTIL_BBDD_EXAMPLE_*`` (sin ella explica cómo configurarla y termina: eso lo cubre
``tests/unit/test_docs_examples.py``). Aquí cada caso crea un schema propio (``zz_ex_*``; ``zz_util_bbdd_ex_*`` en
MariaDB, donde ``bench`` solo tiene permisos sobre ese prefijo) con las tablas que el ejemplo
espera, lo ejecuta tal cual en un proceso aparte (``tmp_path`` como directorio de trabajo, porque los ejemplos
escriben ficheros), comprueba su efecto y borra el schema. Las URL del banco: ``scripts/bench_env.example.sh``; sin la
de un motor, su caso se salta.
"""

from __future__ import annotations

import importlib.util
import os
import secrets
import subprocess
import sys

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine, make_url

pytestmark = pytest.mark.integration

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "docs" / "examples"

PG_URL = "UTIL_BBDD_TEST_POSTGRESQL_URL"
MARIADB_URL = "UTIL_BBDD_TEST_MARIADB_URL"
MYSQL_URL = "UTIL_BBDD_TEST_MYSQL_URL"
MSSQL_URL = "UTIL_BBDD_TEST_MSSQL_URL"
ORACLE_ADMIN_URL = "UTIL_BBDD_TEST_ORACLE_ADMIN_URL"
ORACLE_URL = "UTIL_BBDD_TEST_ORACLE_URL"


def _url(env_name: str) -> URL:
    value = os.environ.get(env_name)
    if not value:
        pytest.skip(f"{env_name} no definida (ver scripts/bench_env.example.sh)")
    return make_url(value)


def _render(url: URL) -> str:
    return url.render_as_string(hide_password=False)


def _requires_mariadb_driver() -> None:
    # SyncDatabaseManager("mariadb") usa MariaDB Connector/Python, no el PyMySQL de la URL del banco
    if importlib.util.find_spec("mariadb") is None:
        pytest.skip("paquete mariadb no instalado (driver del manager para mariadb)")


def _execute(engine: Engine, statements: Sequence[str]) -> None:
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def _run_example(name: str, cwd: Path, env: dict[str, str]) -> str:
    completed = subprocess.run(
        [sys.executable, str(EXAMPLES_DIR / f"{name}.py")],
        cwd=cwd,
        env={**os.environ, **env, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode == 0, f"{name}.py terminó con {completed.returncode}:\n{output[-4000:]}"
    assert "Traceback" not in output, f"{name}.py imprimió una traza:\n{output[-4000:]}"
    return output


# ── PostgreSQL ───────────────────────────────────────────────────────────────


@pytest.fixture
def pg_engine() -> Iterator[Engine]:
    engine = create_engine(_url(PG_URL))
    yield engine
    engine.dispose()


def test_migrate_postgresql_source(pg_engine: Engine, tmp_path: Path) -> None:
    schema = "zz_ex_pg"
    _execute(pg_engine, [f"DROP SCHEMA IF EXISTS {schema} CASCADE", f"CREATE SCHEMA {schema}"])
    try:
        _execute(
            pg_engine,
            [
                f"CREATE TABLE {schema}.zz_ex_clientes (id SERIAL PRIMARY KEY, nombre VARCHAR(50) NOT NULL)",
                f"CREATE TABLE {schema}.zz_ex_pedidos (id INTEGER PRIMARY KEY, "
                f"cliente_id INTEGER REFERENCES {schema}.zz_ex_clientes (id))",
            ],
        )
        _run_example(
            "migrate_postgresql_source",
            tmp_path,
            {"UTIL_BBDD_EXAMPLE_URL": _render(_url(PG_URL)), "UTIL_BBDD_EXAMPLE_SCHEMA": schema},
        )
        ddl = (tmp_path / f"{schema}_schema_mariadb.sql").read_text(encoding="utf-8")
        assert "zz_ex_clientes" in ddl
        assert "zz_ex_pedidos" in ddl
        assert "AUTO_INCREMENT" in ddl  # el SERIAL de PostgreSQL
    finally:
        _execute(pg_engine, [f"DROP SCHEMA IF EXISTS {schema} CASCADE"])


def test_bulk_insert_csv(pg_engine: Engine, tmp_path: Path) -> None:
    schema = "zz_ex_bulk"
    _execute(pg_engine, [f"DROP SCHEMA IF EXISTS {schema} CASCADE", f"CREATE SCHEMA {schema}"])
    try:
        url = _url(PG_URL).update_query_dict({"schema": schema})  # la tabla del ejemplo va a este schema
        output = _run_example("bulk_insert_csv", tmp_path, {"UTIL_BBDD_EXAMPLE_URL": _render(url)})
        with pg_engine.connect() as conn:
            assert conn.execute(text(f"SELECT COUNT(*) FROM {schema}.usuarios")).scalar() == 100
        assert "Filas insertadas (última operación): 100" in output
        assert (tmp_path / "audit_bulk" / "auditoria.csv").is_file()
    finally:
        _execute(pg_engine, [f"DROP SCHEMA IF EXISTS {schema} CASCADE"])


def test_migrate_views(pg_engine: Engine, tmp_path: Path) -> None:
    if importlib.util.find_spec("sqlglot") is None:
        pytest.skip("sqlglot no instalado (extra util_bbdd[migrate]): el ejemplo usa view_strategy='transpile'")
    schema = "zz_ex_views"
    _execute(pg_engine, [f"DROP SCHEMA IF EXISTS {schema} CASCADE", f"CREATE SCHEMA {schema}"])
    try:
        _execute(
            pg_engine,
            [
                f"CREATE TABLE {schema}.zz_ex_clientes (id INTEGER PRIMARY KEY, nombre VARCHAR(50) NOT NULL)",
                f"CREATE VIEW {schema}.zz_ex_clientes_a AS SELECT id, nombre FROM {schema}.zz_ex_clientes "
                "WHERE nombre ILIKE 'a%'",
            ],
        )
        output = _run_example(
            "migrate_views",
            tmp_path,
            {"UTIL_BBDD_EXAMPLE_URL": _render(_url(PG_URL)), "UTIL_BBDD_EXAMPLE_SCHEMA": schema},
        )
        assert "VIEW_REWRITTEN" in output  # ILIKE no existe en MySQL: la vista se reescribe
        assert "[syntax]: válida" in output
        ddl = (tmp_path / f"{schema}_views_mysql.sql").read_text(encoding="utf-8")
        assert "zz_ex_clientes_a" in ddl
        assert "ILIKE" not in ddl.upper()
    finally:
        _execute(pg_engine, [f"DROP SCHEMA IF EXISTS {schema} CASCADE"])


# ── SQL Server (y volcado PostgreSQL → SQL Server) ───────────────────────────


@pytest.fixture
def mssql_engine() -> Iterator[Engine]:
    engine = create_engine(_url(MSSQL_URL))
    yield engine
    engine.dispose()


def _drop_mssql_schema(engine: Engine, schema: str, tables: Sequence[str]) -> None:
    _execute(engine, [f"DROP TABLE IF EXISTS {schema}.{table}" for table in tables])
    _execute(engine, [f"IF SCHEMA_ID('{schema}') IS NOT NULL EXEC('DROP SCHEMA {schema}')"])


def test_migrate_sqlserver_source(mssql_engine: Engine, tmp_path: Path) -> None:
    schema, tables = "zz_ex_ss", ("zz_ex_pedidos", "zz_ex_clientes")
    _drop_mssql_schema(mssql_engine, schema, tables)
    _execute(mssql_engine, [f"EXEC('CREATE SCHEMA {schema}')"])
    try:
        _execute(
            mssql_engine,
            [
                f"CREATE TABLE {schema}.zz_ex_clientes (id INT IDENTITY PRIMARY KEY, nombre NVARCHAR(MAX) NOT NULL)",
                f"CREATE TABLE {schema}.zz_ex_pedidos (id INT PRIMARY KEY, "
                f"cliente_id INT REFERENCES {schema}.zz_ex_clientes (id))",
            ],
        )
        _run_example(
            "migrate_sqlserver_source",
            tmp_path,
            {"UTIL_BBDD_EXAMPLE_URL": _render(_url(MSSQL_URL)), "UTIL_BBDD_EXAMPLE_SCHEMA": schema},
        )
        ddl = (tmp_path / f"{schema}_schema_postgresql.sql").read_text(encoding="utf-8")
        assert "zz_ex_clientes" in ddl
        assert "zz_ex_pedidos" in ddl
        assert "TEXT" in ddl  # el NVARCHAR(MAX) de SQL Server
    finally:
        _drop_mssql_schema(mssql_engine, schema, tables)


def test_dump_data_export(pg_engine: Engine, mssql_engine: Engine, tmp_path: Path) -> None:
    schema, tables = "zz_ex_dump", ("zz_ex_items",)
    _execute(pg_engine, [f"DROP SCHEMA IF EXISTS {schema} CASCADE", f"CREATE SCHEMA {schema}"])
    _drop_mssql_schema(mssql_engine, schema, tables)
    _execute(mssql_engine, [f"EXEC('CREATE SCHEMA {schema}')"])
    try:
        _execute(
            pg_engine,
            [
                f"CREATE TABLE {schema}.zz_ex_items (id INTEGER PRIMARY KEY, nombre VARCHAR(50))",
                f"INSERT INTO {schema}.zz_ex_items SELECT g, 'item ' || g FROM generate_series(1, 250) AS g",
            ],
        )
        _execute(mssql_engine, [f"CREATE TABLE {schema}.zz_ex_items (id INT PRIMARY KEY, nombre NVARCHAR(50))"])
        output = _run_example(
            "dump_data_export",
            tmp_path,
            {
                "UTIL_BBDD_EXAMPLE_SOURCE_URL": _render(_url(PG_URL)),
                "UTIL_BBDD_EXAMPLE_TARGET_URL": _render(_url(MSSQL_URL)),
                "UTIL_BBDD_EXAMPLE_SOURCE_SCHEMA": schema,
                "UTIL_BBDD_EXAMPLE_TARGET_SCHEMA": schema,
            },
        )
        with mssql_engine.connect() as conn:
            assert conn.execute(text(f"SELECT COUNT(*) FROM {schema}.zz_ex_items")).scalar() == 250
        assert "[SUCCESS" in output
        assert list((tmp_path / "reports").glob("*.xlsx"))
    finally:
        _execute(pg_engine, [f"DROP SCHEMA IF EXISTS {schema} CASCADE"])
        _drop_mssql_schema(mssql_engine, schema, tables)


# ── MariaDB y MySQL ──────────────────────────────────────────────────────────


@pytest.fixture
def mariadb_engine() -> Iterator[Engine]:
    engine = create_engine(_url(MARIADB_URL))
    yield engine
    engine.dispose()


def test_migrate_mariadb_source(mariadb_engine: Engine, tmp_path: Path) -> None:
    _requires_mariadb_driver()
    database = "zz_util_bbdd_ex_ventas"  # bench solo tiene permisos sobre zz_util_bbdd_% (docker-compose.bench.yml)
    _execute(mariadb_engine, [f"DROP DATABASE IF EXISTS {database}", f"CREATE DATABASE {database}"])
    try:
        _execute(
            mariadb_engine,
            [
                f"CREATE TABLE {database}.zz_ex_clientes (id INT AUTO_INCREMENT PRIMARY KEY, "
                "estado ENUM('A','B') NOT NULL)",
                f"CREATE TABLE {database}.zz_ex_pedidos (id INT PRIMARY KEY, cliente_id INT, "
                f"FOREIGN KEY (cliente_id) REFERENCES {database}.zz_ex_clientes (id))",
            ],
        )
        _run_example(
            "migrate_mariadb_source",
            tmp_path,
            {"UTIL_BBDD_EXAMPLE_URL": _render(_url(MARIADB_URL)), "UTIL_BBDD_EXAMPLE_SCHEMA": database},
        )
        ddl = (tmp_path / f"{database}_schema_postgresql.sql").read_text(encoding="utf-8")
        assert "zz_ex_clientes" in ddl
        assert "zz_ex_pedidos" in ddl
        assert f'search_path = "{database}"' in ddl  # pg_schema del ejemplo
    finally:
        _execute(mariadb_engine, [f"DROP DATABASE IF EXISTS {database}"])


def test_update_auto_increment_example(mariadb_engine: Engine, tmp_path: Path) -> None:
    database = "zz_util_bbdd_ex_ai"
    _execute(mariadb_engine, [f"DROP DATABASE IF EXISTS {database}", f"CREATE DATABASE {database}"])
    try:
        _execute(
            mariadb_engine,
            [
                f"CREATE TABLE {database}.zz_ex_contador (id INT AUTO_INCREMENT PRIMARY KEY, v INT)",
                f"INSERT INTO {database}.zz_ex_contador (v) VALUES (1), (2), (3)",
            ],
        )
        url = _url(MARIADB_URL).set(database=database)  # el ejemplo genera el script del schema de la URL
        output = _run_example("update_auto_increment_example", tmp_path, {"UTIL_BBDD_EXAMPLE_URL": _render(url)})
        assert "zz_ex_contador" in output
        assert "AUTO_INCREMENT" in output
    finally:
        _execute(mariadb_engine, [f"DROP DATABASE IF EXISTS {database}"])


def test_migrate_mysql(tmp_path: Path) -> None:
    engine = create_engine(_url(MYSQL_URL))
    database = "zz_util_bbdd_ex_mysql"
    _execute(engine, [f"DROP DATABASE IF EXISTS {database}", f"CREATE DATABASE {database}"])
    try:
        _execute(
            engine,
            [
                f"CREATE TABLE {database}.zz_ex_clientes (id INT AUTO_INCREMENT PRIMARY KEY, "
                "estado ENUM('A','B') NOT NULL)",
                f"CREATE TABLE {database}.zz_ex_pedidos (id INT PRIMARY KEY, cliente_id INT, "
                f"FOREIGN KEY (cliente_id) REFERENCES {database}.zz_ex_clientes (id))",
            ],
        )
        _run_example(
            "migrate_mysql",
            tmp_path,
            {"UTIL_BBDD_EXAMPLE_URL": _render(_url(MYSQL_URL)), "UTIL_BBDD_EXAMPLE_SCHEMA": database},
        )
        ddl = (tmp_path / f"{database}_schema_postgresql.sql").read_text(encoding="utf-8")
        assert "zz_ex_clientes" in ddl
        assert "zz_ex_pedidos" in ddl
    finally:
        _execute(engine, [f"DROP DATABASE IF EXISTS {database}"])
        engine.dispose()


def test_mysql_variables_example(tmp_path: Path) -> None:
    output = _run_example("mysql_variables_example", tmp_path, {"UTIL_BBDD_EXAMPLE_URL": _render(_url(MYSQL_URL))})
    assert "Define UTIL_BBDD_EXAMPLE_URL" not in output  # el ejemplo 6 usó el servidor


# ── Oracle ───────────────────────────────────────────────────────────────────


def test_migrate_oracle_mariadb(tmp_path: Path) -> None:
    # En Oracle el schema es un usuario: se crea uno propio con SYSTEM para no leer los objetos de otras pruebas
    admin = create_engine(_url(ORACLE_ADMIN_URL))
    user, password = "ZZ_EX_MIGRATE", "Zz" + secrets.token_hex(12)
    drop = [f"BEGIN EXECUTE IMMEDIATE 'DROP USER {user} CASCADE'; EXCEPTION WHEN OTHERS THEN NULL; END;"]
    try:
        _execute(
            admin,
            [
                *drop,
                f'CREATE USER {user} IDENTIFIED BY "{password}" QUOTA UNLIMITED ON USERS',
                f"GRANT CREATE SESSION TO {user}",
                f"CREATE TABLE {user}.ZZ_EX_CLIENTES (ID NUMBER(10) PRIMARY KEY, NOMBRE VARCHAR2(50) NOT NULL)",
                f"CREATE TABLE {user}.ZZ_EX_PEDIDOS (ID NUMBER(10) PRIMARY KEY, "
                f"CLIENTE_ID NUMBER(10) REFERENCES {user}.ZZ_EX_CLIENTES (ID), IMPORTE NUMBER)",
            ],
        )
        url = _url(ORACLE_URL).set(username=user, password=password)
        output = _run_example(
            "migrate_oracle_mariadb",
            tmp_path,
            {"UTIL_BBDD_EXAMPLE_URL": _render(url), "UTIL_BBDD_EXAMPLE_SCHEMA": user},
        )
        ddl = (tmp_path / f"{user.lower()}_oracle_to_mariadb.sql").read_text(encoding="utf-8")
        assert "ZZ_EX_CLIENTES" in ddl
        assert "ZZ_EX_PEDIDOS" in ddl
        assert "DOUBLE" in ddl  # NUMBER sin precisión con number_fallback="DOUBLE"
        assert "Avisos WARNING" in output
    finally:
        _execute(admin, drop)
        admin.dispose()
