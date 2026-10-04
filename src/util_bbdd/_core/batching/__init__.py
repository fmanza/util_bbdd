"""Resolución de tamaño de lote de escritura por motor (batch_resolver).

Refactor de v0.30.1: centraliza lógica de batching motor-específico (antes en DumpOrchestrator._resolve_write_batch_size).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy import Engine

# PostgreSQL optimization: default write batch si commit_every_n_chunks es None
_PG_DEFAULT_WRITE_BATCH = 20_000


def resolve_write_batch_size(
    db_type: str | None, chunk_size: int, commit_every_n_chunks: int | None, target_engine: Engine | None = None
) -> int:
    """Resuelve el tamaño de lote de escritura por motor de destino.

    Lógica:
    - Si se especificó ``write_batch_size`` en DumpConfig, úsalo (validado antes)
    - Si destino es PostgreSQL y ``commit_every_n_chunks`` es None, usa 20_000 (optimización COPY)
    - En el resto de casos, usa ``chunk_size``

    Args:
        db_type: Nombre del motor (ej. "postgresql", "mysql", "oracle", "sqlserver", "sqlite").
        chunk_size: Tamaño base de lote (filas).
        commit_every_n_chunks: Cadencia de commits periódicos (None o entero ≥ 1).
        target_engine: (Alternativo) SQLAlchemy Engine del destino. Si se pasa, ignora ``db_type`` y usa ``engine.dialect.name``.

    Returns:
        Tamaño de lote de escritura optimizado por motor.
    """
    # Determinar motor: preferir engine.dialect.name si se pasa
    dialect_name = db_type
    if target_engine is not None:
        dialect_name = target_engine.dialect.name

    # PostgreSQL special: optimize write batch for COPY performance (without changing commit cadence)
    if dialect_name == "postgresql" and commit_every_n_chunks is None:
        return max(chunk_size, _PG_DEFAULT_WRITE_BATCH)

    # Resto de motores: usar chunk_size
    return chunk_size
