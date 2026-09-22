# REQUEST

## Session metadata
- id: 2026-09-22-audit-completo-remediacion
- fecha: 2026-09-22
- rama: develop
- skill: audit_code → tech_debt (remediación)
- fase solicitada: PLAN + AUDIT_PLAN (sin IMPLEMENT)

## Solicitud original saneada
1. "AUDIT_CODE — De todo el proyecto — Separa la auditoría por módulos y por capas."
2. "Aplicar un PLAN y AUDIT_PLAN de la auditoria, pregunta lo que necesites."

## Objetivo operativo de esta sesión
- Auditar los 335 archivos de `src/util_bbdd/` en 12 franjas paralelas, organizadas según la
  arquitectura por capas de `docs/architecture.md` / Regla #6 (Nivel 1 Foundation, Nivel 2
  Servicios, Nivel 3 Especialización).
- Consolidar los hallazgos de las 12 franjas en un único AUDIT_CODE con veredicto por módulo.
- Producir un PLAN + AUDIT_PLAN de remediación que cubra **todas** las condiciones emitidas por
  las 12 franjas, excluyendo explícitamente los hallazgos específicos de `metadata/redshift` y
  `metadata/snowflake` (decisión de producto aplazada, ver Restricciones).
- Estructurar la remediación como una lista de fixes independientes, priorizados, cada uno
  implementable/auditable/commiteable por separado sin mezclar módulos no relacionados.

## Restricciones explícitas
- No mezclar en un mismo commit módulos no relacionados (Conventional Commits, `.github/SHARED_INSTRUCTIONS.md`).
- Excluir de esta ronda los hallazgos propios de `metadata/redshift` y `metadata/snowflake`
  (p. ej. integración end-to-end nunca verificada contra una BD real, bug de índices Redshift,
  `fetch_routine_definition_*` ausente en ambos) — decisión de producto pendiente, no técnica.
- Esta sesión cubre solo PLAN + AUDIT_PLAN. No se ha implementado ningún fix todavía.
- El AUDIT_CODE original (12 franjas) es de solo lectura; ningún archivo de `src/` se modificó
  durante esa fase.

## Resultado esperado
- `.ai/sessions/2026-09-22-audit-completo-remediacion/00_CONTEXT_SNAPSHOT.md` con el Gate G0.
- `01_PLAN_remediacion.md` con el backlog priorizado (PLAN) y el análisis de riesgos (AUDIT_PLAN).
- Entrada añadida en `.ai/sessions/INDEX.md`.
- Decisión explícita del usuario sobre los puntos abiertos señalados en AUDIT_PLAN antes de
  iniciar IMPLEMENT en próximas sesiones.
