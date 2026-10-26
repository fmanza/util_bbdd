"""``batcherrors`` de oracledb para ``BulkCrud(rejects=RejectOptions(on_error="isolate"))`` en Oracle (S-5, sesión 2026-10-01s).

Con ``batcherrors=True``, ``cursor.executemany`` aplica las filas buenas del lote y devuelve las erróneas con su
posición (``getbatcherrors()``) en lugar de fallar en la primera: un envío por lote, sin bisección. Además aísla
ORA-12899 (demasiado largo), ORA-01400 (NOT NULL) y ORA-01438 (precisión), que llegan como ``DatabaseError`` y la
bisección no aísla.

No se salta SQLAlchemy: un listener de ``do_executemany`` sustituye la llamada al driver solo mientras hay un colector
activo en el hilo (:func:`collect`), con los procesadores de bind y ``setinputsizes`` ya aplicados. En Oracle
SQLAlchemy hace un único ``executemany`` por lote (``use_insertmanyvalues=False``), así que los offsets son los del lote.
Medido (INSERT 1M, 10 filas malas): 1,06× frente a 1,22× con bisección; datos idénticos en 8 tipos.

G32 de util_bbdd_web (4.4.0): con un lote de **una sola fila** SQLAlchemy llama a ``execute`` y no a ``executemany``,
así que el listener no actuaba y el error de la fila (p. ej. ORA-00001) hacía fallar la operación entera: una tabla de
una fila, o el último lote de una fila (5 001 filas con lotes de 5 000), no se aislaba. Con ``collect(single_row=True)``
un listener de ``do_execute`` envía esa fila con ``executemany([fila], batcherrors=True)``.
"""

from __future__ import annotations

import contextvars

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, event

_SINK: contextvars.ContextVar[list[Any] | None] = contextvars.ContextVar("bulk_oracle_batch_errors", default=None)
#: ``True`` mientras el colector activo es de un lote de una fila (lo envía ``execute``; ver la cabecera, G32).
_SINGLE_ROW: contextvars.ContextVar[bool] = contextvars.ContextVar("bulk_oracle_batch_errors_single", default=False)
#: Sentencias de un lote: el listener de ``do_execute`` no toca ninguna otra (consultas, DDL, PL/SQL).
_BATCH_VERBS: tuple[str, ...] = ("INSERT", "UPDATE", "DELETE", "MERGE")

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

    event.listen(engine, "do_execute", execute_single_row)
    setattr(engine, _INSTALLED_ATTR, True)


def execute_single_row(cursor: Any, statement: str, parameters: Any, context: Any) -> bool | None:
    """Listener de ``do_execute``: con un colector de una fila, la envía con ``batcherrors`` (G32, 4.4.0).

    Sin colector, sin ``single_row`` o si no es un INSERT/UPDATE/DELETE/MERGE, devuelve ``None`` y SQLAlchemy ejecuta
    como siempre.
    """
    sink = _SINK.get()
    if sink is None or not _SINGLE_ROW.get() or not statement.lstrip()[:6].upper().startswith(_BATCH_VERBS):
        return None
    cursor.executemany(statement, [parameters], batcherrors=True)
    sink.extend(cursor.getbatcherrors())
    return True


@contextmanager
def collect(*, single_row: bool = False) -> Generator[list[Any], None, None]:
    """Activa el colector en este hilo; devuelve la lista de errores de fila (objetos con ``offset`` y ``full_code``).

    Args:
        single_row: El lote es de una sola fila: SQLAlchemy la envía con ``execute`` y también se recoge (G32).
    """
    sink: list[Any] = []
    token = _SINK.set(sink)
    single = _SINGLE_ROW.set(single_row)
    try:
        yield sink
    finally:
        _SINGLE_ROW.reset(single)
        _SINK.reset(token)


def as_exception(batch_error: Any) -> Exception:
    """Excepción del driver para un error de fila (para el CSV de rechazos): ``DatabaseError: ORA-xxxxx: …``."""
    import oracledb  # solo se llega aquí con oracledb (supports)

    return oracledb.DatabaseError(batch_error)


__all__: list[str] = ["as_exception", "collect", "execute_single_row", "install", "supports"]
