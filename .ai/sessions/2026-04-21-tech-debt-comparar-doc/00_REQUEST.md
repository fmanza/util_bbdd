# 00_REQUEST — Tech Debt: comparar/ + doc/

**Fecha:** 2026-04-21
**Rama:** develop
**Skill:** tech-debt
**Scope:** Solo análisis (PLAN → AUDIT_PLAN → AUDIT_CODE). Sin IMPLEMENT por ahora.
**Política de compatibilidad:** Se autoriza romper contratos públicos.

## Solicitud saneada

Identificar deuda técnica en `src/util_bbdd/comparar/` y `src/util_bbdd/doc/` a partir de los cambios acumulados hasta v0.8.0.

## Módulos objetivo

- `src/util_bbdd/comparar/` (comparator, models, contracts, reporters/)
- `src/util_bbdd/doc/` (database_documentation, application/ports, infrastructure/)

## Contexto de entrada

- Release v0.8.0 completa cobertura de tipo de sistema (8 motores)
- `comparar/` creció orgánicamente desde v0.6.7 con 12+ sesiones new_feature/refactor
- `doc/` mantiene arquitectura hexagonal desde v0.6.x sin revisión post-v0.6.7

## Fuentes leídas

- `docs/v0.8.0/RELEASE_v0.8.0.md`
- `.ai/architecture.md`
- `.ai/sessions/INDEX.md`
- Todos los archivos `.py` de ambos módulos

## Restricciones

- Sin implementar cambios
- Documentar en `.ai/sessions/2026-04-21-tech-debt-comparar-doc/`
- Documentar en `docs/v0.8.1/`
