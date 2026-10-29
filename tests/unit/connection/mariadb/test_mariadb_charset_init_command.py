"""MariaDB: ``charset``, ``init_command`` y ``encoding_errors`` frente a lo que admiten los drivers reales.

Comprobado contra el banco (MariaDB 11.4, MariaDB Connector/Python 1.1.14, la última publicada):

- ``mariadb.connect`` y ``mariadb.ConnectionPool`` rechazan ``charset`` y ``encoding_errors`` (``TypeError``) y solo
  admiten sesiones utf8mb4: ``SET NAMES latin1`` → ``ProgrammingError: Character set 'latin1' is not supported``.
- v0.35.6 hizo el ``init_command`` por defecto ``SET NAMES <charset>``: con ``charset="latin1"`` la conexión sync
  dejaba de abrirse (regresión). En sync la sesión es siempre ``SET NAMES utf8mb4``; ``charset`` solo lo usa aiomysql
  (async).
- ``encoding_errors`` no lo aplica ningún driver. Hasta 4.x se aceptaba con ``FutureWarning`` y no se enviaba; desde
  5.0.0 (U-8.6) no es un parámetro del motor y se descarta sin aviso, como cualquier parámetro no declarado.
"""

from __future__ import annotations

import warnings

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd._drivers import get_db_type_info
from util_bbdd.connection import build_conn_params
from util_bbdd.connection.config import MariaDBConnectionConfig
from util_bbdd.connection.mariadb import pool_connection_mariadb
from util_bbdd.connection.mariadb.async_connection_mariadb import AsyncMariaDBConnection
from util_bbdd.connection.mariadb.connection_mariadb import MariaDBConnection
from util_bbdd.connection.params import ConnectionParamsManager

BASE: dict[str, Any] = {"host": "h", "user": "u", "password": "p", "database": "d"}


def test_default_init_command_is_utf8mb4_whatever_the_charset() -> None:
    config = MariaDBConnectionConfig.from_params({**BASE, "charset": "latin1"})

    assert config.charset == "latin1"
    assert config.init_command == "SET NAMES utf8mb4"


def test_explicit_init_command_wins() -> None:
    config = MariaDBConnectionConfig.from_params({**BASE, "init_command": "SET time_zone = '+00:00'"})

    assert config.init_command == "SET time_zone = '+00:00'"


@pytest.mark.parametrize("charset", ["utf8mb4; DROP TABLE t", "../../etc/passwd", "utf8 mb4", "latin1'"])
def test_invalid_charset_is_rejected(charset: str) -> None:
    with pytest.raises(ValueError, match="charset"):
        MariaDBConnectionConfig.from_params({**BASE, "charset": charset})


def test_encoding_errors_is_no_longer_a_parameter() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        config = MariaDBConnectionConfig.from_params({**BASE, "encoding_errors": "strict"})
        built = build_conn_params("mariadb", **BASE, encoding_errors="replace")

    assert not hasattr(config, "encoding_errors")
    assert "encoding_errors" not in config.to_driver_kwargs()
    assert "encoding_errors" not in built
    assert "encoding_errors" not in ConnectionParamsManager.param_kinds("mariadb")
    params = get_db_type_info("mariadb")["connection_params"]
    declared = {param["name"] for param in params["optional"]} | set(params["kinds"])
    assert "encoding_errors" not in declared


def test_sync_connect_sends_only_kwargs_the_driver_accepts(monkeypatch: pytest.MonkeyPatch) -> None:
    mariadb = pytest.importorskip("mariadb")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(mariadb, "connect", lambda **kwargs: calls.append(kwargs) or "conn")

    MariaDBConnection.connect({**BASE, "charset": "latin1"})

    assert len(calls) == 1  # sin TypeError ni reintentos
    assert "charset" not in calls[0]
    assert "encoding_errors" not in calls[0]
    assert calls[0]["init_command"] == "SET NAMES utf8mb4"


def test_pool_sends_only_kwargs_the_driver_accepts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    fake = MagicMock()
    fake.ConnectionPool = lambda **kwargs: calls.append(kwargs) or MagicMock()
    monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
    monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake)

    pool_connection_mariadb.PoolConnection({**BASE, "pool_name": "p"}).close()

    assert len(calls) == 1
    assert "charset" not in calls[0]
    assert "encoding_errors" not in calls[0]
    assert calls[0]["init_command"] == "SET NAMES utf8mb4"


def test_async_aiomysql_still_receives_charset() -> None:
    sanitized = ConnectionParamsManager.sanitize_for_connection("mariadb", {**BASE, "charset": "latin1"})

    assert AsyncMariaDBConnection._map_connect_kwargs(sanitized)["charset"] == "latin1"
