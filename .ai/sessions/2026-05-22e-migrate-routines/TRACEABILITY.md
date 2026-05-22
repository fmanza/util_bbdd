# TRACEABILITY

## Session metadata
- id: 2026-05-22e-migrate-routines
- fecha: 2026-05-22
- rama: develop
- skill: new_feature
- fase: IMPLEMENT (Bloques 0–7) + tests + refactor cognitive complexity

## Prompt issued
> "Actualizar .ai\sessions / Preparar mensaje para subir código a GitHub"
> (la implementación se realizó en la sesión comprimida anterior)

## Context supplied
- Historial de conversación comprimido con estado completo de bloques 0–7
- `migrate/extractors/mariadb.py` — `extract_routines()` con complexity 17 (SonarQube)
- `migrate/extractors/postgresql.py` — `extract_routines()` con complexity > 15 (SonarQube)
- Suite de tests preexistente: 1189 tests en `tests/unit/migrate/`

## AI output summary
1. Refactorizó `extract_routines()` en `migrate/extractors/mariadb.py` — extrajo
   `_parse_routine_row()` helper; complexity reducida de ~17 a ≤ 15.
2. Refactorizó `extract_routines()` en `migrate/extractors/postgresql.py` — misma
   técnica; complexity reducida de ~17 a ≤ 15.
3. Ejecutó tests existentes post-refactor → 1189 passed, 0 failed.
4. Creó 10 archivos de tests nuevos en `tests/unit/migrate/`:
   - `test_routines_canonical.py` — `CanonicalRoutine` + `MigrationPlan.routines`
   - `test_routines_oracle_extractor.py` — extractor Oracle (body, package, warning)
   - `test_routines_mariadb_extractor.py` — extractor MariaDB (body, tipo desconocido)
   - `test_routines_postgresql_extractor.py` — extractor PostgreSQL (excluye AGGREGATE/WINDOW)
   - `test_routines_sqlserver_extractor.py` — extractor SQL Server (mock fetch_routines_sync)
   - `test_routines_mariadb_emitter.py` — emisor MariaDB (body, stub, package member, backward compat)
   - `test_routines_postgresql_emitter.py` — emisor PostgreSQL
   - `test_routines_sqlserver_emitter.py` — emisor SQL Server
   - `test_routines_oracle_emitter.py` — emisor Oracle (verifica `CREATE OR REPLACE` prepend)
   - `test_routines_planner.py` — integración planner (routines en `MigrationPlan`, warnings propagadas)
5. Iteró sobre 7 fallos iniciales (métodos `plan_from_oracle` inexistentes → `plan()`;
   test warning inline → header genérico).
6. Ejecutó suite completa: **3269 passed, 0 failed**.

## Artefactos generados

| Artefacto                                          | Ruta                                                              | Estado     |
|----------------------------------------------------|-------------------------------------------------------------------|------------|
| Refactor `_parse_routine_row` MariaDB extractor    | `src/util_bbdd/migrate/extractors/mariadb.py`                    | completado |
| Refactor `_parse_routine_row` PostgreSQL extractor | `src/util_bbdd/migrate/extractors/postgresql.py`                 | completado |
| Test `CanonicalRoutine` + `MigrationPlan.routines` | `tests/unit/migrate/test_routines_canonical.py`                  | 11 tests   |
| Test extractor Oracle                              | `tests/unit/migrate/test_routines_oracle_extractor.py`           | 8 tests    |
| Test extractor MariaDB                             | `tests/unit/migrate/test_routines_mariadb_extractor.py`          | 6 tests    |
| Test extractor PostgreSQL                          | `tests/unit/migrate/test_routines_postgresql_extractor.py`       | 7 tests    |
| Test extractor SQL Server                          | `tests/unit/migrate/test_routines_sqlserver_extractor.py`        | 4 tests    |
| Test emisor MariaDB                                | `tests/unit/migrate/test_routines_mariadb_emitter.py`            | 8 tests    |
| Test emisor PostgreSQL                             | `tests/unit/migrate/test_routines_postgresql_emitter.py`         | 6 tests    |
| Test emisor SQL Server                             | `tests/unit/migrate/test_routines_sqlserver_emitter.py`          | 6 tests    |
| Test emisor Oracle                                 | `tests/unit/migrate/test_routines_oracle_emitter.py`             | 6 tests    |
| Test integración planner                           | `tests/unit/migrate/test_routines_planner.py`                    | 6 tests    |
| Sesión `.ai/sessions/`                             | `.ai/sessions/2026-05-22e-migrate-routines/`                     | completado |

**Tests nuevos: 74 (67 nuevos + 7 corregidos en iteración)**
**Suite total al cierre: 3269 passed, 0 failed**

## Directrices para Futuras IAs

**[migrate/extractors cognitive complexity]**: Los extractores que implementen `extract_routines()`
deben delegar el parseo de cada fila a un método helper privado `_parse_routine_row(row, schema)`
para mantener cognitive complexity ≤ 15. Este patrón está establecido en MariaDB y PostgreSQL.

**[emitters/routines backward compat]**: El parámetro `routines` en `emit()` y `emit_statements()`
es siempre `list[CanonicalRoutine] | None = None`. Código existente sin `routines` sigue
funcionando sin cambios. No eliminar el default None.

**[emitters/routines warnings]**: El emisor emite un header genérico
`-- NOTE: requires manual review (see migration warnings)` cuando la rutina tiene warnings,
pero NO incrusta el texto de cada warning individualmente en el DDL generado. Las warnings
individuales viajan en `MigrationPlan.warnings`, no en el script DDL.

**[Oracle emitter routines]**: `ALL_SOURCE` no incluye `CREATE OR REPLACE` en el body.
El emisor Oracle prepend `CREATE OR REPLACE ` + body verbatim. No añadir prefijo en otros emisores.

**[Oracle package/package body]**: Rutinas con `routine_type in ("PACKAGE", "PACKAGE BODY")`
→ `is_package_member=True`, `body=""`. El emisor emite solo un comentario DDL con el package name.
No generar ningún CREATE para estas rutinas (migración manual requerida).

**[MigrationPlanner API]**: El método público es `plan(connection, schema)`, no `plan_from_oracle()`
ni `plan_from_mariadb()`. Los métodos `_plan_from_*()` son privados e internos.

**[SQL Server extractor patch path]**: Para mockear `fetch_routines_sync` y `fetch_routine_body_sync`
en tests del extractor SQL Server, el path correcto es
`util_bbdd.migrate.extractors.sqlserver.fetch_routines_sync` (módulo extractor, no metadata).

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- CHANGELOG.md no actualizado con la sección de routines (pendiente para VERSION)
- Commit no realizado (solicitado en esta sesión como artefacto separado)
