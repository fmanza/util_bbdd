"""Ejecutor de queries sync."""

import logging
import time

from typing import Any

from ..database_exceptions import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from ..query_registry import QueryRegistry
from ..query_resolver import QueryResolver
from ..result_normalizer import ResultNormalizer
from ..result_types import RowOrNone, Rows


class SyncQueryExecutor:
    """Ejecuta queries SQL de forma sincrónica."""

    def __init__(
        self,
        connection_provider,
        connection_releaser,
        registry: QueryRegistry | None = None,
        resolver: QueryResolver | None = None,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.connection_provider = connection_provider
        self.connection_releaser = connection_releaser
        self.registry: QueryRegistry = registry or QueryRegistry()
        self.resolver: QueryResolver = resolver or QueryResolver(self.registry)
        self.result_normalizer = ResultNormalizer()

    @staticmethod
    def _build_deadline(timeout: float | None) -> float | None:
        if timeout is None:
            return None
        return time.monotonic() + timeout

    @staticmethod
    def _raise_if_timed_out(deadline: float | None, message: str) -> None:
        if deadline is None:
            return
        if time.monotonic() >= deadline:
            raise QueryTimeoutError(message)

    def _execute_resolved(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any],
        timeout: float | None,
        expect_one: bool,
    ) -> RowOrNone | Rows:
        conn = None
        cursor = None
        start_time: float = time.time()
        timeout_msg: str = f"Query execution exceeded timeout: {query_name}"
        deadline = self._build_deadline(timeout)

        try:
            self._raise_if_timed_out(deadline, timeout_msg)
            resolved = self.resolver.resolve(query_name, db_type, params)
            self._raise_if_timed_out(deadline, timeout_msg)

            conn = self.connection_provider()
            self._raise_if_timed_out(deadline, timeout_msg)

            cursor = conn.cursor()
            cursor.execute(resolved.final_sql, params or {})
            self._raise_if_timed_out(deadline, timeout_msg)

            if expect_one:
                result = self.result_normalizer.normalize_one(cursor.fetchone())
                result_rows = 1 if result is not None else 0
            else:
                result = self.result_normalizer.normalize_many(cursor.fetchall())
                result_rows = len(result)
            self._raise_if_timed_out(deadline, timeout_msg)

            elapsed_ms: float = (time.time() - start_time) * 1000
            self.logger.debug(
                f"✅ Query executed: query_name={query_name}, db_type={db_type}, "
                f"elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}"
            )
            return result

        except TimeoutError as err:
            raise QueryTimeoutError(timeout_msg) from err
        except (QueryNotFoundError, QueryValidationError, QueryTimeoutError):
            raise
        except Exception as err:
            msg = f"Error executing query {query_name}: {str(err)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "SELECT", db_type=db_type) from err
        finally:
            if cursor and hasattr(cursor, "close"):
                try:
                    cursor.close()
                except Exception:
                    self.logger.debug("No se pudo cerrar cursor sync", exc_info=True)
            if conn:
                self.connection_releaser(conn)

    def _execute_custom(
        self,
        sql: str,
        params: dict[str, Any] | None,
        timeout: float | None,
        expect_one: bool,
    ) -> RowOrNone | Rows:
        conn = None
        cursor = None
        start_time: float = time.time()
        timeout_msg = "Custom query execution exceeded timeout"
        deadline = self._build_deadline(timeout)

        try:
            self._raise_if_timed_out(deadline, timeout_msg)
            conn = self.connection_provider()
            self._raise_if_timed_out(deadline, timeout_msg)

            cursor = conn.cursor()
            cursor.execute(sql, params or {})
            self._raise_if_timed_out(deadline, timeout_msg)

            if expect_one:
                result = self.result_normalizer.normalize_one(cursor.fetchone())
                result_rows = 1 if result is not None else 0
            else:
                result = self.result_normalizer.normalize_many(cursor.fetchall())
                result_rows = len(result)
            self._raise_if_timed_out(deadline, timeout_msg)

            elapsed_ms: float = (time.time() - start_time) * 1000
            self.logger.debug(f"✅ Custom query executed: elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}")
            return result

        except TimeoutError as err:
            raise QueryTimeoutError(timeout_msg) from err
        except QueryTimeoutError:
            raise
        except Exception as err:
            msg = f"Error executing custom query: {str(err)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "CUSTOM", db_type="unknown") from err
        finally:
            if cursor and hasattr(cursor, "close"):
                try:
                    cursor.close()
                except Exception:
                    self.logger.debug("No se pudo cerrar cursor sync", exc_info=True)
            if conn:
                self.connection_releaser(conn)

    def execute_query_many(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> Rows:
        result = self._execute_resolved(
            query_name=query_name,
            db_type=db_type,
            params=params,
            timeout=timeout,
            expect_one=False,
        )
        return self.result_normalizer.normalize_many(result)

    def execute_query_one(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> RowOrNone:
        result = self._execute_resolved(
            query_name=query_name,
            db_type=db_type,
            params=params,
            timeout=timeout,
            expect_one=True,
        )
        return self.result_normalizer.normalize_one(result)

    def execute_custom_many(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Rows:
        result = self._execute_custom(
            sql=sql,
            params=params,
            timeout=timeout,
            expect_one=False,
        )
        return self.result_normalizer.normalize_many(result)

    def execute_custom_one(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> RowOrNone:
        result = self._execute_custom(
            sql=sql,
            params=params,
            timeout=timeout,
            expect_one=True,
        )
        return self.result_normalizer.normalize_one(result)
