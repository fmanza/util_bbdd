# REQUEST

## Session metadata
- id: 2026-04-10
- fecha: 2026-04-10
- rama: develop
- skill: maturity-assessment → tech-debt → refactor → version-closure
- fase solicitada: Maturity assessment inicial, análisis de deuda técnica y eliminación completa de facades legacy

## Solicitud original saneada

1. `/maturity-assessment` sobre el repositorio `util_bbdd` en rama `develop`.
2. `/tech-debt` sobre `src/util_bbdd/_core/` y `src/util_bbdd/_foundation/` — decidir si mantener ambas, fusionar o eliminar una. Alcance: solo análisis (PLAN + AUDIT_PLAN), sin IMPLEMENT.
3. Ejecutar Phase A, B y C del plan de deuda técnica:
   - Phase A: documentar `_foundation/` en `CLAUDE.md`
   - Phase B: colapsar `validators_core.py` + mover `driver_validator.py` a `_drivers/`
   - Phase C: mover `DatabaseQueries` a `query/` y eliminar `_foundation/` íntegramente
4. `/refactor` — identificar y eliminar TODOS los facades legacy en `src/util_bbdd/`. Contratos pueden romperse; documentar antes si necesario. Usuario eligió **Opción A** (nombres canónicos, fully breaking) para `database_exceptions.py`.
5. Completar checklist de cierre de v0.6.7.

## Objetivo operativo de esta sesión

- Unificar la jerarquía de excepciones bajo `_core/exceptions.py` como única fuente de verdad.
- Eliminar el módulo `_foundation/` íntegramente (Phases A/B/C).
- Eliminar todos los facades raíz legacy: `database_exceptions.py`, `database_queries.py`, `database_type_validator.py`, `driver_validator.py`.
- Publicar excepciones canónicas desde `util_bbdd.__init__` (Option A).
- Cerrar todos los bloqueantes de v0.6.7 y dejar el release en estado `READY_TO_RELEASE`.

## Restricciones explícitas

- Opción A: aliases históricos desaparecen, consumidores externos deben actualizar. No se mantiene compatibilidad con nombres como `DatabaseConnectionError`, `DatabaseError`, etc.
- Scope refactor: solo `src/util_bbdd/`; no tocar tests de integración funcional.
- No añadir funcionalidades nuevas durante el refactor.

## Resultado esperado

- `_foundation/` eliminado del árbol de fuentes.
- `database_exceptions.py`, `database_queries.py`, `database_type_validator.py`, `driver_validator.py` eliminados del paquete raíz.
- `util_bbdd.__init__` exporta todas las excepciones canónicas.
- 21 ficheros de test actualizados con imports canónicos.
- `SourceAdapter`/`RoutineAdapter` deprecated aliases eliminados.
- ruff limpio · mypy 241 ficheros OK · pytest 1703 passed.
- `pyproject.toml`: versión `0.6.7`, keywords y classifiers completos.
- `CHANGELOG.md` con sección `[0.6.7]`.
- `.ai/architecture.md` actualizado a v0.6.7.
- Test B5 de contrato de excepciones de managers.
- `v0.6.7-release-tracking.md` en estado `READY_TO_RELEASE`.
