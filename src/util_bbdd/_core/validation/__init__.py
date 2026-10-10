"""Validadores centralizados para parámetros comunes (chunk_size, commit_cadence, batch_config, rutas).

Refactor de v0.30.1: extrae lógica fragmentada de validación a un punto único.
"""

from __future__ import annotations

from .batch_config import validate_batch_config
from .chunk_size import validate_chunk_size
from .commit_cadence import validate_commit_cadence
from .paths import StrPath, validate_optional_path, validate_path

__all__: list[str] = [
    "validate_chunk_size",
    "validate_commit_cadence",
    "validate_batch_config",
    "StrPath",
    "validate_path",
    "validate_optional_path",
]
