"""P3 del plan de pendientes (v0.40.0, F5): las URL de los Engine sync y async siguen la misma semántica
(``factory/_url.py::server_url``)."""

from __future__ import annotations

import itertools

from typing import Any

import pytest

from sqlalchemy.engine import make_url

from util_bbdd._core.exceptions import ValidationError
from util_bbdd.factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory as Async
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory as Sync

MOTORS = ["mariadb", "mysql", "oracle", "postgresql", "sqlserver"]
BASE = {"user": "u", "password": "p", "host": "h", "port": 1234}


def _build(factory: Any, motor: str, params: dict[str, Any], database: str | None) -> Any:
    return getattr(factory, f"_build_{motor}_connection_string")(params, database)


def _parts(url: str) -> tuple[Any, ...]:
    parsed = make_url(url)
    return (parsed.username, parsed.password, parsed.host, parsed.port, parsed.database, dict(parsed.query))


def _outcome(factory: Any, motor: str, params: dict[str, Any], database: str | None) -> tuple[Any, ...]:
    try:
        return ("ok", *_parts(_build(factory, motor, params, database)))
    except ValidationError as exc:
        return ("error", str(exc))


@pytest.mark.parametrize("motor", MOTORS)
def test_sync_and_async_agree_except_driver(motor: str) -> None:
    """Para cualquier combinación de entradas límite, sync y async dan el mismo destino o el mismo error."""
    grid = {
        "host": [None, "h"],
        "user": [None, "", "u"],
        "port": [None, 1234],
        "database": [None, "cpdb"],
        "service_name": [None, "", "S"],
    }
    for combo in itertools.product(*grid.values()):
        params = {"password": "p", **{k: v for k, v in zip(grid, combo, strict=True) if v is not None}}
        for database in (None, "", "db"):
            assert _outcome(Sync, motor, params, database) == _outcome(Async, motor, params, database), (
                params,
                database,
            )


@pytest.mark.parametrize("factory", [Sync, Async])
def test_none_host_user_port_take_defaults(factory: Any) -> None:
    url = make_url(_build(factory, "postgresql", {"password": "p", "host": None, "user": None, "port": None}, "db"))
    assert (url.host, url.username, url.port) == ("localhost", "postgres", 5432)


@pytest.mark.parametrize("factory", [Sync, Async])
def test_database_none_comes_from_conn_params(factory: Any) -> None:
    url = make_url(_build(factory, "mariadb", {**BASE, "database": "cpdb"}, None))
    assert url.database == "cpdb"


@pytest.mark.parametrize("factory", [Sync, Async])
def test_sqlserver_requires_database(factory: Any) -> None:
    with pytest.raises(ValidationError, match="database"):
        _build(factory, "sqlserver", dict(BASE), "")


@pytest.mark.parametrize("factory", [Sync, Async])
def test_oracle_empty_service_name_uses_database_alias(factory: Any) -> None:
    url = make_url(_build(factory, "oracle", {**BASE, "service_name": ""}, "ORCL"))
    assert url.query["service_name"] == "ORCL"


@pytest.mark.parametrize("factory", [Sync, Async])
def test_credentials_are_still_escaped(factory: Any) -> None:
    url = make_url(_build(factory, "mysql", {**BASE, "password": "a@evil.example:3306/x?"}, "db"))
    assert (url.host, url.password) == ("h", "a@evil.example:3306/x?")
