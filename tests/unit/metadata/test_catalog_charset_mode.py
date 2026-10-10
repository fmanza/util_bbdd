"""Bloque CS de drivers-connections-audit (v0.38.0): ``catalog_charset_mode`` (``auto`` | ``native`` | ``convert``) en
MariaDB y MySQL. ``native``/``convert`` fijan la estrategia de lectura del catálogo sin el diagnóstico de charset."""

from __future__ import annotations

import asyncio

from typing import Any
from unittest import mock

import pytest

from util_bbdd import AsyncDatabaseManager
from util_bbdd.connection.config import MariaDBConnectionConfig, MySQLConnectionConfig
from util_bbdd.connection.params import ConnectionParamsManager
from util_bbdd.exceptions import ValidationError
from util_bbdd.managers._catalog_executor import AsyncManagerCatalogExecutor, ManagerCatalogExecutor
from util_bbdd.metadata._adaptive_executor import AdaptiveCatalogExecutor

NET = {"host": "h", "user": "u", "password": "p", "database": "d"}
SQL = "SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = :schema"


# --- Config y validación ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("config_cls", [MariaDBConnectionConfig, MySQLConnectionConfig])
def test_config_default_is_auto_and_not_sent_to_driver(config_cls: Any) -> None:
    config = config_cls.from_params(dict(NET))
    assert config.catalog_charset_mode == "auto"
    assert "catalog_charset_mode" not in config.to_driver_kwargs()


@pytest.mark.parametrize("mode", ["auto", "native", "convert", "NATIVE"])
def test_config_accepts_modes(mode: str) -> None:
    assert (
        MariaDBConnectionConfig.from_params({**NET, "catalog_charset_mode": mode}).catalog_charset_mode == mode.lower()
    )


@pytest.mark.parametrize("db_type", ["mariadb", "mysql"])
def test_invalid_mode_is_rejected_by_managers(db_type: str) -> None:
    with pytest.raises(ValidationError, match="catalog_charset_mode"):
        AsyncDatabaseManager(db_type, {**NET, "catalog_charset_mode": "failfast"})


@pytest.mark.parametrize("db_type", ["postgresql", "sqlserver"])
def test_other_engines_reject_the_key(db_type: str) -> None:
    assert "catalog_charset_mode" not in ConnectionParamsManager.allowed_keys(db_type)


# --- Ejecutor sync ------------------------------------------------------------------------------------------------


class _Cursor:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def execute(self, sql: str, args: Any = None) -> None:
        self.log.append(sql)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [("t", "c")]

    def fetchone(self) -> tuple[Any, ...]:
        return ("utf8mb4",)

    def close(self) -> None:
        pass


class _Conn:
    def __init__(self) -> None:
        self.log: list[str] = []

    def cursor(self) -> _Cursor:
        return _Cursor(self.log)


@pytest.mark.parametrize(("mode", "convert"), [("native", False), ("convert", True)])
def test_adaptive_executor_explicit_mode_skips_diagnosis(mode: str, convert: bool) -> None:
    conn = _Conn()
    with mock.patch("util_bbdd.metadata._adaptive_executor.CharsetStateDetector") as detector:
        executor = AdaptiveCatalogExecutor(conn, "qmark", mode=mode)
        executor.fetch_all(SQL, {"schema": "d"})
    detector.assert_not_called()
    assert executor.strategy == mode
    assert ("CONVERT(CAST(" in conn.log[-1]) is convert


def test_adaptive_executor_auto_still_diagnoses() -> None:
    conn = _Conn()
    executor = AdaptiveCatalogExecutor(conn, "qmark")
    executor.fetch_all(SQL, {"schema": "d"})
    assert executor.diagnosis is not None
    assert len(conn.log) > 1  # consultas de diagnóstico + la del catálogo


def test_manager_executor_passes_mode_to_adaptive() -> None:
    conn = _Conn()
    type(conn).__module__ = "mariadb.connections"
    try:
        executor = ManagerCatalogExecutor(lambda: conn, lambda c: None, charset_mode="convert")
        executor.fetch_all(SQL, {"schema": "d"})
    finally:
        type(conn).__module__ = __name__
    assert len(conn.log) == 1
    assert "CONVERT(CAST(" in conn.log[0]


# --- Ejecutor async -----------------------------------------------------------------------------------------------


class _AsyncCursor(_Cursor):
    async def execute(self, sql: str, args: Any = None) -> None:  # type: ignore[override]
        self.log.append(sql)

    async def fetchall(self) -> list[tuple[Any, ...]]:  # type: ignore[override]
        return [("t", "c")]

    async def close(self) -> None:  # type: ignore[override]
        pass


class _AsyncConn:
    def __init__(self) -> None:
        self.log: list[str] = []

    def cursor(self) -> _AsyncCursor:
        return _AsyncCursor(self.log)


@pytest.mark.parametrize(("mode", "convert"), [("native", False), ("convert", True)])
def test_async_executor_explicit_mode_skips_adiagnose(mode: str, convert: bool) -> None:
    conn = _AsyncConn()
    type(conn).__module__ = "aiomysql.connection"

    async def provider() -> Any:
        return conn

    async def releaser(_c: Any) -> None:
        return None

    async def run() -> None:
        executor = AsyncManagerCatalogExecutor(provider, releaser, charset_mode=mode)
        await executor.fetch_all(SQL, {"schema": "d"})

    try:
        with mock.patch("util_bbdd.managers._catalog_executor.adiagnose") as adiagnose:
            asyncio.run(run())
    finally:
        type(conn).__module__ = __name__
    adiagnose.assert_not_called()
    assert ("CONVERT(CAST(" in conn.log[-1]) is convert


def test_async_manager_builds_executor_with_mode() -> None:
    manager = AsyncDatabaseManager("mariadb", {**NET, "catalog_charset_mode": "native"})
    with mock.patch("util_bbdd.managers.async_mgr.AsyncManagerCatalogExecutor") as executor_cls:
        _ = manager.metadata_source
    assert executor_cls.call_args.kwargs["charset_mode"] == "native"


def test_sync_manager_builds_executor_with_mode() -> None:
    """F2 de FASE 5: el manager sync pasa ``catalog_charset_mode`` al ejecutor de catálogo."""
    from util_bbdd import SyncDatabaseManager

    with mock.patch("util_bbdd.managers.sync_mgr.ManagerCatalogExecutor") as executor_cls:
        manager = SyncDatabaseManager.__new__(SyncDatabaseManager)
        manager.db_type = "mariadb"
        manager.conn_params = {**NET, "catalog_charset_mode": "convert"}
        manager.database = "d"
        _ = manager.metadata_source
    assert executor_cls.call_args.kwargs["charset_mode"] == "convert"
