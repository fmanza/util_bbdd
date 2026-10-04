"""Validación de tamaño de lote (chunk_size).

Refactor de v0.30.1: centraliza validación de chunk_size (antes en bulk._execution.executors).
"""

from __future__ import annotations

import operator

from typing import Any


def validate_chunk_size(chunk_size: Any) -> int:
    """Devuelve ``chunk_size`` como ``int`` si es un entero ≥ 1; si no, ``ValueError``.

    Sin esta validación, un ``chunk_size`` negativo no generaba ningún lote (``range`` vacío): la carga no escribía nada,
    sin error, y la auditoría registraba las filas como procesadas. Con 0, fallaba al ejecutar con
    ``range() arg 3 must not be zero``. Acepta enteros de numpy; rechaza ``bool`` y decimales.

    Args:
        chunk_size: Tamaño del lote a validar.

    Returns:
        El valor de ``chunk_size`` como ``int`` si es válido.

    Raises:
        ValueError: Si ``chunk_size`` no es un entero ≥ 1 o es un booleano.
    """
    if isinstance(chunk_size, bool):
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}")
    try:
        value = operator.index(chunk_size)
    except TypeError:
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}") from None
    if value < 1:
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}")
    return value
