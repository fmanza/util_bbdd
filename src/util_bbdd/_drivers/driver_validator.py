"""Validador de disponibilidad de drivers para bases de datos."""

import importlib.util
import logging

from typing import Any

from .._core.exceptions import DriverError, InvalidDatabaseType, ValidationError


class DriverValidator:
    """Valida la disponibilidad de drivers para cada tipo de base de datos."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def check_driver_availability(
        db_type: str,
        conn_params: dict[str, Any],
    ) -> str:
        """
        Verifica que el driver necesario esté disponible.

        Args:
            db_type: Tipo de base de datos ('mariadb', 'mysql', 'oracle', 'postgresql', 'hsqldb', 'sqlserver', 'sqlite')
            conn_params: Parámetros de conexión (para SQL Server)

        Returns:
            Driver a usar (especialmente importante para SQL Server)

        Raises:
            DriverError: Si el driver requerido no está disponible
            InvalidDatabaseType: Si db_type no es un tipo de base de datos soportado
            ValidationError: Si hay error en la validación
        """
        DriverValidator.logger.debug(f"🔍 Verificando disponibilidad del driver para {db_type}")

        try:
            if db_type == "mariadb":
                DriverValidator._check_mariadb_driver()
                return "mariadb"
            elif db_type == "mysql":
                DriverValidator._check_mysql_driver()
                return "pymysql"
            elif db_type == "oracle":
                DriverValidator._check_oracle_driver()
                return "oracledb"
            elif db_type == "postgresql":
                DriverValidator._check_postgresql_driver()
                return "psycopg"
            elif db_type == "hsqldb":
                DriverValidator._check_hsqldb_driver()
                return "jaydebeapi"
            elif db_type == "sqlserver":
                return DriverValidator._check_sqlserver_driver(conn_params)
            elif db_type == "sqlite":
                DriverValidator._check_sqlite_driver()
                return "sqlite3"
            else:
                raise InvalidDatabaseType(
                    message=f"Tipo de base de datos desconocido: {db_type}",
                    db_type=db_type,
                )
        except DriverError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            DriverValidator.logger.error(f"❌ Error verificando disponibilidad de driver: {e}")
            raise DriverError(f"Error verificando driver: {str(e)}", db_type=db_type) from e

    @staticmethod
    def _check_mariadb_driver() -> None:
        """Verifica disponibilidad del driver MariaDB.

        Raises:
            DriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("mariadb") is None:
            DriverValidator.logger.error("❌ Driver MariaDB no disponible")
            raise DriverError(
                "MariaDB driver no disponible",
                "mariadb",
                "pip install mariadb",
                "mariadb",
            )
        DriverValidator.logger.debug("✅ Driver MariaDB disponible")

    @staticmethod
    def _check_mysql_driver() -> None:
        """Verifica disponibilidad del driver MySQL (PyMySQL).

        Raises:
            DriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("pymysql") is None:
            DriverValidator.logger.error("❌ Driver MySQL (pymysql) no disponible")
            raise DriverError(
                "MySQL driver no disponible",
                "pymysql",
                "pip install pymysql[rsa]",
                "mysql",
            )
        DriverValidator.logger.debug("✅ Driver MySQL (pymysql) disponible")

    @staticmethod
    def _check_oracle_driver() -> None:
        """Verifica disponibilidad del driver Oracle.

        Raises:
            DriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("oracledb") is None:
            DriverValidator.logger.error("❌ Driver Oracle no disponible")
            raise DriverError(
                "Oracle driver no disponible",
                "oracledb",
                'pip install "util_bbdd[oracle]"',
                "oracle",
            )
        DriverValidator.logger.debug("✅ Driver Oracle disponible")

    @staticmethod
    def _check_postgresql_driver() -> None:
        """Verifica disponibilidad del driver PostgreSQL (psycopg3).

        Raises:
            DriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("psycopg") is None:
            DriverValidator.logger.error("❌ Driver PostgreSQL (psycopg) no disponible")
            raise DriverError(
                "PostgreSQL driver no disponible",
                "psycopg",
                "pip install psycopg[binary]",
                "postgresql",
            )
        DriverValidator.logger.debug("✅ Driver PostgreSQL (psycopg) disponible")

    @staticmethod
    def _check_hsqldb_driver() -> None:
        """Verifica disponibilidad del driver HSQLDB.

        Raises:
            DriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("jaydebeapi") is None:
            DriverValidator.logger.error("❌ Driver HSQLDB no disponible")
            raise DriverError(
                "HSQLDB driver no disponible",
                "jaydebeapi",
                "pip install JayDeBeApi",
                "hsqldb",
            )
        DriverValidator.logger.debug("✅ Driver HSQLDB disponible")

    @staticmethod
    def _check_sqlserver_driver(conn_params: dict[str, Any]) -> str:
        """Detecta, valida y verifica disponibilidad del driver SQL Server.

        Args:
            conn_params: Parámetros de conexión

        Returns:
            Driver SQL Server a usar ('pymssql' o 'pyodbc')

        Raises:
            ValidationError: Si el driver especificado es inválido
            DriverError: Si el driver no está disponible
        """
        # Detectar driver SQL Server a usar (por defecto pymssql)
        sql_server_driver: str = conn_params.get("sql_server_driver", "pymssql").lower()
        DriverValidator.logger.debug(f"🔍 Driver SQL Server detectado: {sql_server_driver}")

        # Validar que el driver especificado es válido
        if sql_server_driver not in ["pymssql", "pyodbc"]:
            DriverValidator.logger.error(f"❌ Driver SQL Server inválido: {sql_server_driver}")
            raise ValidationError(
                f"Driver SQL Server inválido: {sql_server_driver}. Use 'pymssql' o 'pyodbc'",
                db_type="sqlserver",
            )

        # Verificar disponibilidad del driver especificado
        pymssql_available: bool = importlib.util.find_spec("pymssql") is not None
        pyodbc_available: bool = importlib.util.find_spec("pyodbc") is not None

        if sql_server_driver == "pymssql" and not pymssql_available:
            DriverValidator.logger.error("❌ Driver pymssql para SQL Server no disponible")
            raise DriverError(
                "SQL Server driver pymssql no disponible",
                "pymssql",
                "pip install pymssql",
                "sqlserver",
            )
        elif sql_server_driver == "pyodbc" and not pyodbc_available:
            DriverValidator.logger.error("❌ Driver pyodbc para SQL Server no disponible")
            raise DriverError(
                "SQL Server driver pyodbc no disponible",
                "pyodbc",
                "pip install pyodbc",
                "sqlserver",
            )
        elif not pymssql_available and not pyodbc_available:
            DriverValidator.logger.error("❌ Ningún driver disponible para SQL Server")
            raise DriverError(
                "Ningún driver disponible para SQL Server",
                "pymssql/pyodbc",
                "pip install pymssql pyodbc",
                "sqlserver",
            )

        DriverValidator.logger.debug(f"✅ Driver SQL Server ({sql_server_driver}) disponible")
        return sql_server_driver

    @staticmethod
    def _check_sqlite_driver() -> None:
        """Verifica disponibilidad del driver SQLite.

        SQLite viene incluido en Python por defecto, así que siempre está disponible.

        Raises:
            DriverError: Si por alguna razón sqlite3 no está disponible
        """
        if importlib.util.find_spec("sqlite3") is None:
            DriverValidator.logger.error("❌ Driver SQLite no disponible (esto es muy extraño)")
            raise DriverError(
                "SQLite driver no disponible",
                "sqlite3",
                "SQLite3 viene incluido en Python. Reinstala Python.",
                "sqlite",
            )
        DriverValidator.logger.debug("✅ Driver SQLite disponible (incluido en Python)")
