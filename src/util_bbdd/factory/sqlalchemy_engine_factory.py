"""Factory para crear Engine de SQLAlchemy según el tipo de base de datos."""

import logging

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Engine

from .._core.exceptions import ConnectionError, ValidationError


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
            DatabaseConnectionError: Si hay error creando la Engine

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
                conn_str = SQLAlchemyEngineFactory._build_hsqldb_connection_string(conn_params, database)
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

            # pool_pre_ping: valida conexiones antes de usarlas (detecta "Server has gone away")
            # pool_recycle: fuerza rotación de conexiones cada hora; compensa bugs del
            #   driver mariadb+mariadbconnector donde ping() puede fallar silenciosamente
            pool_kwargs: dict[str, Any] = {"pool_pre_ping": True, "echo": False}
            if db_type in ("mariadb", "mysql"):
                pool_kwargs["pool_recycle"] = 3600
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

    @staticmethod
    def _get_test_query(db_type: str) -> str:
        """
        Retorna query de verificación de conexión apropiada por motor.

        Oracle requiere FROM DUAL; otros motores usan SELECT 1.

        Args:
            db_type: Tipo de motor ('mariadb', 'oracle', 'postgresql', 'sqlserver', 'hsqldb', 'sqlite')

        Returns:
            Query SQL de verificación de conexión
        """
        if db_type == "oracle":
            return "SELECT 1 FROM DUAL"
        return "SELECT 1"

    @staticmethod
    def _sanitize_conn_str(conn_str: str) -> str:
        """Oculta contraseña en una URL de conexión para logging.

        SVC-01 (AUDIT_CODE 2026-09-22): antes se logueaban los primeros 50 caracteres del
        connection string sin redactar, exponiendo la contraseña en claro para hosts/usuarios
        cortos. Réplica exacta de ``AsyncSQLAlchemyEngineFactory._sanitize_conn_str``.
        """
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
    def _build_mariadb_connection_string(conn_params: dict[str, Any], database: str) -> str:
        """Construye connection string para MariaDB.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para MariaDB

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        host: str = conn_params.get("host", "localhost")
        user: str = conn_params.get("user", "root")
        password: str | None = conn_params.get("password")
        port: int = conn_params.get("port", 3306)

        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para MariaDB")
            raise ValidationError(
                "Se requiere una contraseña para la conexión a MariaDB",
                db_type="mariadb",
            )

        if not database:
            raise ValidationError("Se requiere 'database' para MariaDB", db_type="mariadb")

        return SQLAlchemyEngineFactory._render_url("mariadb+mariadbconnector", user, password, host, port, database)

    @staticmethod
    def _build_mysql_connection_string(conn_params: dict[str, Any], database: str) -> str:
        """Construye connection string para MySQL (``mysql+pymysql``).

        Usuario y contraseña se escapan con ``URL.create`` (admiten ``@``, ``:`` o ``/``).

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para MySQL

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        from sqlalchemy.engine import URL

        password: str | None = conn_params.get("password")
        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para MySQL")
            raise ValidationError("Se requiere una contraseña para la conexión a MySQL", db_type="mysql")
        if not database:
            raise ValidationError("Se requiere 'database' para MySQL", db_type="mysql")

        url = URL.create(
            "mysql+pymysql",
            username=str(conn_params.get("user", "root")),
            password=str(password),
            host=str(conn_params.get("host", "localhost")),
            port=int(conn_params.get("port", 3306)),
            database=str(database),
        )
        return url.render_as_string(hide_password=False)

    @staticmethod
    def _build_oracle_connection_string(conn_params: dict[str, Any], database: str) -> str:
        """Construye connection string para Oracle.

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para Oracle

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        user: str | None = conn_params.get("user")
        password: str | None = conn_params.get("password")
        host: str = conn_params.get("host", "localhost")
        port: int = conn_params.get("port", 1521)
        service_name: str = conn_params.get("service_name") or database

        if not user:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó usuario para Oracle")
            raise ValidationError(
                "Se requiere un usuario para la conexión a Oracle",
                db_type="oracle",
            )

        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para Oracle")
            raise ValidationError(
                "Se requiere una contraseña para la conexión a Oracle",
                db_type="oracle",
            )

        if not service_name:
            if conn_params.get("dsn") or conn_params.get("sid"):
                # El destino lo resuelve el ``creator`` nativo (OracleConnection: makedsn con dsn/sid).
                return SQLAlchemyEngineFactory._render_url("oracle+oracledb", user, password, host, port, "")
            raise ValidationError("Se requiere 'service_name' o 'database' para Oracle", db_type="oracle")

        return SQLAlchemyEngineFactory._render_url(
            "oracle+oracledb", user, password, host, port, "", query={"service_name": service_name}
        )

    @staticmethod
    def _build_postgresql_connection_string(conn_params: dict[str, Any], database: str) -> str:
        """Construye connection string para PostgreSQL (psycopg3).

        Args:
            conn_params: Parámetros de conexión
            database: Nombre de la base de datos

        Returns:
            Connection string para PostgreSQL

        Raises:
            ValidationError: Si faltan parámetros requeridos
        """
        host: str = conn_params.get("host", "localhost")
        user: str = conn_params.get("user", "postgres")
        password: str | None = conn_params.get("password")
        port: int = conn_params.get("port", 5432)

        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para PostgreSQL")
            raise ValidationError(
                "Se requiere una contraseña para la conexión a PostgreSQL",
                db_type="postgresql",
            )

        if not database:
            raise ValidationError("Se requiere 'database' para PostgreSQL", db_type="postgresql")

        return SQLAlchemyEngineFactory._render_url("postgresql+psycopg", user, password, host, port, database)

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
            ValidationError: Si faltan parámetros requeridos
        """
        host: str = conn_params.get("host", "localhost")
        user: str = conn_params.get("user", "sa")
        password: str | None = conn_params.get("password")
        port: int = conn_params.get("port", 1433)

        if not password:
            SQLAlchemyEngineFactory.logger.warning("⚠️ No se proporcionó contraseña para SQL Server")
            raise ValidationError(
                "Se requiere una contraseña para la conexión a SQL Server",
                db_type="sqlserver",
            )

        # Construir URL diferente según el driver (pymssql por defecto)
        drivername = "mssql+pyodbc" if sql_server_driver == "pyodbc" else "mssql+pymssql"
        return SQLAlchemyEngineFactory._render_url(drivername, user, password, host, port, database)

    @staticmethod
    def _render_url(
        drivername: str,
        user: str,
        password: str,
        host: str,
        port: Any,
        database: str,
        query: dict[str, str] | None = None,
    ) -> str:
        """URL con usuario y contraseña escapados (``URL.create``).

        Interpolarlos crudos permite que ``@``, ``:``, ``/``, ``?`` o ``#`` en la contraseña cambien el host de la URL
        (hotfix S1, drivers-connections-audit FASE 1).
        """
        from sqlalchemy.engine import URL

        url = URL.create(
            drivername,
            username=str(user),
            password=str(password),
            host=str(host),
            port=int(port),
            database=database,
            query=query or {},
        )
        return url.render_as_string(hide_password=False)

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

        # SQLite URL: sqlite:////absolute/path o sqlite:///relative/path o sqlite:///:memory:
        if db_path == ":memory:":
            return "sqlite:///:memory:"

        # Normaliza separadores Windows (\) a / — una ruta absoluta tipo "C:\a\b.db" sin
        # normalizar produce un URI SQLite inválido/frágil (SVC-03: la versión async ya
        # normalizaba, la sync no).
        normalized_path: str = db_path.replace("\\", "/")
        return f"sqlite:///{normalized_path}"
