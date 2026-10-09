"""Hotfix P0 B1 de drivers-connections-audit (FASE 1, 2026-10-08).

La lista blanca de ``data/database_types.json`` (``DatabaseTypeValidator.validate_connection_params``) rechazaba
parámetros que las clases de ``connection/config.py`` aceptan y que la librería documenta o lee
(``oracle_thick_mode`` en ``docs/guides/drivers.md``, ``close_timeout`` en ``SyncDatabaseManager``). ``builder.py``
rechazaba además Oracle con solo ``database``, aunque ``OracleConnectionConfig`` lo admite como alias de
``service_name``.
"""

from __future__ import annotations

import dataclasses

from typing import Any

import pytest

from util_bbdd._drivers import get_database_validator
from util_bbdd.connection import config
from util_bbdd.connection.params import ConnectionParamsManager

BASE: dict[str, dict[str, Any]] = {
    "mariadb": {"host": "h", "user": "u", "password": "p", "database": "d"},
    "mysql": {"host": "h", "user": "u", "password": "p", "database": "d"},
    "postgresql": {"host": "h", "user": "u", "password": "p", "database": "d"},
    "oracle": {"user": "u", "password": "p", "service_name": "ORCL"},
    "sqlserver": {"host": "h", "user": "u", "password": "p", "database": "d"},
    "sqlite": {"database": ":memory:"},
    "hsqldb": {"user": "SA", "jdbc_url": "jdbc:hsqldb:mem:t", "jdbc_jar": "hsqldb.jar"},
}


@pytest.mark.parametrize(
    ("db_type", "extra"),
    [
        ("oracle", {"oracle_thick_mode": True, "oracle_client_path": "C:/instantclient"}),
        ("mariadb", {"pool_name": "app_pool"}),
        ("postgresql", {"options": "-c statement_timeout=0"}),
        ("postgresql", {"target_session_attrs": "read-write"}),
        *[(db_type, {"close_timeout": 5}) for db_type in BASE],
    ],
)
def test_prepare_and_validate_accepts_params_supported_by_config(db_type: str, extra: dict[str, Any]) -> None:
    params = ConnectionParamsManager.prepare_and_validate(db_type, {**BASE[db_type], **extra})

    for key, value in extra.items():
        assert params[key] == value


def test_prepare_and_validate_accepts_oracle_database_as_service_name_alias() -> None:
    params = ConnectionParamsManager.prepare_and_validate("oracle", {"user": "u", "password": "p", "database": "ORCL"})

    assert params["database"] == "ORCL"


CONFIGS: dict[str, tuple[type, type | None]] = {
    "mariadb": (config.MariaDBConnectionConfig, config.MariaDBPoolConfig),
    "mysql": (config.MySQLConnectionConfig, config.MySQLPoolConfig),
    "postgresql": (config.PostgreSQLConnectionConfig, config.PostgreSQLPoolConfig),
    "oracle": (config.OracleConnectionConfig, config.OraclePoolConfig),
    "sqlserver": (config.SQLServerConnectionConfig, config.SQLServerPoolConfig),
    "sqlite": (config.SQLiteConnectionConfig, config.SQLitePoolConfig),
    "hsqldb": (config.HSQLDBConnectionConfig, None),
}


@pytest.mark.parametrize("db_type", sorted(CONFIGS))
def test_json_whitelist_covers_every_config_field(db_type: str) -> None:
    """Guardián: un campo nuevo en ``*Config`` debe añadirse también a ``database_types.json``."""
    connection_cls, pool_cls = CONFIGS[db_type]
    fields = {f.name for f in dataclasses.fields(connection_cls)} | {"close_timeout"}
    if pool_cls is not None:
        fields |= {f.name for f in dataclasses.fields(pool_cls)} - {"connection"}
    validator = get_database_validator()
    whitelist = set(validator.get_required_params(db_type)) | {
        str(p["name"]) for p in validator.get_optional_params(db_type)
    }

    assert fields - whitelist == set()


# --- B1 de drivers-connections-audit (v0.37.0): *Config es la fuente única; el JSON es documentación verificada ----


def _config_defaults(db_type: str) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for config_cls in CONFIGS[db_type]:
        if config_cls is None:
            continue
        for f in dataclasses.fields(config_cls):
            if f.name != "connection" and f.default is not dataclasses.MISSING:
                defaults[f.name] = f.default
    return defaults


@pytest.mark.parametrize("db_type", sorted(CONFIGS))
def test_json_keys_equal_allowed_keys(db_type: str) -> None:
    """Las claves del JSON son exactamente las que acepta ``prepare_and_validate`` (derivadas de ``*Config``)."""
    validator = get_database_validator()
    json_keys = set(validator.get_required_params(db_type)) | {
        str(p["name"]) for p in validator.get_optional_params(db_type)
    }

    assert json_keys == set(ConnectionParamsManager.allowed_keys(db_type))


@pytest.mark.parametrize("db_type", sorted(CONFIGS))
def test_json_defaults_match_config_defaults(db_type: str) -> None:
    """Un ``default`` documentado en el JSON es el que aplica ``*Config``; si la config no tiene default, el JSON
    tampoco lo declara (antes: MySQL ``charset`` y PostgreSQL ``sslmode``)."""
    from util_bbdd.connection.close import DEFAULT_CLOSE_TIMEOUT_SECONDS

    config_defaults = _config_defaults(db_type)
    config_defaults.setdefault("close_timeout", DEFAULT_CLOSE_TIMEOUT_SECONDS)
    mismatches: dict[str, tuple[Any, Any]] = {}
    for param in get_database_validator().get_optional_params(db_type):
        if "default" not in param:
            continue
        name = str(param["name"])
        if config_defaults.get(name) != param["default"]:
            mismatches[name] = (param["default"], config_defaults.get(name))

    assert mismatches == {}


@pytest.mark.parametrize("db_type", sorted(CONFIGS))
def test_prepare_and_validate_rejects_unknown_key(db_type: str) -> None:
    with pytest.raises(ValueError, match="no_existe"):
        ConnectionParamsManager.prepare_and_validate(db_type, {**BASE[db_type], "no_existe": 1})
