"""H1 (v0.41.2): una lectura de catálogo no deja abierta la transacción que ella misma abre (``use_pool=False``).

Antes, con la conexión única del manager: PostgreSQL quedaba ``idle in transaction`` y MySQL (REPEATABLE READ) no veía
una tabla creada desde fuera ni después de ``clear_cache()``. La transacción del usuario en la misma conexión se respeta.

SQL Server (H1-MS): ver la sección final. Requiere ``UTIL_BBDD_TEST_POSTGRESQL_URL`` / ``UTIL_BBDD_TEST_MYSQL_URL`` /
``UTIL_BBDD_TEST_MSSQL_URL`` (``scripts/bench_env.example.sh``).
"""

from __future__ import annotations

import asyncio
import os
import uuid

from typing import Any

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.metadata.model import Kind

pytestmark = pytest.mark.integration

PG_ENV = "UTIL_BBDD_TEST_POSTGRESQL_URL"
MYSQL_ENV = "UTIL_BBDD_TEST_MYSQL_URL"


def _params(env: str) -> dict[str, Any]:
    if not os.environ.get(env):
        pytest.skip(f"{env} no definida")
    url = make_url(os.environ[env])
    return {
        "host": url.host,
        "port": url.port,
        "user": url.username,
        "password": url.password,
        "database": url.database,
    }


def _admin(env: str) -> Any:
    if not os.environ.get(env):
        pytest.skip(f"{env} no definida")
    return create_engine(os.environ[env], isolation_level="AUTOCOMMIT")


def _pg_state(pid: int) -> str:
    with _admin(PG_ENV).connect() as conn:
        return str(conn.execute(text("SELECT state FROM pg_stat_activity WHERE pid = :p"), {"p": pid}).scalar())


def test_postgresql_catalog_read_leaves_no_open_transaction() -> None:
    manager = SyncDatabaseManager("postgresql", _params(PG_ENV), use_pool=False)
    try:
        manager.get_schema_metadata()
        assert _pg_state(manager.get_connection().info.backend_pid) == "idle"
    finally:
        manager.close()


def test_postgresql_async_catalog_read_leaves_no_open_transaction() -> None:
    async def run() -> str:
        manager = AsyncDatabaseManager("postgresql", _params(PG_ENV), use_pool=False)
        try:
            await manager.get_schema_metadata()
            connection = await manager.get_connection()
            return _pg_state(connection.get_server_pid())
        finally:
            await manager.close()

    assert asyncio.run(run()) == "idle"


def test_mysql_sees_external_ddl_after_clear_cache() -> None:
    table = f"zz_h1_{uuid.uuid4().hex[:8]}"
    manager = SyncDatabaseManager("mysql", _params(MYSQL_ENV), use_pool=False)
    try:
        manager.get_schema_metadata(kinds={Kind.TABLES})
        with _admin(MYSQL_ENV).connect() as conn:
            conn.execute(text(f"CREATE TABLE {table} (id INT)"))
        manager.clear_cache()
        assert table in {t.name for t in manager.get_schema_metadata(kinds={Kind.TABLES}).tables()}
    finally:
        manager.close()
        with _admin(MYSQL_ENV).connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))


@pytest.mark.parametrize("env, db_type", [(PG_ENV, "postgresql"), (MYSQL_ENV, "mysql")])
def test_user_transaction_on_the_shared_connection_survives_a_catalog_read(env: str, db_type: str) -> None:
    table = f"zz_h1_user_{uuid.uuid4().hex[:8]}"
    with _admin(env).connect() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT)"))
    manager = SyncDatabaseManager(db_type, _params(env), use_pool=False)
    try:
        connection = manager.get_connection()
        cursor = connection.cursor()
        cursor.execute(f"INSERT INTO {table} VALUES (1)")  # transacción del usuario, sin confirmar
        cursor.close()
        manager.get_schema_metadata()
        connection.commit()
        with _admin(env).connect() as conn:
            assert conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == 1
    finally:
        manager.close()
        with _admin(env).connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))


