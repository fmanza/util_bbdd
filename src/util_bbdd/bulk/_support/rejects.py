"""Aislamiento de filas erróneas en las operaciones masivas (``BulkCrud(on_error="isolate")``, S-2 de 2026-10-01).

Una carga atómica se deshacía entera por una sola fila con un error de datos. Con ``on_error="isolate"`` cada lote se
envía dentro de un SAVEPOINT; si falla con un error de datos (``IntegrityError`` o ``DataError``), se vuelve al SAVEPOINT
y se reenvía por mitades, cada una en su SAVEPOINT, hasta aislar las filas que fallan. Las demás se aplican; las que
fallan se escriben en un CSV de rechazos. INSERT de 1M filas con la API final: sin filas malas 1,00–1,02×; con 10
filas malas 1,13–1,23× (PostgreSQL 1,65×, lotes de 20 000): cada fila mala reenvía unas 2 veces su lote.
"""

from __future__ import annotations

import contextlib
import csv
import json
import logging
import sqlite3

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.exc import DataError, IntegrityError

from .._audit.repository import AuditCsvRepository, _get_file_lock
from . import oracle_batch_errors

#: Errores que se aíslan. Cualquier otro (columna inexistente, permisos, sintaxis, desconexión) se propaga: no es un
#: problema de una fila y aislarlo acabaría rechazando todas.
ISOLATED_ERRORS: tuple[type[Exception], ...] = (IntegrityError, DataError)

#: Columnas del CSV de rechazos (UTF-8, separado por tabuladores, como el CSV de auditoría).
#: ``particion``: la de ``ParallelBulkLoader`` (vacía fuera de él); añadida tras la 0.26.0 (Fase 3, 2026-10-01t).
REJECT_COLUMNS: tuple[str, ...] = ("timestamp", "tabla", "operacion", "particion", "fila", "error", "valores")

# Una celda que empieza así se ejecutaría como fórmula al abrir el CSV en Excel (los valores son datos del usuario).
_FORMULA_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")


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
    if max_rejects is not None and (
        isinstance(max_rejects, bool) or not isinstance(max_rejects, int) or max_rejects < 0
    ):
        raise ValueError(f"max_rejects debe ser None o un entero ≥ 0, recibido: {max_rejects!r}")


def _safe_cell(text: str) -> str:
    """``text`` con un apóstrofo delante si empieza como una fórmula de hoja de cálculo."""
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def _error_text(error: BaseException) -> str:
    """Clase y primera línea del error del driver (sin la sentencia ni los parámetros que añade SQLAlchemy)."""
    origin: BaseException = getattr(error, "orig", None) or error
    lines = str(origin).strip().splitlines()
    return f"{type(error).__name__}: {lines[0] if lines else ''}"


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


class RejectsWriter:
    """Escribe las filas rechazadas en ``path`` (lo crea con cabecera si no existe; añade si ya existe).

    El fichero contiene datos de las filas: solo se escribe cuando el usuario indica la ruta (``rejects_csv_path``).

    B-4 (audit-code 2026-10-01): las escrituras a una misma ruta se serializan con el lock por ruta de la auditoría
    (entre hilos de un proceso; entre procesos no hay lock, como en la auditoría), y antes de la primera escritura de la
    instancia un fichero con otra cabecera se aparta como ``<nombre>.invalid-<fecha><ext>`` con un WARNING.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._lock = _get_file_lock(self.path)
        self._header_checked: bool = False

    def write(
        self,
        *,
        table: str,
        operation: str,
        position: int,
        error: BaseException,
        values: Mapping[str, Any],
        partition: int | None = None,
    ) -> None:
        """Añade una fila rechazada: ``position`` es su posición (base 0) en la entrada de la operación (o de la
        partición de ``ParallelBulkLoader``, ``partition``)."""
        with self._lock:
            if not self._header_checked:
                self._set_aside_if_foreign()
                self._header_checked = True
            self._append(
                table=table, operation=operation, position=position, error=error, values=values, partition=partition
            )

    def _append(
        self,
        *,
        table: str,
        operation: str,
        position: int,
        error: BaseException,
        values: Mapping[str, Any],
        partition: int | None,
    ) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t")
            # En modo "a" el fichero se abre al final: posición 0 = nuevo o vacío (como la auditoría, H4).
            if handle.tell() == 0:
                writer.writerow(REJECT_COLUMNS)
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    _safe_cell(table),
                    operation,
                    "" if partition is None else partition,
                    position,
                    _safe_cell(_error_text(error)),
                    _safe_cell(json.dumps(dict(values), default=str, ensure_ascii=False)),
                ]
            )

    def _set_aside_if_foreign(self) -> None:
        """Aparta el fichero existente si su primera línea no es la cabecera de rechazos (se llama con el lock tomado).

        Si no se puede renombrar (p. ej. abierto en Excel), el ``OSError`` se propaga: la operación falla con la nota
        «no se pudo escribir el CSV de rechazos», como cualquier fallo de escritura (M-1).
        """
        if not self.path.is_file():
            return
        try:
            with self.path.open(encoding="utf-8", newline="") as handle:
                first: str = handle.readline()
        except UnicodeDecodeError:
            first = "<no es texto UTF-8>"
        if not first or first.lstrip("\ufeff").rstrip("\r\n") == "\t".join(REJECT_COLUMNS):
            return
        aside: Path = AuditCsvRepository._ruta_apartado(self.path)
        self.path.rename(aside)
        self.logger.warning(
            f"El CSV de rechazos '{self.path}' tenía otra cabecera ({first[:120]!r}); se ha apartado como "
            f"'{aside.name}' y se empieza uno nuevo."
        )


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
    ) -> None:
        self._on_reject = on_reject
        self._max_rejects = max_rejects
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
        budget: int | None = None if self._max_rejects is None else self._max_rejects - self.rejected
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
        if self._max_rejects is not None and self.rejected >= self._max_rejects:
            error.add_note(
                f"bulk: la fila {position} de la entrada habría superado max_rejects={self._max_rejects}; "
                "la operación falla como sin on_error='isolate'"
            )
            raise error
        self._on_reject(position, values, error)
        self.rejected += 1  # M-1: solo filas entregadas (escritas): si on_reject falla, no cuenta


__all__: list[str] = ["ISOLATED_ERRORS", "REJECT_COLUMNS", "Isolator", "RejectsWriter", "validate_isolation"]
