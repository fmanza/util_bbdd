"""Conexión raw a MySQL con PyMySQL."""

import logging
import ssl

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager


def pop_mysql_ssl_options(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Extrae de ``kwargs`` las claves TLS de ``MySQLConnectionConfig`` como dict ``ssl`` de PyMySQL.

    ``ssl_verify_cert`` / ``ssl_verify_identity`` van **dentro** del dict (``verify_mode`` / ``check_hostname``): como
    kwargs sueltos, PyMySQL rehace ``ssl`` desde ``ssl_ca``/``ssl_cert``/``ssl_key`` (ya vacíos) y pierde la CA y el
    certificado de cliente. Devuelve ``{}`` si no hay TLS.
    """
    options: dict[str, Any] = {}
    for key, ssl_key in (("ssl_ca", "ca"), ("ssl_cert", "cert"), ("ssl_key", "key")):
        value: Any = kwargs.pop(key, None)
        if value:
            options[ssl_key] = str(value)
    for key, ssl_key in (("ssl_verify_cert", "verify_mode"), ("ssl_verify_identity", "check_hostname")):
        flag: Any = kwargs.pop(key, None)
        if flag is not None:
            options[ssl_key] = bool(flag)
    if options.get("verify_mode") is False:
        # Sin verificar el certificado no se puede verificar el hostname (SSLContext rechaza CERT_NONE con
        # check_hostname activo, que PyMySQL activa por defecto si hay CA).
        options["check_hostname"] = False
    return options


def build_ssl_context(options: dict[str, Any]) -> ssl.SSLContext:
    """``SSLContext`` equivalente al que PyMySQL crea desde ``options`` (``Connection._create_ssl_ctx``).

    Con CA: verifica certificado y hostname salvo que ``verify_mode`` / ``check_hostname`` digan lo contrario; sin CA,
    ninguna de las dos (cifrado sin verificación), como PyMySQL. Lo usa aiomysql, que solo acepta ``ssl=SSLContext``.
    """
    has_ca: bool = "ca" in options
    ctx: ssl.SSLContext = ssl.create_default_context(cafile=options.get("ca"))
    # Como PyMySQL: los certificados autofirmados que genera MySQL no pasan VERIFY_X509_STRICT (Python 3.13+).
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    verify: Any = options.get("verify_mode")
    if verify is None:
        verify = has_ca
    ctx.check_hostname = bool(verify) and has_ca and bool(options.get("check_hostname", True))
    ctx.verify_mode = ssl.CERT_REQUIRED if verify else ssl.CERT_NONE
    if "cert" in options:
        ctx.load_cert_chain(options["cert"], keyfile=options.get("key"))
    return ctx


def build_pymysql_connect_kwargs(driver_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Traduce los kwargs de ``MySQLConnectionConfig`` al contrato de ``pymysql.connect``.

    Los parámetros TLS van agrupados en ``ssl`` (ver :func:`pop_mysql_ssl_options`); el resto de claves coincide con
    la firma de PyMySQL.
    """
    kwargs: dict[str, Any] = dict(driver_kwargs)
    options: dict[str, Any] = pop_mysql_ssl_options(kwargs)
    if options:
        kwargs["ssl"] = options
    return kwargs


class MySQLConnection:
    """Maneja la conexión raw a MySQL (PyMySQL)."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any], found_rows: bool = False) -> Any:
        """
        Establece conexión raw a MySQL.

        Args:
            conn_params: Parámetros de conexión validados.
            found_rows: Activa ``CLIENT.FOUND_ROWS`` (``rowcount`` = filas encontradas, no cambiadas), como hace
                SQLAlchemy al conectar; lo usa el ``creator`` de ``SQLAlchemyEngineFactory``. No se lee de
                ``conn_params``: ``client_flag`` sigue fuera de la lista blanca.

        Returns:
            Conexión PyMySQL.

        Raises:
            ConnectionError: Si hay error en la conexión.
        """
        try:
            import pymysql

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "mysql",
                conn_params,
            )
            connect_kwargs: dict[str, Any] = build_pymysql_connect_kwargs(sanitized_conn_params)
            if found_rows:
                from pymysql.constants import CLIENT

                connect_kwargs["client_flag"] = CLIENT.FOUND_ROWS

            MySQLConnection.logger.debug(f"🔗 Conectando a MySQL con parámetros: {list(connect_kwargs.keys())}")
            conn = pymysql.connect(**connect_kwargs)
            MySQLConnection.logger.info("✅ Conexión MySQL establecida")
            return conn
        except ImportError as e:
            MySQLConnection.logger.error("❌ Error: módulo pymysql no disponible")
            raise ConnectionError("Módulo pymysql no disponible", db_type="mysql", details=str(e)) from e
        except Exception as e:
            MySQLConnection.logger.error(f"❌ Error conectando a MySQL: {e}")
            raise ConnectionError(f"Error conectando a MySQL: {str(e)}", db_type="mysql", details=str(e)) from e