# --- SQL Server (H1-MS, v0.42.1) -------------------------------------------------------------------------------------
# pymssql, pyodbc y aioodbc dejan @@TRANCOUNT = 1 desde que conectan (pymssql abre BEGIN TRAN al conectar y tras cada
# commit/rollback; los ODBC trabajan con transacciones implícitas): no se puede saber si la transacción es del usuario,
# así que el ejecutor no hace rollback. Lo que importa de H1 se cumple igual con READ COMMITTED: la lectura no retiene
# bloqueos, no frena el DDL de otra sesión y el catálogo ve ese DDL tras clear_cache().

MSSQL_ENV = "UTIL_BBDD_TEST_MSSQL_URL"
_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"


def _mssql_params(driver: str) -> dict[str, Any]:
    params = _params(MSSQL_ENV)
    if driver == "pymssql":
        return params
    pyodbc = pytest.importorskip("pyodbc")
    if _ODBC_DRIVER not in pyodbc.drivers():
        pytest.skip(f"{_ODBC_DRIVER} no instalado")
    return {**params, "sql_server_driver": "pyodbc", "driver_name": _ODBC_DRIVER, "trust_cert": True}


def _mssql_locks(spid: int) -> list[Any]:
    with _admin(MSSQL_ENV).connect() as conn:
        sql = (
            "SELECT resource_type FROM sys.dm_tran_locks WHERE request_session_id = :s AND resource_type <> 'DATABASE'"
        )
        return list(conn.execute(text(sql), {"s": spid}).fetchall())


@pytest.mark.parametrize("driver", ["pymssql", "pyodbc"])
def test_sqlserver_catalog_read_holds_no_locks_and_sees_external_ddl(driver: str) -> None:
    table = f"zz_h1ms_{uuid.uuid4().hex[:8]}"
    with _admin(MSSQL_ENV).connect() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT)"))
    manager = SyncDatabaseManager("sqlserver", _mssql_params(driver), use_pool=False)
    try:
        manager.get_schema_metadata(kinds={Kind.TABLES, Kind.COLUMNS})
        cursor = manager.get_connection().cursor()
        cursor.execute("SELECT @@SPID")
        spid = int(cursor.fetchone()[0])
        cursor.close()
        assert _mssql_locks(spid) == []
        with _admin(MSSQL_ENV).connect() as conn:
            conn.execute(text("SET LOCK_TIMEOUT 3000"))
            conn.execute(text(f"ALTER TABLE {table} ADD extra INT"))  # sin bloqueo de la lectura anterior
            conn.execute(text(f"CREATE TABLE {table}_b (id INT)"))
        manager.clear_cache()
        assert f"{table}_b" in {t.name for t in manager.get_schema_metadata(kinds={Kind.TABLES}).tables()}
    finally:
        manager.close()
        with _admin(MSSQL_ENV).connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            conn.execute(text(f"DROP TABLE IF EXISTS {table}_b"))


@pytest.mark.parametrize("driver", ["pymssql", "pyodbc"])
def test_sqlserver_user_transaction_survives_a_catalog_read(driver: str) -> None:
    table = f"zz_h1ms_user_{uuid.uuid4().hex[:8]}"
    with _admin(MSSQL_ENV).connect() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT)"))
    manager = SyncDatabaseManager("sqlserver", _mssql_params(driver), use_pool=False)
    try:
        connection = manager.get_connection()
        cursor = connection.cursor()
        cursor.execute(f"INSERT INTO {table} VALUES (1)")  # transacción del usuario, sin confirmar
        cursor.close()
        manager.get_schema_metadata(kinds={Kind.TABLES})
        connection.commit()
        with _admin(MSSQL_ENV).connect() as conn:
            assert conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == 1
    finally:
        manager.close()
        with _admin(MSSQL_ENV).connect() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
