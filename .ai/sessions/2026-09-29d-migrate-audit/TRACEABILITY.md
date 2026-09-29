# TRACEABILITY

## Session metadata
- id: 2026-09-29d-migrate-audit
- fecha: 2026-09-29
- rama: develop
- skill: audit_code + hotfix
- fase: AUDIT (PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION); hotfix A1 (PLAN → VERSION)

## Prompt issued
- `/audit-code` sin archivos → alcance elegido por el usuario: «Paquete migrate/ completo».
- `/hotfix` A1 (+A5, A7): `MigrationPlan.execute` falla en la primera sentencia DDL con destino PostgreSQL, SQL Server,
  MariaDB y Oracle.

## Context supplied
- `.github/prompts/audit_code.prompt.md`, `.github/agents/code-auditor.agent.md`, `.github/prompts/hotfix.prompt.md`,
  `.github/agents/hotfix-responder.agent.md`; banco Docker de 5 motores (`scripts/bench_env.example.sh`).

## AI output summary
- Auditoría de `src/util_bbdd/migrate/` (69 ficheros): núcleo leído completo, resto por patrones de riesgo; hipótesis
  verificadas contra el banco en `zz_util_bbdd_audit`/`ZZAUD_*` (limpiado). Veredicto **RECHAZADO** para cerrar 0.20.0.
  Hallazgos (todos anteriores a la sesión 2026-09-29c):
  - **A1 (crítico, confirmado)**: `MigrationPlan.execute` usa `execute_custom_one` (fetch tras el DDL, sin commit): falla
    en PG/SS (la tabla ni se crea), MariaDB/Oracle (se crea y corta); solo MySQL funcionaba.
  - **A2 (alto, confirmado)**: trigger de identidad Oracle termina en `END` sin `;` → `INVALID`, ORA-04098 al insertar;
    el script de `emit()` no lleva `/` tras los bloques PL/SQL.
  - **A3 (alto, confirmado)**: nombres de índice duplicados hacia PG/Oracle (únicos por schema); MySQL/MariaDB nombran
    los índices sin nombre como la columna → `relation "cliente_id" already exists`.
  - **A4 (medio, confirmado)**: `\` sin escapar en comentarios y DEFAULT de texto hacia MariaDB/MySQL (`C:\datos` →
    `C:datos`).
  - **A5 (medio, confirmado)**: sentencias solo-comentario (rutinas sin cuerpo, miembros de PACKAGE) → ORA-00900.
  - **A6 (medio)**: límite de identificadores en caracteres, no en bytes (PG 63 bytes, Oracle).
  - **A7 (medio)**: `SET search_path` de `pg_schema` exige la misma conexión para todo el plan.
  - A8 (bajo, hipótesis): `_dq` de Oracle pone todo en mayúsculas (columnas que solo difieren en case). A9 (bajo):
    `engine` sin validar.
- **Hotfix A1 (+A5, A7)**: test-first: el e2e de vistas pasa a aplicar el plan con `plan.execute(manager destino)` (y
  `pg_schema` con destino PG) → 16/20 pares fallan (todos salvo destino MySQL), como predijo el RCA. Fix en
  `ir/models.py`: con `get_sqlalchemy_engine()` (o un Engine) se aplica por una conexión DB-API (`raw_connection`),
  cursor del driver sin parámetros, `commit` tras cada sentencia, `rollback` protegido y `DatabaseOperationError` con
  posición y primera línea; el Engine creado se libera. Se omiten las sentencias solo-comentario (`_has_sql`). Objetos
  con solo `execute_custom_one` conservan la vía anterior. Tras el fix: e2e 20/20.
- Calidad: ruff/format/mypy limpios; pytest 5585 passed / 225 skipped; integración 364 passed.
- **Hotfix A2**: test-first: tabla `zzvw_autoinc` (AUTO_INCREMENT / SERIAL / IDENTITY) en el e2e; tras `plan.execute`
  se inserta sin id y se comprueba que se genera → fallan los 4 pares hacia Oracle (ORA-04098), pasan los 16 restantes.
  Fix en `emitters/oracle.py`: el trigger termina en `END;`; `emit()` cierra los bloques PL/SQL (`_is_plsql_block`:
  CREATE [OR REPLACE] TRIGGER/PROCEDURE/FUNCTION/PACKAGE/TYPE tras comentarios) con `
