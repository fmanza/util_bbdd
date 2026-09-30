# TRACEABILITY

## Session metadata
- id: 2026-09-30h-migrate-audit-022
- fecha: 2026-09-30
- rama: develop
- skill: audit_code (cambios de la 0.22.0: `v0.21.0..HEAD`) + fixes C1, C2, H1, L1, L2
- fase: AUDIT (PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION) → «IMPLEMENT C1, H1, C2, L1 y L2» → commit sin push

## Prompt issued
- `/audit-code` sin archivos → alcance elegido: «Cambios de la 0.22.0». Después: «IMPLEMENT C1, H1, C2, L1 y L2».

## Context supplied
- `.github/prompts/audit_code.prompt.md`, `.github/agents/code-auditor.agent.md`; diff `v0.21.0..HEAD` (27 ficheros de
  `src/`, +286/−43): E3 (`793ebd8`), E2 (`bdc97bc`), E1 (`79691af`).

## AI output summary
- Auditoría (APROBADO CON CONDICIONES), con evidencia ejecutada (scripts en el scratchpad de la sesión; objetos
  `zzaud_*` del banco borrados):
  - **C1 (alto, confirmado)**: `NOCYCLE` → PostgreSQL rechaza la CTE si la clave es `VARCHAR(n)` o `NUMERIC(p,s)`
    («`character varying(5)[]` in non-recursive term but `character varying[]` overall»); `BIGINT` funciona, por eso el
    e2e (NUMBER(10) → BIGINT) no lo vio. Afecta a claves `VARCHAR2`, `NUMBER(19+)` y `NUMBER(p,s>0)`.
  - **C2 (bajo, confirmado)**: con `NULL` en la columna de `PRIOR`, `NOT NULL = ANY(...)` es NULL y la fila se perdía
    (Oracle la devuelve).
  - **H1 (alto, confirmado, previo: V4 0.20.0)**: `SELECT *` / `e.*` en una jerarquía convertida devolvía
    `jefe_id, id, CB_LEVEL`: la CTE solo lleva las columnas nombradas. Sin error.
  - **L1 (bajo)**: el aviso de comentario se añadía después de escribir la nota de revisión → dos emisiones, dos
    scripts (MySQL/MariaDB y Oracle; al corregir se vio que SQL Server también).
  - **L2 (bajo)**: el test guardián de E1 solo miraba etiquetas literales.
- **Fixes**:
  - C1: `cb_keys` como `ARRAY[CAST(clave AS TEXT)]` en ancla y rama recursiva; comparación `CAST(... AS TEXT)`.
  - C2: `NOT COALESCE(CAST(x AS TEXT) = ANY(cb_keys), FALSE)` (rama recursiva e ISLEAF).
  - H1: `*`/`alias.*` se expanden con las columnas de la tabla del plan (orden de extracción = orden de Oracle) en una
    copia del SELECT; en el generador `FROM dual`, `SELECT *` deja la vista sin reescribir (Oracle devuelve DUMMY).
  - L1: MariaDB añade el aviso antes de mirar `view.warnings`; Oracle y SQL Server calculan los comentarios
    (`fit_comment`) antes de los `CREATE VIEW`.
  - L2: guardián más estricto: fuera de `TYPE`, `DEFAULT`, `IDENTIFIER`, `IDENTIFIER_CASE_COLLISION`, `INDEX` y
    `AUTO_INCREMENT`, todo aviso lleva `code` aunque `target_type` sea una variable. Destapó el aviso de rutina
    pass-through sin código → nuevo `ROUTINE_PASSTHROUGH` (21 códigos).
- Tests: `TestSelectStar` (SQLite: nombres y filas), `TestNocycle` actualizado, `test_emitting_twice_gives_the_same_script`
  (4 emisores; falla 4/4 sin el fix), e2e `test_oracle_nocycle_hierarchy_to_postgresql` parametrizado por clave
  `NUMBER(10)`/`VARCHAR2(10)`/`NUMBER(20)`, con fila `NULL` y vista `SELECT *` (falla sin el fix: C1 y C2).

## Verificación
- ruff, mypy (386 ficheros): sin errores. `pytest`: 5725 passed, 229 skipped. `tests/integration`: 368 passed.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| AUDIT_CODE 0.22.0 | conversación (APROBADO CON CONDICIONES: C1, H1, C2) | emitido |
| Fixes | `src/util_bbdd/migrate/views/_rewrites.py`, `emitters/{mariadb,oracle,sqlserver}.py`, `ir/models.py`, `transformers/_base_transformer.py` | completado |
| Tests | `tests/unit/migrate/test_{view_connect_by,view_comments,warning_codes}.py`, `tests/integration/test_migrate_views_e2e.py` | completado |
| Docs | `docs/functional/migrate_views.md`, `docs/guides/ddl_migration_guide.md`, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **[migrate/views/CONNECT BY]**: en una CTE recursiva de PostgreSQL, las columnas de la rama ancla no pueden llevar
  typmod distinto del resultado de la rama recursiva (`VARCHAR(n)[]` frente a `VARCHAR[]` tras `||`); convertir a un
  tipo sin typmod (aquí TEXT). El e2e debe cubrir claves de texto y numéricas grandes, no solo `NUMBER(10)` → BIGINT.
- **[migrate/views/CONNECT BY]**: toda comparación con `= ANY(array)` que decide si una fila sale necesita `COALESCE`
  por los NULL.
- **[migrate/emitters]**: los avisos que un emisor añade a una vista se calculan antes de escribir la nota de revisión
  (`if view.warnings`), para que la emisión sea idempotente.
- **[auditoría]**: verificar las hipótesis ejecutándolas en el banco destapó un fallo mayor que el buscado (C1 al
  probar C2); vale la pena probar con tipos que el e2e no usa.

## Veredicto final
Veredicto: CLOSED — condiciones de la auditoría cumplidas (C1, H1, C2) y L1, L2 corregidos. La 0.22.0 queda lista para
`/version-closure`.
