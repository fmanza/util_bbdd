"""Medición del tiempo de ejecución de una función, registrado en el logger de su módulo.

Sustituye a ``util.timing.medir_tiempo`` (paquete externo ``util``, que la librería dejó de requerir en 3.1.0).
"""

from __future__ import annotations

import inspect
import logging

from collections.abc import Callable
from functools import wraps
from time import perf_counter

_SECONDS_PER_DAY: int = 86_400


def _format_seconds(seconds: float) -> str:
    """Formatea una duración como ``HH:MM:SS.mmm`` (con ``N día(s)`` delante si llega a 24 horas).

    Redondea a milisegundos **antes** de repartir en horas, minutos y segundos: así 59.9996 s da ``00:01:00.000`` y no
    ``00:00:60.000``.

    Args:
        seconds: Duración en segundos; no negativa.

    Returns:
        La duración legible.

    Examples:
        >>> _format_seconds(3661)
        '01:01:01.000'
        >>> _format_seconds(86461)
        '1 día 00:01:01.000'
    """
    total_ms: int = round(seconds * 1000)
    total_s, ms = divmod(total_ms, 1000)
    days, rest = divmod(total_s, _SECONDS_PER_DAY)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    clock: str = f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
    if days == 0:
        return clock
    return f"{days} {'día' if days == 1 else 'días'} {clock}"


def _returns_lazy_object(function: Callable[..., object]) -> bool:
    """True si llamar a ``function`` solo crea una corrutina o un generador (síncrono o async) sin ejecutar su cuerpo."""
    return (
        inspect.iscoroutinefunction(function)
        or inspect.isgeneratorfunction(function)
        or inspect.isasyncgenfunction(function)
    )


def medir_tiempo[**P, R](proceso: str = "", *, level: int = logging.INFO) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorador que registra cuánto tarda cada llamada a la función decorada.

    El tiempo se registra en el logger del módulo de la función (``function.__module__``, p. ej.
    ``util_bbdd.bulk.crud``), de modo que la configuración del logger ``util_bbdd`` lo controla. Si la función lanza una
    excepción, también se registra el tiempo (con ``(con error)``) y la excepción se propaga sin cambios. Conserva la
    firma de la función para el tipado (``ParamSpec``) y sus metadatos (``functools.wraps``).

    Args:
        proceso: Nombre que aparece en el mensaje; si se omite, el nombre de la función.
        level: Nivel de logging del mensaje. Con el nivel desactivado no se formatea nada.

    Returns:
        El decorador.

    Raises:
        TypeError: Al decorar una función ``async def`` o un generador (síncrono o async): devuelven un objeto que se
            ejecuta después, así que se mediría su creación y no su ejecución.

    Example:
        >>> @medir_tiempo()
        ... def cargar() -> int:
        ...     return 1
        >>> cargar()
        1
    """

    def decorador(function: Callable[P, R]) -> Callable[P, R]:
        # functools.partial y los objetos con __call__ no tienen __name__ (ni siempre __module__).
        nombre_funcion: str = getattr(function, "__name__", type(function).__name__)
        if _returns_lazy_object(function):
            raise TypeError(
                f"medir_tiempo no admite funciones async ni generadores (mediría su creación): {nombre_funcion}"
            )
        logger: logging.Logger = logging.getLogger(getattr(function, "__module__", None) or __name__)
        nombre_proceso: str = proceso or nombre_funcion

        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start: float = perf_counter()
            failed: bool = True
            try:
                result: R = function(*args, **kwargs)
                failed = False
                return result
            finally:
                if logger.isEnabledFor(level):
                    elapsed: str = _format_seconds(perf_counter() - start)
                    suffix: str = " (con error)" if failed else ""
                    logger.log(level, f"⏱️  Tiempo ejecución de {nombre_proceso}: {elapsed}{suffix}")

        return wrapper

    return decorador


__all__: list[str] = ["medir_tiempo"]
