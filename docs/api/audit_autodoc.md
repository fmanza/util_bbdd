# Auditoría

`util_bbdd.audit` es el punto común de la auditoría de `bulk`, `dump` y `migrate` (ADR-002): eventos `AuditEvent` que se
escriben en un `AuditSink`. Referencia curada: [Auditoría centralizada](audit.md).

---

## AuditEvent

::: util_bbdd.audit.events.AuditEvent
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"

---

## Contratos y destinos

::: util_bbdd.audit.contracts.AuditSink
    options:
      show_source: false
      heading_level: 3

::: util_bbdd.audit.sinks.JsonLinesAuditSink
    options:
      show_source: false
      heading_level: 3

::: util_bbdd.audit.sinks.MemoryAuditSink
    options:
      show_source: false
      heading_level: 3

::: util_bbdd.audit.sinks.NullAuditSink
    options:
      show_source: false
      heading_level: 3
