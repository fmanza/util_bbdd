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
from ..results import CustomQueryResult, ResultNormalizer, RowOrNone, Rows
from ._oracle_numbers import prepare_query_cursor
from ._read_only import is_server_timeout, read_only_statements, server_timeout_statements, validate_max_rows

# ``%`` literales en SQL para drivers pyformat (PyMySQL/aiomysql): todo ``%`` que no sea marcador (``%s``,
# ``%(nombre)s``) ni esté ya escapado (``%%``) se duplica.
_PYFORMAT_LITERAL_PERCENT: re.Pattern[str] = re.compile(r"%%|%(?!\([A-Za-z_]\w*\)s|s)")


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
        max_rows: int | None = None,
    ) -> RowOrNone | Rows:
        binary_cursor = None
        saved_charset: str | None = None
        try:
            self._raise_if_timed_out(deadline, timeout_msg)
            # conn.character_set setter is client-side only and does NOT send SET NAMES
            # to the server; use explicit SQL so character_set_results='binary' is set
            # server-side, making the C-ext return raw bytes instead of decoding as utf-8
            try:
                saved_charset = str(getattr(conn, "character_set", "utf8mb4"))
                set_cursor = conn.cursor()
                set_cursor.execute("SET NAMES 'binary'")
                set_cursor.close()
            except Exception:
                saved_charset = None
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
                if max_rows is not None and len(rows) >= max_rows:
                    break
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
                    restore_cursor = conn.cursor()
                    restore_cursor.execute(f"SET NAMES '{saved_charset}'")
                    restore_cursor.close()
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
        max_rows: int | None = None,
    ) -> RowOrNone | Rows:
        try:
            if expect_one:
                raw_one = cursor.fetchone()
                materialized_one = self._materialize_lob_value(raw_one)
                return self.result_normalizer.normalize_one(materialized_one)
            # G20 (v4.6.0): con max_rows, solo esas filas llegan a memoria (fetchmany).
            raw_many = cursor.fetchall() if max_rows is None else cursor.fetchmany(max_rows)
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
                max_rows=max_rows,
            )

    @staticmethod
    def _normalize_sql_for_db(sql: str, db_type: str, params: dict[str, Any] | None = None) -> str:
        """Escapa ``%`` literales en SQL final para MariaDB (paramstyle pyformat).

        SVC-03 (AUDIT_CODE 2026-09-22): esta normalización ya existía en
        ``AsyncQueryExecutor`` pero faltaba aquí (asimetría sync/async).

        MySQL (PyMySQL) solo formatea con ``%`` cuando recibe parámetros: sin ellos el SQL llega tal cual y escapar
        rompería los ``%`` literales (``LIKE 'a%'``); con ellos se escapan los ``%`` que no son marcadores.
        """
        if db_type == "mariadb":
            return sql.replace("%", "%%")
        if db_type == "mysql" and params and SyncQueryExecutor._sql_uses_bind_params(sql, params):
            return _PYFORMAT_LITERAL_PERCENT.sub("%%", sql)
        return sql

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
        start_time: float = time.perf_counter()  # monotónico (T1)
        timeout_msg: str = f"Query execution exceeded timeout: {query_name}"
        deadline = self._build_deadline(timeout)

        try:
            self._raise_if_timed_out(deadline, timeout_msg)
            resolved = self._get_bound_resolver(db_type).resolve(query_name=query_name, params=params)
            final_sql: str = self._normalize_sql_for_db(resolved.final_sql, db_type, params)
            self._raise_if_timed_out(deadline, timeout_msg)

            conn = self.connection_provider()
            self._raise_if_timed_out(deadline, timeout_msg)

            cursor = conn.cursor()
            prepare_query_cursor(conn, cursor)
            execute_params = self._resolve_execute_params(final_sql, params)
            self._execute_sql_with_optional_params(cursor, final_sql, execute_params)
            self._raise_if_timed_out(deadline, timeout_msg)

            result = self._fetch_with_decode_fallback(
                cursor=cursor,
                conn=conn,
                sql=final_sql,
                params=params,
                expect_one=expect_one,
                db_type=db_type,
                deadline=deadline,
                timeout_msg=timeout_msg,
            )
            result_rows = self._calculate_result_rows(result, expect_one)
            self._raise_if_timed_out(deadline, timeout_msg)

            elapsed_ms: float = (time.perf_counter() - start_time) * 1000
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
        *,
        read_only: bool = False,
        max_rows: int | None = None,
        db_type: str | None = None,
        columns: list[str] | None = None,
        server_timeout: bool = False,
    ) -> RowOrNone | Rows:
        """Ejecuta ``sql``; con ``columns``, añade ahí los nombres de columna del cursor (``execute_custom_result``).

        ``server_timeout`` (5.0.0): con ``read_only``, ``timeout`` también es el plazo del servidor
        (``server_timeout_statements``), y su cancelación se lanza como ``QueryTimeoutError``.
        """
        conn = None
        cursor = None
        start_time: float = time.perf_counter()  # monotónico (T1)
        timeout_msg = "Custom query execution exceeded timeout"
        deadline: float | None = self._build_deadline(timeout)
        validate_max_rows(max_rows)
        prelude, epilogue = read_only_statements(db_type) if read_only else ((), ())
        if read_only and server_timeout:
            prelude += server_timeout_statements(db_type, timeout)

        try:
            self._raise_if_timed_out(deadline, timeout_msg)
            conn = self.connection_provider()
            self._raise_if_timed_out(deadline, timeout_msg)

            if read_only:
                self._start_read_only(conn, prelude)
            cursor = conn.cursor()
            prepare_query_cursor(conn, cursor)
            self._execute_sql_with_optional_params(cursor, sql, params)
            self._raise_if_timed_out(deadline, timeout_msg)
            if columns is not None:
                columns.extend(str(item[0]) for item in cursor.description or ())
                if cursor.description is None:  # sin conjunto de resultados (p. ej. un DML): no hay filas que leer
                    return []

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
                max_rows=max_rows,
            )
            result_rows: int = self._calculate_result_rows(result, expect_one)
            self._raise_if_timed_out(deadline, timeout_msg)

            elapsed_ms: float = (time.perf_counter() - start_time) * 1000
            self.logger.debug(f"✅ Custom query executed: elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}")
            return result

        except TimeoutError as err:
            raise QueryTimeoutError(timeout_msg) from err
        except QueryTimeoutError:
            raise
        except Exception as err:
            if server_timeout and is_server_timeout(err):
                raise QueryTimeoutError(timeout_msg) from err
            msg = f"Error executing custom query: {str(err)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "CUSTOM", db_type="unknown") from err
        finally:
            if read_only and conn is not None:
                self._end_read_only(conn, epilogue)
            self._cleanup_cursor_and_connection(cursor, conn)

    def _start_read_only(self, conn: Any, prelude: tuple[str, ...]) -> None:
        """Cierra la transacción abierta y pone la siguiente (o la sesión) en solo lectura (G19)."""
        self._rollback_quietly(conn)
        cursor = conn.cursor()
        try:
            for statement in prelude:
                cursor.execute(statement)
        finally:
            cursor.close()

    def _end_read_only(self, conn: Any, epilogue: tuple[str, ...]) -> None:
        """``rollback()`` siempre (nada queda confirmado) y quita las marcas de sesión; un fallo aquí solo se registra."""
        self._rollback_quietly(conn)
        try:
            cursor = conn.cursor()
            try:
                for statement in epilogue:
                    cursor.execute(statement)
            finally:
                cursor.close()
        except Exception:
            self.logger.warning("No se pudo restaurar la sesión tras una consulta read_only", exc_info=True)

    def _rollback_quietly(self, conn: Any) -> None:
        """``conn.rollback()``; con autocommit (JDBC de HSQLDB) el driver puede rechazarlo, y no hay nada que deshacer."""
        try:
            conn.rollback()
        except Exception:
            self.logger.debug("rollback() no aplicable en esta conexión", exc_info=True)

    def execute_query_many(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> Rows:
        """Resuelve ``query_name`` para ``db_type`` con ``params``, la ejecuta y devuelve todas las filas.

        Raises:
            QueryNotFoundError: Si la consulta no existe para el motor.
            QueryValidationError: Si los parámetros no superan la validación del motor.
            QueryTimeoutError: Si se supera ``timeout`` (segundos).
            DatabaseOperationError: Si falla la ejecución (el error original queda en ``__cause__``).
        """
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
        """Como :meth:`execute_query_many`, pero devuelve la primera fila o ``None``."""
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
        *,
        read_only: bool = False,
        max_rows: int | None = None,
        db_type: str | None = None,
    ) -> Rows:
        """Ejecuta ``sql`` (parámetros ``:nombre``) y devuelve todas las filas.

        Args:
            sql: Consulta.
            params: Parámetros de *bind*.
            timeout: Segundos máximos.
            read_only: Ejecuta en una transacción de solo lectura del motor que termina siempre en ``rollback``
                (``executors._read_only``; v4.6.0, G19). Necesita ``db_type``.
            max_rows: Como mucho estas filas (``fetchmany``; v4.6.0, G20).
            db_type: Motor de la conexión (lo pasa el manager).

        Raises:
            QueryTimeoutError: Si se supera ``timeout`` (segundos).
            DatabaseOperationError: Si falla la ejecución (el error original queda en ``__cause__``).
            ValueError: Si ``max_rows`` no es un entero ≥ 1, o ``read_only`` sin ``db_type`` válido.
        """
        result = self._execute_custom(
            sql=sql,
            params=params,
            timeout=timeout,
            expect_one=False,
            read_only=read_only,
            max_rows=max_rows,
            db_type=db_type,
        )
        return self.result_normalizer.normalize_many(result)

    def execute_custom_one(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        *,
        read_only: bool = False,
        db_type: str | None = None,
    ) -> RowOrNone:
        """Como :meth:`execute_custom_many`, pero devuelve la primera fila o ``None``."""
        result = self._execute_custom(
            sql=sql,
            params=params,
            timeout=timeout,
            expect_one=True,
            read_only=read_only,
            db_type=db_type,
        )
        return self.result_normalizer.normalize_one(result)

    def execute_custom_result(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
        *,
        read_only: bool = False,
        max_rows: int | None = None,
        db_type: str | None = None,
    ) -> CustomQueryResult:
        """Como :meth:`execute_custom_many`, pero devuelve también los nombres de columna (5.0.0, G42).

        Con ``read_only`` y ``timeout``, en PostgreSQL el plazo también corta la consulta en el servidor
        (``SET LOCAL statement_timeout``, D8-4).

        Raises:
            QueryTimeoutError: Si se supera ``timeout`` (en el cliente o, en PostgreSQL, en el servidor).
            DatabaseOperationError: Si falla la ejecución (el error original queda en ``__cause__``).
            ValueError: Si ``max_rows`` no es un entero ≥ 1, o ``read_only`` sin ``db_type`` válido.
        """
        columns: list[str] = []
        result = self._execute_custom(
            sql=sql,
            params=params,
            timeout=timeout,
            expect_one=False,
            read_only=read_only,
            max_rows=max_rows,
            db_type=db_type,
            columns=columns,
            server_timeout=True,
        )
        return CustomQueryResult(columns=tuple(columns), rows=self.result_normalizer.normalize_many(result))
