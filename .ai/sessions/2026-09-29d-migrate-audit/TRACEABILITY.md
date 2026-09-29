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
- **Fix A6**: test-first: dos tablas de 35 caracteres / 64 bytes con `ñ` que solo difieren al final (orígenes
  MySQL/MariaDB/SQL Server) → los 3 pares hacia PG fallan («relation already exists»); hacia Oracle 23 no falla (admite
  128 bytes; el 30 es un mínimo conservador). Fix: `identifier_rules.ByteLimit(int)` marca los límites de PG y Oracle;
  `truncate_identifier` mide en bytes UTF-8 y corta sin partir caracteres; el aviso dice la unidad; el planner ya no
  hace `int()` del límite (perdía el tipo). Sin cambios en las ~40 llamadas. e2e 20/20; `test_identifier_bytes.py` (7).
- **Fix A8**: hipótesis verificada en el banco (`a8_case_collision.py`, origen PostgreSQL): columnas `"Nombre"`/`nombre`
  → ORA-00957, MySQL/MariaDB 1060, SQL Server 2705; tablas `"ZZAUD_T"`/`zzaud_t` → ORA-00955, SQL Server 2714; el plan
  tenía 0 errores y el aviso de tablas decía «no colisiona». Decisión: detectar y bloquear en vez de renombrar
  (renombrar exigiría propagar a PK, índices, FKs de otras tablas y vistas). `planner._case_collision_warnings`: columnas
  ERROR (Oracle/MySQL/MariaDB) o WARNING (SQL Server, collation); tablas/vistas ERROR (Oracle) o WARNING (resto, con
  mensaje correcto por destino). Verificado de nuevo en el banco. `test_case_collisions.py` (16).
- **Fix A9**: `charset.validate_storage_engine` (identificador simple, sin lista cerrada) en `MigrationPlanner` (solo
  destino MariaDB/MySQL) y en `MariaDBDDLEmitter.__init__` (lo hereda `MySQLDDLEmitter`). `test_storage_engine.py` (17).
- Auditoría de migrate/ cerrada: A1–A4, A6, A8 y A9 corregidos (A5 y A7 dentro de A1).
- Diagrama de capas: 12 paquetes importan de Foundation (nuevo `migrate → _core` por A1); SVG actualizado. El pie de
  `docs/architecture.md` (v0.19.0, 377 ficheros) se actualiza en `/version-closure` (hoy 384 ficheros).

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
| Fix A6 | `src/util_bbdd/migrate/_compat/identifier_rules.py`, `src/util_bbdd/migrate/planner.py` | completado |
| Tests A6 | `tests/unit/migrate/test_identifier_bytes.py`, `tests/integration/test_migrate_views_e2e.py` | completado |
| Fix A8 | `src/util_bbdd/migrate/planner.py` | completado |
| Tests A8 | `tests/unit/migrate/test_case_collisions.py`, `a8_case_collision.py` | completado |
| Fix A9 | `src/util_bbdd/migrate/charset.py`, `emitters/mariadb.py`, `planner.py` | completado |
| Tests A9 | `tests/unit/migrate/test_storage_engine.py` | completado |
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
- **[migrate/identificadores]**: PostgreSQL y Oracle limitan identificadores en bytes, MySQL/MariaDB/SQL Server en
  caracteres; el tipo `ByteLimit` de las constantes lo decide. No convertir los límites con `int()`. SQLAlchemy no aplica
  su convención de nombres en minúsculas de Oracle a identificadores no ASCII (reflexión con `ñ` falla).
- **[migrate/identificadores]**: mayúsculas en el destino: Oracle emite todo en mayúsculas (`_dq`); MySQL/MariaDB no
  distinguen mayúsculas en columnas y en tablas dependen de `lower_case_table_names`; SQL Server depende de la
  collation; PostgreSQL respeta el case entrecomillado. Las colisiones se detectan en el planner, no se renombran.
- **[migrate/auditoría]**: sin pendientes de la auditoría 2026-09-29d. Deuda anotada, no corregida: N+1 consultas por
  tabla en los extractores; el campo `oracle_type` guarda el tipo del origen sea cual sea el motor; los extractores de
  PostgreSQL y SQL Server no leen comentarios.

## Veredicto final
Veredicto: auditoría de migrate/ resuelta — A1–A9 corregidos (GO). Sesión lista para `/version-closure`.
