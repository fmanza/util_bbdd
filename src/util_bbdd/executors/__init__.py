"""Módulo executors: Ejecutores de queries SQL sincrónico y asincrónico.

Proporciona abstracciones consolidadas para:
- Clase base común (base.py)
- Ejecutor sincrónico (sync_query_executor.py)
- Ejecutor asincrónico (async_query_executor.py)
"""

from .async_query_executor import AsyncQueryExecutor
from .base import QueryExecutorBase
from .sync_query_executor import SyncQueryExecutor

__all__ = [
    "QueryExecutorBase",
    "SyncQueryExecutor",
    "AsyncQueryExecutor",
]
