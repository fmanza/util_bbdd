"""U-T5 (G11 de util_bbdd_web): ``get_database_info`` no devuelve secretos."""

from __future__ import annotations

import json

from unittest.mock import MagicMock, patch

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.connection import ConnectionParamsManager
from util_bbdd.connection.params import REDACTED

pytestmark = pytest.mark.unit

SECRET = "Sup3r-Secreta"
PG = {"host": "localhost", "user": "u", "password": SECRET, "database": "db", "sslmode": "require"}


def _sync_manager() -> SyncDatabaseManager:
    with patch.object(SyncDatabaseManager, "_init_pool"), patch.object(SyncDatabaseManager, "_connect"):
        return SyncDatabaseManager("postgresql", dict(PG))


def test_sync_info_masks_the_password() -> None:
    manager = _sync_manager()
    with patch.object(manager, "get_available_queries", return_value=[]):
        info = manager.get_database_info()

    assert info["connection_params"]["password"] == REDACTED
    assert info["connection_params"]["user"] == "u" and info["connection_params"]["sslmode"] == "require"
    assert SECRET not in json.dumps(info, default=str)
    assert manager.conn_params["password"] == SECRET  # el manager sigue conectando con la real


@pytest.mark.asyncio
async def test_async_info_masks_the_password() -> None:
    params = {key: value for key, value in PG.items() if key != "sslmode"}
    manager = AsyncDatabaseManager(db_type="mariadb", conn_params=params, use_pool=False)
    manager.query_executor = MagicMock()
    manager.query_executor.registry.get_available_queries.return_value = []
    manager._initialized = True

    info = await manager.get_database_info()

    assert info["connection_params"]["password"] == REDACTED
    assert SECRET not in json.dumps(info, default=str)


@pytest.mark.parametrize("db_type", SyncDatabaseManager.get_supported_db_types())
def test_redact_secrets_masks_every_secret_kind(db_type: str) -> None:
    kinds = ConnectionParamsManager.param_kinds(db_type)
    params = dict.fromkeys(kinds, SECRET)

    redacted = ConnectionParamsManager.redact_secrets(db_type, params)

    assert {name for name, value in redacted.items() if value == REDACTED} == {
        name for name, kind in kinds.items() if kind == "secret"
    }
    assert params == dict.fromkeys(kinds, SECRET)  # no modifica la entrada


def test_redact_secrets_details() -> None:
    redacted = ConnectionParamsManager.redact_secrets(
        "hsqldb",
        {
            "user": "sa",
            "password": "",
            "connection_properties": {"PassWord": SECRET, "ifexists": "true", "x_password": None},
        },
    )
    assert redacted["password"] == ""  # vacío: no hay nada que ocultar
    assert redacted["connection_properties"] == {"PassWord": REDACTED, "ifexists": "true", "x_password": None}
