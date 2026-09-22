"""Tests de regresión CNX-01 (AUDIT_CODE 2026-09-22).

``PoolConnection.__create_pool()`` construía el ``conninfo`` de psycopg por interpolación
f-string sin URL-encoding: un ``user``/``password``/``database`` con caracteres reservados de
URI (``/``, ``#``, ``%``, espacios) se parseaba mal o cambiaba el destino real de la conexión.
"""

from __future__ import annotations

import logging

from typing import Any, cast
from urllib.parse import unquote, urlsplit

import pytest

from util_bbdd.connection.postgresql import pool_connection_postgresql


class _FakePsycopgPool:
    """Captura el conninfo pasado por PoolConnection sin conectar a una BD real."""

    last_conninfo: str | None = None

    def __init__(self, *, conninfo: str, **_kwargs: Any) -> None:
        _FakePsycopgPool.last_conninfo = conninfo
        self.wait_called = False

    def wait(self, timeout: float | None = None) -> None:
        self.wait_called = True


def _build_pool(monkeypatch: pytest.MonkeyPatch, conn_params: dict[str, Any]) -> str:
    monkeypatch.setattr(pool_connection_postgresql, "PsycopgConnectionPool", _FakePsycopgPool)

    pool = object.__new__(pool_connection_postgresql.PoolConnection)
    pool.logger = logging.getLogger(__name__)
    pool.pool_size = 5
    pool.pool_timeout = 30
    pool.max_idle = 300
    pool.conn_params = cast(dict[str, "str | int | bool"], conn_params)

    pool._PoolConnection__create_pool()  # type: ignore[attr-defined]

    assert _FakePsycopgPool.last_conninfo is not None
    return _FakePsycopgPool.last_conninfo


def test_conninfo_url_encodes_password_with_reserved_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    conninfo = _build_pool(
        monkeypatch,
        {"user": "app_user", "password": "p@ss/word#1", "host": "localhost", "port": 5432, "database": "mydb"},
    )

    parsed = urlsplit(conninfo)
    assert unquote(parsed.password or "") == "p@ss/word#1"
    assert parsed.hostname == "localhost"
    assert parsed.path == "/mydb"


def test_conninfo_url_encodes_user_and_database_with_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un '/' sin escapar en user/database desplaza los componentes siguientes de la URI."""
    conninfo = _build_pool(
        monkeypatch,
        {"user": "dom/user", "password": "pw", "host": "localhost", "port": 5432, "database": "my/db"},
    )

    parsed = urlsplit(conninfo)
    assert unquote(parsed.username or "") == "dom/user"
    assert unquote(parsed.password or "") == "pw"
    assert parsed.hostname == "localhost"
    assert unquote(parsed.path) == "/my/db"


def test_conninfo_without_credentials_has_empty_userinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    conninfo = _build_pool(
        monkeypatch,
        {"host": "localhost", "port": 5432, "database": "mydb"},
    )

    assert conninfo == "postgresql://:@localhost:5432/mydb"
