"""P1 Y2 y M3 de drivers-connections-audit (FASE 1, 2026-10-08): detección de charset en el catálogo.

- **Y2**: ``ManagerCatalogExecutor._resolve_executor`` decidía por el módulo de la conexión; con el pool de MySQL
  (``QueuePool`` de SQLAlchemy) la conexión es un proxy del módulo ``sqlalchemy`` y nunca usaba el ejecutor adaptativo.
- **M3**: ``AsyncManagerCatalogExecutor`` no detectaba el charset: en async (aiomysql, MariaDB y MySQL) el catálogo
  nunca aplicaba ``CONVERT`` aunque el diagnóstico lo pidiera.
"""

from __future__ import annotations

import asyncio

from typing import Any

from util_bbdd.managers._catalog_executor import AsyncManagerCatalogExecutor, ManagerCatalogExecutor
from util_bbdd.metadata._adaptive_executor import AdaptiveCatalogExecutor

PyMySQLConnection = type("Connection", (), {"__module__": "pymysql.connections"})
SAFairy = type("_ConnectionFairy", (), {"__module__": "sqlalchemy.pool.base"})


def test_pooled_pymysql_connection_uses_adaptive_executor() -> None:
    fairy = SAFairy()
    fairy.dbapi_connection = PyMySQLConnection()  # type: ignore[attr-defined]
    executor = ManagerCatalogExecutor(provider=lambda: fairy, releaser=lambda _conn: None)

    assert isinstance(executor._resolve_executor(fairy), AdaptiveCatalogExecutor)


# --- async (aiomysql) ---------------------------------------------------------------------------------------------

LATIN1_SESSION = {
    "SELECT @@character_set_server": "latin1",
    "SELECT @@character_set_database": "utf8mb4",
    "SELECT @@character_set_client": "latin1",
    "SELECT @@character_set_connection": "latin1",
    "SELECT @@collation_connection": "latin1_swedish_ci",
}
UTF8MB4_SESSION = {
    "SELECT @@character_set_server": "utf8mb4",
    "SELECT @@character_set_database": "utf8mb4",
    "SELECT @@character_set_client": "utf8mb4",
    "SELECT @@character_set_connection": "utf8mb4",
    "SELECT @@collation_connection": "utf8mb4_general_ci",
}


class _Cursor:
    def __init__(self, conn: _AioConnection) -> None:
        self._conn = conn
        self._sql = ""

    async def execute(self, sql: str, args: Any = None) -> None:
        self._sql = sql
        self._conn.executed.append(sql)

    async def fetchone(self) -> tuple[Any, ...] | None:
        if self._sql in self._conn.variables:
            return (self._conn.variables[self._sql],)
        if "SCHEMATA" in self._sql:
            return ("utf8mb4",)
        return ("ok",)

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return [("t1", "comentario")]

    async def close(self) -> None:
        return None


class _AioConnection:
    __module__ = "aiomysql.connection"

    def __init__(self, variables: dict[str, str]) -> None:
        self.variables = variables
        self.executed: list[str] = []

    async def cursor(self) -> _Cursor:
        return _Cursor(self)


_AioConnection.__module__ = "aiomysql.connection"

CATALOG_SQL = "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = :schema"


def _run_catalog(conn: _AioConnection, times: int = 1) -> list[str]:
    async def _provider() -> _AioConnection:
        return conn

    async def _releaser(_conn: Any) -> None:
        return None

    executor = AsyncManagerCatalogExecutor(provider=_provider, releaser=_releaser)

    async def _run() -> None:
        for _ in range(times):
            await executor.fetch_all(CATALOG_SQL, {"schema": "s"})

    asyncio.run(_run())
    return [sql for sql in conn.executed if "information_schema.TABLES WHERE TABLE_SCHEMA = %(schema)s" in sql]


def test_async_aiomysql_applies_convert_when_diagnosis_requires_it() -> None:
    catalog_sql = _run_catalog(_AioConnection(LATIN1_SESSION))

    assert len(catalog_sql) == 1
    assert "CONVERT(CAST(TABLE_COMMENT AS BINARY) USING utf8mb4)" in catalog_sql[0]


def test_async_aiomysql_reads_natively_when_charset_is_clean() -> None:
    catalog_sql = _run_catalog(_AioConnection(UTF8MB4_SESSION))

    assert "CONVERT" not in catalog_sql[0]


def test_async_charset_diagnosis_runs_once() -> None:
    conn = _AioConnection(LATIN1_SESSION)

    _run_catalog(conn, times=3)

    assert conn.executed.count("SELECT @@character_set_server") == 1
