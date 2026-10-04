"""Validación exhaustiva de configuración de batch (chunk_size, commit_cadence, write_batch_size).

Refactor de v0.30.1: centraliza validación integral de parámetros de batch.
"""

from __future__ import annotations

import operator

from typing import Any

from .chunk_size import validate_chunk_size
from .commit_cadence import validate_commit_cadence


def validate_batch_config(
    chunk_size: Any, commit_every_n_chunks: Any = None, write_batch_size: Any = None
) -> tuple[int, int | None, int | None]:
    """Valida la configuración de batch integral (chunk_size, commit_cadence, write_batch_size).

    Se usa en ``DumpConfig.__post_init__()`` y ``BulkCrud`` para garantizar coherencia de parámetros.
    Soporta numpy ints via ``operator.index()`` para todos los parámetros enteros.

    Args:
        chunk_size: Tamaño del lote (filas por lote).
        commit_every_n_chunks: Cadencia de commits periódicos (opcional).
        write_batch_size: Tamaño de lote de escritura (opcional, puede diferir de chunk_size en PostgreSQL).

    Returns:
        Tupla ``(chunk_size, commit_every_n_chunks, write_batch_size)`` validada.

    Raises:
        ValueError: Si algún parámetro es inválido.
    """
    # Validar chunk_size
    validated_chunk_size = validate_chunk_size(chunk_size)

    # Validar commit_every_n_chunks
    validated_commit_cadence = validate_commit_cadence(commit_every_n_chunks)

    # Validar write_batch_size
    validated_write_batch_size: int | None = None
    if write_batch_size is not None:
        if isinstance(write_batch_size, bool):
            raise ValueError(f"write_batch_size debe ser None o un entero ≥ 1, recibido: {write_batch_size!r}")
        try:
            value = operator.index(write_batch_size)
        except TypeError:
            raise ValueError(
                f"write_batch_size debe ser None o un entero ≥ 1, recibido: {write_batch_size!r}"
            ) from None
        if value < 1:
            raise ValueError(f"write_batch_size debe ser None o un entero ≥ 1, recibido: {write_batch_size!r}")
        validated_write_batch_size = value

    return validated_chunk_size, validated_commit_cadence, validated_write_batch_size
