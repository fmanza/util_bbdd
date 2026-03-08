"""Gestor async de conexiones y ejecucion de consultas."""

from __future__ import annotations

import inspect
import logging

from collections.abc import Awaitable, Callable
from typing import Any

from .async_database_query_executor import AsyncDatabaseQueryExecutor
from .connection.connect_factory import ConnectFactory
from .factory.pool_factory import PoolFactory


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class AsyncDatabaseManager:
    """Manager async-first para conexiones directas o con pool."""

    def __init__(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        use_pool: bool = True,
        connection_factory: Callable[..., Awaitable[Any]] | None = None,
        pool_factory: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.db_type: str = db_type.lower().strip()
        self.conn_params: dict[str, Any] = conn_params
        self.database: str = str(conn_params.get("database", "") or "").strip()
        self.use_pool: bool = use_pool
        self._connection_factory: Callable[..., Awaitable[Any]] = (
            connection_factory or ConnectFactory.create_async_connection
        )
        self._pool_factory: Callable[..., Awaitable[Any]] = pool_factory or PoolFactory.create_async_pool

        self._initialized: bool = False
        self._connection: Any = None
        self.pool_connection: Any = None
        self.query_executor: AsyncDatabaseQueryExecutor | None = None

    async def ainit(self) -> AsyncDatabaseManager:
        """Inicializa recursos async una única vez."""
        if self._initialized:
            return self

        if self.use_pool:
            try:
                self.pool_connection = await self._pool_factory(self.db_type, self.conn_params)
            except NotImplementedError:
                self.use_pool = False

        if not self.use_pool:
            self._connection = await self._connection_factory(self.db_type, self.conn_params)

        self.query_executor = AsyncDatabaseQueryExecutor(
            connection_provider=self.get_connection,
            connection_releaser=self.release_connection,
        )
        self._initialized = True
        return self

    async def __aenter__(self) -> AsyncDatabaseManager:
        return await self.ainit()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def get_connection(self) -> Any:
        """Obtiene conexión del pool o directa."""
        if not self._initialized:
            await self.ainit()

        if self.pool_connection is not None:
            return await _maybe_await(self.pool_connection.acquire())

        return self._connection

    async def release_connection(self, connection: Any) -> None:
        """Libera conexión al pool o no-op en conexión directa."""
        if self.pool_connection is None:
            return
        await _maybe_await(self.pool_connection.release(connection))

    async def execute_custom_query(
        self,
        sql: str,
        params: Any | None = None,
        fetch_one: bool = False,
    ) -> Any:
        """Ejecuta SQL usando el executor async."""
        if not self._initialized:
            await self.ainit()

        if self.query_executor is None:
            raise RuntimeError("AsyncDatabaseQueryExecutor no inicializado")

        return await self.query_executor.execute_custom_query(
            sql=sql,
            params=params,
            fetch_one=fetch_one,
        )

    async def execute_query(
        self,
        query_name: str,
        fetch_one: bool = False,
        **params,
    ) -> Any:
        """Ejecuta query registrada por nombre usando el executor async.

        Args:
            query_name: Nombre de la query registrada
            fetch_one: Si True devuelve una fila, si False todas
            **params: Parámetros para la query

        Returns:
            Resultado de la query (lista de filas o una fila)

        Raises:
            QueryNotFoundError: Si la query no existe
            QueryValidationError: Si validación de parámetros falla
            RuntimeError: Si executor no está inicializado
        """
        if not self._initialized:
            await self.ainit()

        if self.query_executor is None:
            raise RuntimeError("AsyncDatabaseQueryExecutor no inicializado")

        return await self.query_executor.execute_query(
            query_name=query_name,
            db_type=self.db_type,
            params=params,
            fetch_one=fetch_one,
        )

    async def aclose(self) -> None:
        """Cierra pool o conexión directa."""
        if self.pool_connection is not None:
            await _maybe_await(self.pool_connection.aclose())
            self.pool_connection = None

        if self._connection is not None and hasattr(self._connection, "close"):
            await _maybe_await(self._connection.close())
            self._connection = None

    def _get_query_context_database(self) -> str:
        """Obtiene contexto schema/database para consultas de metadatos."""
        context_database: str = self.database
        if self.db_type == "oracle":
            oracle_user: str = str(self.conn_params.get("user", "")).strip()
            context_database = oracle_user or context_database
        elif self.db_type == "postgresql":
            explicit_schema: str = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "public"
        elif self.db_type == "hsqldb":
            explicit_schema = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "PUBLIC"
        elif self.db_type == "sqlserver":
            explicit_schema = str(self.conn_params.get("schema", "")).strip()
            context_database = explicit_schema or context_database or "dbo"
        return context_database

    def _add_metadata_context_params(self, params: dict[str, str], context: str | None) -> dict[str, str]:
        """Añade parámetros de contexto metadata según motor."""
        if not context or self.db_type == "mariadb":
            return params
        if self.db_type in {"oracle", "sqlserver"}:
            params["esquema"] = context
        if self.db_type in {"postgresql", "hsqldb", "sqlserver"}:
            params["database"] = context
        return params

    async def get_query_context_database(self) -> str:
        """Devuelve contexto efectivo schema/database para metadata."""
        return self._get_query_context_database()

    async def get_tables(self) -> list[Any]:
        context_database = self._get_query_context_database()
        return await self.execute_query("obtener_tablas", fetch_one=False, database=context_database)

    async def get_views(self) -> list[Any]:
        context_database = self._get_query_context_database()
        return await self.execute_query("obtener_vistas", fetch_one=False, database=context_database)

    async def get_routines(self) -> list[Any]:
        context_database = self._get_query_context_database()
        return await self.execute_query("obtener_rutinas", fetch_one=False, database=context_database)

    async def get_ddl(self, tabla: str) -> str:
        context_database = self._get_query_context_database()
        params: dict[str, str] = self._add_metadata_context_params({"tabla": tabla}, context_database)
        row = await self.execute_query("create_table", fetch_one=True, **params)
        return str(row[0]) if row else ""

    async def get_view_ddl(self, vista: str) -> str:
        context_database = self._get_query_context_database()
        params: dict[str, str] = self._add_metadata_context_params({"vista": vista}, context_database)
        row = await self.execute_query("create_view", fetch_one=True, **params)
        return str(row[0]) if row else ""

    async def get_columns(self, tabla: str) -> list[Any]:
        context_database = self._get_query_context_database()
        return await self.execute_query("columnas_tabla", fetch_one=False, database=context_database, tabla=tabla)

    async def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list[Any]:
        context_database = self._get_query_context_database()
        return await self.execute_query(
            "parametros_rutina",
            fetch_one=False,
            database=context_database,
            rutina=rutina,
            tipo_rutina=tipo_rutina.upper(),
        )

    async def get_routine_ddl(self, rutina: str, tipo_rutina: str) -> str:
        context_database = self._get_query_context_database()
        params: dict[str, str] = {
            "rutina": rutina,
            "tipo_rutina": tipo_rutina.upper(),
        }
        params = self._add_metadata_context_params(params, context_database)
        row = await self.execute_query("create_rutina", fetch_one=True, **params)
        return str(row[0]) if row else ""

    async def get_indices(self, tabla: str) -> list[Any]:
        context_database = self._get_query_context_database()
        params: dict[str, str] = self._add_metadata_context_params({"tabla": tabla}, context_database)
        return await self.execute_query("indices", fetch_one=False, **params)

    async def get_primary_keys(self, tabla: str) -> list[Any]:
        context_database = self._get_query_context_database()
        params: dict[str, str] = self._add_metadata_context_params({"tabla": tabla}, context_database)
        return await self.execute_query("claves_primarias", fetch_one=False, **params)

    async def get_foreign_keys(self, tabla: str) -> list[Any]:
        context_database = self._get_query_context_database()
        params: dict[str, str] = self._add_metadata_context_params({"tabla": tabla}, context_database)
        return await self.execute_query("claves_foraneas", fetch_one=False, **params)

    async def get_unique_constraints(self, tabla: str) -> list[Any]:
        context_database = self._get_query_context_database()
        params: dict[str, str] = self._add_metadata_context_params({"tabla": tabla}, context_database)
        return await self.execute_query("claves_unicas", fetch_one=False, **params)

    async def get_storage_inventory(self, tablespace: str | None = None) -> dict[str, Any]:
        context_database = self._get_query_context_database()
        results: dict[str, Any] = {"primary": [], "secondary": []}
        if self.db_type == "sqlserver":
            results["primary"] = await self.execute_query("ficheros_fisicos", fetch_one=False)
            return results
        if self.db_type == "oracle":
            if not tablespace:
                raise ValueError("Para Oracle debe proporcionar 'tablespace'")
            results["primary"] = await self.execute_query("ficheros_fisicos", fetch_one=False, tablespace=tablespace)
            return results
        if self.db_type == "mariadb":
            if not context_database:
                raise ValueError("Para MariaDB debe proporcionar 'database'")
            results["primary"] = await self.execute_query("ficheros_fisicos", fetch_one=False, database=context_database)
            results["secondary"] = await self.execute_query(
                "ficheros_fisicos_adicional",
                fetch_one=False,
                database=context_database,
            )
            return results
        if self.db_type == "postgresql":
            if not tablespace:
                raise ValueError("Para PostgreSQL debe proporcionar 'tablespace'")
            results["primary"] = await self.execute_query("ficheros_fisicos", fetch_one=False, tablespace=tablespace)
            results["secondary"] = await self.execute_query("temp_tablespaces", fetch_one=False)
            return results
        if self.db_type == "sqlite":
            results["primary"] = await self.execute_query("ficheros_fisicos", fetch_one=False)
            results["secondary"] = await self.execute_query("ficheros_fisicos_adicional", fetch_one=False)
            try:
                results["temp_tablespaces"] = await self.execute_query("temp_tablespaces", fetch_one=False)
            except Exception:
                results["temp_tablespaces"] = []
            return results
        return results

    async def get_database_version(self) -> str:
        row = await self.execute_query("database_version", fetch_one=True)
        return str(row[0]) if row else "Unknown"

    async def get_available_queries(self) -> list[str]:
        if not self._initialized:
            await self.ainit()
        if self.query_executor is None:
            raise RuntimeError("AsyncDatabaseQueryExecutor no inicializado")
        return self.query_executor.registry.get_available_queries(self.db_type)
