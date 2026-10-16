"""CSV de filas rechazadas de ``BulkCrud(rejects=RejectOptions(on_error="isolate"))``. **Formato congelado.**

Movido desde ``util_bbdd.bulk._support.rejects`` (sesión 2026-10-02c) sin cambios de comportamiento; aquel módulo lo
re-exporta y conserva el aislamiento por SAVEPOINT (``Isolator``), que es lógica de ejecución, no de auditoría.

Formato (lo fija ``tests/unit/audit/test_legacy_format.py`` contra un fichero de v0.28.0): UTF-8, tabulador, fin de
línea ``\\r\\n``, columnas :data:`REJECT_COLUMNS`; ``timestamp`` ISO 8601 al segundo (hora local); ``error``: clase y
primera línea del error; ``valores``: la fila en JSON. Las celdas de texto pasan por
:meth:`~util_bbdd.audit.text.AuditText.safe_csv_cell`.
"""

from __future__ import annotations

import csv
import json
import logging

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .files import AuditFiles
from .locks import path_lock
from .text import AuditText

#: Columnas del CSV de rechazos (UTF-8, separado por tabuladores, como el CSV de auditoría).
#: ``particion``: la de ``ParallelBulkLoader`` (vacía fuera de él); añadida tras la 0.26.0 (Fase 3, 2026-10-01t).
REJECT_COLUMNS: tuple[str, ...] = ("timestamp", "tabla", "operacion", "particion", "fila", "error", "valores")

#: Nombre del logger de siempre (el del módulo antes del traslado), para no cambiar la configuración de logging.
_LOGGER_NAME = "util_bbdd.bulk._support.rejects"


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
        self.logger: logging.Logger = logging.getLogger(_LOGGER_NAME)
        self._lock = path_lock(self.path)
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
                    AuditText.safe_csv_cell(table),
                    operation,
                    "" if partition is None else partition,
                    position,
                    AuditText.safe_csv_cell(AuditText.error_summary(error)),
                    AuditText.safe_csv_cell(json.dumps(dict(values), default=str, ensure_ascii=False)),
                ]
            )

    def _set_aside_if_foreign(self) -> None:
        """Aparta el fichero existente si su primera línea no es la cabecera de rechazos (se llama con el lock tomado).

        Si no se puede renombrar (p. ej. abierto en Excel), el ``OSError`` se propaga: la operación falla con la nota
        «no se pudo escribir el CSV de rechazos», como cualquier fallo de escritura (M-1).
        """
        if not self.path.is_file():
            return
        first: str = AuditFiles.first_line(self.path)
        if AuditFiles.has_header(first, "\t".join(REJECT_COLUMNS)):
            return
        aside: Path = AuditFiles.set_aside(self.path)
        self.logger.warning(
            f"El CSV de rechazos '{self.path}' tenía otra cabecera ({first[:120]!r}); se ha apartado como "
            f"'{aside.name}' y se empieza uno nuevo."
        )


__all__: list[str] = ["REJECT_COLUMNS", "RejectsWriter"]
