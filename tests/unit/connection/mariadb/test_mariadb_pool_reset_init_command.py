"""Hotfix v0.40.3: el pool nativo de MariaDB reaplica ``init_command`` en cada ``get_connection()``.

``mariadb.ConnectionPool`` reinicia la sesión (``COM_RESET_CONNECTION``, ``pool_reset_connection=True`` por defecto) al
reutilizar una conexión y no vuelve a ejecutar ``init_command``: la sesión vuelve al charset del servidor. Contra MariaDB
10.3.10 con ``character_set_server=latin1`` (driver 1.1.14), el segundo uso de una conexión del pool tenía la sesión en
latin1 y la lectura del catálogo fallaba con ``SystemError`` (``UnicodeDecodeError`` en ``cursor.fetchrows``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.connection.mariadb import pool_connection_mariadb

BASE: dict[str, Any] = {"host": "h", "user": "u", "password": "p", "database": "d"}


def _pool_accepting_init_command(
    monkeypatch: pytest.MonkeyPatch, cursor: MagicMock, **params: Any
) -> tuple[Any, MagicMock]:
    connection = MagicMock()
    connection.cursor.return_value = cursor
    native_pool = MagicMock()
    native_pool.get_connection.return_value = connection
    fake = MagicMock()
    fake.ConnectionPool = lambda **kwargs: native_pool
    monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
    monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake)
    return pool_connection_mariadb.PoolConnection({**BASE, "pool_name": "p", **params}), connection


def test_init_command_is_reapplied_on_every_checkout(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = MagicMock()
    pool, _ = _pool_accepting_init_command(monkeypatch, cursor)

    pool.get_connection()
    pool.get_connection()

    assert [c.args[0] for c in cursor.execute.call_args_list] == ["SET NAMES utf8mb4", "SET NAMES utf8mb4"]
    pool.close()


def test_explicit_init_command_is_reapplied(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = MagicMock()
    init = "SET SESSION character_set_server = utf8mb4, NAMES utf8mb4"
    pool, _ = _pool_accepting_init_command(monkeypatch, cursor, init_command=init)

    pool.get_connection()

    cursor.execute.assert_called_once_with(init)
    pool.close()


def test_reapply_failure_returns_connection_to_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = MagicMock()
    cursor.execute.side_effect = RuntimeError("SET NAMES falló")
    pool, connection = _pool_accepting_init_command(monkeypatch, cursor)

    with pytest.raises(RuntimeError, match="SET NAMES falló"):
        pool.get_connection()
    connection.close.assert_called_once()
    pool.close()
