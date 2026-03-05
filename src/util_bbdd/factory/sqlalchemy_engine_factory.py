"""Factory para crear Engine de SQLAlchemy según el tipo de base de datos."""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

from ..database_exceptions import DatabaseConnectionError, DatabaseValidationError


class SQLAlchemyEngineFactory:
    """Factory para crear y gestionar Engine de SQLAlchemy."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def create_engine(
        db_type: str,
        conn_params: dict[str, Any],
        database: str,
        sql_server_driver: str = "pymssql",
    ) -> "Engine":
        """
        Crea un Engine de SQLAlchemy basado en el tipo de base de datos.

        Args:
            db_type: Tipo de base de datos ('mariadb', 'oracle', 'postgresql', etc.)
            conn_params: Parámetros de conexión validados
            database: Nombre de la base de datos
            sql_server_driver: Driver para SQL Server ('pymssql' o 'pyodbc')

        Returns:
            Engine de SQLAlchemy configurado

        Raises:
            ImportError: Si SQLAlchemy no está instalado
            DatabaseConnectionError: Si hay error creando la Engine

        Note:
            oracle_client_path no es necesario. SQLAlchemy con oracledb
            maneja automáticamente la ubicación del cliente Oracle.
        """
        SQLAlchemyEngineFactory.logger.debug(f"🔧 Creando Engine de SQLAlchemy para {db_type}")

        try:
            from sqlalchemy import create_engine, text

            # Construir connection string según tipo de BD
            if db_type == "mariadb":
                conn_str: str = SQLAlchemyEngineFactory._build_mariadb_connection_string(conn_params, database)
            elif db_type == "oracle":
                conn_str = SQLAlchemyEngineFactory._build_oracle_connection_string(conn_params, database)
            elif db_type == "postgresql":
                conn_str = SQLAlchemyEngineFactory._build_postgresql_connection_string(conn_params, database)
            elif db_type == "hsqldb":
                conn_str = SQLAlchemyEngineFactory._build_hsqldb_connection_string(conn_params, database)
            elif db_type == "sqlserver":
                conn_str = SQLAlchemyEngineFactory._build_sqlserver_connection_string(conn_params, database, sql_server_driver)
            elif db_type == "sqlite":
                conn_str = SQLAlchemyEngineFactory._build_sqlite_connection_string(conn_params)
            else:
                raise DatabaseConnectionError(f"Tipo de BD no soportado para SQLAlchemy: {db_type}", db_type)

            SQLAlchemyEngineFactory.logger.debug(f"📝 Connection string construido: {conn_str[:50]}...")

            # Crear engine con pool_pre_ping para validar conexiones
            engine: "Engine" = create_engine(conn_str, pool_pre_ping=True, echo=False)

            # Verificar que la conexión funciona
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            SQLAlchemyEngineFactory.logger.info(f"✅ Engine de SQLAlchemy creado exitosamente para {db_type}")
            return engine

        except ImportError as e:
            SQLAlchemyEngineFactory.logger.error("❌ SQLAlchemy no está instalado")
            raise DatabaseConnectionError(
                "SQLAlchemy no instalado. Instala con: pip install sqlalchemy",
                db_type,
                str(e),
            ) from e
        except DatabaseConnectionError:
            raise
        except Exception as e:
            SQLAlchemyEngineFactory.logger.error(f"❌ Error creando Engine de SQLAlchemy: {e}")
            raise DatabaseConnectionError(f"Error creando Engine de SQLAlchemy: {str(e)}", db_type, str(e)) from e

    @staticmethod
    def _build_mariadb_connection_string(conn_params: dict[str, Any], database: str) -> str:
        """Construye connection string para MariaDB.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para MariaDB

        Raises:
            DatabaseValidationError: Si faltan parámetros requeridos
        """
        host: str = conn_params.get("host", "localhost")
        user: str = conn_params.get("user", "root")
        password: str | None = conn_params.get("password")
        port: int = conn_params.get("port", 3306)

        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para MariaDB")
            raise DatabaseValidationError(
                "Se requiere una contraseña para la conexión a MariaDB",
                "mariadb",
            )

        return f"mariadb+mariadbconnector://{user}:{password}@{host}:{port}/{database}"

    @staticmethod
    def _build_oracle_connection_string(conn_params: dict[str, Any], database: str) -> str:
        """Construye connection string para Oracle.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para Oracle

        Raises:
            DatabaseValidationError: Si faltan parámetros requeridos
        """
        user: str | None = conn_params.get("user")
        password: str | None = conn_params.get("password")
        host: str = conn_params.get("host", "localhost")
        port: int = conn_params.get("port", 1521)
        service_name: str = conn_params.get("service_name") or database

        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para Oracle")
            raise DatabaseValidationError(
                "Se requiere una contraseña para la conexión a Oracle",
                "oracle",
            )

        return f"oracle+oracledb://{user}:{password}@{host}:{port}/?service_name={service_name}"

    @staticmethod
    def _build_postgresql_connection_string(conn_params: dict[str, Any], database: str) -> str:
        """Construye connection string para PostgreSQL (psycopg3).

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para PostgreSQL

        Raises:
            DatabaseValidationError: Si faltan parámetros requeridos
        """
        host: str = conn_params.get("host", "localhost")
        user: str = conn_params.get("user", "postgres")
        password: str | None = conn_params.get("password")
        port: int = conn_params.get("port", 5432)

        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para PostgreSQL")
            raise DatabaseValidationError(
                "Se requiere una contraseña para la conexión a PostgreSQL",
                "postgresql",
            )

        masked_pass: str = "*" * len(password)
        return f"postgresql+psycopg://{user}:{masked_pass}@{host}:{port}/{database}"

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
        database: str,
        sql_server_driver: str = "pymssql",
    ) -> str:
        """Construye connection string para SQL Server según el driver configurado.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos
            sql_server_driver: Driver a usar ('pymssql' o 'pyodbc')

        Returns:
            Connection string para SQL Server

        Raises:
            DatabaseValidationError: Si faltan parámetros requeridos
        """
        host: str = conn_params.get("host", "localhost")
        user: str = conn_params.get("user", "sa")
        password: str | None = conn_params.get("password")
        port: int = conn_params.get("port", 1433)

        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para SQL Server")
            raise DatabaseValidationError(
                "Se requiere una contraseña para la conexión a SQL Server",
                "sqlserver",
            )

        masked_pass: str = "*" * len(password)

        # Construir URL diferente según el driver
        if sql_server_driver == "pyodbc":
            return f"mssql+pyodbc://{user}:{masked_pass}@{host}:{port}/{database}"
        else:  # pymssql por defecto
            return f"mssql+pymssql://{user}:{masked_pass}@{host}:{port}/{database}"

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
            >>> SQLAlchemyEngineFactory._build_sqlite_connection_string(conn_params)
            'sqlite:////path/to/app.db'
        """
        db_path: str = conn_params.get("database", ":memory:")

        if not db_path:
            raise DatabaseValidationError(
                "Se requiere el parámetro 'database' para SQLite",
                "sqlite",
            )

        # SQLite URL: sqlite:////absolute/path o sqlite:///relative/path o sqlite:///:memory:
        if db_path == ":memory:":
            return "sqlite:///:memory:"
        elif db_path.startswith("/"):
            # Ruta absoluta: agrega cuarto / para archivo local absoluto
            return f"sqlite:///{db_path}"
        else:
            # Ruta relativa: agrega triple / para archivo relativo
            return f"sqlite:///{db_path}"
