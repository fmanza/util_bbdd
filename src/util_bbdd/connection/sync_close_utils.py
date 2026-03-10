"""Utilidades compartidas para cierres sync estrictos."""

from __future__ import annotations

import threading

from collections.abc import Callable
from typing import Any

from ..database_exceptions import DatabasePoolError, DatabasePoolTimeoutError

DEFAULT_CLOSE_TIMEOUT_SECONDS: float = 10.0
FORCE_CLOSE_TIMEOUT_SECONDS: float = 1.0


def parse_close_timeout(value: Any, default: float = DEFAULT_CLOSE_TIMEOUT_SECONDS) -> float | None:
    """Normaliza timeout de cierre; <=0 deshabilita timeout."""
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return default
    return timeout if timeout > 0 else None


def run_sync_close_operation(
    action: Callable[[], None],
    timeout_seconds: float | None,
    action_name: str,
    db_type: str | None = None,
) -> None:
    """Ejecuta una operación de cierre sync con timeout explícito."""
    if timeout_seconds is None:
        action()
        return

    errors: list[BaseException] = []
    finished = threading.Event()

    def _run() -> None:
        try:
            action()
        except Exception as err:
            errors.append(err)
        except BaseException as err:  # pragma: no cover - ruta crítica no-Exception
            errors.append(err)
            raise
        finally:
            finished.set()

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    completed = finished.wait(timeout_seconds)
    if completed is False:
        raise DatabasePoolTimeoutError(
            message=f"Timeout en operación de cierre: {action_name}",
            timeout_seconds=timeout_seconds,
            db_type=db_type,
        )

    if errors:
        err = errors[0]
        if isinstance(err, Exception):
            raise DatabasePoolError(
                message=f"Error en operación de cierre: {action_name}",
                db_type=db_type,
                details=str(err),
            ) from err
        raise DatabasePoolError(
            message=f"Error crítico en operación de cierre: {action_name}",
            db_type=db_type,
            details=repr(err),
        )
