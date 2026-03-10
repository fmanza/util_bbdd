"""Utilidades compartidas para cierre async acotado en tiempo."""

from __future__ import annotations

import asyncio
import logging

from collections.abc import Awaitable
from typing import Any, Literal, TypeAlias

DEFAULT_CLOSE_TIMEOUT_SECONDS: float = 10.0
FORCE_CLOSE_TIMEOUT_SECONDS: float = 1.0
AsyncCloseMode: TypeAlias = Literal["immediate", "graceful"]


def parse_close_timeout(value: Any, default: float = DEFAULT_CLOSE_TIMEOUT_SECONDS) -> float | None:
    """Normaliza timeout de cierre; <=0 deshabilita timeout."""
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return default
    return timeout if timeout > 0 else None


def normalize_close_mode(mode: str) -> AsyncCloseMode:
    """Normaliza y valida el modo de cierre async."""
    normalized = str(mode).strip().lower()
    if normalized == "immediate":
        return "immediate"
    if normalized == "graceful":
        return "graceful"
    raise ValueError("Modo de cierre async inválido. Use 'immediate' o 'graceful'.")


async def run_close_operation(
    action: Awaitable[Any],
    timeout_seconds: float | None,
    logger: logging.Logger,
    action_name: str,
) -> bool:
    """Ejecuta una acción de cierre con timeout opcional y manejo homogéneo."""
    try:
        if timeout_seconds is None:
            await action
        else:
            await asyncio.wait_for(action, timeout=timeout_seconds)
        return True
    except TimeoutError:
        logger.warning(f"⚠️ Timeout en {action_name} tras {timeout_seconds}s")
    except Exception:
        logger.warning(f"⚠️ Error en {action_name}", exc_info=True)
    return False
