"""Destinos de eventos de auditoría (:class:`~util_bbdd.audit.contracts.AuditSink`)."""

from __future__ import annotations

import json
import logging
import threading

from collections.abc import Sequence
from pathlib import Path

from .events import AuditEvent
from .files import AuditFiles
from .locks import path_lock


class _ClosableSink:
    """Estado de cierre común: ``close`` idempotente y ``ValueError`` al escribir tras cerrar."""

    def __init__(self) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._lock: threading.Lock = threading.Lock()
        self._closed: bool = False

    @property
    def closed(self) -> bool:
        """``True`` después de :meth:`close`."""
        return self._closed

    def close(self) -> None:
        """Cierra el destino; llamarlo otra vez no hace nada."""
        with self._lock:
            self._closed = True

    def _check_open(self) -> None:
        if self._closed:
            raise ValueError(f"{type(self).__name__} está cerrado")


class NullAuditSink(_ClosableSink):
    """Destino que descarta los eventos (auditoría deshabilitada).

    Example:
        >>> sink = NullAuditSink()
        >>> sink.write([])
    """

    def write(self, _events: Sequence[AuditEvent], /) -> None:
        """Descarta los eventos (posicional, como exige :class:`~util_bbdd.audit.contracts.AuditSink`)."""
        with self._lock:
            self._check_open()


class MemoryAuditSink(_ClosableSink):
    """Destino que guarda los eventos en memoria; también es :class:`~util_bbdd.audit.contracts.AuditEventSource`.

    Pensado para tests y para inspeccionar una ejecución corta sin escribir ficheros.

    Example:
        >>> sink = MemoryAuditSink()
        >>> sink.write([AuditEvent.now(source="bulk", kind="operation", status="ok", rows=10)])
        >>> [event.rows for event in sink.events()]
        [10]
    """

    def __init__(self) -> None:
        super().__init__()
        self._events: list[AuditEvent] = []

    def write(self, events: Sequence[AuditEvent], /) -> None:
        """Añade ``events`` a la lista en memoria."""
        with self._lock:
            self._check_open()
            self._events.extend(events)

    def events(self) -> Sequence[AuditEvent]:
        """Copia de los eventos escritos, en orden de escritura."""
        with self._lock:
            return tuple(self._events)


class JsonLinesAuditSink(_ClosableSink):
    """Destino en fichero JSON Lines: una línea JSON por evento (H-04, sesión 2026-10-02c).

    A diferencia del CSV heredado de ``bulk``: ``timestamp`` en ISO 8601 con zona horaria, números con punto decimal,
    todos los campos de :class:`AuditEvent` (``run_id``, ``attributes``…) y eventos de ``bulk``, ``dump`` y ``migrate``
    en el mismo fichero. Se abre en modo añadir; varias instancias (o hilos) sobre la misma ruta comparten el lock por
    ruta de :mod:`util_bbdd.audit.locks`, y las líneas de una llamada a :meth:`write` no se intercalan con otras (en
    un mismo proceso). Si el fichero existe y su primera línea no es un evento JSON, se aparta como
    ``<nombre>.invalid-<fecha><ext>`` con un WARNING y se empieza uno nuevo. La rotación queda a cargo de quien lo usa.

    El fichero puede contener datos: ``message`` lleva el texto de los errores, que en un ``IntegrityError`` incluye
    valores de clave.

    Args:
        path: Fichero de destino (se crea su directorio).

    Example:
        >>> sink = JsonLinesAuditSink(Path("auditoria.jsonl"))  # doctest: +SKIP
        >>> crud = BulkCrud(engine, audit=AuditOptions(sink=sink))  # doctest: +SKIP
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path: Path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file_lock: threading.Lock = path_lock(self.path)
        self._checked: bool = False

    def write(self, events: Sequence[AuditEvent], /) -> None:
        """Añade ``events`` al fichero, una línea por evento."""
        with self._lock:
            self._check_open()
            if not events:
                return
            lines = "".join(f"{json.dumps(event.as_dict(), ensure_ascii=False, default=str)}\n" for event in events)
            with self._file_lock:
                if not self._checked:
                    self._set_aside_if_foreign()
                    self._checked = True
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(lines)

    def _set_aside_if_foreign(self) -> None:
        if not self.path.is_file():
            return
        first = AuditFiles.first_line(self.path).strip()
        if not first or self._is_event_line(first):
            return
        aside = AuditFiles.set_aside(self.path)
        self.logger.warning(
            f"El fichero de auditoría JSON Lines '{self.path}' no contenía eventos ({first[:120]!r}); se ha apartado "
            f"como '{aside.name}' y se empieza uno nuevo."
        )

    @staticmethod
    def _is_event_line(line: str) -> bool:
        try:
            data = json.loads(line)
        except ValueError:
            return False
        return isinstance(data, dict) and {"source", "kind", "status", "timestamp"} <= data.keys()


__all__: list[str] = ["JsonLinesAuditSink", "MemoryAuditSink", "NullAuditSink"]
