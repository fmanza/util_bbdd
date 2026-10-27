"""Transacción de solo lectura por motor para ``execute_custom_*(read_only=True)`` (v4.6.0, G19 de util_bbdd_web).

La consulta se ejecuta entre un prólogo que pone la transacción (o la sesión) en solo lectura y un ``rollback()`` que
siempre la cierra, seguido del epílogo que devuelve la sesión a su estado (SQLite y HSQLDB). Así, una escritura falla en
el motor en lugar de aplicarse, y nada queda confirmado.

SQL Server no tiene transacciones de solo lectura: el prólogo abre una transacción explícita y el ``rollback()`` final
deshace cualquier cambio. Es una garantía más débil (la escritura llega a ejecutarse y bloquea filas hasta el rollback).
"""

from __future__ import annotations

from typing import Final

#: Sentencias antes de la consulta. MySQL/MariaDB y Oracle necesitan empezar una transacción nueva: ``SET``/``START
#: TRANSACTION`` solo valen como primera sentencia (el ``rollback()`` previo cierra la que hubiera abierta).
READ_ONLY_PRELUDE: Final[dict[str, tuple[str, ...]]] = {
    "postgresql": ("SET TRANSACTION READ ONLY",),
    "mysql": ("START TRANSACTION READ ONLY",),
    "mariadb": ("START TRANSACTION READ ONLY",),
    "oracle": ("SET TRANSACTION READ ONLY",),
    "sqlserver": ("BEGIN TRANSACTION",),
    "sqlite": ("PRAGMA query_only = ON",),
    "hsqldb": ("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY",),
}

#: Sentencias después del ``rollback()`` final: las marcas de solo lectura de sesión se quitan.
READ_ONLY_EPILOGUE: Final[dict[str, tuple[str, ...]]] = {
    "sqlite": ("PRAGMA query_only = OFF",),
    "hsqldb": ("SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE",),
}


def read_only_statements(db_type: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Prólogo y epílogo de solo lectura de ``db_type``.

    Raises:
        ValueError: Si ``db_type`` no se indica o no es un motor soportado.
    """
    key = (db_type or "").lower().strip()
    if key not in READ_ONLY_PRELUDE:
        raise ValueError(f"read_only=True necesita el db_type del motor (soportados: {', '.join(READ_ONLY_PRELUDE)})")
    return READ_ONLY_PRELUDE[key], READ_ONLY_EPILOGUE.get(key, ())


def validate_max_rows(max_rows: int | None) -> None:
    """``ValueError`` si ``max_rows`` no es ``None`` ni un entero ≥ 1 (``bool`` no cuenta como entero)."""
    if max_rows is not None and (isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1):
        raise ValueError(f"max_rows debe ser un entero >= 1 o None, recibido: {max_rows!r}")


__all__: list[str] = ["READ_ONLY_EPILOGUE", "READ_ONLY_PRELUDE", "read_only_statements", "validate_max_rows"]
