"""Conexión raw al driver SQL Server."""

import logging

from typing import Any, ClassVar

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager


class SQLServerConnection:
    """Maneja la conexión raw a SQL Server."""

    logger: logging.Logger = logging.getLogger(__name__)

    #: ``encryption`` de la librería → ``encryption`` de pymssql (FreeTDS). ``optional`` no se envía.
    _PYMSSQL_ENCRYPTION: ClassVar[dict[str, str]] = {"mandatory": "require", "off": "off"}
    _ENCRYPT_OPTION_SQL: ClassVar[str] = "SELECT encrypt_option FROM sys.dm_exec_connections WHERE session_id = @@SPID"

    @staticmethod
    def odbc_encrypt(encryption: Any) -> str:
        """``Encrypt`` de la cadena ODBC: ``yes`` para ``mandatory``, ``no`` para el resto.

        Son los únicos valores que aceptan a la vez ODBC Driver 17 y 18 (18 rechaza ``off``; en 18, ``no`` equivale
        a ``Optional``).
        """
        return "yes" if str(encryption).lower() == "mandatory" else "no"

    @staticmethod
    def connect(conn_params: dict[str, Any], driver: str = "pymssql") -> Any:
        """
        Establece conexión raw a SQL Server usando pymssql o pyodbc.

        Args:
            conn_params: Parámetros de conexión validados.
            driver: Driver a usar ('pymssql' o 'pyodbc'). Por defecto 'pymssql'.

        Returns:
            Conexión a SQL Server.

        Raises:
            ConnectionError: Si hay error en la conexión.
        """
        try:
            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "sqlserver",
                conn_params,
                driver=driver,
            )

            if driver == "pymssql":
                return SQLServerConnection._connect_pymssql(sanitized_conn_params)
            elif driver == "pyodbc":
                return SQLServerConnection._connect_pyodbc(sanitized_conn_params)
            else:
                raise ConnectionError(f"Driver SQL Server no reconocido: {driver}", db_type="sqlserver")
        except ConnectionError:
            raise
        except Exception as e:
            SQLServerConnection.logger.error(f"❌ Error conectando a SQL Server: {e}")
            raise ConnectionError(
                f"Error conectando a SQL Server: {str(e)}", db_type="sqlserver", details=str(e)
            ) from e

    @staticmethod
    def _connect_pymssql(conn_params: dict[str, Any]) -> Any:
        """
        Crea conexión raw a SQL Server usando pymssql.

        ``encryption`` se traduce al parámetro de pymssql/FreeTDS: ``mandatory`` → ``require``, ``off`` → ``off``;
        ``optional`` no se envía (manda la configuración de FreeTDS, que por defecto pide cifrado si el servidor lo
        ofrece). ``trust_cert`` no tiene equivalente en pymssql: la validación del certificado depende de FreeTDS
        (``ca file`` en ``freetds.conf``); para controlarla por conexión use ``sql_server_driver="pyodbc"``.

        Args:
            conn_params: Parámetros filtrados de conexión.

        Returns:
            Conexión a SQL Server con pymssql.

        Raises:
            ConnectionError: Si hay error en la conexión.
        """
        try:
            import pymssql

            params: dict[str, Any] = dict(conn_params)
            params.pop("sql_server_driver", None)
            params.pop("driver_name", None)
            params.pop("login_timeout", None)
            encryption: str | None = SQLServerConnection._PYMSSQL_ENCRYPTION.get(
                str(params.pop("encryption", "optional")).lower()
            )
            if encryption is not None:
                params["encryption"] = encryption
            params.pop("trust_cert", None)
            params.pop("use_mars", None)

            SQLServerConnection.logger.debug(
                f"🔗 Conectando a SQL Server (pymssql) con parámetros: {list(params.keys())}"
            )
            conn = pymssql.connect(**params)
            if encryption == "require":
                SQLServerConnection._require_encrypted_session(conn)
            SQLServerConnection.logger.info("✅ Conexión SQL Server (pymssql) establecida")
            return conn
        except ImportError as e:
            SQLServerConnection.logger.error("❌ Error: módulo pymssql no disponible")
            raise ConnectionError("Módulo pymssql no disponible", db_type="sqlserver", details=str(e)) from e
        except ConnectionError:
            raise
        except Exception as e:
            SQLServerConnection.logger.error(f"❌ Error conectando a SQL Server (pymssql): {e}")
            raise ConnectionError(
                f"Error conectando a SQL Server: {str(e)}", db_type="sqlserver", details=str(e)
            ) from e

    @staticmethod
    def _require_encrypted_session(conn: Any) -> None:
        """Falla (y cierra ``conn``) si la sesión pymssql no va cifrada pese a ``encryption="mandatory"``.

        Algunos builds de FreeTDS aceptan ``encryption="require"`` y no cifran (wheel de pymssql para Windows con
        FreeTDS 1.4.27). ``sys.dm_exec_connections`` requiere ``VIEW SERVER STATE``: sin ese permiso no se puede
        comprobar y solo se avisa (``CONNECTIONPROPERTY`` no expone ``encrypt_option``).
        """
        cursor = conn.cursor()
        try:
            cursor.execute(SQLServerConnection._ENCRYPT_OPTION_SQL)
            row = cursor.fetchone()
        except Exception as exc:
            SQLServerConnection.logger.warning(
                f"⚠️ encryption='mandatory': no se pudo verificar el cifrado de la sesión pymssql "
                f"(requiere VIEW SERVER STATE): {exc}"
            )
            return
        finally:
            cursor.close()
        if not row:
            SQLServerConnection.logger.warning("⚠️ encryption='mandatory': no se pudo leer el cifrado de la sesión")
            return
        if str(row[0]).upper() != "TRUE":
            conn.close()
            raise ConnectionError(
                "encryption='mandatory' pero la sesión pymssql no va cifrada (el FreeTDS de pymssql no soporta TLS en "
                "este entorno); use sql_server_driver='pyodbc' con un ODBC Driver for SQL Server",
                db_type="sqlserver",
            )

    @staticmethod
    def _escape_odbc_value(value: Any) -> str:
        """Envuelve un valor en ``{}`` (doblando ``}`` internas) para un connection string ODBC.

        Sin este quoting, un valor con ``;``, ``{`` o ``}`` puede inyectar atributos adicionales
        en la cadena de conexión (p. ej. ``TrustServerCertificate=yes``) — ver AUDIT_CODE CNX-02,
        2026-09-22.
        """
        return "{" + str(value).replace("}", "}}") + "}"

    @staticmethod
    def _connect_pyodbc(conn_params: dict[str, Any]) -> Any:
        """
        Crea conexión raw a SQL Server usando pyodbc.

        Args:
            conn_params: Parámetros filtrados de conexión.

        Returns:
            Conexión a SQL Server con pyodbc.

        Raises:
            ConnectionError: Si hay error en la conexión.
        """
        try:
            import pyodbc

            host = conn_params.get("host", "localhost")
            user = conn_params.get("user", "sa")
            password = conn_params.get("password", "")
            database = conn_params.get("database", "master")
            port = conn_params.get("port", 1433)
            driver_name = conn_params.get("driver_name", "ODBC Driver 17 for SQL Server")
            encryption = conn_params.get("encryption", "optional")
            trust_cert = conn_params.get("trust_cert", False)

            esc = SQLServerConnection._escape_odbc_value
            conn_str: str = (
                f"Driver={esc(driver_name)};"
                f"Server={esc(f'{host},{port}')};"  # host,puerto dentro de las llaves: fuera, el Driver Manager lo rechaza
                f"Database={esc(database)};"
                f"UID={esc(user)};"
                f"PWD={esc(password)};"
                f"Encrypt={SQLServerConnection.odbc_encrypt(encryption)};"
                f"TrustServerCertificate={'yes' if trust_cert else 'no'};"
            )

            timeout = conn_params.get("login_timeout", 20)

            SQLServerConnection.logger.debug(f"🔗 Conectando a SQL Server (pyodbc) a {host}:{port}/{database}")
            conn: Any = pyodbc.connect(conn_str, timeout=timeout)
            SQLServerConnection.logger.info("✅ Conexión SQL Server (pyodbc) establecida")
            return conn
        except ImportError as e:
            SQLServerConnection.logger.error("❌ Error: módulo pyodbc no disponible")
            raise ConnectionError("Módulo pyodbc no disponible", db_type="sqlserver", details=str(e)) from e
        except Exception as e:
            SQLServerConnection.logger.error(f"❌ Error conectando a SQL Server (pyodbc): {e}")
            raise ConnectionError(
                f"Error conectando a SQL Server: {str(e)}", db_type="sqlserver", details=str(e)
            ) from e
