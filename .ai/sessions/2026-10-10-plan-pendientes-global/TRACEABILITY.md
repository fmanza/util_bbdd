# TRACEABILITY

## Session metadata
- id: 2026-10-10-plan-pendientes-global
- fecha: 2026-10-10
- rama: develop
- skill: PLAN + AUDIT_PLAN (todo lo pendiente)
- fase: PLAN + AUDIT_PLAN (solo lectura)

## Prompt issued
```text
PLAN y ADUIT_PLAN de todo lo pendiente
```

## Context supplied
- `.ai/CURRENT_STATE.md`, `docs/roadmap.md`, `TRACEABILITY.md` de 2026-10-05 a 2026-10-10, sesiones
  `2026-10-03-metadata-centralization`, `2026-10-04-api-single-entry-point-audit` y `2026-10-01l-plan-bulk-pending`.
- Banco docker para las sondas de H1 y H2.

## AI output summary
- Inventario de 15 pendientes; 6 descartados por resueltos.
- H1 confirmado con sondas: PostgreSQL `idle in transaction` y MySQL sin ver una tabla nueva tras `clear_cache()`
  (`use_pool=False`).
- H2 no reproducido (directo sobre `SnapshotCache` y vía `AsyncDatabaseManager`).
- Plan Q0–Q6 con decisiones D1–D5.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-10-plan-pendientes-global/PLAN_AUDIT_PLAN.md` | emitido |

## Directrices para Futuras IAs
- **[metadata/transacciones]**: `managers/_catalog_executor.py` solo hace `rollback` cuando la lectura falla; con
  `use_pool=False` la conexión queda en transacción. En MySQL eso congela el catálogo (REPEATABLE READ): una tabla creada
  desde fuera no aparece tras `clear_cache()`. Con pool no pasa (reset al devolver).
- **[metadata/async]**: `SnapshotCache.aget_or_load` funciona en dos `asyncio.run` seguidos con contención;
  `invalidate` parece descartar el lock de la clave.
- **[sondas async]**: un `AsyncDatabaseManager` con aiosqlite que no se cierra deja vivo el hilo del driver y el proceso
  no termina; cerrar siempre el manager en las sondas.
- **[herramientas]**: aquí no hay `gh`: el estado del CI y de las PR de GitHub no se puede comprobar desde la sesión.

## Veredicto final
Veredicto: GO_CONDICIONAL (AUDIT_PLAN)
Pendientes al cierre:
- Decisiones D1–D5 del usuario antes de IMPLEMENT.
