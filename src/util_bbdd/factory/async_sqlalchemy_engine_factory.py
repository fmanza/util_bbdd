"""Factory async para crear AsyncEngine de SQLAlchemy según el tipo de base de datos."""

from __future__ import annotations

import logging

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from .._core.exceptions import ConnectionError, ValidationError
from ._pool_policy import engine_pool_kwargs
from ._url import get_test_query, render_url, sanitize_conn_str, sqlite_url


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
        """Construye connection string para MariaDB.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para MariaDB

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        host_value: Any = conn_params.get("host", "localhost")
        host: str = str(host_value) if host_value is not None else "localhost"

        user_value: Any = conn_params.get("user", "root")
        user: str = str(user_value) if user_value is not None else "root"

        password_value: Any = conn_params.get("password")
        password: str | None = str(password_value) if password_value is not None else None

        port_value: Any = conn_params.get("port", 3306)
        port: int = int(port_value)

        if not password:
            AsyncSQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para MariaDB")
            raise ValidationError(
                "Se requiere una contraseña para la conexión a MariaDB",
                db_type="mariadb",
            )

        raw_target_db: Any = database if database is not None else conn_params.get("database")
        target_db: str = str(raw_target_db) if raw_target_db is not None else ""
        if not target_db:
            raise ValidationError("Se requiere 'database' para MariaDB", db_type="mariadb")

        return AsyncSQLAlchemyEngineFactory._render_url("mysql+aiomysql", user, password, host, port, target_db)

    @staticmethod
    def _build_mysql_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """Construye connection string async para MySQL (``mysql+aiomysql``).

        Usuario y contraseña se escapan con ``URL.create`` (admiten ``@``, ``:`` o ``/``).

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos (si es None, se usa ``conn_params["database"]``)

        Returns:
            Connection string para MySQL

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        password_value: Any = conn_params.get("password")
        if password_value is None or not str(password_value):
            AsyncSQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para MySQL")
            raise ValidationError("Se requiere una contraseña para la conexión a MySQL", db_type="mysql")

        raw_target_db: Any = database if database is not None else conn_params.get("database")
        target_db: str = str(raw_target_db) if raw_target_db is not None else ""
        if not target_db:
            raise ValidationError("Se requiere 'database' para MySQL", db_type="mysql")

        return render_url(
            "mysql+aiomysql",
            conn_params.get("user") or "root",
            password_value,
            conn_params.get("host") or "localhost",
            conn_params.get("port", 3306),
            target_db,
        )

    @staticmethod
    def _build_oracle_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """Construye connection string para Oracle.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para Oracle

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        user_value: Any = conn_params.get("user")
        user: str | None = str(user_value) if user_value is not None else None

        password_value: Any = conn_params.get("password")
        password: str | None = str(password_value) if password_value is not None else None

        host_value: Any = conn_params.get("host", "localhost")
        host: str = str(host_value) if host_value is not None else "localhost"

        port_value: Any = conn_params.get("port", 1521)
        port: int = int(port_value)

        service_name_value: Any = conn_params.get("service_name")
        raw_service_name: Any = service_name_value if service_name_value is not None else database
        service_name: str = str(raw_service_name) if raw_service_name is not None else ""

        if not user:
            AsyncSQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó usuario para Oracle")
            raise ValidationError(
                "Se requiere un usuario para la conexión a Oracle",
                db_type="oracle",
            )

        if not password:
            AsyncSQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para Oracle")
            raise ValidationError(
                "Se requiere una contraseña para la conexión a Oracle",
                db_type="oracle",
            )

        if not service_name:
            if conn_params.get("dsn") or conn_params.get("sid"):
                # El destino lo resuelve el ``async_creator`` nativo (AsyncOracleConnection: makedsn con dsn/sid).
                return AsyncSQLAlchemyEngineFactory._render_url("oracle+oracledb", user, password, host, port, "")
            raise ValidationError(
                "Se requiere 'service_name' o 'database' para Oracle",
                db_type="oracle",
            )

        return AsyncSQLAlchemyEngineFactory._render_url(
            "oracle+oracledb", user, password, host, port, "", query={"service_name": service_name}
        )

    @staticmethod
    def _build_postgresql_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """Construye connection string para PostgreSQL async.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para PostgreSQL

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        host_value: Any = conn_params.get("host", "localhost")
        host: str = str(host_value) if host_value is not None else "localhost"

        user_value: Any = conn_params.get("user", "postgres")
        user: str = str(user_value) if user_value is not None else "postgres"

        password_value: Any = conn_params.get("password")
        password: str | None = str(password_value) if password_value is not None else None

        port_value: Any = conn_params.get("port", 5432)
        port: int = int(port_value)

        if not password:
            AsyncSQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para PostgreSQL")
            raise ValidationError(
                "Se requiere una contraseña para la conexión a PostgreSQL",
                db_type="postgresql",
            )

        raw_target_db: Any = database if database is not None else conn_params.get("database")
        target_db: str = str(raw_target_db) if raw_target_db is not None else ""
        if not target_db:
            raise ValidationError("Se requiere 'database' para PostgreSQL", db_type="postgresql")

        return AsyncSQLAlchemyEngineFactory._render_url("postgresql+asyncpg", user, password, host, port, target_db)

    @staticmethod
    def _build_sqlserver_connection_string(
        conn_params: dict[str, Any],
        database: str | None,
        sql_server_driver: str = "aioodbc",
    ) -> str:
        """Construye connection string para SQL Server según el driver configurado.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos
            sql_server_driver: Driver a usar para async (solo 'aioodbc')

        Returns:
            Connection string para SQL Server

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        host_value: Any = conn_params.get("host", "localhost")
        host: str = str(host_value) if host_value is not None else "localhost"

        user_value: Any = conn_params.get("user", "sa")
        user: str = str(user_value) if user_value is not None else "sa"

        password_value: Any = conn_params.get("password")
        password: str | None = str(password_value) if password_value is not None else None

        port_value: Any = conn_params.get("port", 1433)
        port: int = int(port_value)

        if not password:
            AsyncSQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para SQL Server")
            raise ValidationError(
                "Se requiere una contraseña para la conexión a SQL Server",
                db_type="sqlserver",
            )

        raw_target_db: Any = database if database is not None else conn_params.get("database")
        target_db: str = str(raw_target_db) if raw_target_db is not None else ""
        if not target_db:
            raise ValidationError("Se requiere 'database' para SQL Server", db_type="sqlserver")

        if sql_server_driver != "aioodbc":
            raise ValidationError(
                "Para SQLAlchemy async en SQL Server use sql_server_driver='aioodbc'",
                db_type="sqlserver",
            )

        return AsyncSQLAlchemyEngineFactory._render_url("mssql+aioodbc", user, password, host, port, target_db)

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
