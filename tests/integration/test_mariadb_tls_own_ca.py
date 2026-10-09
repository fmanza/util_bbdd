"""TLS de MariaDB con una CA propia contra el MariaDB del banco (v0.39.0 y validación de P4, 2026-10-09).

Requiere el banco con ``docker-compose.bench-tls.yml`` (certificados de ``scripts/bench_tls_certs.py`` en
``build/bench_tls/``; el certificado de servidor solo tiene ``IP:127.0.0.1``). Se salta si no hay URL o falta la CA::

    python scripts/bench_tls_certs.py
    docker compose -f docker-compose.bench.yml -f docker-compose.bench-tls.yml up -d --wait --force-recreate -V mariadb
    UTIL_BBDD_TEST_MARIADB_URL=... python -m pytest tests/integration/test_mariadb_tls_own_ca.py

Hecho comprobado con MariaDB Connector/Python 1.1.14 (Connector/C 3.4.7): el conector sync no comprueba el hostname
cuando se conecta como ``localhost`` (exención de conexiones locales), pero sí con cualquier otra dirección.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os

from pathlib import Path
from typing import Any

import pytest

from sqlalchemy.engine import make_url

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd._core.exceptions import DatabaseException

URL_ENV = "UTIL_BBDD_TEST_MARIADB_URL"
CA = Path(__file__).resolve().parents[2] / "build" / "bench_tls" / "ca.pem"
QUERY = "SHOW SESSION STATUS LIKE 'Ssl_cipher'"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get(URL_ENV), reason=f"{URL_ENV} no definida"),
    pytest.mark.skipif(importlib.util.find_spec("mariadb") is None, reason="paquete mariadb no instalado"),
    pytest.mark.skipif(not CA.exists(), reason="sin CA del banco (scripts/bench_tls_certs.py)"),
]


def _params(**extra: Any) -> dict[str, Any]:
    url = make_url(os.environ[URL_ENV])
    return {
        "host": "127.0.0.1",
        "port": url.port or 3306,
        "user": url.username,
        "password": url.password,
        "database": url.database,
        **extra,
    }


def _sync_cipher(params: dict[str, Any], use_pool: bool) -> str:
    manager = SyncDatabaseManager("mariadb", params, use_pool=use_pool)
    try:
        connection = manager.get_connection()
        cursor = connection.cursor()
        cursor.execute(QUERY)
        cipher = str(cursor.fetchone()[1])
        cursor.close()
        if use_pool:
            manager.close_connection(connection)
        return cipher
    finally:
        manager.close()


async def _async_cipher(params: dict[str, Any], use_pool: bool) -> str:
    manager = AsyncDatabaseManager("mariadb", params, use_pool=use_pool)
    await manager.init()
    try:
        connection = await manager.get_connection()
        async with connection.cursor() as cursor:
            await cursor.execute(QUERY)
            cipher = str((await cursor.fetchone())[1])
        await manager.release_connection(connection)
        return cipher
    finally:
        await manager.close()


@pytest.mark.parametrize("use_pool", [False, True])
def test_sync_verifies_with_own_ca(use_pool: bool) -> None:
    assert _sync_cipher(_params(ssl_ca=str(CA)), use_pool).startswith("TLS")


@pytest.mark.parametrize("use_pool", [False, True])
def test_async_verifies_with_own_ca(use_pool: bool) -> None:
    cipher = asyncio.run(_async_cipher(_params(ssl_ca=str(CA)), use_pool), loop_factory=asyncio.SelectorEventLoop)
    assert cipher.startswith("TLS")


def test_foreign_ca_is_rejected_sync_and_async() -> None:
    certifi = pytest.importorskip("certifi")
    foreign = _params(ssl_ca=certifi.where())
    with pytest.raises(DatabaseException):
        _sync_cipher(foreign, use_pool=False)
    with pytest.raises(DatabaseException):
        asyncio.run(_async_cipher(foreign, use_pool=False), loop_factory=asyncio.SelectorEventLoop)


def test_async_rejects_hostname_not_in_certificate() -> None:
    """``localhost`` no está en el certificado (solo ``IP:127.0.0.1``): aiomysql comprueba el hostname."""
    with pytest.raises(DatabaseException):
        asyncio.run(
            _async_cipher(_params(host="localhost", ssl_ca=str(CA)), use_pool=False),
            loop_factory=asyncio.SelectorEventLoop,
        )


def test_without_tls_still_connects() -> None:
    """El certificado propio no obliga a TLS (sin ``require_secure_transport``)."""
    assert _sync_cipher(_params(), use_pool=False) == ""
