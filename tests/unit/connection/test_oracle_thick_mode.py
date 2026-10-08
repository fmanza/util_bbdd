"""Hotfix P0 B2 de drivers-connections-audit (FASE 1, 2026-10-08).

``OracleConnectionConfig.to_driver_kwargs()`` no emitía ``oracle_thick_mode``, así que la rama thick de
``OracleConnection.connect`` nunca se ejecutaba. El pool llamaba a ``oracledb.init_oracle_client`` directamente,
sin el lock de inicialización única de ``_thick_mode.init_oracle_thick_mode``.
"""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.connection.oracle import connection_oracle, pool_connection_oracle
from util_bbdd.connection.params import ConnectionParamsManager

THICK_PARAMS: dict[str, Any] = {
    "user": "u",
    "password": "p",
    "service_name": "ORCL",
    "oracle_thick_mode": True,
    "oracle_client_path": "C:/instantclient",
}


def test_sanitize_for_connection_keeps_oracle_thick_mode() -> None:
    sanitized = ConnectionParamsManager.sanitize_for_connection("oracle", THICK_PARAMS)

    assert sanitized["oracle_thick_mode"] is True


def test_connect_initializes_thick_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    import oracledb

    initialized: list[str] = []
    monkeypatch.setattr(connection_oracle, "init_oracle_thick_mode", initialized.append)
    monkeypatch.setattr(oracledb, "connect", lambda **_kwargs: "conn")

    assert connection_oracle.OracleConnection.connect(THICK_PARAMS) == "conn"
    assert initialized == ["C:/instantclient"]


def test_pool_initializes_thick_mode_through_single_init_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    initialized: list[str] = []

    def _unexpected_direct_init(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("init_oracle_client llamado sin el lock de _thick_mode")

    monkeypatch.setattr(pool_connection_oracle, "init_oracle_thick_mode", initialized.append)
    monkeypatch.setattr(pool_connection_oracle.oracledb, "init_oracle_client", _unexpected_direct_init)
    monkeypatch.setattr(pool_connection_oracle.oracledb, "create_pool", lambda **_kwargs: object())

    pool = pool_connection_oracle.PoolConnection(dict(THICK_PARAMS))
    pool._closed = True  # sin pool real que cerrar en __del__

    assert initialized == ["C:/instantclient"]
