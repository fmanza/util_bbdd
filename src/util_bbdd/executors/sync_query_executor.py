"""Ejecutor de queries sync."""

import logging
import time

from typing import Any, cast

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

    @staticmethod
    def _decode_binary_value(value: Any) -> Any:
        """Decodifica valores binarios de MariaDB con fallback multi-codec."""
        if isinstance(value, tuple):
            return tuple(SyncQueryExecutor._decode_binary_value(item) for item in value)
        if isinstance(value, list):
            return [SyncQueryExecutor._decode_binary_value(item) for item in value]
        if isinstance(value, (bytes, bytearray, memoryview)):
            return SyncQueryExecutor._safe_decode_bytes(bytes(value))
        return value

    @staticmethod
    def _safe_decode_bytes(raw: bytes) -> str | bytes:
        """Decodifica bytes con estrategia multi-codec fallback.

        Intenta decodificar en orden de probabilidad:
        1. utf-8 (más probable para Latin)
        2. cp1252 (Windows encoding)
        3. iso-8859-1 / latin-1 (universal)
        4. utf-16 (para datos internacionales específicos)
        5. HEX encoding (último recurso)
        """
        if not raw:
            return ""

        # Intenta decodificadores en orden de probabilidad
        decoders = ["utf-8", "cp1252", "iso-8859-1", "latin-1", "utf-16"]

        for codec in decoders:
            try:
                return raw.decode(codec)
            except (UnicodeDecodeError, LookupError):
                continue

        # Si todos fallan, retorna como HEX para preservar información
        return f"0x{raw.hex().upper()}"

    @staticmethod
    def _is_mariadb_connection(conn: Any) -> bool:
        module_name: str = str(type(conn).__module__).lower()
        return "mariadb" in module_name

    @staticmethod
    def _iter_exception_chain(err: BaseException) -> list[BaseException]:
        """Obtiene la cadena de errores enlazados sin bucles."""
        chain: list[BaseException] = []
        seen: set[int] = set()
        current: BaseException | None = err
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            chain.append(current)
            next_error = current.__cause__ if current.__cause__ is not None else current.__context__
            current = next_error
        return chain

    @staticmethod
    def _is_decode_error(err: BaseException) -> bool:
        for item in SyncQueryExecutor._iter_exception_chain(err):
            if isinstance(item, UnicodeDecodeError):
                return True
            message = str(item).lower()
            if "codec can't decode" in message:
                return True
        return False

    def _retry_fetch_with_binary_cursor(
        self,
        *,
        conn: Any,
        sql: str,
        params: dict[str, Any],
        expect_one: bool,
        deadline: float | None,
        timeout_msg: str,
    ) -> RowOrNone | Rows:
        binary_cursor = None
        try:
            self._raise_if_timed_out(deadline, timeout_msg)
            binary_cursor = conn.cursor(binary=True)
            binary_cursor.execute(sql, params or {})
            self._raise_if_timed_out(deadline, timeout_msg)

            if expect_one:
                fetched = binary_cursor.fetchone()
                decoded = self._decode_binary_value(fetched)
                return self.result_normalizer.normalize_one(decoded)

            fetched = binary_cursor.fetchall()
            decoded = self._decode_binary_value(fetched)
            return self.result_normalizer.normalize_many(decoded)
        finally:
            if binary_cursor and hasattr(binary_cursor, "close"):
                try:
                    binary_cursor.close()
                except Exception:
                    self.logger.debug("No se pudo cerrar cursor binario sync", exc_info=True)

    def _fetch_with_decode_fallback(
        self,
        *,
        cursor: Any,
        conn: Any,
        sql: str,
        params: dict[str, Any],
        expect_one: bool,
        db_type: str,
        deadline: float | None,
        timeout_msg: str,
    ) -> RowOrNone | Rows:
        try:
            if expect_one:
                return self.result_normalizer.normalize_one(cursor.fetchone())
            return self.result_normalizer.normalize_many(cursor.fetchall())
        except Exception as err:
            if db_type != "mariadb" and not self._is_mariadb_connection(conn):
                raise
            if not self._is_decode_error(err):
                raise
            self.logger.warning("Error de decodificación en fetch para MariaDB. Reintentando con cursor binario.")
            return self._retry_fetch_with_binary_cursor(
                conn=conn,
                sql=sql,
                params=params,
                expect_one=expect_one,
                deadline=deadline,
                timeout_msg=timeout_msg,
            )

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

            result = self._fetch_with_decode_fallback(
                cursor=cursor,
                conn=conn,
                sql=resolved.final_sql,
                params=params,
                expect_one=expect_one,
                db_type=db_type,
                deadline=deadline,
                timeout_msg=timeout_msg,
            )
            if expect_one:
                result_rows = 1 if result is not None else 0
            else:
                result_rows = len(cast(Rows, result))
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

            db_type_hint: str = "mariadb" if self._is_mariadb_connection(conn) else "unknown"
            result = self._fetch_with_decode_fallback(
                cursor=cursor,
                conn=conn,
                sql=sql,
                params=params or {},
                expect_one=expect_one,
                db_type=db_type_hint,
                deadline=deadline,
                timeout_msg=timeout_msg,
            )
            if expect_one:
                result_rows = 1 if result is not None else 0
            else:
                result_rows = len(cast(Rows, result))
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
