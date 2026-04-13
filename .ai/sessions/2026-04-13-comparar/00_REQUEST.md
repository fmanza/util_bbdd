# REQUEST

## Session metadata
- id: 2026-04-13-comparar
- fecha: 2026-04-13
- rama: develop
- skill: tech-debt
- fase solicitada: PLAN + AUDIT_CODE (sin IMPLEMENT)

## Solicitud original saneada

Inventario de deuda técnica en `src/util_bbdd/comparar/`.
Deuda conocida: no contempla todos los motores definidos en `connection/params.py` y `_BUILD_SUPPORTED_TYPES`.
Scope: solo análisis (PLAN + AUDIT_CODE), sin IMPLEMENT por ahora.
Política de compatibilidad: se autoriza romper contratos públicos.
Prerequisitos: leer `.ai/architecture.md` y `.ai/sessions/INDEX.md` antes de analizar.
Requisito de sesión: documentar siguiendo `.ai/sessions/INDEX.md`.

## Objetivo operativo de esta sesión

- Mapear todos los motores soportados (`_BUILD_SUPPORTED_TYPES`) vs. cobertura real del módulo `comparar/`.
- Identificar gaps en `_ROUTINE_FETCHERS`, `_DDL_STRIP_RULES` y abstracción de dialects.
- Clasificar deuda por prioridad (quick_win / fase_media / deuda_estructural).
- Emitir plan por fases con orden de dependencias.
- Emitir veredicto: LIMPIO | DEUDA_MENOR | DEUDA_SIGNIFICATIVA | CRÍTICO.

## Restricciones explícitas

- Solo análisis: PLAN + AUDIT_CODE. Sin IMPLEMENT.
- Se autoriza proponer breaking changes en contratos públicos.
- Leer `.ai/architecture.md` y `.ai/sessions/INDEX.md` como prerequisito.

## Resultado esperado

- Informe AUDIT_CODE con hallazgos a nivel archivo:línea, clasificados y con plan por fases.
- Carpeta `.ai/sessions/2026-04-13-comparar/` con artefactos mínimos.
- Entrada en `.ai/sessions/INDEX.md`.
