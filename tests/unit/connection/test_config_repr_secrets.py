"""P2 S3 de drivers-connections-audit (FASE 1, 2026-10-08): las configs no exponen la contraseña en ``repr``.

Las ``*Config`` son dataclasses: ``repr`` incluía ``password``, que acababa en tracebacks con variables locales, en
depuradores o en herramientas como Sentry.
"""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.connection.params import ConnectionParamsManager

SECRET = "S3cr3t-p4ss"
PARAMS: dict[str, dict[str, Any]] = {
    "mariadb": {"host": "h", "user": "u", "password": SECRET, "database": "d"},
    "mysql": {"host": "h", "user": "u", "password": SECRET, "database": "d"},
    "postgresql": {"host": "h", "user": "u", "password": SECRET, "database": "d"},
    "oracle": {"user": "u", "password": SECRET, "service_name": "ORCL"},
    "sqlserver": {"host": "h", "user": "u", "password": SECRET, "database": "d"},
    "hsqldb": {"user": "SA", "password": SECRET, "jdbc_url": "jdbc:hsqldb:mem:t", "jdbc_jar": "hsqldb.jar"},
}


@pytest.mark.parametrize("db_type", sorted(PARAMS))
def test_connection_config_repr_hides_password(db_type: str) -> None:
    config = ConnectionParamsManager.get_connection_config(db_type, PARAMS[db_type])

    assert SECRET not in repr(config)
    assert config.to_driver_kwargs()["password"] == SECRET  # el driver la sigue recibiendo


@pytest.mark.parametrize("db_type", sorted(set(PARAMS) - {"hsqldb"}))
def test_pool_config_repr_hides_password(db_type: str) -> None:
    assert SECRET not in repr(ConnectionParamsManager.get_pool_config(db_type, PARAMS[db_type]))
