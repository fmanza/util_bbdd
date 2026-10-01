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

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.exc import DataError, IntegrityError

#: Errores que se aíslan. Cualquier otro (columna inexistente, permisos, sintaxis, desconexión) se propaga: no es un
#: problema de una fila y aislarlo acabaría rechazando todas.
ISOLATED_ERRORS: tuple[type[Exception], ...] = (IntegrityError, DataError)

#: Columnas del CSV de rechazos (UTF-8, separado por tabuladores, como el CSV de auditoría).
REJECT_COLUMNS: tuple[str, ...] = ("timestamp", "tabla", "operacion", "fila", "error", "valores")

# Una celda que empieza así se ejecutaría como fórmula al abrir el CSV en Excel (los valores son datos del usuario).
_FORMULA_PREFIXES: tuple[str, ...] = ("=", "+", "-", "@", "\t", "\r")


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
    """
    if getattr(getattr(connection, "dialect", None), "name", None) == "sqlite":
        driver = connection.connection.driver_connection
        if getattr(driver, "isolation_level", None) is not None and not getattr(driver, "in_transaction", True):
            driver.execute("BEGIN")
    return connection.begin_nested()


class RejectsWriter:
    """Escribe las filas rechazadas en ``path`` (lo crea con cabecera si no existe; añade si ya existe).

    El fichero contiene datos de las filas: solo se escribe cuando el usuario indica la ruta (``rejects_csv_path``).
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self, *, table: str, operation: str, position: int, error: BaseException, values: Mapping[str, Any]
    ) -> None:
        """Añade una fila rechazada: ``position`` es su posición (base 0) en la entrada de la operación."""
        new_file: bool = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t")
            if new_file:
                writer.writerow(REJECT_COLUMNS)
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    _safe_cell(table),
                    operation,
                    position,
                    _safe_cell(_error_text(error)),
                    _safe_cell(json.dumps(dict(values), default=str, ensure_ascii=False)),
                ]
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
    ) -> None:
        self._on_reject = on_reject
        self._max_rejects = max_rejects
        #: Filas rechazadas por esta instancia: las que ``on_reject`` procesó sin error.
        self.rejected: int = 0

    def run_records(
        self, connection: Any, records: Sequence[Mapping[str, Any]], send: Callable[[Any], None], *, first_row: int
    ) -> None:
        """Lote de registros (``list[dict]``)."""
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
        except ISOLATED_ERRORS:
            savepoint.rollback()
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
            savepoint.rollback()
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


__all__: list[str] = ["ISOLATED_ERRORS", "REJECT_COLUMNS", "Isolator", "RejectsWriter"]
