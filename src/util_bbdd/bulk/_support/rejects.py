"""Aislamiento de filas erróneas en las operaciones masivas (``BulkCrud(on_error="isolate")``, S-2 de 2026-10-01).

Una carga atómica se deshacía entera por una sola fila con un error de datos. Con ``on_error="isolate"`` cada lote se
envía dentro de un SAVEPOINT; si falla con un error de datos (``IntegrityError`` o ``DataError``), se vuelve al SAVEPOINT
y se reenvía por mitades, cada una en su SAVEPOINT, hasta aislar las filas que fallan. Las demás se aplican; las que
fallan se escriben en un CSV de rechazos. INSERT de 1M filas con la API final: sin filas malas 1,00–1,02×; con 10
filas malas 1,13–1,23× (PostgreSQL 1,65×, lotes de 20 000): cada fila mala reenvía unas 2 veces su lote.
"""

from __future__ import annotations

import contextlib
import logging
import operator
import sqlite3

from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Table
from sqlalchemy.exc import DataError, IntegrityError

from ...audit.rejects import REJECT_COLUMNS, RejectsWriter
from . import oracle_batch_errors

# El CSV de rechazos (``RejectsWriter``, ``REJECT_COLUMNS``) vive en ``util_bbdd.audit.rejects`` desde la sesión
# 2026-10-02c y se re-exporta aquí para los imports existentes. Este módulo conserva el aislamiento por SAVEPOINT.

#: Errores que se aíslan. Cualquier otro (columna inexistente, permisos, sintaxis, desconexión) se propaga: no es un
#: problema de una fila y aislarlo acabaría rechazando todas.
ISOLATED_ERRORS: tuple[type[Exception], ...] = (IntegrityError, DataError)


