"""Validación de cadencia de commits (commit_every_n_chunks).

Refactor de v0.30.1: centraliza validación de commit_cadence (antes en dump._models.DumpConfig.__post_init__).
"""

from __future__ import annotations

import operator

from typing import Any


def validate_commit_cadence(commit_every_n_chunks: Any) -> int | None:
    """Devuelve ``commit_every_n_chunks`` como ``int`` si es válido, o ``None`` si lo es.

    Acepta ``None`` (sin commits periódicos) o enteros ≥ 1. Soporta numpy ints via ``operator.index()``.

    Args:
        commit_every_n_chunks: Cadencia de commits (filas entre cada COMMIT).

    Returns:
        El valor de ``commit_every_n_chunks`` como ``int`` o ``None`` si es válido.

    Raises:
        ValueError: Si ``commit_every_n_chunks`` no es ``None`` ni un entero ≥ 1.
    """
    if commit_every_n_chunks is None:
        return None
    if isinstance(commit_every_n_chunks, bool):
        raise ValueError(f"commit_every_n_chunks debe ser None o un entero ≥ 1, recibido: {commit_every_n_chunks!r}")
    try:
        value = operator.index(commit_every_n_chunks)
    except TypeError:
        raise ValueError(
            f"commit_every_n_chunks debe ser None o un entero ≥ 1, recibido: {commit_every_n_chunks!r}"
        ) from None
    if value < 1:
        raise ValueError(f"commit_every_n_chunks debe ser None o un entero ≥ 1, recibido: {commit_every_n_chunks!r}")
    return value
