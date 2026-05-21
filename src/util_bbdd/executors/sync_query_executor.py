"""Ejecutor de queries sync."""

import logging
import re
import time

from typing import Any, cast

from .._core.exceptions import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from ..query.registry import QueryRegistry
from ..query.resolver import QueryResolver
from ..results import ResultNormalizer, RowOrNone, Rows


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
        self._bound_resolvers: dict[str, QueryResolver] = {}
        self.result_normalizer = ResultNormalizer()

    def _get_bound_resolver(self, db_type: str) -> QueryResolver:
        """Obtiene un resolver ligado al motor para reutilizar validaciones/cache."""
        normalized_db_type: str = db_type.lower().strip()
        bound_resolver: QueryResolver | None = self._bound_resolvers.get(normalized_db_type)
        if bound_resolver is None:
            bound_resolver = self.resolver.bind(normalized_db_type)
            self._bound_resolvers[normalized_db_type] = bound_resolver
        return bound_resolver

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
    def _sql_uses_bind_params(sql: str, params: dict[str, Any]) -> bool:
        if not params:
            return False
        if re.search(r"%\([A-Za-z_]\w*\)s", sql):
            return True
        if "%s" in sql:
            return True
        if "?" in sql:
            return True
        return re.search(r"(?<!:):[A-Za-z_]\w*", sql) is not None

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
        """Decodifica bytes binarios de MariaDB sin forzar conversiones ambiguas.

        Estrategia:
        1. `utf-8` para datos correctamente codificados.
        2. `cp1252` para el caso legacy más habitual en MariaDB/Windows.
        3. `HEX` como preservación literal cuando no se puede inferir un texto fiable.

        No se usa `latin-1`/`iso-8859-1` porque decodifican cualquier secuencia de bytes
        y convierten errores de encoding en texto potencialmente corrupto.
        """
        if not raw:
            return ""

        decoders: list[str] = ["utf-8", "cp1252"]

        for codec in decoders:
            try:
                return raw.decode(codec)
            except (UnicodeDecodeError, LookupError):
                continue

        return f"0x{raw.hex().upper()}"

    @staticmethod
    def _is_lob_value(value: Any) -> bool:
        try:
            read = value.read
        except AttributeError:
            return False
        return callable(read)

    def _materialize_lob_value(self, value: Any) -> Any:
        """Materializa LOB/CLOB/BLOB mientras la conexión sigue abierta."""
        if isinstance(value, tuple):
            return tuple(self._materialize_lob_value(item) for item in value)
        if isinstance(value, list):
            return [self._materialize_lob_value(item) for item in value]
        if self._is_lob_value(value):
            try:
                return value.read()
            except Exception:
                self.logger.debug("No se pudo materializar LOB en sync", exc_info=True)
                return ""
        return value

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
            # mariadb C-extension raises SystemError via fetchrows (called by fetchall)
            # when charset data cannot be decoded, without chaining a UnicodeDecodeError
            if "returned a result with an exception set" in message:
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
        saved_charset: str | None = None
        try:
            self._raise_if_timed_out(deadline, timeout_msg)
            # binary=True uses prepared-stmt protocol but still does charset conversion;
            # setting character_set='binary' makes the server send raw bytes instead,
            # bypassing the C-ext conversion bug that affects both fetchrows and fetchone
            try:
                saved_charset = conn.character_set
                conn.character_set = "binary"
            except Exception:
                pass
            binary_cursor = conn.cursor()

            if params:
                binary_cursor.execute(sql, params)
            else:
                binary_cursor.execute(sql)

            self._raise_if_timed_out(deadline, timeout_msg)

            if expect_one:
                fetched = binary_cursor.fetchone()
                decoded = self._decode_binary_value(fetched)
                return self.result_normalizer.normalize_one(decoded)

            rows: list[Any] = []
            row = binary_cursor.fetchone()
            while row is not None:
                rows.append(row)
                row = binary_cursor.fetchone()
            decoded = self._decode_binary_value(rows)
            return self.result_normalizer.normalize_many(decoded)
        finally:
            if binary_cursor and hasattr(binary_cursor, "close"):
                try:
                    binary_cursor.close()
                except Exception:
                    self.logger.debug("No se pudo cerrar cursor binario sync", exc_info=True)
            if saved_charset is not None:
                try:
                    conn.character_set = saved_charset
                except Exception:
                    pass

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
                raw_one = cursor.fetchone()
                materialized_one = self._materialize_lob_value(raw_one)
                return self.result_normalizer.normalize_one(materialized_one)
            raw_many = cursor.fetchall()
            materialized_many = self._materialize_lob_value(raw_many)
            return self.result_normalizer.normalize_many(materialized_many)
        except Exception as err:
            if db_type != "mariadb" and not self._is_mariadb_connection(conn):
                raise
            if not self._is_decode_error(err):
                raise
            self.logger.warning(
                "Error de decodificación en fetch para MariaDB. Activando ruta de seguridad con cursor binario."
            )
            return self._retry_fetch_with_binary_cursor(
                conn=conn,
                sql=sql,
                params=params,
                expect_one=expect_one,
                deadline=deadline,
                timeout_msg=timeout_msg,
            )

    @staticmethod
    def _resolve_execute_params(sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
        if SyncQueryExecutor._sql_uses_bind_params(sql, params):
            return params
        return None

    @staticmethod
    def _execute_sql_with_optional_params(cursor: Any, sql: str, params: dict[str, Any] | None) -> None:
        if params:
            cursor.execute(sql, params)
            return
        cursor.execute(sql)

    @staticmethod
    def _calculate_result_rows(result: RowOrNone | Rows, expect_one: bool) -> int:
        if expect_one:
            return 1 if result is not None else 0
        return len(cast(Rows, result))

    def _cleanup_cursor_and_connection(self, cursor: Any, conn: Any) -> None:
        if cursor and hasattr(cursor, "close"):
            try:
                cursor.close()
            except Exception:
                self.logger.debug("No se pudo cerrar cursor sync", exc_info=True)
        if conn:
            self.connection_releaser(conn)

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
            resolved = self._get_bound_resolver(db_type).resolve(query_name=query_name, params=params)
            self._raise_if_timed_out(deadline, timeout_msg)

            conn = self.connection_provider()
            self._raise_if_timed_out(deadline, timeout_msg)

            cursor = conn.cursor()
            execute_params = self._resolve_execute_params(resolved.final_sql, params)
            self._execute_sql_with_optional_params(cursor, resolved.final_sql, execute_params)
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
            result_rows = self._calculate_result_rows(result, expect_one)
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
            self._cleanup_cursor_and_connection(cursor, conn)

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
        deadline: float | None = self._build_deadline(timeout)

        try:
            self._raise_if_timed_out(deadline, timeout_msg)
            conn = self.connection_provider()
            self._raise_if_timed_out(deadline, timeout_msg)

            cursor = conn.cursor()
            self._execute_sql_with_optional_params(cursor, sql, params)
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
            result_rows: int = self._calculate_result_rows(result, expect_one)
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
            self._cleanup_cursor_and_connection(cursor, conn)

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
