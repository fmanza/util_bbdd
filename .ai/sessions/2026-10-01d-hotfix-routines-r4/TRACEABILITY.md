# TRACEABILITY

## Session metadata
- id: 2026-10-01d-hotfix-routines-r4
- fecha: 2026-10-01
- rama: develop
- skill: hotfix (R4, P2: las rutinas no se crean con `MigrationPlan.execute()`)
- fase: PLAN → AUDIT_PLAN (decisión del usuario en D) → IMPLEMENT (RCA + fix, test-first) → AUDIT_CODE → VERSION
  (commit sin push)

## Prompt issued
- «Adelante, luego R4. En español» tras liberar v0.23.0 → `/hotfix` R4 (síntomas de la sesión
  `2026-10-01b-migrate-routine-comments`). Decisión del usuario para D: «Comentarla y no enviarla (Recomendado)».

## Context supplied
- `migrate/extractors/{mariadb,oracle}.py`, `metadata/{mariadb,oracle}/tables.py`, `migrate/transformers/
  {_base_transformer,_mysql_family}.py`, `migrate/ir/models.py` (`execute`, `_has_sql`), `migrate/planner.py`
  (origen = destino prohibido, línea 119).

## AI output summary
- **RCA** (verificado en el banco con `r4_execute.py`):
  1. Extracción incompleta: MySQL/MariaDB guardaban `ROUTINE_DEFINITION` (sin `CREATE`); Oracle leía
     `ALL_PROCEDURES.procedure_name` (NULL en rutinas sueltas → nombre '' y sin cuerpo; el package de un miembro tomaba
     el nombre del miembro); PostgreSQL califica con el schema origen.
  2. `execute()` enviaba todas las rutinas, aunque el cuerpo esté en el dialecto del origen; como origen ≠ destino
     siempre, solo MySQL ↔ MariaDB puede crearlas. PostgreSQL → MySQL (1064) y SQL Server → PostgreSQL (sintaxis)
     fallaban a mitad; Oracle → X «funcionaba» solo porque la rutina se perdía (stub de solo comentarios).
  - Corregir solo el nombre de Oracle (el supuesto inicial) habría hecho fallar también Oracle → X: por eso D.
- **Fix**:
  - A (MySQL/MariaDB): `_mysql_create_routine` reconstruye `CREATE PROCEDURE|FUNCTION` con parámetros (nueva
    `fetch_routine_parameters_for_schema_sql`, una consulta por schema, agrupada por (nombre, tipo)), `RETURNS`,
    `DETERMINISTIC`, acceso a datos, `SQL SECURITY` y `COMMENT` (columnas añadidas a `fetch_routines_sql`, solo de
    migrate); sin `DEFINER`.
  - B (Oracle): nueva `fetch_routines_for_schema_sql` (object_name, object_type, procedure_name); rutina suelta =
    object_name y `CREATE OR REPLACE` + ALL_SOURCE; miembro = procedure_name con package = object_name. La
    `fetch_routines_sql` compartida con el adaptador no se toca (probablemente tiene el mismo fallo de nombre en los
    metadatos: anotado, fuera de alcance).
  - C (schema origen en PostgreSQL): no se corrige; no existe el par PostgreSQL → PostgreSQL, así que ese cuerpo nunca
    se ejecuta (y con D va comentado).
  - D: `BaseTransformer._ROUTINES_EXECUTABLE` (False; True en `MySQLFamilyTransformer`): si es False, el cuerpo va
    comentado línea a línea (`-- `), `_has_sql` lo descarta en `execute()` y `ROUTINE_PASSTHROUGH` dice «no se crea».
- **Test first**: e2e `test_routines_in_execute` (mysql→mariadb, mariadb→mysql con procedimientos y `CALL`;
  postgresql→mysql, sqlserver→postgresql, oracle→sqlserver con `execute()` que termina bien) y
  `test_mariadb_routines_are_recreated_from_the_catalog` (función + procedimiento del mismo nombre recreados en otra
  base MariaDB y llamados): 6/6 fallaban antes del fix. Unitarios de Oracle con la forma real de ALL_PROCEDURES (+2).
- Banco: MySQL con binlog y sin SUPER no deja **crear funciones** (1419), ni en el origen; por eso las funciones se
  prueban en MariaDB. Documentado en la guía.

## AUDIT_CODE
- Regresiones: el cuerpo de las rutinas cambia de contrato (Oracle/MySQL/MariaDB: `CREATE` completo; pares
  incompatibles: comentado). Ningún consumidor interno lee `routine.body` salvo los emisores y `execute()`.
- Edge cases: rutina sin `ROUTINE_DEFINITION` (sin permisos) → sigue siendo stub; parámetros sin nombre (valor de
  retorno, ORDINAL_POSITION 0) excluidos; comentario con `\` y `'` escapado para MySQL.
- Compatibilidad: consultas nuevas o columnas al final de consultas solo de migrate; API pública sin cambios.
- Veredicto: APROBADO.

## Verificación
- ruff, mypy (386 ficheros): sin errores. `pytest`: 5744 passed, 252 skipped. `tests/integration`: 391 passed.

## Directrices para Futuras IAs
- **[migrate/rutinas]**: origen y destino son siempre motores distintos (`planner.py:119`): solo MySQL ↔ MariaDB
  comparte el lenguaje de rutinas; `_ROUTINES_EXECUTABLE` decide si el cuerpo se envía o va comentado.
- **[migrate/rutinas]**: `CanonicalRoutine.body` es el `CREATE` completo del origen en todos los extractores
  (MySQL/MariaDB lo reconstruyen desde INFORMATION_SCHEMA; Oracle antepone `CREATE OR REPLACE` a ALL_SOURCE).
- **[metadata/oracle]**: en ALL_PROCEDURES el nombre de una rutina suelta está en `object_name`; `procedure_name`
  solo existe en miembros de package. La `fetch_routines_sql` de los adaptadores probablemente arrastra este fallo.
- **[banco]**: el MySQL del banco no deja crear funciones sin SUPER (binlog activo, error 1419): probar funciones en
  MariaDB.

## Veredicto final
Veredicto: CLOSED — R4 corregido y verificado en el banco (commit sin push).