def optional_non_negative_int(value: Any, name: str) -> int | None:
    """``value`` como ``int`` si es ``None`` o un entero ≥ 0 (también de numpy, como ``chunk_size``); si no, ``ValueError``.

    B-2 (audit-code 2026-10-02): ``isinstance(x, int)`` rechazaba ``numpy.int64``, lo habitual si el valor sale de pandas.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} debe ser None o un entero ≥ 0, recibido: {value!r}")
    try:
        number = operator.index(value)
    except TypeError:
        raise ValueError(f"{name} debe ser None o un entero ≥ 0, recibido: {value!r}") from None
    if number < 0:
        raise ValueError(f"{name} debe ser None o un entero ≥ 0, recibido: {value!r}")
    return number


def validate_isolation(on_error: str, rejects_csv_path: Path | None, max_rejects: int | None) -> None:
    """``ValueError`` si ``on_error``, ``rejects_csv_path`` y ``max_rejects`` no son una combinación válida.

    Común a ``BulkCrud`` y ``ParallelBulkLoader`` (que valida antes de lanzar los hilos).
    """
    if on_error not in ("raise", "isolate"):
        raise ValueError(f"on_error debe ser 'raise' o 'isolate', recibido: {on_error!r}")
    if on_error == "raise":
        if rejects_csv_path is not None or max_rejects is not None:
            raise ValueError("rejects_csv_path y max_rejects solo se usan con on_error='isolate'")
        return
    if rejects_csv_path is None:
        raise ValueError("on_error='isolate' necesita rejects_csv_path: las filas rechazadas se escriben ahí")
    optional_non_negative_int(max_rejects, "max_rejects")


def _savepoint(connection: Any) -> Any:
    """``connection.begin_nested()`` con una transacción real debajo también en SQLite (pysqlite).

    El módulo ``sqlite3`` (control de transacciones heredado, el de por defecto) solo emite ``BEGIN`` antes de un
    INSERT/UPDATE/DELETE. Si lo primero de la transacción es el ``SAVEPOINT``, SQLite abre con él la transacción y su
    ``RELEASE`` la confirma: un fallo posterior de la sesión ya no deshacía esos lotes. Con ``isolation_level=None``
    (autocommit, o la receta de SQLAlchemy que emite ``BEGIN`` en el evento ``begin``) quien usa el engine controla las
    transacciones y no se toca.

    B-3 (audit-code 2026-10-01): con ``sqlite3.connect(autocommit=True)`` (Python ≥ 3.12) no hay transacción que proteja
    los SAVEPOINT: el ``BEGIN`` quedaba abierto (``commit()`` no hace nada en ese modo) y, sin él, el ``ROLLBACK TO`` de
    una fila mala dejaba abierto el SAVEPOINT externo; en ambos casos las filas no se confirmaban y la BD quedaba
    bloqueada. Se rechaza con ``ValueError`` antes de enviar nada. El modo ``AUTOCOMMIT`` de SQLAlchemy funciona.
    """
    if getattr(getattr(connection, "dialect", None), "name", None) == "sqlite":
        driver = connection.connection.driver_connection
        mode = getattr(driver, "autocommit", sqlite3.LEGACY_TRANSACTION_CONTROL)
        if mode is True:
            raise ValueError(
                "on_error='isolate' necesita una transacción y sqlite3 con autocommit=True no la tiene: crea el engine "
                "sin connect_args={'autocommit': True} (o con isolation_level='AUTOCOMMIT' de SQLAlchemy)"
            )
        if (
            mode == sqlite3.LEGACY_TRANSACTION_CONTROL
            and getattr(driver, "isolation_level", None) is not None
            and not getattr(driver, "in_transaction", True)
        ):
            driver.execute("BEGIN")
    return connection.begin_nested()


def _rollback_after_data_error(savepoint: Any, error: BaseException) -> None:
    """Vuelve al SAVEPOINT tras ``error``; si no se puede, relanza ``error`` con una nota (B-1, audit-code 2026-10-01).

    Con ``XACT_ABORT ON``, SQL Server deshace la transacción entera con el primer error y el SAVEPOINT ya no existe:
    antes llegaba el error del rollback («Cannot roll back sa_savepoint_1», 3903) y el error de datos solo quedaba en
    ``__context__``. Ahora llega el error de datos, como sin aislamiento, con el del rollback como causa.
    """
    try:
        savepoint.rollback()
    except Exception as rollback_error:
        lines = str(getattr(rollback_error, "orig", None) or rollback_error).strip().splitlines()
        error.add_note(
            f"bulk: no se pudo volver al SAVEPOINT tras el error de datos ({type(rollback_error).__name__}: "
            f"{lines[0] if lines else ''}); en SQL Server suele deberse a XACT_ABORT ON, que deshace la transacción "
            "entera con el primer error: on_error='isolate' no puede aislar filas así"
        )
        raise error from rollback_error


class Isolator:
    """Envía lotes dentro de SAVEPOINT y aísla por bisección las filas con errores de datos.

    Args:
        on_reject: ``on_reject(posición, valores, error)`` para cada fila rechazada.
        max_rejects: Filas que se pueden rechazar. La siguiente relanza su error (con una nota) y la operación falla
            como sin aislamiento. ``None``: sin límite.
    """

    def __init__(
        self,
        *,
        on_reject: Callable[[int, Mapping[str, Any], BaseException], None],
        max_rejects: int | None = None,
        batch_errors: bool = False,
        already_rejected: int = 0,
    ) -> None:
        self._on_reject = on_reject
        self._max_rejects = max_rejects
        #: Rechazos de operaciones anteriores del mismo ``BulkCrud.rejects_scope``: comparten el presupuesto de
        #: ``max_rejects`` (sesión 2026-10-02).
        self._already_rejected: int = already_rejected
        #: Oracle con oracledb: un envío por lote con ``batcherrors`` en lugar de bisección (S-5, sesión 2026-10-01s).
        #: ``BulkCrud`` lo desactiva en el UPDATE con columnas LOB (ORA-03106 del driver con ``batcherrors``).
        self.batch_errors: bool = batch_errors
        #: Filas rechazadas por esta instancia: las que ``on_reject`` procesó sin error.
        self.rejected: int = 0

    def run_records(
        self, connection: Any, records: Sequence[Mapping[str, Any]], send: Callable[[Any], None], *, first_row: int
    ) -> None:
        """Lote de registros (``list[dict]``)."""
        if self.batch_errors:
            self._run_batch_errors(connection, records, send, first_row=first_row, at=lambda items, i: items[i])
            return
        self._run(
            connection,
            records,
            send,
            first_row=first_row,
            cut=lambda items, a, b: items[a:b],
            row=lambda items: items[0],
        )

    def run_frame(self, connection: Any, frame: Any, send: Callable[[Any], None], *, first_row: int) -> None:
        """Lote como DataFrame (DELETE)."""
        if self.batch_errors:
            self._run_batch_errors(
                connection, frame, send, first_row=first_row, at=lambda items, i: items.iloc[i].to_dict()
            )
            return
        self._run(
            connection,
            frame,
            send,
            first_row=first_row,
            cut=lambda items, a, b: items.iloc[a:b],
            row=lambda items: items.iloc[0].to_dict(),
        )

    def run_columns(
        self,
        connection: Any,
        block: Any,
        send_columns: Callable[[Any], None],
        send_records: Callable[[Any], None],
        *,
        first_row: int,
    ) -> None:
        """Bloque por columnas (``SqlColumns``): se intenta entero; si falla, se pasa a registros solo en ese camino."""
        savepoint = _savepoint(connection)
        try:
            send_columns(block)
        except ISOLATED_ERRORS as error:
            _rollback_after_data_error(savepoint, error)
            records = [block[index] for index in range(len(block))]
            self._bisect(
                connection, records, send_records, first_row, lambda items, a, b: items[a:b], lambda items: items[0]
            )
            return
        except BaseException:
            with contextlib.suppress(Exception):
                savepoint.rollback()
            raise
        savepoint.commit()

    def _run(
        self,
        connection: Any,
        items: Any,
        send: Callable[[Any], None],
        *,
        first_row: int,
        cut: Callable[[Any, int, int], Any],
        row: Callable[[Any], Mapping[str, Any]],
    ) -> None:
        savepoint = _savepoint(connection)
        try:
            send(items)
        except ISOLATED_ERRORS as error:
            _rollback_after_data_error(savepoint, error)
            if len(items) == 1:
                self._reject(first_row, row(items), error)
                return
            self._bisect(connection, items, send, first_row, cut, row)
            return
        except BaseException:
            # No es un error de datos: se propaga. El SAVEPOINT se deshace si la conexión aún lo admite.
            with contextlib.suppress(Exception):
                savepoint.rollback()
            raise
        savepoint.commit()

    def _run_batch_errors(
        self,
        connection: Any,
        items: Any,
        send: Callable[[Any], None],
        *,
        first_row: int,
        at: Callable[[Any, int], Mapping[str, Any]],
    ) -> None:
        """Un envío con ``batcherrors``: las filas buenas se aplican y las erróneas se rechazan con su posición.

        Si el lote tiene más filas erróneas de las que ``max_rejects`` admite, se rechazan las que caben, se vuelve al
        SAVEPOINT y se reenvía el lote sin ``batcherrors`` para que el driver lance su error real (clase y mensaje).
        """
        savepoint = _savepoint(connection)
        try:
            with oracle_batch_errors.collect() as errors:
                send(items)
        except BaseException:
            # Error de sentencia o de conexión (batcherrors solo recoge errores de fila): se propaga.
            with contextlib.suppress(Exception):
                savepoint.rollback()
            raise
        errors.sort(key=lambda batch_error: batch_error.offset)
        budget: int | None = (
            None if self._max_rejects is None else self._max_rejects - self._already_rejected - self.rejected
        )
        accepted = errors if budget is None else errors[:budget]
        for batch_error in accepted:
            offset: int = batch_error.offset
            self._reject(first_row + offset, at(items, offset), oracle_batch_errors.as_exception(batch_error))
        if len(accepted) == len(errors):
            savepoint.commit()
            return
        savepoint.rollback()
        note = (
            f"bulk: el lote que empieza en la fila {first_row} de la entrada tiene {len(errors)} filas con error y "
            f"max_rejects={self._max_rejects} solo admitía {len(accepted)} más; la operación falla como sin "
            "on_error='isolate'"
        )
        resend = _savepoint(connection)
        try:
            send(items)
        except Exception as error:
            with contextlib.suppress(Exception):
                resend.rollback()
            error.add_note(note)
            raise
        resend.rollback()  # no debería llegar aquí: los mismos datos tienen errores de fila
        exception = oracle_batch_errors.as_exception(errors[len(accepted)])
        exception.add_note(note)
        raise exception

    def _bisect(
        self,
        connection: Any,
        items: Any,
        send: Callable[[Any], None],
        first_row: int,
        cut: Callable[[Any, int, int], Any],
        row: Callable[[Any], Mapping[str, Any]],
    ) -> None:
        size = len(items)
        half = size // 2
        self._run(connection, cut(items, 0, half), send, first_row=first_row, cut=cut, row=row)
        self._run(connection, cut(items, half, size), send, first_row=first_row + half, cut=cut, row=row)

    def _reject(self, position: int, values: Mapping[str, Any], error: BaseException) -> None:
        if self._max_rejects is not None and self._already_rejected + self.rejected >= self._max_rejects:
            error.add_note(
                f"bulk: la fila {position} de la entrada habría superado max_rejects={self._max_rejects}; "
                "la operación falla como sin on_error='isolate'"
            )
            raise error
        self._on_reject(position, values, error)
        self.rejected += 1  # M-1: solo filas entregadas (escritas): si on_reject falla, no cuenta


#: Nota que lleva el ``OSError`` de no poder escribir el CSV de rechazos (M-1, audit-code 2026-10-01).
REJECTS_FAILURE_NOTE: str = "bulk: no se pudo escribir el CSV de rechazos"


@dataclass(slots=True)
class RejectsSequence:
    """Estado de ``BulkCrud.rejects_scope``: una secuencia de entrada para los rechazos de varias operaciones."""

    partition: int | None
    #: Posición en la secuencia de la primera fila de la operación siguiente.
    row_offset: int
    #: Rechazos de las operaciones ya terminadas del ámbito (presupuesto común de ``max_rejects``).
    rejected: int = 0


@dataclass(slots=True)
class IsolatedOperation:
    """Lo que :meth:`RejectsCoordinator.operation` necesita saber de la operación: sus filas, para avanzar el ámbito."""

    rows: int = 0


class RejectsCoordinator:
    """Rechazos de una ``BulkCrud`` con ``on_error="isolate"``: escritor, presupuesto, ámbito y aislador en curso.

    Extraído de ``bulk/crud.py`` en v1.1.0 (A5, SRP de ``BulkCrud`` por dentro) sin cambios de comportamiento. Sin
    escritor (``on_error="raise"``) no hace nada. ``BulkCrud`` le pasa cómo reflejar la tabla, si se aísla con
    ``batcherrors`` (Oracle) y cómo enganchar el aislador a sus ejecutores, para que este módulo no dependa de ellos.

    Args:
        writer: CSV de rechazos, o ``None`` sin aislamiento.
        max_rejects: Filas que una operación (o un :meth:`scope`) puede rechazar; ``None`` sin límite.
        reflect_table: ``Table`` de una tabla destino (``BulkCrud.reflect_table``).
        batch_errors: ``True`` si se aíslan filas con ``batcherrors`` (``BulkCrud.__batch_errors``).
        attach: Engancha el aislador de la operación a los ejecutores (``None`` al terminar).
        logger: Logger de ``BulkCrud``.
    """

    def __init__(
        self,
        *,
        writer: RejectsWriter | None,
        max_rejects: int | None,
        reflect_table: Callable[[str], Table],
        batch_errors: Callable[[], bool],
        attach: Callable[[Isolator | None], None],
        logger: logging.Logger,
    ) -> None:
        self._writer: RejectsWriter | None = writer
        self._max_rejects: int | None = max_rejects
        self._reflect_table: Callable[[str], Table] = reflect_table
        self._batch_errors: Callable[[], bool] = batch_errors
        self._attach: Callable[[Isolator | None], None] = attach
        self.logger: logging.Logger = logger
        #: Filas rechazadas por la instancia, acumulado (``BulkCrud.rows_rejected``).
        self.rows_rejected: int = 0
        #: Aislador de la operación en curso; None fuera de una operación.
        self.isolator: Isolator | None = None
        #: Ámbito de ``rejects_scope`` en curso (None fuera de él).
        self._sequence: RejectsSequence | None = None

    @contextmanager
    def scope(self, *, partition: int | None, row_offset: int) -> Generator[None, None, None]:
        """Cuerpo de ``BulkCrud.rejects_scope`` (validación y ámbito; la documentación pública está allí)."""
        # B-1 (audit-code 2026-10-02): partition va sin neutralizar al CSV (se abre en Excel); solo enteros.
        checked_partition = optional_non_negative_int(partition, "partition")
        checked_offset = optional_non_negative_int(row_offset, "row_offset")
        if checked_offset is None:
            raise ValueError(f"row_offset debe ser un entero ≥ 0, recibido: {row_offset!r}")
        if self._sequence is not None:
            raise RuntimeError("rejects_scope ya está abierto en esta instancia de BulkCrud")
        self._sequence = RejectsSequence(partition=checked_partition, row_offset=checked_offset)
        try:
            yield
        finally:
            self._sequence = None

    @contextmanager
    def operation(self, tabla_destino: str, operation: str) -> Generator[IsolatedOperation, None, None]:
        """Con ``on_error="isolate"``, aísla las filas erróneas de la operación (S-2); si no, no hace nada.

        Un ``*_from_chunks`` es una sola operación (``max_rejects`` cuenta toda la secuencia): dentro de él, el
        aislador del stream se reutiliza. Dentro de :meth:`scope`, la posición y el presupuesto de ``max_rejects``
        continúan los del ámbito; quien llama anota en ``rows`` las filas de entrada de la operación.
        """
        operation_rows = IsolatedOperation()
        if self._writer is None or self.isolator is not None:
            yield operation_rows
            return
        writer: RejectsWriter = self._writer
        tabla: Table = self._reflect_table(tabla_destino)
        columns: set[str] = set(tabla.c.keys())
        scope = self._sequence
        base: int = 0 if scope is None else scope.row_offset
        partition: int | None = None if scope is None else scope.partition

        def on_reject(position: int, values: Mapping[str, Any], error: BaseException) -> None:
            # Sin los alias de PK del UPDATE: solo las columnas de la tabla.
            row = {key: value for key, value in values.items() if key in columns}
            position += base  # posición en la secuencia de rejects_scope (filas saltadas al reanudar, chunks previos)
            try:
                writer.write(
                    table=tabla_destino,
                    operation=operation,
                    position=position,
                    error=error,
                    values=row,
                    partition=partition,
                )
            except OSError as exc:
                # M-1 (audit-code 2026-10-01): p. ej. el CSV abierto en Excel. La operación falla (no se pierde el
                # rechazo en silencio); la nota distingue este fallo del de la auditoría en el log de la operación.
                exc.add_note(f"{REJECTS_FAILURE_NOTE} ({writer.path}; fila {position} de la entrada)")
                raise
            # B-2: una línea por fila solo en DEBUG; el resumen de la operación va en WARNING.
            self.logger.debug(
                f"bulk {operation} en '{tabla_destino}': fila {position} rechazada ({type(error).__name__})"
            )

        isolator = Isolator(
            on_reject=on_reject,
            max_rejects=self._max_rejects,
            batch_errors=self._batch_errors(),
            already_rejected=0 if scope is None else scope.rejected,
        )
        self.isolator = isolator
        self._attach(isolator)
        try:
            yield operation_rows
        finally:
            self.isolator = None
            self._attach(None)
            self.rows_rejected += isolator.rejected
            if scope is not None:
                scope.row_offset += operation_rows.rows
                scope.rejected += isolator.rejected
            if isolator.rejected:
                self.logger.warning(
                    f"⚠️ bulk {operation} en '{tabla_destino}': {isolator.rejected} filas rechazadas en {writer.path}"
                )

    def rejected_so_far(self) -> int:
        """Filas rechazadas hasta ahora en la operación en curso (0 sin aislamiento)."""
        return 0 if self.isolator is None else self.isolator.rejected


__all__: list[str] = [
    "ISOLATED_ERRORS",
    "REJECTS_FAILURE_NOTE",
    "REJECT_COLUMNS",
    "IsolatedOperation",
    "Isolator",
    "RejectsCoordinator",
    "RejectsSequence",
    "RejectsWriter",
    "optional_non_negative_int",
    "validate_isolation",
]
