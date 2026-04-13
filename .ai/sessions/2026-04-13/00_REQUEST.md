# REQUEST

## Session metadata
- id: 2026-04-13
- fecha: 2026-04-13
- rama: develop
- skill: audit-code
- fase solicitada: PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION

## Solicitud original saneada

Auditoría técnica de `src/util_bbdd/_core/` y `src/util_bbdd/core/`.
Contexto: identificar el motivo por el que existen dos módulos "core".
Prerequisitos declarados: leer `.ai/architecture.md` y `.ai/sessions/INDEX.md` antes de proponer cambios.
Requisito de sesión: documentar la sesión siguiendo `.ai/sessions/INDEX.md`.

## Objetivo operativo de esta sesión

- Determinar si `_core/` y `core/` tienen responsabilidades distintas o son duplicados.
- Identificar cualquier divergencia funcional o de contrato entre ambos módulos.
- Emitir veredicto (APROBADO / APROBADO CON CONDICIONES / RECHAZADO) con evidencias a nivel de archivo:línea.
- Documentar el fix recomendado con commit message y pruebas sugeridas.

## Restricciones explícitas

- Leer `.ai/architecture.md` antes de proponer cambios.
- Leer `.ai/sessions/INDEX.md` para contexto de decisiones previas.
- Documentar la sesión al cierre.

## Resultado esperado

- Informe AUDIT_CODE con veredicto y hallazgos concretos (archivo:línea).
- Carpeta `.ai/sessions/2026-04-13/` con los tres artefactos mínimos de trazabilidad.
- Entrada añadida en `.ai/sessions/INDEX.md`.
