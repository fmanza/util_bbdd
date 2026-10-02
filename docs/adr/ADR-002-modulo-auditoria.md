# ADR-002: Módulo de auditoría centralizado (`util_bbdd.audit`)

## 1. Contexto y Problema

Hasta v0.28.0 la auditoría estaba repartida y acoplada a `bulk`:

- El CSV de auditoría (`AuditManager` y su repositorio, analítica y exportadores) vivía en `bulk/_audit/`, y el CSV de filas rechazadas en `bulk/_support/rejects.py`. Este último importaba partes privadas de la auditoría (`_get_file_lock`, `AuditCsvRepository._ruta_apartado`).
- `dump` leía el CSV para su resumen importando partes privadas de `bulk` (`AuditCsvRepository`, `bulk._audit.counters`).
- `migrate` no dejaba rastro persistente: `MigrationPlan.execute` no registraba qué sentencias había aplicado.
- Cada módulo describía lo ocurrido con tipos distintos (`AuditRecord`, `PartitionResult`, `TableDumpResult`, `MigrationWarning`), sin un identificador para relacionarlos con su ejecución.

Restricciones: el formato del CSV es un contrato de facto (lo leen informes y el propio `dump`). No se admiten cambios incompatibles ni dependencias nuevas. Y la Regla #6 manda que un paquete solo importe de capas inferiores: `bulk` y `migrate` están en la capa 6, y `dump` en la 7.

## 2. Decisión

Crear el paquete `util_bbdd.audit` en la **capa 3** (Servicios), que solo importa de `_core`:

1. **Modelo de evento común** `AuditEvent`, inmutable y con zona horaria, cuyos campos equivalen a las convenciones semánticas de OpenTelemetry para bases de datos, sin depender de su SDK. Un **contrato de destino** (`AuditSink`, `Protocol`) y tres implementaciones: `JsonLinesAuditSink`, `MemoryAuditSink` y `NullAuditSink`.
2. **El CSV heredado y el de rechazos se mueven sin cambios** a `audit/legacy_csv.py` y `audit/rejects.py`, con su formato congelado. Un test los compara byte a byte con ficheros generados con v0.28.0. `AuditManager` se queda en `bulk/audit.py` como fachada, y `bulk/_audit/*` re-exporta para no romper imports.
3. **El paquete no conoce a sus consumidores**: cada uno convierte sus tipos en eventos con un adaptador propio (`bulk/_audit/events.py`, `dump/_audit_events.py`, `migrate/_audit_events.py`).
4. **Las capacidades nuevas son opcionales**: el parámetro `audit_sink` en `BulkCrud`, `ParallelBulkLoader`, `DumpConfig`, `MigrationPlan.execute` y `MigrationPlan.validate_views`. Sin él, el comportamiento es el de v0.28.0.
5. **Mismas reglas que el CSV**: en `bulk` el evento se escribe en el mismo punto que la fila del CSV (al confirmarse la transacción) y con la misma política `audit_strict`. Los eventos de cierre (cargas, volcados, migraciones) nunca interrumpen la operación.

## 3. Consecuencias

| Tipo | Descripción |
|---|---|
| Ventaja | Un punto canónico; `dump` y los rechazos ya no importan partes privadas de la auditoría de `bulk` |
| Ventaja | `migrate` es auditable (sentencias, avisos, validación de vistas) |
| Ventaja | Eventos comparables entre módulos y relacionados por `run_id` en un mismo fichero |
| Compromiso | Dos formatos conviven: el CSV heredado (congelado) y los eventos |
| Compromiso | Cambiaron tres tests: dos `patch` a rutas privadas que se movieron y la comprobación de la firma de `MigrationPlan.execute`, que ahora admite `audit_sink` |
| Deuda técnica | Los re-exportadores de `bulk/_audit/*` se mantienen hasta una versión mayor |
| Deuda técnica | `dump/_models.py` sigue importando `validate_isolation` y `validate_chunk_size` de partes privadas de `bulk` (fuera de alcance: no son auditoría) |
| Riesgo aceptado | Locks solo dentro del proceso: varios procesos sobre el mismo fichero pueden intercalar líneas (H-05) |
| Riesgo aceptado | El CSV heredado no neutraliza fórmulas en `tabla`: hacerlo cambiaría su formato |

## 4. Alternativas Consideradas

| Alternativa | Pros | Contras | Motivo de rechazo |
|---|---|---|---|
| Dejar la auditoría en `bulk` y que `migrate` la importe | Sin traslado de código | `bulk` y `migrate` están en la misma capa (6) | Lo prohíbe la Regla #6 |
| Sustituir el CSV por eventos | Un solo formato | Rompe el formato y el resumen de `dump` | Cambio incompatible |
| Adoptar el SDK de OpenTelemetry | Estándar, exportadores listos | Dependencia nueva; destinos externos fuera de alcance | Restricción de dependencias |
| Paquete en la capa 5 | También sirve a `bulk`, `dump` y `migrate` | Impediría auditar desde `executors`, `factory` o `metadata` sin moverlo | La capa 3 no tiene ese límite y no cuesta nada |

## 5. Estado y Revisión

**Estado:** ACEPTADO

Propuesto en el PLAN de la sesión `.ai/sessions/2026-10-02c-audit-module/` (veredicto GO_CONDICIONAL; condiciones C1–C5 aceptadas por el usuario) e implementado en las fases F0–F5 de la misma sesión.

Fecha de última revisión: 2026-10-02
