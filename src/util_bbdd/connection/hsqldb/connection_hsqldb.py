"""Conexión raw al driver HSQLDB."""

import logging
import re

from typing import Any

from util_bbdd._core.exceptions import ConnectionError, ValidationError

from ..params import ConnectionParamsManager


class HSQLDBConnection:
    """Maneja la conexión raw a HSQLDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any]) -> Any:
        """
        Establece conexión raw a HSQLDB.

        Args:
            conn_params: Parámetros de conexión validados.

        Returns:
            Conexión a HSQLDB.

        Raises:
            ConnectionError: Si hay error en la conexión.
            ValidationError: Si faltan parámetros requeridos.
        """
        try:
            import jaydebeapi

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "hsqldb",
                conn_params,
            )

            # HSQLDB requiere parámetros especiales JDBC
            jdbc_driver = sanitized_conn_params.get("jdbc_driver", "org.hsqldb.jdbcDriver")
            jdbc_url = sanitized_conn_params.get("jdbc_url", None)
            jdbc_jar = sanitized_conn_params.get("jdbc_jar", None)

            if not jdbc_url:
                HSQLDBConnection.logger.error("❌ Se requiere jdbc_url para HSQLDB")
                raise ValidationError("Se requiere jdbc_url para HSQLDB", db_type="hsqldb")
            if not jdbc_jar:
                HSQLDBConnection.logger.error("❌ Se requiere jdbc_jar para HSQLDB")
                raise ValidationError("Se requiere jdbc_jar para HSQLDB", db_type="hsqldb")

            # Firma real: connect(jclassname, url, driver_args, jars). Antes se pasaba (…, user, password, jar): el
            # usuario acababa en driver_args, la contraseña como ruta de jars y el jar como libs.
            # driver_args = propiedades JDBC: user/password más connection_properties (antes validadas y descartadas).
            driver_args: dict[str, Any] = {
                "user": sanitized_conn_params.get("user", ""),
                "password": sanitized_conn_params.get("password", ""),
                **(sanitized_conn_params.get("connection_properties") or {}),
            }

            # La jdbc_url puede llevar ;password=...: no se registra en claro (S2068 es un falso positivo: la regex la oculta)
            safe_url: str = re.sub(r"(?i)(password=)[^;]*", r"\1***", str(jdbc_url))  # NOSONAR
            HSQLDBConnection.logger.debug(f"🔗 Conectando a HSQLDB con JDBC: {safe_url}")
            conn = jaydebeapi.connect(jdbc_driver, jdbc_url, driver_args, jdbc_jar)
            HSQLDBConnection.logger.info("✅ Conexión HSQLDB establecida")
            return conn
        except ValidationError:
            raise
        except ImportError as e:
            HSQLDBConnection.logger.error("❌ Error: módulo jaydebeapi no disponible")
            raise ConnectionError("Módulo jaydebeapi no disponible", db_type="hsqldb", details=str(e)) from e
        except Exception as e:
            HSQLDBConnection.logger.exception(f"❌ Error conectando a HSQLDB: {e}")
            raise ConnectionError(f"Error conectando a HSQLDB: {str(e)}", db_type="hsqldb", details=str(e)) from e
