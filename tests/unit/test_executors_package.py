"""Tests de regresión para el paquete executors/ [SVC-04].

QueryExecutorBase (executors/base.py) era un contrato ABC huérfano: ningún
adaptador real (SyncQueryExecutor, AsyncQueryExecutor) heredaba de él, y sus
métodos abstractos async (execute_one/execute_many) ni siquiera coincidían con
la interfaz sync real de SyncQueryExecutor. Retirado como código muerto.
"""

from __future__ import annotations

import util_bbdd.executors as executors_pkg


def test_executors_package_does_not_export_query_executor_base() -> None:
    assert not hasattr(executors_pkg, "QueryExecutorBase")
    assert "QueryExecutorBase" not in executors_pkg.__all__


def test_executors_package_still_exports_real_executors() -> None:
    assert hasattr(executors_pkg, "SyncQueryExecutor")
    assert hasattr(executors_pkg, "AsyncQueryExecutor")


def test_sync_query_executor_does_not_inherit_from_removed_base() -> None:
    from util_bbdd.executors.sync_query_executor import SyncQueryExecutor

    base_names = {cls.__name__ for cls in SyncQueryExecutor.__mro__}
    assert "QueryExecutorBase" not in base_names


def test_async_query_executor_does_not_inherit_from_removed_base() -> None:
    from util_bbdd.executors.async_query_executor import AsyncQueryExecutor

    base_names = {cls.__name__ for cls in AsyncQueryExecutor.__mro__}
    assert "QueryExecutorBase" not in base_names
