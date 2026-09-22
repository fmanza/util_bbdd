"""Módulo executors: Ejecutores de queries SQL sincrónico y asincrónico.

Proporciona abstracciones consolidadas para:
- Ejecutor sincrónico (sync_query_executor.py)
- Ejecutor asincrónico (async_query_executor.py)
"""

from .async_query_executor import AsyncQueryExecutor
from .sync_query_executor import SyncQueryExecutor

__all__: list[str] = [
    "SyncQueryExecutor",
    "AsyncQueryExecutor",
]
