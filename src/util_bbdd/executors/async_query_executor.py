"""Ejecutor de queries async."""

import asyncio
import logging
import time

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from ..async_utils import maybe_await
from ..database_exceptions import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from ..query.registry import QueryRegistry
from ..query.resolver import QueryResolver
from ..result_normalizer import ResultNormalizer
from ..result_types import RowOrNone, Rows


class AsyncQueryExecutor:
    """Ejecuta queries SQL de forma asincrónica."""

    def __init__(
        self,
        connection_provider: Callable[[], Awaitable[Any]],
        connection_releaser: Callable[[Any], Awaitable[None]],
        registry: QueryRegistry | None = None,
        resolver: QueryResolver | None = None,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.connection_provider: Callable[[], Awaitable[Any]] = connection_provider
        self.connection_releaser: Callable[[Any], Awaitable[None]] = connection_releaser
        self.registry: QueryRegistry = registry or QueryRegistry()
        self.resolver: QueryResolver = resolver or QueryResolver(self.registry)
        self.result_normalizer = ResultNormalizer()

    @asynccontextmanager
    async def _timeout_context(self, timeout_message: str, deadline_seconds: float | None) -> AsyncIterator[None]:
        if deadline_seconds is None:
            yield
            return
        try:
            async with asyncio.timeout(deadline_seconds):
                yield
        except TimeoutError as err:
            raise QueryTimeoutError(timeout_message) from err

    async def _execute_resolved(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any],
        deadline_seconds: float | None,
        expect_one: bool,
    ) -> RowOrNone | Rows:
        conn = None
        cursor = None
        owns_cursor = False
        start_time: float = time.time()

        try:
            async with self._timeout_context(
                f"Query execution exceeded timeout: {query_name}",
                deadline_seconds=deadline_seconds,
            ):
                resolved = self.resolver.resolve(query_name, db_type, params)
                final_sql: str = resolved.final_sql
                if db_type == "mariadb":
                    final_sql = final_sql.replace("%", "%%")
                self.logger.debug(f"SQL final: {final_sql}")

                conn = await self.connection_provider()
                if hasattr(conn, "cursor"):
                    cursor = await maybe_await(conn.cursor())
                    owns_cursor = cursor is not conn
                else:
                    cursor = conn

                await maybe_await(cursor.execute(final_sql, params))
                if expect_one:
                    result = self.result_normalizer.normalize_one(await maybe_await(cursor.fetchone()))
                    result_rows = 1 if result is not None else 0
                else:
                    result = self.result_normalizer.normalize_many(await maybe_await(cursor.fetchall()))
                    result_rows = len(result)

            elapsed_ms: float = (time.time() - start_time) * 1000
            self.logger.debug(
                f"✅ Query executed: query_name={query_name}, db_type={db_type}, "
                f"elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}"
            )
            return result

        except (QueryNotFoundError, QueryValidationError, QueryTimeoutError):
            raise
        except Exception as err:
            msg = f"Error executing query {query_name}: {str(err)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "SELECT", db_type=db_type) from err
        finally:
            if owns_cursor and cursor and hasattr(cursor, "close"):
                try:
                    await maybe_await(cursor.close())
                except Exception:
                    self.logger.debug("No se pudo cerrar cursor async", exc_info=True)
            if conn:
                await self.connection_releaser(conn)

    async def _execute_custom(
        self,
        sql: str,
        params: dict[str, Any] | None,
        deadline_seconds: float | None,
        expect_one: bool,
    ) -> RowOrNone | Rows:
        conn = None
        cursor = None
        owns_cursor = False
        start_time: float = time.time()

        try:
            async with self._timeout_context(
                "Custom query execution exceeded timeout",
                deadline_seconds=deadline_seconds,
            ):
                conn = await self.connection_provider()
                if hasattr(conn, "cursor"):
                    cursor = await maybe_await(conn.cursor())
                    owns_cursor = cursor is not conn
                else:
                    cursor = conn

                execute_params: dict[str, Any] = params or {}
                await maybe_await(cursor.execute(sql, execute_params))
                if expect_one:
                    result = self.result_normalizer.normalize_one(await maybe_await(cursor.fetchone()))
                    result_rows = 1 if result is not None else 0
                else:
                    result = self.result_normalizer.normalize_many(await maybe_await(cursor.fetchall()))
                    result_rows = len(result)

            elapsed_ms: float = (time.time() - start_time) * 1000
            self.logger.debug(f"✅ Custom query executed: elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}")
            return result

        except QueryTimeoutError:
            raise
        except Exception as err:
            msg = f"Error executing custom query: {str(err)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "CUSTOM", db_type="unknown") from err
        finally:
            if owns_cursor and cursor and hasattr(cursor, "close"):
                try:
                    await maybe_await(cursor.close())
                except Exception:
                    self.logger.debug("No se pudo cerrar cursor async", exc_info=True)
            if conn:
                await self.connection_releaser(conn)

    async def execute_query_many(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
        deadline_seconds: float | None = None,
    ) -> Rows:
        result = await self._execute_resolved(
            query_name=query_name,
            db_type=db_type,
            params=params or {},
            deadline_seconds=deadline_seconds,
            expect_one=False,
        )
        return self.result_normalizer.normalize_many(result)

    async def execute_query_one(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
        deadline_seconds: float | None = None,
    ) -> RowOrNone:
        result = await self._execute_resolved(
            query_name=query_name,
            db_type=db_type,
            params=params or {},
            deadline_seconds=deadline_seconds,
            expect_one=True,
        )
        return self.result_normalizer.normalize_one(result)

    async def execute_custom_many(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        deadline_seconds: float | None = None,
    ) -> Rows:
        result = await self._execute_custom(
            sql=sql,
            params=params,
            deadline_seconds=deadline_seconds,
            expect_one=False,
        )
        return self.result_normalizer.normalize_many(result)

    async def execute_custom_one(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        deadline_seconds: float | None = None,
    ) -> RowOrNone:
        result = await self._execute_custom(
            sql=sql,
            params=params,
            deadline_seconds=deadline_seconds,
            expect_one=True,
        )
        return self.result_normalizer.normalize_one(result)
