"""U-T3 (G12 de util_bbdd_web): ``kind`` de cada parámetro de conexión (``connection_params.kinds``)."""

from __future__ import annotations

from typing import get_args

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd.connection import ConnectionParamsManager, ParamKind
from util_bbdd.exceptions import InvalidDatabaseType

pytestmark = pytest.mark.unit

ENGINES = SyncDatabaseManager.get_supported_db_types()


@pytest.mark.parametrize("db_type", ENGINES)
def test_every_parameter_has_a_kind(db_type: str) -> None:
    params = SyncDatabaseManager.get_db_type_info_static(db_type)["connection_params"]
    declared = set(params["required"]) | {option["name"] for option in params["optional"]}
    kinds = ConnectionParamsManager.param_kinds(db_type)

    assert set(kinds) == declared == ConnectionParamsManager.allowed_keys(db_type)
    assert set(kinds.values()) <= set(get_args(ParamKind))


@pytest.mark.parametrize(
    ("db_type", "name", "kind"),
    [
        ("postgresql", "password", "secret"),
        ("hsqldb", "password", "secret"),
        ("mariadb", "host", "host"),
        ("oracle", "dsn", "host"),
        ("hsqldb", "jdbc_url", "host"),
        ("sqlserver", "port", "port"),
        ("mysql", "ssl_key", "path"),
        ("oracle", "oracle_client_path", "path"),
        ("hsqldb", "jdbc_jar", "path"),
        ("sqlite", "database", "path"),
        ("postgresql", "database", "plain"),
        ("mariadb", "init_command", "blocked"),
        ("postgresql", "sslmode", "plain"),
    ],
)
def test_kind_of_known_parameters(db_type: str, name: str, kind: str) -> None:
    assert ConnectionParamsManager.param_kind(db_type, name) == kind


def test_only_password_is_secret() -> None:
    secrets = {
        name for db in ENGINES for name, kind in ConnectionParamsManager.param_kinds(db).items() if kind == "secret"
    }
    assert secrets == {"password"}


def test_unknown_parameter_or_engine() -> None:
    with pytest.raises(ValueError, match="sslmode"):
        ConnectionParamsManager.param_kind("mysql", "sslmode")
    with pytest.raises(InvalidDatabaseType):
        ConnectionParamsManager.param_kinds("db2")
