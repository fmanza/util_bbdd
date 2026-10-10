"""Simetría sync/async del ciclo de vida de los managers (API 1.0, decisión A4).

Ambos managers exponen ``init()``, ``release_connection()`` y los validadores estáticos de tipo con el mismo nombre;
``SyncDatabaseManager.close_connection()`` queda como alias deprecado de ``release_connection()`` hasta 1.0.0.
"""

from __future__ import annotations

import inspect

from unittest.mock import MagicMock

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager

SHARED_LIFECYCLE: tuple[str, ...] = (
    "init",
    "get_connection",
    "release_connection",
    "close",
    "get_supported_db_types",
    "is_db_type_supported",
    "validate_db_type_static",
    "get_db_type_info_static",
)


@pytest.mark.parametrize("name", SHARED_LIFECYCLE)
def test_both_managers_expose_the_same_lifecycle_name(name: str) -> None:
    assert callable(getattr(SyncDatabaseManager, name))
    assert callable(getattr(AsyncDatabaseManager, name))


@pytest.mark.parametrize("name", ("init", "get_connection", "release_connection", "close"))
def test_async_lifecycle_methods_are_coroutines(name: str) -> None:
    assert inspect.iscoroutinefunction(getattr(AsyncDatabaseManager, name))
    assert not inspect.iscoroutinefunction(getattr(SyncDatabaseManager, name))


@pytest.mark.parametrize("manager_cls", (SyncDatabaseManager, AsyncDatabaseManager))
def test_static_db_type_validators_agree(manager_cls: type) -> None:
    assert manager_cls.is_db_type_supported("sqlite") is SyncDatabaseManager.is_db_type_supported("sqlite")
    assert manager_cls.is_db_type_supported("motor_inexistente") is False
    assert manager_cls.validate_db_type_static("sqlite") is True


@pytest.fixture
def sync_manager():
    manager = SyncDatabaseManager("sqlite", {"database": ":memory:"}, use_pool=False)
    yield manager
    manager.close()


def test_sync_init_is_idempotent_and_returns_self(sync_manager: SyncDatabaseManager) -> None:
    connection = sync_manager.connection
    assert sync_manager.init() is sync_manager
    assert sync_manager.init() is sync_manager
    assert sync_manager.connection is connection


def test_sync_release_connection_delegates_to_session(sync_manager: SyncDatabaseManager) -> None:
    session = MagicMock()
    sync_manager.session_manager = session
    conn = object()
    sync_manager.release_connection(conn)
    session.close_connection.assert_called_once_with(connection=conn)


def test_sync_close_connection_is_a_deprecated_alias(sync_manager: SyncDatabaseManager) -> None:
    session = MagicMock()
    sync_manager.session_manager = session
    conn = object()
    with pytest.warns(DeprecationWarning, match=r"usa 'release_connection\(\)'") as record:
        sync_manager.close_connection(conn)
    session.close_connection.assert_called_once_with(connection=conn)
    assert record[0].filename == __file__


def test_sync_queries_do_not_use_the_deprecated_alias(
    sync_manager: SyncDatabaseManager, recwarn: pytest.WarningsRecorder
) -> None:
    sync_manager.execute_custom_many("SELECT 1 AS x")
    assert not [w for w in recwarn if "close_connection" in str(w.message)]
