"""Cadena ODBC del pool async de SQL Server (aioodbc) (hotfix de 1.1.0).

Hasta v1.0.0 el pool leía la configuración sin indicar el driver pyodbc: ``SQLServerConnectionConfig`` tomaba
``pymssql`` por defecto, no incluía ``driver_name`` y la cadena usaba siempre ``ODBC Driver 17 for SQL Server``. Con
solo el Driver 18 instalado, ``AsyncDatabaseManager("sqlserver", {..., "driver_name": "ODBC Driver 18 ..."})`` fallaba
con ``IM002`` con pool y conectaba sin él.
"""

from __future__ import annotations

import sys
import types

from typing import Any
from unittest.mock import AsyncMock

import pytest

from util_bbdd.connection.sqlserver.async_pool_connection_sqlserver import AsyncSQLServerPool

PARAMS: dict[str, Any] = {"host": "h", "port": 1433, "user": "u", "password": "p", "database": "d"}


@pytest.fixture
def create_pool(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    fake = types.ModuleType("aioodbc")
    fake.create_pool = AsyncMock(return_value=object())  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "aioodbc", fake)
    return fake.create_pool  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pool_dsn_uses_the_given_driver_name(create_pool: AsyncMock) -> None:
    await AsyncSQLServerPool.create({**PARAMS, "driver_name": "ODBC Driver 18 for SQL Server", "trust_cert": True})

    dsn: str = create_pool.await_args.kwargs["dsn"]
    assert "Driver={ODBC Driver 18 for SQL Server};" in dsn
    assert "TrustServerCertificate=yes;" in dsn


@pytest.mark.asyncio
async def test_pool_dsn_default_driver_is_unchanged(create_pool: AsyncMock) -> None:
    await AsyncSQLServerPool.create(PARAMS)

    assert "Driver={ODBC Driver 17 for SQL Server};" in create_pool.await_args.kwargs["dsn"]
