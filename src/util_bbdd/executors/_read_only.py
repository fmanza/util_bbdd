"""Transacción de solo lectura por motor para ``execute_custom_*(read_only=True)`` (v4.6.0, G19 de util_bbdd_web).

La consulta se ejecuta entre un prólogo que pone la transacción (o la sesión) en solo lectura y un ``rollback()`` que
siempre la cierra, seguido del epílogo que devuelve la sesión a su estado (SQLite y HSQLDB). Así, una escritura falla en
el motor en lugar de aplicarse, y nada queda confirmado.

SQL Server no tiene transacciones de solo lectura: el prólogo abre una transacción explícita y el ``rollback()`` final
deshace cualquier cambio. Es una garantía más débil (la escritura llega a ejecutarse y bloquea filas hasta el rollback).
"""

from __future__ import annotations

import math

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


#: SQLSTATE de PostgreSQL para una sentencia cancelada (``statement_timeout`` o ``pg_cancel_backend``).
_PG_QUERY_CANCELED: Final[str] = "57014"


def server_timeout_statements(db_type: str | None, timeout: float | None) -> tuple[str, ...]:
    """Sentencias que ponen ``timeout`` (segundos) como plazo en el servidor, dentro de la transacción de solo lectura.

    Solo PostgreSQL (5.0.0, D8-4 del plan de util_bbdd_web): ``SET LOCAL statement_timeout``, que dura hasta el
    ``rollback()`` que cierra la transacción. En el resto de motores el plazo sigue siendo solo del cliente.
    """
    if timeout is None or not math.isfinite(timeout) or (db_type or "").lower().strip() != "postgresql":
        return ()  # un plazo infinito (o NaN) no limita nada en el servidor
    # 0 desactiva el límite en PostgreSQL: un plazo de menos de 1 ms se redondea a 1 ms.
    milliseconds = max(1, math.ceil(timeout * 1000))
    return (f"SET LOCAL statement_timeout = {milliseconds}",)


def is_server_timeout(err: BaseException) -> bool:
    """``True`` si ``err`` (o su cadena de causas) es la cancelación de PostgreSQL por ``statement_timeout``.

    psycopg2 da el SQLSTATE en ``pgcode``; psycopg 3 y asyncpg, en ``sqlstate``; SQLAlchemy envuelve el error del
    driver en ``orig``.
    """
    seen: set[int] = set()
    current: BaseException | None = err
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for source in (current, getattr(current, "orig", None)):
            if any(getattr(source, attr, None) == _PG_QUERY_CANCELED for attr in ("pgcode", "sqlstate")):
                return True
        current = current.__cause__ or current.__context__
    return False


__all__: list[str] = [
    "READ_ONLY_EPILOGUE",
    "READ_ONLY_PRELUDE",
    "is_server_timeout",
    "read_only_statements",
    "server_timeout_statements",
    "validate_max_rows",
]
