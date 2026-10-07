"""Conexión raw al driver MariaDB."""

import logging
import re

from typing import Any

from util_bbdd._core.exceptions import ConnectionError

from ..params import ConnectionParamsManager

# Parámetros que el driver puede rechazar según versión; se eliminan uno a uno si procede.
_OPTIONAL_CONN_PARAMS: frozenset[str] = frozenset({"charset", "init_command", "encoding_errors"})


class MariaDBConnection:
    """Maneja la conexión raw a MariaDB."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def connect(conn_params: dict[str, Any]) -> Any:
        """
        Establece conexión raw a MariaDB.

        Args:
            conn_params: Parámetros de conexión validados.

        Returns:
            Conexión a MariaDB.

        Raises:
            ConnectionError: Si hay error en la conexión.
        """
        try:
            import mariadb

            sanitized_conn_params: dict[str, Any] = ConnectionParamsManager.sanitize_for_connection(
                "mariadb",
                conn_params,
            )

            MariaDBConnection.logger.debug(
                f"🔗 Conectando a MariaDB con parámetros: {list(sanitized_conn_params.keys())}"
            )

            # Retry defensivo: si el driver rechaza kwargs opcionales, reintentamos sin ellos
            conn_params_retry: dict[str, Any] = dict(sanitized_conn_params)
            max_attempts = len(_OPTIONAL_CONN_PARAMS) + 1

            for attempt in range(max_attempts):
                try:
                    conn = mariadb.connect(**conn_params_retry)
                    MariaDBConnection.logger.info("✅ Conexión MariaDB establecida")
                    return conn
                except TypeError as err:
                    msg = str(err)
                    if "unexpected keyword argument" not in msg:
                        raise

                    match = re.search(r"unexpected keyword argument '(\w+)'", msg)
                    if not match or match.group(1) not in _OPTIONAL_CONN_PARAMS:
                        raise

                    rejected = match.group(1)
                    conn_params_retry = {k: v for k, v in conn_params_retry.items() if k != rejected}
                    mariadb_version: str = str(getattr(mariadb, "__version__", "?"))
                    MariaDBConnection.logger.warning(
                        f"⚠️ mariadb.connect() rechazó '{rejected}'; "
                        f"reintentando sin él (mariadb version={mariadb_version})"
                    )

                    # Si es el último intento, lanzar error
                    if attempt == max_attempts - 1:
                        raise RuntimeError("No se pudo conectar a MariaDB; parámetros opcionales agotados") from err
        except ImportError as e:
            MariaDBConnection.logger.error("❌ Error: módulo mariadb no disponible")
            raise ConnectionError("Módulo mariadb no disponible", db_type="mariadb", details=str(e)) from e
        except Exception as e:
            MariaDBConnection.logger.error(f"❌ Error conectando a MariaDB: {e}")
            raise ConnectionError(f"Error conectando a MariaDB: {str(e)}", db_type="mariadb", details=str(e)) from e
