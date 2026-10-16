"""Modelo de evento común de la auditoría de ``bulk``, ``dump`` y ``migrate`` (H-01, sesión 2026-10-02c).

Cada módulo de origen describe lo que ocurrió con sus propios tipos (``PartitionResult``, ``TableDumpResult``,
``MigrationWarning``…). Para que un mismo destino (:class:`~util_bbdd.audit.contracts.AuditSink`) pueda guardarlos y
compararlos, el módulo de origen los convierte en :class:`AuditEvent`. Este paquete no conoce a sus consumidores
(Regla #6): la conversión vive en cada uno (``bulk/_audit/events.py``, ``dump/_audit_events.py``,
``migrate/_audit_events.py``).

Equivalencia con las convenciones semánticas de OpenTelemetry para bases de datos (sin depender de su SDK):

============== ==========================
``engine``     ``db.system.name``
``namespace``  ``db.namespace``
``target``     ``db.collection.name``
``operation``  ``db.operation.name``
``error_type`` ``error.type``
============== ==========================

``rows`` **no** equivale a ``db.response.returned_rows``: en ``bulk`` son las filas *enviadas* a la operación, como en el
CSV de auditoría. El texto SQL no se registra.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Literal

#: Módulo que emite el evento.
AuditSource = Literal["bulk", "dump", "migrate"]

#: Resultado del hecho auditado. ``info``/``warning``/``error`` son avisos (p. ej. de un plan de migración), no
#: operaciones: ``error`` es un aviso de severidad ERROR, ``failed`` una operación que falló.
AuditStatus = Literal["ok", "failed", "skipped", "info", "warning", "error"]

#: Qué se audita.
#:
#: - ``operation``: una operación de ``BulkCrud`` (INSERT, UPDATE o DELETE), cuando su transacción se confirma.
#: - ``partition``: una partición de ``ParallelBulkLoader`` (con sus ``rows_rejected``: las filas rechazadas no generan
#:   un evento cada una; sus valores solo van al CSV de rechazos).
#: - ``run``: cierre de un volcado, de una carga paralela o de la ejecución de un plan de migración.
#: - ``table``, ``constraint``, ``index``, ``pk_sync``: resultados por elemento de un volcado.
#: - ``plan_warning``: aviso de un plan de migración.
#: - ``statement``: una sentencia DDL ejecutada por ``MigrationPlan.execute``.
#: - ``view_validation``: validación de una vista en el destino.
AuditKind = Literal[
    "operation",
    "partition",
    "run",
    "table",
    "constraint",
    "index",
    "pk_sync",
    "plan_warning",
    "statement",
    "view_validation",
]

#: Valor admitido en :attr:`AuditEvent.attributes`.
AttributeValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Un hecho auditado, inmutable y comparable entre módulos.

    Attributes:
        source: Módulo que lo emite (``bulk``, ``dump`` o ``migrate``).
        kind: Qué se audita (ver :data:`AuditKind`).
        status: Resultado (ver :data:`AuditStatus`).
        timestamp: Momento en que terminó el hecho, con zona horaria (``__post_init__`` rechaza uno sin zona).
        engine: Motor de base de datos (``postgresql``, ``oracle``…).
        namespace: Esquema o base de datos.
        target: Tabla, vista, constraint, índice u otro objeto afectado.
        operation: Operación (``INSERT``, ``UPDATE``, ``DELETE``, ``CREATE TABLE``, ``ENABLE``…).
        rows: Filas afectadas; en ``bulk``, filas *enviadas* (como el CSV de auditoría).
        elapsed_s: Duración en segundos.
        error_type: Clase del error (``IntegrityError``…) si lo hubo.
        message: Texto libre en una línea, truncado a :attr:`MAX_MESSAGE` caracteres. Puede contener datos (los
            mensajes de ``IntegrityError`` incluyen valores de clave): solo lo guardan los destinos que el usuario
            configura de forma explícita.
        run_id: Identificador de la ejecución a la que pertenece. Todos los eventos de un volcado (también los de sus
            ``BulkCrud`` y cargas paralelas) comparten el ``run_id`` del volcado; los de una carga paralela, el suyo.
        parent_id: Identificador de una ejecución que contiene a ``run_id``. La librería no lo rellena hoy (las
            ejecuciones anidadas heredan el ``run_id`` de la de fuera); queda para quien emita sus propios eventos.
        attributes: Datos adicionales como pares ``(nombre, valor)`` ordenados por nombre: inmutable y hashable.

    Examples:
        >>> event = AuditEvent.now(source="bulk", kind="operation", status="ok", engine="sqlite",
        ...                        target="clientes", operation="INSERT", rows=1000, elapsed_s=0.42)
        >>> event.attribute("batch_size") is None
        True
    """

    #: Longitud máxima de :attr:`message`.
    MAX_MESSAGE: ClassVar[int] = 500

    source: AuditSource
    kind: AuditKind
    status: AuditStatus
    timestamp: datetime
    engine: str | None = None
    namespace: str | None = None
    target: str | None = None
    operation: str | None = None
    rows: int | None = None
    elapsed_s: float | None = None
    error_type: str | None = None
    message: str | None = None
    run_id: str | None = None
    parent_id: str | None = None
    attributes: tuple[tuple[str, AttributeValue], ...] = ()

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError(f"AuditEvent.timestamp necesita zona horaria, recibido: {self.timestamp!r}")
        if self.rows is not None and self.rows < 0:
            raise ValueError(f"AuditEvent.rows debe ser ≥ 0, recibido: {self.rows}")
        if self.elapsed_s is not None and self.elapsed_s < 0:
            raise ValueError(f"AuditEvent.elapsed_s debe ser ≥ 0, recibido: {self.elapsed_s}")
        if self.message is not None:
            object.__setattr__(self, "message", self.one_line(self.message, self.MAX_MESSAGE))
        names = [name for name, _ in self.attributes]
        if len(set(names)) != len(names):
            raise ValueError(f"AuditEvent.attributes tiene nombres repetidos: {names}")
        object.__setattr__(self, "attributes", tuple(sorted(self.attributes)))

    @classmethod
    def now(
        cls,
        *,
        source: AuditSource,
        kind: AuditKind,
        status: AuditStatus,
        attributes: Mapping[str, AttributeValue] | None = None,
        **fields: str | int | float | None,
    ) -> AuditEvent:
        """Evento con ``timestamp`` = ahora en UTC y ``attributes`` desde un diccionario."""
        return cls(
            source=source,
            kind=kind,
            status=status,
            timestamp=datetime.now(UTC),
            attributes=tuple((attributes or {}).items()),
            **fields,  # type: ignore[arg-type]
        )

    def attribute(self, name: str) -> AttributeValue:
        """Valor del atributo ``name`` o ``None`` si no está."""
        for key, value in self.attributes:
            if key == name:
                return value
        return None

    def as_dict(self) -> dict[str, AttributeValue | dict[str, AttributeValue]]:
        """Campos del evento como diccionario serializable (``timestamp`` en ISO 8601 con zona)."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "kind": self.kind,
            "status": self.status,
            "engine": self.engine,
            "namespace": self.namespace,
            "target": self.target,
            "operation": self.operation,
            "rows": self.rows,
            "elapsed_s": self.elapsed_s,
            "error_type": self.error_type,
            "message": self.message,
            "run_id": self.run_id,
            "parent_id": self.parent_id,
            "attributes": dict(self.attributes),
        }

    @staticmethod
    def one_line(text: str, limit: int) -> str:
        """``text`` sin saltos de línea ni tabuladores (OWASP: inyección en logs) y truncado a ``limit`` caracteres."""
        flat = " ".join(text.replace("\t", " ").split())
        return flat if len(flat) <= limit else f"{flat[: limit - 1]}…"


__all__: list[str] = ["AttributeValue", "AuditEvent", "AuditKind", "AuditSource", "AuditStatus"]
