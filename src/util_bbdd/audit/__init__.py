"""Módulo audit: punto canónico de la auditoría de ``bulk``, ``dump`` y ``migrate``.

Capa 3 (Regla #6): solo importa de ``_core``. Los módulos que lo usan convierten sus propios tipos en
:class:`AuditEvent` (este paquete no los conoce).

- events.py - ``AuditEvent``: modelo de evento común
- contracts.py - ``AuditSink`` (escritura) y ``AuditEventSource`` (lectura)
- sinks.py - ``NullAuditSink``, ``MemoryAuditSink`` y ``JsonLinesAuditSink``
"""

from .contracts import AuditEventSource, AuditSink
from .events import AttributeValue, AuditEvent, AuditKind, AuditSource, AuditStatus
from .sinks import JsonLinesAuditSink, MemoryAuditSink, NullAuditSink

__all__: list[str] = [
    # Modelo
    "AttributeValue",
    "AuditEvent",
    "AuditKind",
    "AuditSource",
    "AuditStatus",
    # Contratos
    "AuditEventSource",
    "AuditSink",
    # Destinos
    "JsonLinesAuditSink",
    "MemoryAuditSink",
    "NullAuditSink",
]
