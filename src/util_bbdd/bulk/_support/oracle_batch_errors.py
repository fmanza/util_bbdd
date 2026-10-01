"""``batcherrors`` de oracledb para ``BulkCrud(on_error="isolate")`` en Oracle (S-5, sesión 2026-10-01s).

Con ``batcherrors=True``, ``cursor.executemany`` aplica las filas buenas del lote y devuelve las erróneas con su
posición (``getbatcherrors()``) en lugar de fallar en la primera: un envío por lote, sin bisección. Además aísla
ORA-12899 (demasiado largo), ORA-01400 (NOT NULL) y ORA-01438 (precisión), que llegan como ``DatabaseError`` y la
bisección no aísla.

No se salta SQLAlchemy: un listener de ``do_executemany`` sustituye la llamada al driver solo mientras hay un colector
activo en el hilo (:func:`collect`), con los procesadores de bind y ``setinputsizes`` ya aplicados. En Oracle
SQLAlchemy hace un único ``executemany`` por lote (``use_insertmanyvalues=False``), así que los offsets son los del lote.
Medido (INSERT 1M, 10 filas malas): 1,06× frente a 1,22× con bisección; datos idénticos en 8 tipos.
"""

from __future__ import annotations

import contextvars

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, event

_SINK: contextvars.ContextVar[list[Any] | None] = contextvars.ContextVar("bulk_oracle_batch_errors", default=None)

#: Atributo que marca un engine con el listener ya registrado (idempotencia).
_INSTALLED_ATTR: str = "_util_bbdd_batch_errors_installed"


def supports(engine: Any) -> bool:
    """``True`` si ``engine`` es Oracle con el driver ``oracledb`` (``cx_Oracle``, sin probar, sigue con bisección)."""
    dialect = getattr(engine, "dialect", None)
    return getattr(dialect, "name", None) == "oracle" and getattr(dialect, "driver", None) == "oracledb"


def install(engine: Engine) -> None:
    """Registra (una vez por engine) el listener que usa ``batcherrors`` mientras haya un colector activo."""
    if getattr(engine, _INSTALLED_ATTR, False):
        return

    @event.listens_for(engine, "do_executemany")
    def _executemany_with_batch_errors(cursor: Any, statement: str, parameters: Any, context: Any) -> bool | None:
        sink = _SINK.get()
        if sink is None:
            return None  # SQLAlchemy ejecuta como siempre
        cursor.executemany(statement, parameters, batcherrors=True)
        sink.extend(cursor.getbatcherrors())
        return True

    setattr(engine, _INSTALLED_ATTR, True)


@contextmanager
def collect() -> Generator[list[Any], None, None]:
    """Activa el colector en este hilo; devuelve la lista de errores de fila (objetos con ``offset`` y ``full_code``)."""
    sink: list[Any] = []
    token = _SINK.set(sink)
    try:
        yield sink
    finally:
        _SINK.reset(token)


def as_exception(batch_error: Any) -> Exception:
    """Excepción del driver para un error de fila (para el CSV de rechazos): ``DatabaseError: ORA-xxxxx: …``."""
    import oracledb  # solo se llega aquí con oracledb (supports)

    return oracledb.DatabaseError(batch_error)


__all__: list[str] = ["as_exception", "collect", "install", "supports"]
