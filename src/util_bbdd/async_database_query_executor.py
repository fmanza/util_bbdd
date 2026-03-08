"""Compat layer para el ejecutor async unificado."""

from .executors.async_query_executor import AsyncQueryExecutor


class AsyncDatabaseQueryExecutor(AsyncQueryExecutor):
    """Alias explícito del ejecutor async unificado.

    Mantiene un punto de import estable mientras se migra el código hacia
    `util_bbdd.executors.async_query_executor.AsyncQueryExecutor`.
    """
