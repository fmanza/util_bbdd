"""P2 P2–P6 de drivers-connections-audit (FASE 1, 2026-10-08): PostgreSQL.

- **P2**: asyncpg recibía ``sslmode`` convertido a booleano: se perdía la diferencia entre ``prefer``/``allow``/
  ``require``/``verify-*``. asyncpg acepta el ``sslmode`` de libpq como cadena.
- **P3**: el ``connect_timeout`` de la config no llegaba a asyncpg (su parámetro se llama ``timeout``).
- **P4**: ``schema`` se interpolaba en ``options=-c search_path=<schema>`` sin validar: un valor con espacios añadía
  otros ``-c`` (p. ej. ``"x -c statement_timeout=0"``).
- **P5**: la URI del pool (psycopg_pool) no ponía corchetes a hosts IPv6 (``postgresql://u:p@::1:5432/db``).
- **P6**: agotar el pool lanzaba ``psycopg_pool.PoolTimeout`` en vez de ``PoolTimeoutError`` (MySQL sí lo traducía).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd._core.exceptions import PoolTimeoutError
from util_bbdd.connection.config import PostgreSQLConnectionConfig
from util_bbdd.connection.params import ConnectionParamsManager
from util_bbdd.connection.postgresql import pool_connection_postgresql
from util_bbdd.connection.postgresql.async_connection_postgresql import AsyncPostgreSQLConnection

BASE: dict[str, Any] = {"host": "h", "user": "u", "password": "p", "database": "d"}


def _async_kwargs(**extra: Any) -> dict[str, Any]:
    sanitized = ConnectionParamsManager.sanitize_for_connection("postgresql", {**BASE, **extra})
    return AsyncPostgreSQLConnection._map_connect_kwargs(sanitized)


@pytest.mark.parametrize("sslmode", ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"])
def test_asyncpg_receives_sslmode_as_libpq_string(sslmode: str) -> None:
    assert _async_kwargs(sslmode=sslmode)["ssl"] == sslmode


def test_asyncpg_receives_connect_timeout() -> None:
    assert _async_kwargs(connect_timeout=7)["timeout"] == 7


@pytest.mark.parametrize("schema", ["x -c statement_timeout=0", "a;b", "sales'", "two words"])
def test_unsafe_schema_is_rejected(schema: str) -> None:
    with pytest.raises(ValueError, match="schema"):
        PostgreSQLConnectionConfig.from_params({**BASE, "schema": schema})


@pytest.mark.parametrize("schema", ["public", "ventas_2026", "app,public", "$user,public"])
def test_valid_schema_lists_are_accepted(schema: str) -> None:
    config = PostgreSQLConnectionConfig.from_params({**BASE, "schema": schema})

    assert config.to_driver_kwargs()["options"] == f"-c search_path={schema}"


def _capture_pool(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def _pool(**kwargs: Any) -> Any:
        captured.update(kwargs)
        pool = MagicMock()
        captured["pool"] = pool
        return pool

    monkeypatch.setattr(pool_connection_postgresql, "HAS_PSYCOPG_POOL", True)
    monkeypatch.setattr(pool_connection_postgresql, "PsycopgConnectionPool", _pool, raising=False)
    return captured


def test_pool_uri_brackets_ipv6_host(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_pool(monkeypatch)

    pool_connection_postgresql.PoolConnection({**BASE, "host": "::1"})._closed = True

    assert "@[::1]:5432/" in captured["conninfo"]


def test_pool_timeout_is_translated_to_pool_timeout_error(monkeypatch: pytest.MonkeyPatch) -> None:
    psycopg_pool = pytest.importorskip("psycopg_pool")
    captured = _capture_pool(monkeypatch)
    pool = pool_connection_postgresql.PoolConnection({**BASE, "pool_timeout": 3})
    captured["pool"].getconn.side_effect = psycopg_pool.PoolTimeout("couldn't get a connection after 3.00 sec")

    with pytest.raises(PoolTimeoutError):
        pool.get_connection()
    pool._closed = True
