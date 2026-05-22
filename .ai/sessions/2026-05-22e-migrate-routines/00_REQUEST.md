# REQUEST

## Session metadata
- id: 2026-05-22e-migrate-routines
- fecha: 2026-05-22
- rama: develop
- skill: new_feature
- fase solicitada: IMPLEMENT (Bloques 0–7) + tests

## Solicitud original saneada

Implementar soporte de stored procedures y functions en el módulo `migrate/`
siguiendo el patrón `CanonicalView`. Los bloques de trabajo eran:

- Bloque 0: SQL helpers en `metadata/*/` para body de rutinas
- Bloque 1: modelo `CanonicalRoutine` + `MigrationPlan.routines`
- Bloque 2: protocolos extractors/emitters/transformers
- Bloque 3: `BaseTransformer.transform_routines()` pass-through v1
- Bloque 4: `extract_routines()` en 4 extractores (Oracle, MariaDB, PostgreSQL, SQL Server)
- Bloque 5: `_emit_routine_statements()` + `_emit_create_routine()` en 4 emisores
- Bloque 6: `MigrationPlanner._build_plan()` con routines
- Bloque 7: exports en `migrate/ir/__init__.py` y `migrate/__init__.py`
- Tests: 10 archivos en `tests/unit/migrate/`

## Objetivo operativo de esta sesión
- Completar implementación bloques 0–7 (ya iniciada en sesión anterior comprimida)
- Reducir cognitive complexity en `extract_routines()` de PostgreSQL y MariaDB
- Crear 10 archivos de tests unitarios para la nueva funcionalidad
- Validar 0 fallos en suite completa

## Restricciones explícitas
- v1 pass-through: sin reescritura de body SQL; cuerpo emitido verbatim
- Siempre con `MigrationWarning` de revisión manual en transformer
- Oracle PACKAGE/PACKAGE BODY: `is_package_member=True`, solo comentario DDL
- No romper retrocompatibilidad: `routines=None` por defecto en `emit()` y `emit_statements()`
- Param `routines` opcional en emisores (backward compat. total)

## Resultado esperado
- 10 archivos de tests pasando en `tests/unit/migrate/`
- Suite completa: 0 fallos
- `extract_routines()` en MariaDB y PostgreSQL con cognitive complexity ≤ 15
