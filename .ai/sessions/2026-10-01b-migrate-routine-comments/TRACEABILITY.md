# TRACEABILITY

## Session metadata
- id: 2026-10-01b-migrate-routine-comments
- fecha: 2026-10-01
- rama: develop
- skill: new_feature (F4 de la deuda de la 0.22.0: comentarios de rutinas)
- fase: PLAN + AUDIT_PLAN (GO_CONDICIONAL; condición 4: verificar R4 antes de F4) → IMPLEMENT → commit sin push

## Prompt issued
- «PLAN y AUDIT_PLAN» → «F3: one membership helper per target instead, IMPLEMENT» (plan completo F2 → F3 → F1 → F4;
  F1–F3 en la sesión `2026-10-01-migrate-connect-by-3`).

## Context supplied
- `migrate/extractors/{mariadb,sqlserver,postgresql,oracle}.py`, `metadata/{mariadb,sqlserver}/tables.py`,
  `metadata/postgresql/routines.py`, `metadata/oracle/tables.py`, emisores (`-- COMMENT:` de rutinas).

## AI output summary
- **R4 verificado en el banco** (scratchpad `r4_routines.py`, `r4_execute.py`; objetos creados y borrados):
  - **MySQL/MariaDB**: el cuerpo de la rutina es `ROUTINE_DEFINITION` (`BEGIN SELECT 1; END`, sin `CREATE
    PROCEDURE`); `execute()` mysql → mariadb falla: «Sentencia 1/1 del plan falló (BEGIN SELECT 1; END): You have an
    error in your SQL syntax». Cualquier schema con rutinas hace fallar `execute()`.
  - **Oracle**: `fetch_routines_sql` lee `ALL_PROCEDURES.procedure_name`, que es NULL en procedimientos y funciones
    sueltos (el nombre está en `object_name`; `procedure_name` solo lo tienen los miembros de package): la rutina sale
    con nombre `''` y, al buscar su cuerpo por `('', 'PROCEDURE')`, sin cuerpo (stub). Las rutinas sueltas de Oracle no
    se migran.
  - **PostgreSQL**: `pg_get_functiondef` califica la rutina con el schema **origen**
    (`CREATE OR REPLACE FUNCTION zz_util_bbdd_vw_src.zzvw_proc()`).
  - **SQL Server**: el cuerpo trae su `CREATE PROCEDURE` (T-SQL; en otro motor no se crea, como se espera de un
    pass-through).
  - Según la condición 4 del AUDIT_PLAN, esto va a un `/hotfix` aparte (P2) y no se mezcla con F4.
- **F4**: lectura de comentarios (MySQL/MariaDB `ROUTINE_COMMENT` al final de `fetch_routines_sql` de MariaDB, solo
  de migrate; SQL Server `MS_Description` al final de `fetch_routine_bodies_for_schema_sql`, solo de migrate, en un
  dict aparte para conservarlo aunque no haya cuerpo; PostgreSQL con la nueva
  `fetch_routine_comments_for_schema_sql`, porque `fetch_routines_sql` la comparten los adaptadores; con sobrecargas
  no se asigna). Emisión: la línea `-- COMMENT:` que ya tenían los cuatro emisores; sin sentencia real.
- Tests: `test_routine_comments.py` (7) y e2e `test_routine_comment_is_read_into_the_script` (4 orígenes reales).
- Docstring del extractor PostgreSQL corregido («Comentarios de columna: omitidos en v1», obsoleto desde D3).

## Verificación
- ruff, mypy (386 ficheros): sin errores. `pytest`: 5740 passed, 246 skipped. `tests/integration`: 385 passed.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| F4 | `src/util_bbdd/metadata/{mariadb/tables,sqlserver/tables,postgresql/routines}.py`, `migrate/extractors/{mariadb,sqlserver,postgresql}.py` | completado |
| Tests | `tests/unit/migrate/test_routine_comments.py`, `tests/integration/test_migrate_views_e2e.py` | completado |
| Docs | `docs/guides/ddl_migration_guide.md`, `CHANGELOG.md` | completado |
| Hallazgos R4 | esta sesión | resuelto en `65ad997` (sesión `2026-10-01d-hotfix-routines-r4`) |

## Directrices para Futuras IAs
- **[migrate/rutinas]**: las rutinas no son ejecutables en `execute()` hoy: MySQL/MariaDB sin cabecera `CREATE`,
  Oracle sin nombre (ALL_PROCEDURES.procedure_name es NULL en rutinas sueltas), PostgreSQL con el schema origen. Ningún
  test de integración cubría rutinas hasta F4 (y F4 solo lee comentarios, no ejecuta).
- **[migrate/rutinas]**: no emitir sentencias que dependan de que la rutina exista en el destino (comentarios,
  permisos) mientras las rutinas sean pass-through.
- **[metadata/postgresql]**: `fetch_routines_sql` la usan también los adaptadores sync/async: para migrate, consultas
  aparte en lugar de añadirle columnas.

## Veredicto final
Veredicto: CLOSED — F4 implementado y verificado; liberado en v0.23.0 (2026-10-01). R4 confirmado y resuelto en el hotfix `65ad997` (sesión `2026-10-01d-hotfix-routines-r4`; los escenarios de esta
sesión, revalidados el 2026-10-01 con `r4_execute.py`, terminan bien).
