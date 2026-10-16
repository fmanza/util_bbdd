"""Inicialización del modo thick de Oracle (sincróno y reversible por proceso).

El modo *thick* de ``oracledb`` requiere la inicialización de un cliente Oracle Instant Client
(versión 19 o superior para conectar con Oracle 11g; versión 21+ para 12.1+; versión 23 para 19+).
La inicialización es global por proceso e irreversible.

Esta función es thread-safe y se ejecuta solo una vez por proceso.
"""

import logging
import threading

from util_bbdd._core.exceptions import ConnectionError

__all__: list[str] = ["init_oracle_thick_mode", "ORACLE_THICK_MODE_INITIALIZED"]

logger: logging.Logger = logging.getLogger(__name__)

# Lock global para garantizar inicialización única del modo thick
_THICK_MODE_LOCK = threading.Lock()

# Bandera global: se pone a True la primera vez que se inicializa el modo thick
ORACLE_THICK_MODE_INITIALIZED: bool = False


def init_oracle_thick_mode(client_path: str) -> None:
    """Inicializa el modo thick de Oracle (una sola vez por proceso, thread-safe).

    Args:
        client_path: Ruta del Oracle Instant Client (p.ej. ``C:\\oracle\\instantclient_19_32``).

    Raises:
        ConnectionError: Si ya se llamó a esta función, o si falla la inicialización.

    Examples:
        >>> from util_bbdd.connection.oracle._thick_mode import init_oracle_thick_mode
        >>> init_oracle_thick_mode("C:\\oracle\\instantclient_19_32")
    """
    global ORACLE_THICK_MODE_INITIALIZED

    with _THICK_MODE_LOCK:
        if ORACLE_THICK_MODE_INITIALIZED:
            logger.warning(
                "Oracle thick mode ya ha sido inicializado en este proceso. "
                "No se puede reinicializar ni mezclar thin/thick en el mismo proceso."
            )
            return

        try:
            import oracledb

            logger.debug(f"🔧 Inicializando Oracle thick mode desde {client_path}")
            oracledb.init_oracle_client(lib_dir=client_path)
            ORACLE_THICK_MODE_INITIALIZED = True
            logger.info("✅ Oracle thick mode inicializado correctamente")

        except ImportError as e:
            logger.error("❌ Error: módulo oracledb no disponible")
            raise ConnectionError("Módulo oracledb no disponible", db_type="oracle", details=str(e)) from e
        except Exception as e:
            logger.error(f"❌ Error inicializando Oracle thick mode: {e}")
            raise ConnectionError(
                f"Error inicializando Oracle thick mode desde {client_path}: {str(e)}",
                db_type="oracle",
                details=str(e),
            ) from e
