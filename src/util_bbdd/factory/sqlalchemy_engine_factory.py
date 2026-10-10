"""Factory para crear Engine de SQLAlchemy según el tipo de base de datos."""

import logging

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

from .._core.exceptions import ConnectionError, ValidationError
from ._pool_policy import engine_pool_kwargs
from ._url import get_test_query, render_url, sanitize_conn_str, server_url, sqlite_url


class SQLAlchemyEngineFactory:
    """Factory para crear y gestionar Engine de SQLAlchemy."""

    logger: logging.Logger = logging.getLogger(__name__)

    #: Motores cuyo Engine abre conexiones con :class:`~util_bbdd.connection.factory.ConnectionFactory` (``creator``):
    #: la URL solo elige el dialecto y TLS, charset, ``init_command``, ``dsn``/``sid``… se aplican igual que en los
    #: managers. SQLite y HSQLDB no tienen nada de eso que aplicar y siguen conectando por URL.
    _NATIVE_CREATOR_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"mariadb", "mysql", "oracle", "postgresql", "sqlserver"}
    )

    @staticmethod
    def _native_creator(
        db_type: str,
        conn_params: dict[str, Any],
        database: str,
        sql_server_driver: str,
    ) -> Callable[[], Any] | None:
        """``creator`` de ``create_engine`` que conecta con el driver nativo de la librería (``None`` si no aplica)."""
        if db_type not in SQLAlchemyEngineFactory._NATIVE_CREATOR_TYPES:
            return None
        from ..connection.factory import ConnectionFactory

        params: dict[str, Any] = dict(conn_params)
        if database:
            params["database"] = database

        # Con ``creator`` SQLAlchemy no llama a ``dialect.create_connect_args``: el CLIENT.FOUND_ROWS que añaden los
        # dialectos MySQL/MariaDB (``rowcount`` = filas encontradas) hay que pedirlo aquí.
        found_rows = db_type in ("mariadb", "mysql")

        def _creator() -> Any:
            return ConnectionFactory.create_connection(
                db_type, params, sql_server_driver=sql_server_driver, found_rows=found_rows
            )

        return _creator

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
            ConnectionError: Si hay error creando la Engine

        Note:
            oracle_thick_mode: Si es True para Oracle, inicializa el cliente en modo thick antes del Engine.
        """
        SQLAlchemyEngineFactory.logger.debug(f"🔧 Creando Engine de SQLAlchemy para {db_type}")

        # Para Oracle: inicializar thick mode ANTES de crear el Engine si está activo
        if db_type == "oracle" and conn_params.get("oracle_thick_mode"):
            from ..connection.oracle._thick_mode import init_oracle_thick_mode

            oracle_client_path: str | None = conn_params.get("oracle_client_path")
            if not oracle_client_path:
                raise ConnectionError(
                    "Para usar oracle_thick_mode=True es obligatorio especificar oracle_client_path",
                    db_type="oracle",
                )
            init_oracle_thick_mode(oracle_client_path)

        try:
            from sqlalchemy import create_engine, text

            # Construir connection string según tipo de BD
            if db_type == "mariadb":
                conn_str: str = SQLAlchemyEngineFactory._build_mariadb_connection_string(conn_params, database)
            elif db_type == "mysql":
                conn_str = SQLAlchemyEngineFactory._build_mysql_connection_string(conn_params, database)
            elif db_type == "oracle":
                conn_str = SQLAlchemyEngineFactory._build_oracle_connection_string(conn_params, database)
            elif db_type == "postgresql":
                conn_str = SQLAlchemyEngineFactory._build_postgresql_connection_string(conn_params, database)
            elif db_type == "hsqldb":
                # Sin dialecto de SQLAlchemy para HSQLDB: antes se construía hsqldb+pyodbc://sa@… (usuario fijo,
                # jdbc_url ignorada) y fallaba con "Can't load plugin".
                raise ConnectionError(
                    "HSQLDB no tiene dialecto de SQLAlchemy: use la conexión nativa del manager (JDBC con jaydebeapi)",
                    db_type=db_type,
                )
            elif db_type == "sqlserver":
                conn_str = SQLAlchemyEngineFactory._build_sqlserver_connection_string(
                    conn_params, database, sql_server_driver
                )
            elif db_type == "sqlite":
                conn_str = SQLAlchemyEngineFactory._build_sqlite_connection_string(conn_params)
            else:
                raise ConnectionError(f"Tipo de BD no soportado para SQLAlchemy: {db_type}", db_type=db_type)

            sanitized_conn_str: str = SQLAlchemyEngineFactory._sanitize_conn_str(conn_str)
            SQLAlchemyEngineFactory.logger.debug(f"📝 Connection string construido: {sanitized_conn_str}")

            # pool_pre_ping: valida conexiones antes de usarlas (detecta "Server has gone away").
            # Tamaño, espera y reciclado del pool: misma política que el AsyncEngine (``factory/_pool_policy.py``).
            pool_kwargs: dict[str, Any] = {"pool_pre_ping": True, "echo": False}
            pool_kwargs.update(engine_pool_kwargs(db_type, conn_params))
            creator = SQLAlchemyEngineFactory._native_creator(db_type, conn_params, database, sql_server_driver)
            if creator is not None:
                pool_kwargs["creator"] = creator
            engine: Engine = create_engine(conn_str, **pool_kwargs)

            # Verificar que la conexión funciona con query apropiada por motor
            test_query: str = SQLAlchemyEngineFactory._get_test_query(db_type)
            with engine.connect() as conn:
                conn.execute(text(test_query))

            SQLAlchemyEngineFactory.logger.info(f"✅ Engine de SQLAlchemy creado exitosamente para {db_type}")
            return engine

        except ImportError as e:
            SQLAlchemyEngineFactory.logger.error("❌ SQLAlchemy no está instalado")
            raise ConnectionError(
                "SQLAlchemy no instalado. Instala con: pip install sqlalchemy",
                db_type=db_type,
                details=str(e),
            ) from e
        except ConnectionError:
            raise
        except Exception as e:
            SQLAlchemyEngineFactory.logger.error(f"❌ Error creando Engine de SQLAlchemy: {e}")
            raise ConnectionError(
                f"Error creando Engine de SQLAlchemy: {str(e)}", db_type=db_type, details=str(e)
            ) from e

    # Helpers compartidos con AsyncSQLAlchemyEngineFactory (``factory/_url.py``).
    _get_test_query = staticmethod(get_test_query)
    _sanitize_conn_str = staticmethod(sanitize_conn_str)
    _render_url = staticmethod(render_url)

    @staticmethod
    def _build_mariadb_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """URL de MariaDB (Connector/Python); semántica común en ``factory/_url.py::server_url``."""
        return server_url("mariadb", "mariadb+mariadbconnector", conn_params, database)

    @staticmethod
    def _build_mysql_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """URL de MySQL (``mysql+pymysql``); semántica común en ``factory/_url.py::server_url``."""
        return server_url("mysql", "mysql+pymysql", conn_params, database)

    @staticmethod
    def _build_oracle_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """URL de Oracle (``oracle+oracledb``); semántica común en ``factory/_url.py::server_url``."""
        return server_url("oracle", "oracle+oracledb", conn_params, database)

    @staticmethod
    def _build_postgresql_connection_string(conn_params: dict[str, Any], database: str | None) -> str:
        """URL de PostgreSQL (psycopg 3); semántica común en ``factory/_url.py::server_url``."""
        return server_url("postgresql", "postgresql+psycopg", conn_params, database)

    @staticmethod
    def _build_sqlserver_connection_string(
        conn_params: dict[str, Any],
        database: str | None,
        sql_server_driver: str = "pymssql",
    ) -> str:
        """URL de SQL Server (``mssql+pymssql`` o ``mssql+pyodbc``); semántica común en ``factory/_url.py::server_url``."""
        drivername = "mssql+pyodbc" if sql_server_driver == "pyodbc" else "mssql+pymssql"
        return server_url("sqlserver", drivername, conn_params, database)

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
            >>> SQLAlchemyEngineFactory._build_sqlite_connection_string(conn_params)
            'sqlite:////path/to/app.db'
        """
        db_path: str = conn_params.get("database", ":memory:")

        if not db_path:
            raise ValidationError(
                "Se requiere el parámetro 'database' para SQLite",
                db_type="sqlite",
            )

        return sqlite_url(db_path, "sqlite")
