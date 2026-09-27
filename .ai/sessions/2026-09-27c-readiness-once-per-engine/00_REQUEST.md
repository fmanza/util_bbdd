# REQUEST

## Session metadata
- id: 2026-09-27c-readiness-once-per-engine
- fecha: 2026-09-27
- rama: develop
- skill: hotfix
- fase solicitada: PLAN + AUDIT_PLAN (sin IMPLEMENT)

## Solicitud original saneada
En la verificación de condiciones por motor, esta se debe hacer una sola vez. Se detecta que cuando
obtiene una conexión por el pool vuelve a hacer la comprobación. Revisar la arquitectura para
identificar si la implementación actual es la correcta para esta acción. Revisar `.ai` y
`src/util_bbdd/connection`.

## Objetivo operativo de esta sesión
- Diagnosticar la causa raíz de la verificación repetida (`EngineReadinessAdvisor`).
- Emitir PLAN de fix mínimo: una sola verificación por `Engine`, thread-safe.
- Emitir AUDIT_PLAN con veredicto GO | GO_CONDICIONAL | NO_GO.

## Restricciones explícitas
- Política `/hotfix`: fix mínimo, sin refactor ni optimización. **Ampliada por petición expresa del
  usuario** (PLAN v2): se incluye el traslado de `conn_params` de `bulk/` a `connection/`.
- Solo PLAN y AUDIT_PLAN; no se edita código hasta aprobación.
- El usuario trabaja en paralelo: no usar `git add -A`.

## Resultado esperado
- `.ai/sessions/2026-09-27c-readiness-once-per-engine/01_PLAN.md` (PLAN + AUDIT_PLAN).
- `TRACEABILITY.md` de la sesión.
