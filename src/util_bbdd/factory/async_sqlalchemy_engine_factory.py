"""Factory async para crear AsyncEngine de SQLAlchemy según el tipo de base de datos."""

from __future__ import annotations

import logging

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from .._core.exceptions import ConnectionError, ValidationError
from ._pool_policy import engine_pool_kwargs
from ._url import get_test_query, render_url, sanitize_conn_str, server_url, sqlite_url


class AsyncSQLAlchemyEngineFactory:
    """Factory para crear y gestionar AsyncEngine de SQLAlchemy."""

    logger: logging.Logger = logging.getLogger(__name__)

    #: Motores cuyo AsyncEngine abre conexiones con ``ConnectionFactory.create_async_connection`` (``async_creator``):
    #: la URL solo elige el dialecto y los parámetros de ``conn_params`` se aplican igual que en los managers.
    _NATIVE_CREATOR_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"mariadb", "mysql", "oracle", "postgresql", "sqlserver"}
    )

    @staticmethod
    def _native_async_creator(
        db_type: str,
        conn_params: dict[str, Any],
        database: str | None,
    ) -> Callable[[], Awaitable[Any]] | None:
        """``async_creator`` que conecta con el driver async nativo de la librería (``None`` si no aplica)."""
        if db_type not in AsyncSQLAlchemyEngineFactory._NATIVE_CREATOR_TYPES:
            return None
        from ..connection.factory import ConnectionFactory

        params: dict[str, Any] = dict(conn_params)
        if database:
            params["database"] = database

        # Con ``async_creator`` SQLAlchemy no llama a ``dialect.create_connect_args``: el CLIENT.FOUND_ROWS que añade
        # el dialecto aiomysql (``rowcount`` = filas encontradas) hay que pedirlo aquí.
        extra: dict[str, Any] = {"found_rows": True} if db_type in ("mariadb", "mysql") else {}

        async def _async_creator() -> Any:
            return await ConnectionFactory.create_async_connection(db_type, params, **extra)

        return _async_creator

    @staticmethod
    async def create_engine(
        db_type: str,
        conn_params: dict[str, Any],
        database: str | None = None,
        use_pool: bool = True,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        pool_timeout: int | None = None,
        pool_recycle: int | None = None,
        sql_server_driver: str = "aioodbc",
    ) -> AsyncEngine:
        """Crea un AsyncEngine de SQLAlchemy basado en el tipo de base de datos.

        Los parámetros de pool que no se indiquen se toman de ``conn_params`` y, si faltan, de
        :data:`~util_bbdd.factory._pool_policy.ENGINE_POOL_DEFAULTS` (misma política que el Engine sync).
        """
        normalized_type: str = db_type.lower().strip()
        AsyncSQLAlchemyEngineFactory.logger.debug(f"🔧 Creando AsyncEngine de SQLAlchemy para {normalized_type}")

        # Para Oracle: validar que no se intente usar thick mode con async
        if normalized_type == "oracle" and conn_params.get("oracle_thick_mode"):
            raise ConnectionError(
                "El modo asincrónico de Oracle no es compatible con thick mode. "
                "Thick mode siempre usa thin, que solo conecta con Oracle 12.1+. "
                "Para Oracle 11g, use conexiones sincrónicas con oracle_thick_mode=True.",
                db_type="oracle",
            )

        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy.pool import NullPool

            if normalized_type == "mariadb":
                conn_str: str = AsyncSQLAlchemyEngineFactory._build_mariadb_connection_string(
                    conn_params,
                    database,
                )
            elif normalized_type == "mysql":
                conn_str = AsyncSQLAlchemyEngineFactory._build_mysql_connection_string(
                    conn_params,
                    database,
                )
            elif normalized_type == "oracle":
                conn_str = AsyncSQLAlchemyEngineFactory._build_oracle_connection_string(
                    conn_params,
                    database,
                )
            elif normalized_type == "postgresql":
                conn_str = AsyncSQLAlchemyEngineFactory._build_postgresql_connection_string(
                    conn_params,
                    database,
                )
            elif normalized_type == "hsqldb":
                raise ConnectionError(
                    "hsqldb async no soportado en SQLAlchemyEngineFactory",
                    db_type=normalized_type,
                )
            elif normalized_type == "sqlserver":
                conn_str = AsyncSQLAlchemyEngineFactory._build_sqlserver_connection_string(
                    conn_params,
                    database,
                    sql_server_driver,
                )
            elif normalized_type == "sqlite":
                conn_str = AsyncSQLAlchemyEngineFactory._build_sqlite_connection_string(conn_params)
            else:
                raise ConnectionError(
                    f"Tipo de BD no soportado para SQLAlchemy async: {db_type}",
                    db_type=normalized_type,
                )

            AsyncSQLAlchemyEngineFactory.logger.debug(
                "📝 Connection string async construido (sanitizado): %s",
                AsyncSQLAlchemyEngineFactory._sanitize_conn_str(conn_str),
            )

            engine_kwargs: dict[str, Any] = {
                "pool_pre_ping": True,
                "echo": False,
            }
            if use_pool:
                engine_kwargs.update(
                    engine_pool_kwargs(
                        normalized_type,
                        conn_params,
                        pool_size=pool_size,
                        max_overflow=max_overflow,
                        pool_timeout=pool_timeout,
                        pool_recycle=pool_recycle,
                    )
                )
            else:
                engine_kwargs["poolclass"] = NullPool

            async_creator = AsyncSQLAlchemyEngineFactory._native_async_creator(normalized_type, conn_params, database)
            if async_creator is not None:
                engine_kwargs["async_creator"] = async_creator

            engine: AsyncEngine = create_async_engine(conn_str, **engine_kwargs)

            # Verificar que la conexión funciona con query apropiada por motor
            test_query: str = AsyncSQLAlchemyEngineFactory._get_test_query(normalized_type)
            async with engine.connect() as conn:
                await conn.execute(text(test_query))

            AsyncSQLAlchemyEngineFactory.logger.info(
                "✅ AsyncEngine de SQLAlchemy creado exitosamente para %s",
                normalized_type,
            )
            return engine

        except ImportError as err:
            AsyncSQLAlchemyEngineFactory.logger.error("❌ SQLAlchemy async no está disponible")
            raise ConnectionError(
                "SQLAlchemy async no disponible. Instala con: pip install sqlalchemy",
                db_type=normalized_type,
                details=str(err),
            ) from err
        except ConnectionError:
            raise
        except Exception as err:
            AsyncSQLAlchemyEngineFactory.logger.error(
                "❌ Error creando AsyncEngine de SQLAlchemy: %s",
                err,
            )
            raise ConnectionError(
                f"Error creando AsyncEngine de SQLAlchemy: {str(err)}",
                db_type=normalized_type,
                details=str(err),
            ) from err

    # Helpers compartidos con SQLAlchemyEngineFactory (``factory/_url.py``).
    _get_test_query = staticmethod(get_test_query)
    _sanitize_conn_str = staticmethod(sanitize_conn_str)
    _render_url = staticmethod(render_url)

    @staticmethod
    def _build_mariadb_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """URL async de MariaDB (``mysql+aiomysql``); semántica común en ``factory/_url.py::server_url``."""
        return server_url("mariadb", "mysql+aiomysql", conn_params, database)

    @staticmethod
    def _build_mysql_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """URL async de MySQL (``mysql+aiomysql``); semántica común en ``factory/_url.py::server_url``."""
        return server_url("mysql", "mysql+aiomysql", conn_params, database)

    @staticmethod
    def _build_oracle_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """URL async de Oracle (``oracle+oracledb``); semántica común en ``factory/_url.py::server_url``."""
        return server_url("oracle", "oracle+oracledb", conn_params, database)

    @staticmethod
    def _build_postgresql_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """URL async de PostgreSQL (``postgresql+asyncpg``); semántica común en ``factory/_url.py::server_url``."""
        return server_url("postgresql", "postgresql+asyncpg", conn_params, database)

    @staticmethod
    def _build_sqlserver_connection_string(
        conn_params: dict[str, Any],
        database: str | None,
        sql_server_driver: str = "aioodbc",
    ) -> str:
        """URL async de SQL Server (solo ``mssql+aioodbc``); semántica común en ``factory/_url.py::server_url``."""
        url = server_url("sqlserver", "mssql+aioodbc", conn_params, database)
        if sql_server_driver != "aioodbc":
            raise ValidationError(
                "Para SQLAlchemy async en SQL Server use sql_server_driver='aioodbc'",
                db_type="sqlserver",
            )
        return url

    @staticmethod
    def _build_sqlite_connection_string(conn_params: dict[str, Any]) -> str:
        """
        Construye connection string para SQLite.

        Args:
            conn_params: Parámetros de conexión (requiere 'database').
                - database: Ruta al archivo SQLite o ':memory:' para BD en memoria

        Returns:
            Connection string para SQLite (URI de SQLAlchemy)

        Raises:
            ValidationError: Si faltan parámetros requeridos

        Example:
            >>> conn_params = {"database": "/path/to/app.db"}
            >>> AsyncSQLAlchemyEngineFactory._build_sqlite_connection_string(conn_params)
            'sqlite+aiosqlite:////path/to/app.db'
        """
        db_path_value: Any = conn_params.get("database", ":memory:")
        db_path: str = str(db_path_value) if db_path_value is not None else ""

        if not db_path:
            raise ValidationError(
                "Se requiere el parámetro 'database' para SQLite",
                db_type="sqlite",
            )

        return sqlite_url(db_path, "sqlite+aiosqlite")
