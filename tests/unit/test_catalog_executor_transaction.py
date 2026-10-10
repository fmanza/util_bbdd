"""H1 (v0.41.2): el ejecutor de catálogo termina la transacción que abre su lectura, y solo esa."""

from __future__ import annotations

import asyncio
import sqlite3

from types import SimpleNamespace
from typing import Any

import pytest

from util_bbdd.managers._catalog_executor import (
    AsyncManagerCatalogExecutor,
    ManagerCatalogExecutor,
    _in_transaction,
    register_driver_paramstyle,
)


@pytest.mark.parametrize(
    ("connection", "expected"),
    [
        (SimpleNamespace(info=SimpleNamespace(transaction_status=0)), False),  # psycopg 3 IDLE
        (SimpleNamespace(info=SimpleNamespace(transaction_status=2)), True),  # psycopg 3 INTRANS
        (SimpleNamespace(get_transaction_status=lambda: 0), False),  # psycopg2
        (SimpleNamespace(transaction_in_progress=True), True),  # python-oracledb
        (SimpleNamespace(is_in_transaction=lambda: False), False),  # asyncpg
        (SimpleNamespace(server_status=0x0002), False),  # PyMySQL: solo SERVER_STATUS_AUTOCOMMIT
        (SimpleNamespace(server_status=0x0003), True),  # PyMySQL: IN_TRANS
        (SimpleNamespace(), None),  # pyodbc, pymssql, jaydebeapi…: no se sabe
    ],
)
def test_in_transaction_by_driver(connection: Any, expected: bool | None) -> None:
    assert _in_transaction(connection) is expected


def test_in_transaction_with_sqlite3() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE t (id INTEGER)")
    connection.commit()
    assert _in_transaction(connection) is False
    connection.execute("INSERT INTO t VALUES (1)")
    assert _in_transaction(connection) is True


class _Connection:
    """Conexión DB-API mínima: la lectura abre una transacción si no había (como psycopg sin autocommit)."""

    def __init__(self, in_transaction: bool | None) -> None:
        self._known = in_transaction is not None
        self.in_tx = bool(in_transaction)
        self.rollbacks = 0

    @property
    def info(self) -> Any:
        return SimpleNamespace(transaction_status=2 if self.in_tx else 0) if self._known else None

    def cursor(self) -> Any:
        connection = self

        class _Cursor:
            description = (("x",),)

            def execute(self, *_: Any) -> None:
                connection.in_tx = True

            def fetchall(self) -> list[tuple[int]]:
                return [(1,)]

            def close(self) -> None:
                return None

        return _Cursor()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.in_tx = False


# El ejecutor resuelve el paramstyle por el módulo raíz del tipo de la conexión (el de este fichero de tests)
register_driver_paramstyle(_Connection.__module__.split(".")[0], "qmark")


@pytest.mark.parametrize(
    ("before", "rollbacks"),
    [(False, 1), (True, 0), (None, 0)],
    ids=["sin-transaccion-previa", "transaccion-del-usuario", "driver-sin-estado"],
)
def test_sync_executor_ends_only_its_own_transaction(before: bool | None, rollbacks: int) -> None:
    connection = _Connection(before)
    executor = ManagerCatalogExecutor(lambda: connection, lambda _c: None)

    assert executor.fetch_all("SELECT 1", {}) == [(1,)]
    assert connection.rollbacks == rollbacks


@pytest.mark.parametrize(("before", "rollbacks"), [(False, 1), (True, 0)])
def test_async_executor_ends_only_its_own_transaction(before: bool, rollbacks: int) -> None:
    connection = _Connection(before)

    async def provider() -> Any:
        return connection

    async def releaser(_c: Any) -> None:
        return None

    rows = asyncio.run(AsyncManagerCatalogExecutor(provider, releaser).fetch_all("SELECT 1", {}))

    assert rows == [(1,)]
    assert connection.rollbacks == rollbacks
