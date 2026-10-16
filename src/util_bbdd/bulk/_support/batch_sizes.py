"""Filas por lote de cada operación de ``BulkCrud`` (B-04, performance-audit de bulk 2026-10-01).

Si el usuario no fija ``chunk_size``, el lote depende del motor y de la operación. Barrido de 1M filas, mediana de 3
repeticiones, servidores del banco (sesión ``2026-10-01i-perf-bulk-b04-batch-size``), frente a 5000:

- PostgreSQL INSERT (COPY) 20 000: −13 %; DELETE (``= ANY``) 20 000: −10 %. El UPDATE por tabla temporal empeora con
  lotes mayores (20 000: +31 %), así que sigue en 5000. ``dump`` ya escribía con lotes de 20 000 en PostgreSQL.
- SQL Server DELETE (OPENJSON) 20 000: −20 % (50 000: +26 %). El INSERT apenas cambia (−5 %) y ``dump`` midió lo contrario
  con lotes de 20 000: sigue en 5000.
- Resto de motores y operaciones: ±5 % (ruido) entre 5000 y 20 000; 1000 es peor en todos.

Con ``commit_every_n_chunks`` todas las operaciones usan 5000: la cadencia cuenta lotes y no debe cambiar cada cuántas
filas se confirma. Un ``chunk_size`` explícito se usa en todas las operaciones, como hasta v0.24.x.
"""

from __future__ import annotations

from typing import Literal

BulkOperation = Literal["insert", "update", "delete"]

#: Lote por defecto (y el de todas las operaciones con ``commit_every_n_chunks``).
DEFAULT_CHUNK_SIZE: int = 5000

# Lotes por motor y operación distintos del valor por defecto (sin commit_every_n_chunks).
_ENGINE_BATCH_SIZES: dict[str, dict[BulkOperation, int]] = {
    "postgresql": {"insert": 20_000, "delete": 20_000},
    "mssql": {"delete": 20_000},
}


def resolve_batch_sizes(
    dialect_name: str, chunk_size: int | None, commit_every_n_chunks: int | None
) -> dict[BulkOperation, int]:
    """Filas por lote de INSERT, UPDATE y DELETE.

    Args:
        dialect_name: Dialecto del engine (``engine.dialect.name``).
        chunk_size: Valor de ``BatchOptions(chunk_size=...)`` ya validado, o ``None`` para el valor por motor.
        commit_every_n_chunks: Cadencia de commit; con ella los lotes no dependen del motor.

    Returns:
        ``{"insert": n, "update": n, "delete": n}``.
    """
    if chunk_size is not None:
        return {"insert": chunk_size, "update": chunk_size, "delete": chunk_size}
    sizes: dict[BulkOperation, int] = {
        "insert": DEFAULT_CHUNK_SIZE,
        "update": DEFAULT_CHUNK_SIZE,
        "delete": DEFAULT_CHUNK_SIZE,
    }
    if commit_every_n_chunks is None:
        sizes.update(_ENGINE_BATCH_SIZES.get(dialect_name, {}))
    return sizes


__all__: list[str] = ["DEFAULT_CHUNK_SIZE", "BulkOperation", "resolve_batch_sizes"]
