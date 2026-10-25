# TRACEABILITY

## Session metadata
- id: 2026-10-25-web-gaps-plan
- fecha: 2026-10-25
- rama: claude/practical-ride-44fot0
- skill: new_feature
- fase: PLAN + AUDIT_PLAN (sin IMPLEMENT)

## Prompt issued
Plan por tipo de ejecución (incluida la carga) para resolver en util_bbdd los huecos de
`docs/plan/UTIL_BBDD_GAPS.md` de util_bbdd_web, con orden de ejecución simultáneo de los dos repositorios, un commit
por fase, AUDIT_PLAN e instrucciones de ejecución.

## Context supplied
- `util_bbdd_web/docs/plan/UTIL_BBDD_GAPS.md` (G1-G41), analizado sobre util_bbdd 4.0.0.
- Este repositorio en 4.0.1: rutas de cada hueco verificadas con `grep` en `src/util_bbdd/`.

## AI output summary
- Sin cambios de código. Resumen de las fases `U-` en `PLAN.md`; plan completo en util_bbdd_web.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Resumen de fases `U-` | `.ai/sessions/2026-10-25-web-gaps-plan/PLAN.md` | emitido |

## Directrices para Futuras IAs
- **[web]**: util_bbdd_web consume este paquete por el wheel adjunto a la release de GitHub (URL + hash en su
  `uv.lock`); una release sin wheel bloquea a la web.
- **[semver]**: G30 (`DumpConfig.truncate_target`, `dump/_models.py`) y G35 (`generar_sql`, `bulk/crud.py`) son
  cambios de valor por defecto: en 4.x solo `FutureWarning`.
- **[progreso]**: el contrato de progreso y cancelación (G1) se propone en `audit/progress.py` para no añadir un
  paquete de primer nivel ni cambiar el diagrama de capas.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- Aprobación de las decisiones D1-D5 del plan canónico.
