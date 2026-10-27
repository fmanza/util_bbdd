"""U-T4 (G15 de util_bbdd_web): ``build_conn_params`` conserva los opcionales declarados en ``connection_params``."""

from __future__ import annotations

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd.connection import ConnectionParamsManager, build_conn_params

pytestmark = pytest.mark.unit

PG = {"host": "h", "user": "u", "password": "p", "database": "d"}


def test_postgresql_sslmode_survives() -> None:
    params = build_conn_params("postgresql", **PG, sslmode="require", application_name="web")
    assert (params["sslmode"], params["application_name"]) == ("require", "web")


@pytest.mark.parametrize(
    ("db_type", "base", "extra"),
    [
        ("mysql", PG, {"ssl_ca": "/ca.pem", "ssl_verify_identity": True, "read_timeout": 5}),
        ("mariadb", PG, {"ssl_ca": "/ca.pem", "init_command": "SET x=1", "autocommit": True}),
        ("sqlserver", PG, {"encryption": "mandatory", "trust_cert": True, "login_timeout": 5}),
        (
            "oracle",
            {"user": "u", "password": "p", "service_name": "S"},
            {"protocol": "tcps", "oracle_thick_mode": True},
        ),
        ("hsqldb", {"user": "u", "jdbc_url": "jdbc:hsqldb:mem:x", "jdbc_jar": "/h.jar"}, {"connection_properties": {}}),
        ("sqlite", {"database": "x.db"}, {"close_timeout": 3}),
    ],
)
def test_declared_optionals_survive(db_type: str, base: dict, extra: dict) -> None:
    params = build_conn_params(db_type, **base, **extra)
    assert {key: params[key] for key in extra} == extra


def test_undeclared_and_none_values_are_dropped() -> None:
    params = build_conn_params("postgresql", **PG, no_existe=1, sslmode=None)
    assert "no_existe" not in params and "sslmode" not in params


def test_oracle_dsn_still_wins_over_the_split_destination() -> None:
    params = build_conn_params("oracle", user="u", password="p", dsn="h:1521/S", host="otro", port=1, sid="X")
    assert params["dsn"] == "h:1521/S"
    assert not {"host", "port", "sid", "service_name", "database"} & set(params)


def test_builder_defaults_are_not_overridden() -> None:
    params = build_conn_params("sqlserver", **PG, port=14330)
    assert params["port"] == 14330 and params["sql_server_driver"] == "pymssql"


def test_prepared_params_keep_sslmode() -> None:
    """El camino del manager ya conservaba los opcionales; sigue igual."""
    prepared = ConnectionParamsManager.prepare_and_validate("postgresql", {**PG, "sslmode": "disable"})
    assert prepared["sslmode"] == "disable"
    assert set(SyncDatabaseManager.get_db_type_info_static("postgresql")["connection_params"]["kinds"]) >= set(prepared)
