"""Factory async para crear AsyncEngine de SQLAlchemy según el tipo de base de datos."""

from __future__ import annotations

import logging
import os

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from ..database_exceptions import DatabaseConnectionError, DatabaseValidationError


class AsyncSQLAlchemyEngineFactory:
    """Factory para crear y gestionar AsyncEngine de SQLAlchemy."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    async def create_engine(
        db_type: str,
        conn_params: dict[str, Any],
        database: str | None = None,
        use_pool: bool = True,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
        sql_server_driver: str = "aioodbc",
    ) -> AsyncEngine:
        """Crea un AsyncEngine de SQLAlchemy basado en el tipo de base de datos."""
        normalized_type: str = db_type.lower().strip()
        AsyncSQLAlchemyEngineFactory.logger.debug(f"🔧 Creando AsyncEngine de SQLAlchemy para {normalized_type}")

        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy.pool import NullPool

            if normalized_type == "mariadb":
                conn_str: str = AsyncSQLAlchemyEngineFactory._build_mariadb_connection_string(
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
                raise DatabaseConnectionError(
                    "hsqldb async no soportado en SQLAlchemyEngineFactory",
                    normalized_type,
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
                raise DatabaseConnectionError(
                    f"Tipo de BD no soportado para SQLAlchemy async: {db_type}",
                    normalized_type,
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
                if normalized_type != "sqlite":
                    engine_kwargs.update(
                        {
                            "pool_size": int(pool_size),
                            "max_overflow": int(max_overflow),
                            "pool_timeout": int(pool_timeout),
                            "pool_recycle": int(pool_recycle),
                        }
                    )
            else:
                engine_kwargs["poolclass"] = NullPool

            engine: AsyncEngine = create_async_engine(conn_str, **engine_kwargs)

            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            AsyncSQLAlchemyEngineFactory.logger.info(
                "✅ AsyncEngine de SQLAlchemy creado exitosamente para %s",
                normalized_type,
            )
            return engine

        except ImportError as err:
            AsyncSQLAlchemyEngineFactory.logger.error("❌ SQLAlchemy async no está disponible")
            raise DatabaseConnectionError(
                "SQLAlchemy async no disponible. Instala con: pip install sqlalchemy",
                normalized_type,
                str(err),
            ) from err
        except DatabaseConnectionError:
            raise
        except Exception as err:
            AsyncSQLAlchemyEngineFactory.logger.error(
                "❌ Error creando AsyncEngine de SQLAlchemy: %s",
                err,
            )
            raise DatabaseConnectionError(
                f"Error creando AsyncEngine de SQLAlchemy: {str(err)}",
                normalized_type,
                str(err),
            ) from err

    @staticmethod
    def _sanitize_conn_str(conn_str: str) -> str:
        """Oculta contraseña en una URL de conexión para logging."""
        if "@" not in conn_str or "://" not in conn_str:
            return conn_str
        prefix, rest = conn_str.split("://", 1)
        if ":" not in rest or "@" not in rest:
            return conn_str
        credentials, suffix = rest.split("@", 1)
        if ":" not in credentials:
            return conn_str
        user, _password = credentials.split(":", 1)
        return f"{prefix}://{user}:***@{suffix}"

    @staticmethod
    def _build_mariadb_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """Construye connection string para MariaDB.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para MariaDB

        Raises:
            DatabaseValidationError: Si faltan parámetros requeridos
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
            raise DatabaseValidationError(
                "Se requiere una contraseña para la conexión a MariaDB",
                "mariadb",
            )

        raw_target_db: Any = database if database is not None else conn_params.get("database")
        target_db: str = str(raw_target_db) if raw_target_db is not None else ""
        if not target_db:
            raise DatabaseValidationError("Se requiere 'database' para MariaDB", "mariadb")

        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{target_db}"

    @staticmethod
    def _build_oracle_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """Construye connection string para Oracle.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para Oracle

        Raises:
            DatabaseValidationError: Si faltan parámetros requeridos
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
            raise DatabaseValidationError(
                "Se requiere un usuario para la conexión a Oracle",
                "oracle",
            )

        if not password:
            AsyncSQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para Oracle")
            raise DatabaseValidationError(
                "Se requiere una contraseña para la conexión a Oracle",
                "oracle",
            )

        if not service_name:
            raise DatabaseValidationError(
                "Se requiere 'service_name' o 'database' para Oracle",
                "oracle",
            )

        return f"oracle+oracledb://{user}:{password}@{host}:{port}/?service_name={service_name}"

    @staticmethod
    def _build_postgresql_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """Construye connection string para PostgreSQL async.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para PostgreSQL

        Raises:
            DatabaseValidationError: Si faltan parámetros requeridos
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
            raise DatabaseValidationError(
                "Se requiere una contraseña para la conexión a PostgreSQL",
                "postgresql",
            )

        raw_target_db: Any = database if database is not None else conn_params.get("database")
        target_db: str = str(raw_target_db) if raw_target_db is not None else ""
        if not target_db:
            raise DatabaseValidationError("Se requiere 'database' para PostgreSQL", "postgresql")

        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{target_db}"

    @staticmethod
    def _build_hsqldb_connection_string(conn_params: dict[str, Any], database: str) -> str:
        """Construye connection string para HSQLDB.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para HSQLDB
        """
        host: str = conn_params.get("host", "localhost")
        port: int = conn_params.get("port", 9001)

        return f"hsqldb+pyodbc://sa@{host}:{port}/{database}"

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
            DatabaseValidationError: Si faltan parámetros requeridos
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
            raise DatabaseValidationError(
                "Se requiere una contraseña para la conexión a SQL Server",
                "sqlserver",
            )

        raw_target_db: Any = database if database is not None else conn_params.get("database")
        target_db: str = str(raw_target_db) if raw_target_db is not None else ""
        if not target_db:
            raise DatabaseValidationError("Se requiere 'database' para SQL Server", "sqlserver")

        if sql_server_driver != "aioodbc":
            raise DatabaseValidationError(
                "Para SQLAlchemy async en SQL Server use sql_server_driver='aioodbc'",
                "sqlserver",
            )

        return f"mssql+aioodbc://{user}:{password}@{host}:{port}/{target_db}"

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
            DatabaseValidationError: Si faltan parámetros requeridos

        Example:
            >>> conn_params = {"database": "/path/to/app.db"}
            >>> AsyncSQLAlchemyEngineFactory._build_sqlite_connection_string(conn_params)
            'sqlite+aiosqlite:////path/to/app.db'
        """
        db_path_value: Any = conn_params.get("database", ":memory:")
        db_path: str = str(db_path_value) if db_path_value is not None else ""

        if not db_path:
            raise DatabaseValidationError(
                "Se requiere el parámetro 'database' para SQLite",
                "sqlite",
            )

        # SQLite URL async: sqlite+aiosqlite:///:memory: o sqlite+aiosqlite:///{path}
        if db_path == ":memory:":
            return "sqlite+aiosqlite:///:memory:"

        normalized_path: str = str(db_path).replace("\\", "/")
        if os.path.isabs(db_path):
            return f"sqlite+aiosqlite:///{normalized_path}"
        return f"sqlite+aiosqlite:///{normalized_path}"

