"""P2 de drivers-connections-audit (FASE 1, 2026-10-08): managers.

- **close()**: desde el commit 9ae9a46a (v0.6.6) el cuerpo de ``_verify_sync_executor_initialized`` quedó pegado al
  final de ``SyncDatabaseManager.close()``: cerrar un manager sin ejecutor (``__init__`` a medias, ``__exit__``,
  ``__del__``) lanzaba ``DatabaseOperationError``.
- **G2**: ``_init_pool`` capturaba cualquier ``ValueError`` y pasaba a conexión única sin pool, ocultando errores de
  configuración del pool. Solo HSQLDB (sin pool nativo) usa conexión única.
"""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd import SyncDatabaseManager
from util_bbdd.factory.pool_factory import PoolFactory


def test_close_without_query_executor_does_not_raise() -> None:
    manager = SyncDatabaseManager("sqlite", {"database": ":memory:"})
    manager.sync_query_executor = None

    manager.close()


def test_pool_errors_are_not_hidden_behind_single_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken_pool(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("pool_size fuera de rango")

    monkeypatch.setattr(PoolFactory, "create_pool", staticmethod(_broken_pool))

    with pytest.raises(Exception, match="pool_size fuera de rango"):
        SyncDatabaseManager("sqlite", {"database": ":memory:"})


def test_engines_without_native_pool_are_declared() -> None:
    assert "hsqldb" not in PoolFactory.SUPPORTED_POOL_TYPES
    assert {"mariadb", "mysql", "oracle", "postgresql", "sqlserver", "sqlite"} <= PoolFactory.SUPPORTED_POOL_TYPES