/` y el resto con `;`.
  Verificado además con `sqlplus` del contenedor: trigger VALID, `ID=1`, la sentencia posterior a `/` se ejecuta.
- **Hotfix A3**: test-first: índice `zzvw_idx` en dos tablas en los orígenes MySQL/MariaDB/SQL Server → fallan los 6
  pares hacia PG/Oracle («relation already exists», ORA-00955). Fix: `emitters/_index_names.claim_index_name`, usado
  por `_emit_indexes` de PG (reserva tablas, vistas y PK) y Oracle (reserva PK, compara en mayúsculas); el que choca
  pasa a `<tabla>_<índice>` truncado (`_2`... si aún choca) con aviso en `table.warnings` (sin mutar el IR: emitir
  dos veces da lo mismo). e2e 20/20; `tests/unit/migrate/test_index_names.py` (8).
- **Hotfix A4**: comprobación previa en el banco (`a4_catalog_defaults.py`): MariaDB devuelve `COLUMN_DEFAULT` como
  literal con escapes (`\\`, `\n`, `''`); MySQL devuelve el valor crudo; los comentarios, crudos en ambos. Misma causa
  con dos caras. Test-first: columna `ruta` con DEFAULT y comentario `C:\datos\x'q` en `zzvw_autoinc` → 11 pares
  fallan (hacia MySQL/MariaDB se pierde la barra; desde MariaDB hacia PG/SS/Oracle llega duplicada). Fix:
  `default_normalizer._decode_mariadb_literal` (origen MariaDB → forma canónica) y `emitters/mariadb._mysql_text` /
  `_format_default` (escapan `\` en DEFAULT y comentarios de tabla/columna). e2e 20/20;
  `tests/unit/migrate/test_backslash_literals.py` (16). Los extractores de PostgreSQL y SQL Server no leen comentarios
  (limitación v1 documentada): el e2e solo comprueba comentarios desde MySQL/MariaDB/Oracle.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| AUDIT_CODE migrate/ | conversación (veredicto RECHAZADO, A1–A9) | emitido |
| Hotfix A1 | `src/util_bbdd/migrate/ir/models.py` | completado |
| Tests A1 | `tests/unit/migrate/test_planner.py`, `tests/integration/test_migrate_views_e2e.py` | completado |
| Hotfix A2 | `src/util_bbdd/migrate/emitters/oracle.py` | completado |
| Tests A2 | `tests/unit/migrate/test_emitter_oracle.py`, `tests/integration/test_migrate_views_e2e.py` | completado |
| Hotfix A3 | `src/util_bbdd/migrate/emitters/_index_names.py`, `emitters/postgresql.py`, `emitters/oracle.py` | completado |
| Tests A3 | `tests/unit/migrate/test_index_names.py`, `tests/integration/test_migrate_views_e2e.py` | completado |
| Hotfix A4 | `src/util_bbdd/migrate/_compat/default_normalizer.py`, `src/util_bbdd/migrate/emitters/mariadb.py` | completado |
| Tests A4 | `tests/unit/migrate/test_backslash_literals.py`, `tests/integration/test_migrate_views_e2e.py`, `a4_catalog_defaults.py` | completado |
| Docs A1 | `docs/guides/ddl_migration_guide.md` §3.4, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **[migrate/execute]**: `execute_custom_one`/`execute_custom_many` del manager son para consultas con filas: siempre
  hacen fetch y no hacen commit. Para DDL, usar `get_sqlalchemy_engine().raw_connection()` con el cursor del driver sin
  parámetros y `commit` explícito (patrón de `MigrationPlan.execute` y `views/validation.py`).
- **[migrate/tests]**: los tests unitarios de `migrate` simulan el manager con `MagicMock` (que responde a cualquier
  atributo: usar `spec=[...]` para fijar la vía). Todo lo que ejecuta DDL debe tener un e2e contra el banco; el de vistas
  (`tests/integration/test_migrate_views_e2e.py`) ya aplica el plan con `plan.execute` en los 20 pares.
- **[migrate/oracle]**: un bloque PL/SQL enviado por el driver debe incluir el `;` tras `END` (sin él se crea
  `INVALID` sin error); en un script SQL*Plus va seguido de una línea `/`. El contenedor Oracle del banco trae `sqlplus`
  (`docker exec -e PW -i util_bbdd_bench_oracle bash -c 'sqlplus -s -L "bench/$PW@//localhost:1521/FREEPDB1"'`).
- **[migrate/emitters]**: espacios de nombres del destino: en PostgreSQL índices, tablas, vistas y secuencias son
  «relations» del schema; en Oracle los índices tienen su propio espacio por schema (una PK crea un índice con el nombre
  de la constraint). MySQL/MariaDB/SQL Server: nombre de índice por tabla. Lo resuelve `claim_index_name` al emitir.
- **[migrate/literales]**: forma canónica de un DEFAULT de texto = literal SQL estándar (solo `''`). MariaDB la rompe
  en su catálogo (escapes de barra): se decodifica en `normalize_default`; MySQL devuelve el valor crudo. Los emisores
  de MariaDB/MySQL escapan la barra (`sql_mode` con `NO_BACKSLASH_ESCAPES` en el destino la duplicaría: no soportado).
- **[herramientas]**: el Bash tool pierde un nivel de `\` en heredocs y scripts en línea; para código o SQL con barras
  invertidas, escribir el fichero con Write/Edit.
- **[migrate/emitters]**: pendientes de la auditoría (no bloqueantes): A6 (límite en bytes), A8, A9.

## Veredicto final
Veredicto: A1–A4 corregidos (GO); auditoría de migrate/ → condiciones cumplidas; pendientes no bloqueantes A6, A8, A9 (sesión IN_PROGRESS)
