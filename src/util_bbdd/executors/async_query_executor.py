"""Ejecutor de queries async."""

import asyncio
import logging
import re
import time

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from .._core.exceptions import (
    DatabaseOperationError,
    QueryNotFoundError,
    QueryTimeoutError,
    QueryValidationError,
)
from ..async_utils import maybe_await
from ..query.registry import QueryRegistry
from ..query.resolver import QueryResolver
from ..results import ResultNormalizer, RowOrNone, Rows

# ``%`` literales en SQL para drivers pyformat (PyMySQL/aiomysql): todo ``%`` que no sea marcador (``%s``,
# ``%(nombre)s``) ni esté ya escapado (``%%``) se duplica.
_PYFORMAT_LITERAL_PERCENT: re.Pattern[str] = re.compile(r"%%|%(?!\([A-Za-z_]\w*\)s|s)")

# asyncpg no es DB-API: se ejecuta con ``fetch``/``fetchrow`` y parámetros ``$n``. Se traducen los dos estilos con nombre
# que ya reconoce el ejecutor (``%(nombre)s``, el de psycopg en sync, y ``:nombre``); ``::`` (cast) y ``'10:30'`` no son
# parámetros. Hotfix A-02 (audit-code 2026-10-15b): literales ``'...'``, identificadores ``"..."`` y comentarios se
# reconocen antes y se dejan tal cual; sin ello ``SELECT ':id', :id`` enviaba ``'$1'`` y cambiaba el literal.
_ASYNCPG_PARAM: re.Pattern[str] = re.compile(
    r"""(?P<skip>'(?:[^']|'')*'|"(?:[^"]|"")*"|--[^\n]*|/\*.*?\*/)"""
    r"|%\((?P<pyformat>[A-Za-z_]\w*)\)s|(?<![:\w]):(?P<named>[A-Za-z_]\w*)",
    re.DOTALL,
)


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

    @asynccontextmanager
    async def _timeout_context(
        self, timeout_message: str, deadline_seconds: float | None
    ) -> AsyncGenerator[None, None]:
        if deadline_seconds is None:
            yield
            return
        try:
            async with asyncio.timeout(deadline_seconds):
                yield
        except TimeoutError as err:
            raise QueryTimeoutError(timeout_message) from err

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
                self.logger.debug("No se pudo materializar LOB en async", exc_info=True)
                return ""
        return value

    @staticmethod
    def _normalize_sql_for_db(sql: str, db_type: str, params: dict[str, Any] | None = None) -> str:
        """Escapa ``%`` literales para drivers pyformat (ver ``SyncQueryExecutor._normalize_sql_for_db``)."""
        if db_type == "mariadb":
            return sql.replace("%", "%%")
        if db_type == "mysql" and params and AsyncQueryExecutor._sql_uses_bind_params(sql, params):
            return _PYFORMAT_LITERAL_PERCENT.sub("%%", sql)
        return sql

    def _resolve_execute_params(self, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
        if self._sql_uses_bind_params(sql, params):
            return params
        return None

    @staticmethod
    def _is_asyncpg(conn: Any) -> bool:
        """``True`` con una conexión de asyncpg (también el proxy de su pool): no tiene cursores DB-API."""
        return type(conn).__module__.startswith("asyncpg")

    @staticmethod
    def _to_asyncpg(sql: str, params: dict[str, Any] | None) -> tuple[str, list[Any]]:
        """``sql`` con ``%(nombre)s``/``:nombre`` como ``$n`` (en orden de primera aparición) y sus valores."""
        if not params:
            return sql, []
        names: list[str] = []
        pyformat: bool = False

        def replace(match: re.Match[str]) -> str:
            nonlocal pyformat
            if match.group("skip") is not None:
                return match.group(0)
            name: str = match.group("pyformat") or match.group("named")
            if name not in params:
                return match.group(0)
            pyformat = pyformat or match.group("pyformat") is not None
            if name not in names:
                names.append(name)
            return f"${names.index(name) + 1}"

        translated: str = _ASYNCPG_PARAM.sub(replace, sql)
        if pyformat:
            translated = translated.replace("%%", "%")  # escape de psycopg; con ``$n`` el ``%`` es literal
        return translated, [params[name] for name in names]

    async def _fetch_asyncpg(
        self, conn: Any, sql: str, params: dict[str, Any] | None, expect_one: bool
    ) -> tuple[RowOrNone | Rows, int]:
        """Ejecuta ``sql`` con asyncpg (``fetchrow``/``fetch``) y normaliza como la vía de cursor."""
        driver_sql, args = self._to_asyncpg(sql, params)
        if expect_one:
            record = await conn.fetchrow(driver_sql, *args)
            result_one = self.result_normalizer.normalize_one(None if record is None else tuple(record))
            return result_one, 0 if result_one is None else 1
        records = await conn.fetch(driver_sql, *args)
        result_many = self.result_normalizer.normalize_many([tuple(record) for record in records])
        return result_many, len(result_many)

    async def _get_cursor(self, conn: Any) -> tuple[Any, bool]:
        if hasattr(conn, "cursor"):
            cursor = await maybe_await(conn.cursor())
            return cursor, cursor is not conn
        return conn, False

    async def _execute_sql_with_optional_params(self, cursor: Any, sql: str, params: dict[str, Any] | None) -> None:
        if params:
            await maybe_await(cursor.execute(sql, params))
            return
        await maybe_await(cursor.execute(sql))

    async def _fetch_and_normalize(self, cursor: Any, expect_one: bool) -> tuple[RowOrNone | Rows, int]:
        if expect_one:
            fetched_one = await maybe_await(cursor.fetchone())
            materialized_one = self._materialize_lob_value(fetched_one)
            result_one = self.result_normalizer.normalize_one(materialized_one)
            result_rows = 1 if result_one is not None else 0
            return result_one, result_rows

        fetched_many = await maybe_await(cursor.fetchall())
        materialized_many = self._materialize_lob_value(fetched_many)
        result_many = self.result_normalizer.normalize_many(materialized_many)
        return result_many, len(result_many)

    async def _cleanup_cursor_and_connection(self, owns_cursor: bool, cursor: Any, conn: Any) -> None:
        if owns_cursor and cursor and hasattr(cursor, "close"):
            try:
                await maybe_await(cursor.close())
            except Exception:
                self.logger.debug("No se pudo cerrar cursor async", exc_info=True)
        if conn:
            await self.connection_releaser(conn)

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
        start_time: float = time.perf_counter()  # monotónico (T1)

        try:
            async with self._timeout_context(
                f"Query execution exceeded timeout: {query_name}",
                deadline_seconds=deadline_seconds,
            ):
                resolved = self._get_bound_resolver(db_type).resolve(query_name=query_name, params=params)
                final_sql: str = self._normalize_sql_for_db(resolved.final_sql, db_type, params)
                self.logger.debug(f"SQL final: {final_sql}")

                conn = await self.connection_provider()
                execute_params = self._resolve_execute_params(final_sql, params)
                if self._is_asyncpg(conn):
                    result, result_rows = await self._fetch_asyncpg(conn, final_sql, execute_params, expect_one)
                else:
                    cursor, owns_cursor = await self._get_cursor(conn)
                    await self._execute_sql_with_optional_params(cursor, final_sql, execute_params)
                    result, result_rows = await self._fetch_and_normalize(cursor, expect_one)

            elapsed_ms: float = (time.perf_counter() - start_time) * 1000
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
            await self._cleanup_cursor_and_connection(owns_cursor, cursor, conn)

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
        start_time: float = time.perf_counter()  # monotónico (T1)

        try:
            async with self._timeout_context(
                "Custom query execution exceeded timeout",
                deadline_seconds=deadline_seconds,
            ):
                conn = await self.connection_provider()
                if self._is_asyncpg(conn):
                    result, result_rows = await self._fetch_asyncpg(conn, sql, params, expect_one)
                else:
                    cursor, owns_cursor = await self._get_cursor(conn)
                    await self._execute_sql_with_optional_params(cursor, sql, params)
                    result, result_rows = await self._fetch_and_normalize(cursor, expect_one)

            elapsed_ms: float = (time.perf_counter() - start_time) * 1000
            self.logger.debug(f"✅ Custom query executed: elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}")
            return result

        except QueryTimeoutError:
            raise
        except Exception as err:
            msg = f"Error executing custom query: {str(err)}"
            self.logger.error(msg, exc_info=True)
            raise DatabaseOperationError(msg, "CUSTOM", db_type="unknown") from err
        finally:
            await self._cleanup_cursor_and_connection(owns_cursor, cursor, conn)

    async def execute_query_many(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
        deadline_seconds: float | None = None,
    ) -> Rows:
        """Resuelve ``query_name`` para ``db_type`` con ``params``, la ejecuta y devuelve todas las filas.

        Raises:
            QueryNotFoundError: Si la consulta no existe para el motor.
            QueryValidationError: Si los parámetros no superan la validación del motor.
            QueryTimeoutError: Si se supera ``deadline_seconds``.
            DatabaseOperationError: Si falla la ejecución (el error original queda en ``__cause__``).
        """
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
        """Como :meth:`execute_query_many`, pero devuelve la primera fila o ``None``."""
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
        """Ejecuta ``sql`` (parámetros ``:nombre``) y devuelve todas las filas.

        Raises:
            QueryTimeoutError: Si se supera ``deadline_seconds``.
            DatabaseOperationError: Si falla la ejecución (el error original queda en ``__cause__``).
        """
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
        """Como :meth:`execute_custom_many`, pero devuelve la primera fila o ``None``."""
        result = await self._execute_custom(
            sql=sql,
            params=params,
            deadline_seconds=deadline_seconds,
            expect_one=True,
        )
        return self.result_normalizer.normalize_one(result)
