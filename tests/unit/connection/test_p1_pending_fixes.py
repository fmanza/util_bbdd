"""Hotfix v0.39.2 (P1 del plan de pendientes tras ``drivers-connections-audit``).

- F4: el aviso de TLS async sin verificar sale una vez por servidor, no en cada conexión.
- ``init_command`` propio de MariaDB llega a aiomysql (el por defecto ``SET NAMES utf8mb4`` sigue sin enviarse).
- ``trust_cert=True`` con pymssql avisa una vez de que no se aplica.
"""

from __future__ import annotations

import logging
import sys

from typing import Any
from unittest import mock

import pytest

from util_bbdd.connection._aiomysql import build_aiomysql_connect_kwargs
from util_bbdd.connection.config import MariaDBConnectionConfig
from util_bbdd.connection.mariadb.async_connection_mariadb import AsyncMariaDBConnection

NET = {"host": "h", "user": "u", "password": "p", "database": "d"}


async def _connect(
    host: str,
    port: int = 3306,
    ssl: Any = None,
    db: str | None = None,
    init_command: str | None = None,
    charset: str = "",
) -> None:
    return None


def _kwargs(**extra: Any) -> dict[str, Any]:
    return MariaDBConnectionConfig.from_params({**NET, **extra}).to_driver_kwargs()


def test_unverified_async_tls_warns_once_per_server(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            build_aiomysql_connect_kwargs(_kwargs(ssl=True), _connect)
        build_aiomysql_connect_kwargs(_kwargs(ssl=True, host="otro"), _connect)
    assert caplog.text.count("sin verificar") == 2  # h y otro


def test_mariadb_async_sends_custom_init_command() -> None:
    kwargs = AsyncMariaDBConnection._map_connect_kwargs(_kwargs(init_command="SET time_zone = '+00:00'"))
    assert kwargs["init_command"] == "SET time_zone = '+00:00'"


def test_mariadb_async_still_omits_default_init_command() -> None:
    kwargs = AsyncMariaDBConnection._map_connect_kwargs(_kwargs(charset="latin1"))
    assert "init_command" not in kwargs
    assert kwargs["charset"] == "latin1"


def test_pymssql_trust_cert_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    from util_bbdd.connection.sqlserver.connection_sqlserver import SQLServerConnection

    fake = mock.MagicMock()
    params = {**NET, "port": 1433, "trust_cert": True, "encryption": "optional"}
    with mock.patch.dict(sys.modules, {"pymssql": fake}), caplog.at_level(logging.WARNING):
        SQLServerConnection._connect_pymssql(dict(params))
        SQLServerConnection._connect_pymssql(dict(params))
    assert caplog.text.count("trust_cert") == 1
    assert "trust_cert" not in fake.connect.call_args.kwargs


def test_pymssql_without_trust_cert_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    from util_bbdd.connection.sqlserver.connection_sqlserver import SQLServerConnection

    with mock.patch.dict(sys.modules, {"pymssql": mock.MagicMock()}), caplog.at_level(logging.WARNING):
        SQLServerConnection._connect_pymssql({**NET, "port": 1433, "trust_cert": False})
    assert "trust_cert" not in caplog.text
