# REQUEST

## Session metadata
- id: 2026-10-02c-audit-module
- fecha: 2026-10-02
- rama: develop
- skill: new_feature (con `.github/prompts/audit_module.prompt.md`, que manda sobre `new_feature`)
- fase solicitada: PLAN + AUDIT_PLAN (valor por defecto del prompt; no se pidieron otras fases)

## Solicitud original saneada
`/new-feature .github\prompts\audit_module.prompt.md`

Origen: «Se necesita crear un módulo nuevo de auditoría para el proyecto que la centralice; el módulo
debe recoger como mínimo lo definido actualmente en el proyecto, especialmente en los módulos
`src\util_bbdd\bulk`, `src\util_bbdd\dump`, `src\util_bbdd\migrate`, pero solo ellos.»

## Objetivo operativo de esta sesión
- Emitir PLAN con la matriz de cobertura de todos los `INV-*` de `.ai/audit/audit_module_baseline_inventory.md`.
- Decidir cada hueco `H-01`…`H-07`.
- Proponer la estructura, la capa, los contratos y un plan de fases incremental, más un borrador de ADR.
- Emitir AUDIT_PLAN con veredicto.

## Restricciones explícitas
- No se toca código (`src/`, `tests/`) en esta sesión.
- Consumidores: solo `bulk/`, `dump/` y `migrate/`.
- Sin dependencias nuevas, sin breaking changes, el CSV actual idéntico byte a byte.

## Resultado esperado
- `.ai/sessions/2026-10-02c-audit-module/01_PLAN_AUDIT_PLAN.md`
- `TRACEABILITY.md` de la sesión y su fila en `.ai/sessions/INDEX.md`
