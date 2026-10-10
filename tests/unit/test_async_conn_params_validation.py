"""B1 de drivers-connections-audit (v0.37.0): ``AsyncDatabaseManager`` valida ``conn_params`` como el sync (Q2) y los
defaults de ``schema`` viven en ``*Config`` y valen en todos los caminos (Q3)."""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.connection import build_conn_params
from util_bbdd.connection.params import ConnectionParamsManager
from util_bbdd.exceptions import ValidationError
from util_bbdd.managers._metadata_context import MetadataContextResolver

NET = {"host": "localhost", "user": "u", "password": "p", "database": "db"}


# --- BC1: el manager async valida en el constructor -------------------------------------------------------------


def test_async_manager_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError, match="tipo_erroneo"):
        AsyncDatabaseManager("sqlite", {"database": ":memory:", "tipo_erroneo": 1})


def test_async_manager_rejects_missing_required() -> None:
    with pytest.raises(ValidationError, match="password"):
        AsyncDatabaseManager("postgresql", {"host": "h", "user": "u", "database": "d"})


def test_async_manager_rejects_invalid_value() -> None:
    with pytest.raises(ValidationError, match="schema"):
        AsyncDatabaseManager("postgresql", {**NET, "schema": "a b"})


def test_async_and_sync_reject_the_same_params() -> None:
    bad = {"database": ":memory:", "tipo_erroneo": 1}
    with pytest.raises(ValidationError) as sync_err:
        SyncDatabaseManager("sqlite", dict(bad))
    with pytest.raises(ValidationError) as async_err:
        AsyncDatabaseManager("sqlite", dict(bad))
    assert "tipo_erroneo" in str(sync_err.value) and "tipo_erroneo" in str(async_err.value)


def test_async_manager_normalizes_aliases_without_injecting_sync_defaults() -> None:
    """R1: el async no recibe ``sql_server_driver="pymssql"`` (su Engine exige aioodbc)."""
    manager = AsyncDatabaseManager("sqlserver", dict(NET))
    assert "sql_server_driver" not in manager.conn_params
    assert AsyncDatabaseManager("sqlite", {"filepath": "x.db"}).conn_params == {"database": "x.db"}


def test_async_manager_does_not_check_sync_drivers() -> None:
    """R2: ``DriverValidator`` comprueba drivers sync (p. ej. ``mariadb``); el async usa aiomysql."""
    with mock.patch("util_bbdd._drivers.driver_validator.DriverValidator.check_driver_availability") as check:
        AsyncDatabaseManager("mariadb", dict(NET))
    check.assert_not_called()


# --- BC2: schema por defecto en *Config -------------------------------------------------------------------------


def test_postgresql_config_applies_public_search_path_by_default() -> None:
    kwargs = ConnectionParamsManager.sanitize_for_connection("postgresql", dict(NET))
    assert kwargs["options"] == "-c search_path=public"


@pytest.mark.parametrize(
    ("db_type", "params", "expected"),
    [
        ("postgresql", NET, "public"),
        ("sqlserver", NET, "dbo"),
        ("hsqldb", {"user": "u", "jdbc_url": "j", "jdbc_jar": "a"}, "PUBLIC"),
        ("postgresql", {**NET, "schema": "ventas"}, "ventas"),
    ],
)
def test_metadata_context_uses_config_default_schema_not_database(
    db_type: str, params: dict[str, Any], expected: str
) -> None:
    """BC2b: sin ``schema``, el contexto de metadatos es el schema por defecto, no el nombre de la BD (``db``)."""
    context = MetadataContextResolver.get_context_database(db_type=db_type, database="db", conn_params=dict(params))
    assert context == expected


# --- build_conn_params (API pública) no cambia su salida ---------------------------------------------------------


@pytest.mark.parametrize(
    ("db_type", "params", "expected"),
    [
        ("mariadb", NET, {**NET, "port": 3306, "pool_size": 5}),
        ("postgresql", NET, {**NET, "port": 5432, "schema": "public", "pool_size": 5, "pool_timeout": 30}),
        (
            "sqlserver",
            NET,
            {
                **NET,
                "port": 1433,
                "schema": "dbo",
                "sql_server_driver": "pymssql",
                "driver_name": "ODBC Driver 17 for SQL Server",
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
            },
        ),
        (
            "oracle",
            {"user": "u", "password": "p", "service_name": "s"},
            {
                "user": "u",
                "password": "p",
                "pool_size": 5,
                "max_lifetime": 3600,
                "host": "localhost",
                "port": 1521,
                "service_name": "s",
            },
        ),
        (
            "sqlite",
            {"database": ":memory:"},
            {
                "database": ":memory:",
                "timeout": 5,
                "check_same_thread": False,
                "isolation_level": "",
                "cached_statements": 100,
                "pool_size": 1,
            },
        ),
        (
            "hsqldb",
            {"user": "u", "jdbc_url": "j", "jdbc_jar": "a"},
            {
                "user": "u",
                "password": "",
                "jdbc_url": "j",
                "jdbc_jar": "a",
                "jdbc_driver": "org.hsqldb.jdbcDriver",
                "schema": "PUBLIC",
            },
        ),
    ],
)
def test_build_conn_params_output_unchanged(db_type: str, params: dict[str, Any], expected: dict[str, Any]) -> None:
    assert build_conn_params(db_type, **params) == expected


def test_async_manager_database_comes_from_validated_params() -> None:
    """Hotfix v0.39.1 (F1 de FASE 5): con el alias ``filepath``, ``database`` quedaba vacío en async."""
    manager = AsyncDatabaseManager("sqlite", {"filepath": "x.db"})
    assert manager.database == "x.db"
    assert manager._catalog_source_id().endswith("/x.db")
