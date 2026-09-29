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


# H6 (sesión 2026-09-29b): el conninfo solo llevaba user/password/host/port/database y ``options``; el pool ignoraba
# sslmode (sslmode="require" conectaba sin TLS), connect_timeout, keepalives, application_name, etc.
_BASE: dict[str, Any] = {"user": "u", "password": "pw", "host": "localhost", "port": 5432, "database": "mydb"}


def _libpq_params(conninfo: str) -> dict[str, Any]:
    """Parámetros tal como los interpreta libpq (parser real de psycopg, sin conectar)."""
    psycopg = pytest.importorskip("psycopg")
    return dict(psycopg.conninfo.conninfo_to_dict(conninfo))


def test_conninfo_carries_sslmode_and_libpq_options(monkeypatch: pytest.MonkeyPatch) -> None:
    conninfo = _build_pool(
        monkeypatch,
        {
            **_BASE,
            "sslmode": "verify-full",
            "connect_timeout": 7,
            "application_name": "mi app",
            "fallback_application_name": "util_bbdd",
            "tcp_keepalives_idle": 30,
            "target_session_attrs": "read-write",
            "options": "-c search_path=ventas",
        },
    )
    params = _libpq_params(conninfo)
    assert params["sslmode"] == "verify-full"
    assert params["connect_timeout"] == "7"
    assert params["application_name"] == "mi app"
    assert params["fallback_application_name"] == "util_bbdd"
    assert params["keepalives_idle"] == "30"  # tcp_keepalives_idle es el nombre del parámetro del servidor
    assert params["target_session_attrs"] == "read-write"
    assert params["options"] == "-c search_path=ventas"
    assert params["dbname"] == "mydb"


@pytest.mark.parametrize(("keepalives", "expected"), [(True, "1"), (False, "0")])
def test_conninfo_boolean_options_as_integers(monkeypatch: pytest.MonkeyPatch, keepalives: bool, expected: str) -> None:
    params = _libpq_params(_build_pool(monkeypatch, {**_BASE, "keepalives": keepalives}))
    assert params["keepalives"] == expected


def test_conninfo_excludes_pool_settings_and_prefers_explicit_dbname(monkeypatch: pytest.MonkeyPatch) -> None:
    params = _libpq_params(
        _build_pool(monkeypatch, {**_BASE, "dbname": "otra", "pool_size": 5, "pool_timeout": 30, "max_idle": 300})
    )
    assert params["dbname"] == "otra"
    assert not {"pool_size", "pool_timeout", "max_idle", "database"} & set(params)
