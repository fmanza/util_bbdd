"""Bloque B2 de drivers-connections-audit (v0.39.0): TLS en MariaDB.

Comportamiento de Connector/Python 1.1.14 (Connector/C 3.4.7) comprobado contra MariaDB 11.4: ``ssl_verify_cert``
solo no activa TLS (hace falta ``ssl=True``) y ``ssl_ca`` sin ``ssl_verify_cert=True`` no exige la CA.
"""

from __future__ import annotations

import logging
import ssl

from typing import Any

import pytest

from util_bbdd.connection._aiomysql import build_aiomysql_connect_kwargs
from util_bbdd.connection.config import MariaDBConnectionConfig, MariaDBPoolConfig
from util_bbdd.connection.params import ConnectionParamsManager

NET = {"host": "h", "user": "u", "password": "p", "database": "d"}
TLS_KEYS = {"ssl", "ssl_ca", "ssl_cert", "ssl_key", "ssl_verify_cert"}


def _kwargs(**extra: Any) -> dict[str, Any]:
    return MariaDBConnectionConfig.from_params({**NET, **extra}).to_driver_kwargs()


def test_without_tls_options_driver_kwargs_are_unchanged() -> None:
    assert TLS_KEYS.isdisjoint(_kwargs())


def test_ssl_true_enables_tls() -> None:
    kwargs = _kwargs(ssl=True)
    assert kwargs["ssl"] is True
    assert "ssl_verify_cert" not in kwargs  # el conector verifica por huella (zero-config de MariaDB 11.4)


def test_ssl_ca_enables_tls_and_requires_verification() -> None:
    kwargs = _kwargs(ssl_ca="ca.pem")
    assert kwargs["ssl"] is True
    assert kwargs["ssl_ca"] == "ca.pem"
    assert kwargs["ssl_verify_cert"] is True  # sin esto el conector acepta una CA ajena


def test_explicit_verify_false_keeps_tls_on() -> None:
    kwargs = _kwargs(ssl_ca="ca.pem", ssl_verify_cert=False)
    assert kwargs["ssl"] is True
    assert kwargs["ssl_verify_cert"] is False


def test_verify_cert_alone_enables_tls() -> None:
    assert _kwargs(ssl_verify_cert=True)["ssl"] is True


def test_client_certificate() -> None:
    kwargs = _kwargs(ssl_cert="c.pem", ssl_key="k.pem")
    assert (kwargs["ssl"], kwargs["ssl_cert"], kwargs["ssl_key"]) == (True, "c.pem", "k.pem")


def test_ssl_false_string_is_parsed() -> None:
    assert TLS_KEYS.isdisjoint(_kwargs(ssl="false"))


def test_pool_config_carries_tls() -> None:
    kwargs = MariaDBPoolConfig.from_params({**NET, "ssl": True}).to_driver_kwargs()
    assert kwargs["ssl"] is True


def test_tls_keys_are_accepted_by_whitelist() -> None:
    assert TLS_KEYS <= ConnectionParamsManager.allowed_keys("mariadb")


# --- async (aiomysql) -------------------------------------------------------------------------------------------


async def _connect(host: str, ssl: Any = None, db: str | None = None, charset: str = "") -> None:  # firma mínima
    return None


def test_async_ssl_true_without_ca_encrypts_without_verification(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        kwargs = build_aiomysql_connect_kwargs(_kwargs(ssl=True), _connect)
    ctx = kwargs["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_NONE
    assert "sin verificar" in caplog.text


def test_async_ssl_ca_verifies(tmp_path: Any) -> None:
    import certifi

    kwargs = build_aiomysql_connect_kwargs(_kwargs(ssl_ca=certifi.where()), _connect)
    assert kwargs["ssl"].verify_mode == ssl.CERT_REQUIRED


def test_async_without_tls_has_no_ssl() -> None:
    assert "ssl" not in build_aiomysql_connect_kwargs(_kwargs(), _connect)
