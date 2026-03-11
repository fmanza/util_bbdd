"""Utilidades centralizadas para cierre de conexiones y pools.

Proporciona funciones de cierre con timeout para contexto sync y async,
manejando timeouts y errores de forma consistente.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from collections.abc import Awaitable, Callable
from typing import Any

from .._core import PoolConnectionError, PoolTimeoutError
from .protocols import AsyncCloseMode

__all__ = [
    "AsyncCloseMode",
    "DEFAULT_CLOSE_TIMEOUT_SECONDS",
    "FORCE_CLOSE_TIMEOUT_SECONDS",
    "parse_close_timeout",
    "normalize_close_mode",
    "run_close_operation_async",
    "run_close_operation_sync",
]

logger: logging.Logger = logging.getLogger(__name__)

# Constantes de timeout
DEFAULT_CLOSE_TIMEOUT_SECONDS: float = 10.0
FORCE_CLOSE_TIMEOUT_SECONDS: float = 1.0


# ============================================================================
# Funciones Auxiliares
# ============================================================================


def parse_close_timeout(value: Any, default: float = DEFAULT_CLOSE_TIMEOUT_SECONDS) -> float | None:
    """Normaliza timeout de cierre; <=0 deshabilita timeout.

    Args:
        value: Valor de timeout a normalizar
        default: Valor por defecto si no se puede parsear

    Returns:
        Float positivo o None si timeout está deshabilitado
    """
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return default
    return timeout if timeout > 0 else None


def normalize_close_mode(mode: str) -> AsyncCloseMode:
    """Normaliza y valida el modo de cierre async.

    Args:
        mode: Cadena con modo ('immediate' o 'graceful')

    Returns:
        'immediate' o 'graceful' normalizado

    Raises:
        ValueError: Si el modo no es válido
    """
    normalized = str(mode).strip().lower()
    if normalized == "immediate":
        return "immediate"
    if normalized == "graceful":
        return "graceful"
    raise ValueError("Modo de cierre async inválido. Use 'immediate' o 'graceful'.")


# ============================================================================
# Cierre Asincrónico
# ============================================================================


async def run_close_operation_async(
    action: Awaitable[Any],
    timeout_seconds: float | None,
    action_name: str,
    db_type: str | None = None,
) -> bool:
    """Ejecuta una acción de cierre async con timeout opcional.

    Args:
        action: Corrutina a ejecutar
        timeout_seconds: Timeout en segundos (None = sin límite)
        action_name: Nombre de la acción (para logging)
        db_type: Tipo de BD (para contexto del error)

    Returns:
        True si completó exitosamente, False si tuvo timeout/error
    """
    try:
        if timeout_seconds is None:
            await action
        else:
            await asyncio.wait_for(action, timeout=timeout_seconds)
        return True

    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Timeout en {action_name} tras {timeout_seconds}s para BD '{db_type}'")
        return False

    except Exception as e:
        logger.warning(
            f"⚠️ Error en {action_name} para BD '{db_type}': {e}",
            exc_info=True,
        )
        return False


# ============================================================================
# Cierre Sincrónico
# ============================================================================


def run_close_operation_sync(
    action: Callable[[], None],
    timeout_seconds: float | None,
    action_name: str,
    db_type: str | None = None,
) -> None:
    """Ejecuta una operación de cierre sync con timeout explícito.

    Utiliza threading para implementar timeout en operaciones blocking.

    Args:
        action: Callable sin argumentos que realiza el cierre
        timeout_seconds: Timeout en segundos (None = sin límite)
        action_name: Nombre de la acción (para logging y errores)
        db_type: Tipo de BD (para contexto del error)

    Raises:
        PoolTimeoutError: Si se excede el timeout
        PoolConnectionError: Si hay error en la acción
    """
    # Sin timeout: ejecutar directamente
    if timeout_seconds is None:
        action()
        return

    # Con timeout: ejecutar en thread con espera
    errors: list[BaseException] = []
    finished = threading.Event()

    def _run() -> None:
        """Wrapper que ejecuta action en thread."""
        try:
            action()
        except Exception as err:
            errors.append(err)
        except BaseException as err:  # pragma: no cover - ruta crítica
            errors.append(err)
            raise
        finally:
            finished.set()

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    completed = finished.wait(timeout=timeout_seconds)

    # Timeout excedido
    if not completed:
        raise PoolTimeoutError(
            message=f"Timeout en operación de cierre: {action_name}",
            operation="CLOSE",
            db_type=db_type,
            details=f"Timeout excedido: {timeout_seconds}s en {action_name}",
        )

    # Error en la acción
    if errors:
        err = errors[0]
        if isinstance(err, Exception):
            raise PoolConnectionError(
                message=f"Error en operación de cierre: {action_name}",
                db_type=db_type,
                details=str(err),
            ) from err

        # Error crítico (no-Exception)
        raise PoolConnectionError(
            message=f"Error crítico en operación de cierre: {action_name}",
            db_type=db_type,
            details=repr(err),
        )
