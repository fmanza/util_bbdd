"""P2 G1 de drivers-connections-audit (FASE 1, 2026-10-08): ``get_sqlalchemy_engine()`` reutiliza el Engine.

Cada llamada creaba un Engine nuevo (pool propio y ``SELECT 1`` de prueba) y nadie lo cerraba: llamarlo en un bucle
acumulaba pools abiertos. Ahora el manager guarda el Engine, lo devuelve en las siguientes llamadas y lo cierra
(``dispose``) en ``close()``.
"""

from __future__ import annotations

import asyncio

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory


def test_sync_manager_reuses_engine_and_disposes_it_on_close(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[MagicMock] = []

    def _create_engine(*_args: Any, **_kwargs: Any) -> MagicMock:
        created.append(MagicMock(name=f"engine{len(created)}"))
        return created[-1]

    monkeypatch.setattr(SQLAlchemyEngineFactory, "create_engine", staticmethod(_create_engine))
    manager = SyncDatabaseManager("sqlite", {"database": ":memory:"})

    first = manager.get_sqlalchemy_engine()
    assert manager.get_sqlalchemy_engine() is first
    manager.close()

    assert len(created) == 1
    first.dispose.assert_called_once()


def test_sync_manager_creates_a_new_engine_after_close(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SQLAlchemyEngineFactory, "create_engine", staticmethod(lambda *_a, **_k: MagicMock()))
    manager = SyncDatabaseManager("sqlite", {"database": ":memory:"})

    first = manager.get_sqlalchemy_engine()
    manager.close()

    assert manager.get_sqlalchemy_engine() is not first


def test_async_manager_reuses_engine_and_disposes_it_on_close(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("aiosqlite")
    engine = MagicMock()
    engine.dispose = AsyncMock()
    create = AsyncMock(return_value=engine)
    monkeypatch.setattr(AsyncSQLAlchemyEngineFactory, "create_engine", create)

    async def _run() -> None:
        manager = AsyncDatabaseManager("sqlite", {"database": ":memory:"})
        assert await manager.get_sqlalchemy_engine() is engine
        assert await manager.get_sqlalchemy_engine() is engine
        await manager.close()

    asyncio.run(_run())

    assert create.await_count == 1
    engine.dispose.assert_awaited_once()


@pytest.mark.parametrize(("finalizing", "close_connections"), [(False, True), (True, False)])
def test_sync_manager_close_does_not_close_engine_connections_during_finalization(
    monkeypatch: pytest.MonkeyPatch, finalizing: bool, close_connections: bool
) -> None:
    """Hotfix v0.40.1 (H2): cerrar las conexiones del driver en la finalización del intérprete no es fiable.

    Con ``close()`` desde ``__del__`` al salir, ``dispose()`` cerraba las conexiones del pool del Engine y el conector de
    MariaDB fallaba con ``InterfaceError: Invalid connection or not connected`` (traza de SQLAlchemy en la salida).
    """
    engine = MagicMock()
    monkeypatch.setattr(SQLAlchemyEngineFactory, "create_engine", staticmethod(lambda *_a, **_k: engine))
    manager = SyncDatabaseManager("sqlite", {"database": ":memory:"})
    manager.get_sqlalchemy_engine()

    monkeypatch.setattr("util_bbdd.managers.sync_mgr.sys.is_finalizing", lambda: finalizing)
    manager.close()

    engine.dispose.assert_called_once_with(close=close_connections)
