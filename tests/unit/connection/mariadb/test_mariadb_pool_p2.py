"""P2 M6/M7 de drivers-connections-audit (FASE 1, 2026-10-08): pools de MariaDB.

- **M6**: si ``mariadb.ConnectionPool`` rechaza ``init_command`` (drivers antiguos), el pool lo ejecuta a mano en cada
  ``get_connection()``; si fallaba, solo avisaba y entregaba una conexión con la sesión sin configurar. Ahora la
  devuelve al pool y lanza el error.
- **M7**: el pool async (aiomysql) no reciclaba conexiones (el de MySQL sí): las conexiones ociosas más allá de
  ``wait_timeout`` del servidor se entregaban muertas. ``pool_recycle`` (por defecto 3600 s) se pasa a
  ``aiomysql.create_pool``.
"""

from __future__ import annotations

import asyncio

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.connection.config import MariaDBPoolConfig
from util_bbdd.connection.mariadb import pool_connection_mariadb
from util_bbdd.connection.mariadb.async_pool_connection_mariadb import AsyncMariaDBPool

BASE: dict[str, Any] = {"host": "h", "user": "u", "password": "p", "database": "d"}


def _pool_rejecting_init_command(monkeypatch: pytest.MonkeyPatch, cursor: MagicMock) -> Any:
    connection = MagicMock()
    connection.cursor.return_value = cursor
    native_pool = MagicMock()
    native_pool.get_connection.return_value = connection

    def _connection_pool(**kwargs: Any) -> Any:
        if "init_command" in kwargs:
            raise TypeError("connect() got an unexpected keyword argument 'init_command'")
        return native_pool

    fake = MagicMock()
    fake.ConnectionPool = _connection_pool
    monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
    monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake)
    return pool_connection_mariadb.PoolConnection({**BASE, "pool_name": "p"}), connection


def test_manual_init_command_failure_is_raised_not_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("SET NAMES falló")
    pool, connection = _pool_rejecting_init_command(monkeypatch, cursor)

    with pytest.raises(RuntimeError, match="SET NAMES falló"):
        pool.get_connection()
    connection.close.assert_called_once()  # devuelta al pool, no entregada
    pool.close()


def test_manual_init_command_success_returns_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    pool, connection = _pool_rejecting_init_command(monkeypatch, MagicMock())

    assert pool.get_connection() is connection
    pool.close()


def test_pool_config_has_pool_recycle() -> None:
    assert MariaDBPoolConfig.from_params(BASE).pool_recycle == 3600
    assert MariaDBPoolConfig.from_params({**BASE, "pool_recycle": 600}).pool_recycle == 600


def test_async_pool_passes_pool_recycle_to_aiomysql(monkeypatch: pytest.MonkeyPatch) -> None:
    aiomysql = pytest.importorskip("aiomysql")
    received: dict[str, Any] = {}

    async def _create_pool(**kwargs: Any) -> Any:
        received.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(aiomysql, "create_pool", _create_pool)

    asyncio.run(AsyncMariaDBPool.create({**BASE, "pool_recycle": 600}))

    assert received["pool_recycle"] == 600
