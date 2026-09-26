"""Peculiaridades de drivers y límites de parámetros compartidos por las estrategias de ``bulk``.

Separado de ``batch`` (R10b del refactor de reutilización 2026-09-26) sin cambios de comportamiento.
"""

from __future__ import annotations

import contextlib
import decimal

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import (
    Engine,
)
from sqlalchemy.exc import DBAPIError, StatementError

# SQL Server admite 2100 parámetros por petición (SQLAlchemy usa 2099 en insertmanyvalues); se deja margen.
_MSSQL_MAX_DELETE_PARAMS: int = 2000


# MySQL/MariaDB: máximo de parámetros de una sentencia preparada (P-13; lo aplica el conector ``mariadb``, que prepara
# en el servidor; PyMySQL sustituye en el cliente y no tiene límite, pero trocear no le afecta).
_MYSQL_MAX_STATEMENT_PARAMS: int = 65_535


def _register_fast_executemany(engine: Engine) -> None:
    """Activa fast_executemany en el dialecto mssql+pyodbc igual que ``create_engine(..., fast_executemany=True)``.

    P-18/P-01 (performance-audit de bulk, 2026-09-23): activar ``cursor.fast_executemany`` con un listener, a espaldas
    del dialecto, rompía el UPDATE con columnas DATETIME (``HY104 Invalid precision value``), porque SQLAlchemy solo
    omite ``cursor.setinputsizes()`` en los executemany cuando ``dialect.fast_executemany`` es True. Además, con
    insertmanyvalues activo el INSERT nunca llegaba a ``executemany``. Se fijan los mismos dos atributos que
    ``MSDialect_pyodbc.__init__`` fija con ``fast_executemany=True``; afecta a todo el engine, como el listener.

    Omite engines que no son un Engine SQLAlchemy real (p.ej. MagicMock en tests) y dialectos sin
    ``fast_executemany`` (cualquiera distinto de mssql+pyodbc). Idempotente.
    """
    if not isinstance(engine, Engine):
        return
    dialect: Any = engine.dialect
    if not hasattr(dialect, "fast_executemany"):
        return
    dialect.fast_executemany = True
    dialect.use_insertmanyvalues_wo_returning = False


# Precisión máxima de DECIMAL/NUMERIC en SQL Server.
_MSSQL_MAX_DECIMAL_PRECISION = 38


def _driver_decimal_context(engine: Engine) -> contextlib.AbstractContextManager[Any]:
    """Contexto ``decimal`` para la llamada al driver: en SQL Server con ``fast_executemany``, precisión ≥ 38.

    PD-10 (performance-audit de dump 2026-09-26): con ``fast_executemany`` pyodbc convierte cada ``Decimal`` al
    ``NUMERIC`` del parámetro con el contexto ``decimal`` del hilo, de 28 dígitos por defecto. Un DECIMAL de más de 28
    dígitos significativos se redondeaba sin avisar (o fallaba con el error 8023 si el redondeo desbordaba). Se mira el
    dialecto al ejecutar: ``fast_executemany`` es de todo el engine y puede activarlo otra instancia o el usuario.
    """
    if engine.dialect.name != "mssql" or not getattr(engine.dialect, "fast_executemany", False):
        return contextlib.nullcontext()
    context = decimal.getcontext().copy()
    context.prec = max(context.prec, _MSSQL_MAX_DECIMAL_PRECISION)
    return decimal.localcontext(context)


class _PlainDecimal(decimal.Decimal):
    """``Decimal`` cuyo ``str()`` usa notación fija (``0.0000000000`` en vez de ``0E-10``); ver ``_pymssql_plain_decimals``."""

    def __str__(self) -> str:
        return format(self, "f")

    __repr__ = __str__


def _pymssql_plain_decimals(engine: Engine, records: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    """Con pymssql, los ``Decimal`` de ``records`` en notación fija; con otros drivers, ``records`` tal cual.

    PD-13 (2026-09-26): pymssql incrusta los parámetros en el SQL con ``str()``, y ``str(Decimal("0E-10"))`` es ``0E-10``
    (así llega un cero leído de una columna ``DECIMAL(p,10)``). SQL Server lee ese literal como ``float`` y, en el
    ``INSERT … VALUES (…), (…)`` multi-fila de SQLAlchemy (insertmanyvalues), convierte a ``float`` toda la columna: los
    DECIMAL de más de ~15 dígitos del lote se redondeaban sin aviso. Mismo valor, solo cambia cómo se escribe.
    """
    if engine.dialect.driver != "pymssql":
        return records
    return [
        {key: _PlainDecimal(value) if type(value) is decimal.Decimal else value for key, value in record.items()}
        for record in records
    ]


def _begin_if_needed(connection: Any) -> None:
    """Inicia la transacción de SQLAlchemy antes de escribir por el cursor del driver (P-27).

    SQLAlchemy no ve lo que se ejecuta por ``connection.connection.cursor()``: en modo commit-as-you-go
    (``engine.connect()``, usado con ``commit_every_n_chunks``) no habría transacción iniciada, ``commit()`` no haría
    nada y las filas se desharían al devolver la conexión al pool.
    """
    if not connection.in_transaction():
        connection.begin()


def _wrap_driver_error(connection: Any, statement: str, exc: Exception) -> StatementError:
    """Error del driver como ``DBAPIError`` de SQLAlchemy (``IntegrityError``, ``OperationalError``…) (P-28).

    Lo que se ejecuta por el cursor del driver no pasa por SQLAlchemy, que es quien envuelve sus errores; sin esto
    llegarían sin envolver a quien captura ``SQLAlchemyError`` (``ParallelBulkLoader``, ``dump``). Los parámetros no se
    incluyen (pueden ser miles de filas). Si el error es una desconexión, se invalida la conexión como haría SQLAlchemy.
    """
    dialect = connection.dialect
    invalidated: bool = dialect.is_disconnect(exc, connection.connection.dbapi_connection, None)
    if invalidated:
        connection.invalidate(exc)
    return DBAPIError.instance(
        statement, None, exc, dialect.loaded_dbapi.Error, connection_invalidated=invalidated, dialect=dialect
    )
