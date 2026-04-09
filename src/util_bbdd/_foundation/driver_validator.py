"""Validador de disponibilidad de drivers para bases de datos."""

import importlib.util
import logging

from typing import Any

from .exceptions import DatabaseDriverError, DatabaseValidationError


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
            db_type: Tipo de base de datos ('mariadb', 'oracle', 'postgresql', 'hsqldb', 'sqlserver')
            conn_params: Parámetros de conexión (para SQL Server)

        Returns:
            Driver a usar (especialmente importante para SQL Server)

        Raises:
            DatabaseDriverError: Si el driver requerido no está disponible
            DatabaseValidationError: Si hay error en la validación
        """
        DriverValidator.logger.debug(f"🔍 Verificando disponibilidad del driver para {db_type}")

        try:
            if db_type == "mariadb":
                DriverValidator._check_mariadb_driver()
                return "mariadb"
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
                raise ValueError(f"Tipo de base de datos desconocido: {db_type}")
        except DatabaseDriverError:
            raise
        except DatabaseValidationError:
            raise
        except Exception as e:
            DriverValidator.logger.error(f"❌ Error verificando disponibilidad de driver: {e}")
            raise DatabaseDriverError(f"Error verificando driver: {str(e)}", db_type=db_type) from e

    @staticmethod
    def _check_mariadb_driver() -> None:
        """Verifica disponibilidad del driver MariaDB.

        Raises:
            DatabaseDriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("mariadb") is None:
            DriverValidator.logger.error("❌ Driver MariaDB no disponible")
            raise DatabaseDriverError(
                "MariaDB driver no disponible",
                "mariadb",
                "pip install mariadb",
                "mariadb",
            )
        DriverValidator.logger.debug("✅ Driver MariaDB disponible")

    @staticmethod
    def _check_oracle_driver() -> None:
        """Verifica disponibilidad del driver Oracle.

        Raises:
            DatabaseDriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("oracledb") is None:
            DriverValidator.logger.error("❌ Driver Oracle no disponible")
            raise DatabaseDriverError(
                "Oracle driver no disponible",
                "oracledb",
                "pip install oracledb",
                "oracle",
            )
        DriverValidator.logger.debug("✅ Driver Oracle disponible")

    @staticmethod
    def _check_postgresql_driver() -> None:
        """Verifica disponibilidad del driver PostgreSQL (psycopg3).

        Raises:
            DatabaseDriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("psycopg") is None:
            DriverValidator.logger.error("❌ Driver PostgreSQL (psycopg) no disponible")
            raise DatabaseDriverError(
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
            DatabaseDriverError: Si el driver no está disponible
        """
        if importlib.util.find_spec("jaydebeapi") is None:
            DriverValidator.logger.error("❌ Driver HSQLDB no disponible")
            raise DatabaseDriverError(
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
            DatabaseValidationError: Si el driver especificado es inválido
            DatabaseDriverError: Si el driver no está disponible
        """
        # Detectar driver SQL Server a usar (por defecto pymssql)
        sql_server_driver: str = conn_params.get("sql_server_driver", "pymssql").lower()
        DriverValidator.logger.debug(f"🔍 Driver SQL Server detectado: {sql_server_driver}")

        # Validar que el driver especificado es válido
        if sql_server_driver not in ["pymssql", "pyodbc"]:
            DriverValidator.logger.error(f"❌ Driver SQL Server inválido: {sql_server_driver}")
            raise DatabaseValidationError(
                f"Driver SQL Server inválido: {sql_server_driver}. Use 'pymssql' o 'pyodbc'",
                "sqlserver",
            )

        # Verificar disponibilidad del driver especificado
        pymssql_available: bool = importlib.util.find_spec("pymssql") is not None
        pyodbc_available: bool = importlib.util.find_spec("pyodbc") is not None

        if sql_server_driver == "pymssql" and not pymssql_available:
            DriverValidator.logger.error("❌ Driver pymssql para SQL Server no disponible")
            raise DatabaseDriverError(
                "SQL Server driver pymssql no disponible",
                "pymssql",
                "pip install pymssql",
                "sqlserver",
            )
        elif sql_server_driver == "pyodbc" and not pyodbc_available:
            DriverValidator.logger.error("❌ Driver pyodbc para SQL Server no disponible")
            raise DatabaseDriverError(
                "SQL Server driver pyodbc no disponible",
                "pyodbc",
                "pip install pyodbc",
                "sqlserver",
            )
        elif not pymssql_available and not pyodbc_available:
            DriverValidator.logger.error("❌ Ningún driver disponible para SQL Server")
            raise DatabaseDriverError(
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
            DatabaseDriverError: Si por alguna razón sqlite3 no está disponible
        """
        if importlib.util.find_spec("sqlite3") is None:
            DriverValidator.logger.error("❌ Driver SQLite no disponible (esto es muy extraño)")
            raise DatabaseDriverError(
                "SQLite driver no disponible",
                "sqlite3",
                "SQLite3 viene incluido en Python. Reinstala Python.",
                "sqlite",
            )
        DriverValidator.logger.debug("✅ Driver SQLite disponible (incluido en Python)")
