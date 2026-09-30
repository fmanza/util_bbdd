# TRACEABILITY

## Session metadata
- id: 2026-09-30d-migrate-audit-021
- fecha: 2026-09-30
- rama: develop
- skill: audit_code (cambios de la 0.21.0: `v0.20.0..HEAD`) + fixes C1, H1, H2
- fase: AUDIT (PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION) → «IMPLEMENT C1, H1 Y H2» → commits sin push

## Prompt issued
- `/audit-code` sin archivos → alcance elegido: «Cambios de la 0.21.0». Después: «IMPLEMENT C1, H1 Y H2».

## Context supplied
- `.github/prompts/audit_code.prompt.md`, `.github/agents/code-auditor.agent.md`; diff `v0.20.0..HEAD` (38 ficheros de
  `src/`, +816/−510): D1, D2, D3 y el hotfix de FK de Oracle.

## AI output summary
- Auditoría (APROBADO CON CONDICIONES), verificada contra el banco en `zz_util_bbdd_audit`:
  - **C1 (alto, confirmado)**: comentario de 5000 caracteres (`2026-09-30c-migrate-d3-comments/audit_long_comments.py`)
    → MySQL/MariaDB rechazan el `CREATE TABLE` entero (1629), Oracle el `COMMENT ON` (ORA-01704), SQL Server la
    sentencia única de `MS_Description` (206/15097); PostgreSQL OK. D3 lo hacía más probable.
  - **H1 (bajo, hipótesis)**: agrupar por nombre exacto (D1) frente a los filtros `TABLE_NAME = …` insensibles a
    mayúsculas de MySQL/MariaDB y SQL Server. No reproducible en el banco (Linux).
  - **H2 (bajo, confirmado por lectura)**: tabla sin columnas activas → `CREATE TABLE` inválido sin aviso.
  - Descartadas: coste de `MS_Description` en SQL Server (1200 columnas comentadas: 0,064 s,
    `audit_ss_descriptions_perf.py`) y `col_description` con `ORDINAL_POSITION` tras borrar columnas (correcto).
- **Fix C1** (`232e45a`): `emitters/_comment_limits.fit_comment` (caracteres, bytes UTF-8, unidades UTF-16, sin partir
  caracteres) + categoría `COMMENT`; MySQL/MariaDB (1024 columna / 2048 tabla), Oracle (4000 bytes), SQL Server (3750
  UTF-16). Test-first en el e2e: comentarios del máximo de cada origen (PostgreSQL 5000, Oracle 3900, SQL Server 3700)
  → 11 pares fallaban; ahora 20/20 con el recorte exacto y el aviso. `test_comment_limits.py` (8).
- **Fix H1** (`d5c6029`): `_schema_rows.ObjectRows.for_object` (exacto; si no, la única coincidencia sin mayúsculas);
  los cinco extractores lo usan. `test_schema_rows.py` (5).
- **Fix H2**: aviso `ERROR` de categoría `TABLE` en `planner._build_plan` para tablas sin columnas activas.
  `test_table_without_columns.py` (3).
- Guía §4 (categorías `COMMENT` y `TABLE`), CHANGELOG `[Unreleased] › Fixed`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| AUDIT_CODE 0.21.0 | conversación (APROBADO CON CONDICIONES: C1, H1, H2) | emitido |
| Scripts de verificación | `../2026-09-30c-migrate-d3-comments/audit_long_comments.py`, `audit_ss_descriptions_perf.py` | completado |
| Fix C1 | `src/util_bbdd/migrate/emitters/{_comment_limits,mariadb,oracle,sqlserver}.py`, `ir/models.py` | completado |
| Fix H1 | `src/util_bbdd/migrate/extractors/_schema_rows.py` y extractores | completado |
| Fix H2 | `src/util_bbdd/migrate/planner.py` | completado |
| Tests | `tests/unit/migrate/test_{comment_limits,schema_rows,table_without_columns}.py`, e2e | completado |

## Directrices para Futuras IAs
- **[migrate/comentarios]**: límites de comentario por destino en `emitters/_comment_limits.py` (MySQL/MariaDB 1024
  columna / 2048 tabla en caracteres, Oracle 4000 bytes, SQL Server 3750 unidades UTF-16, PostgreSQL sin límite
  práctico). Todo comentario nuevo que emita DDL debe pasar por `fit_comment`.
- **[migrate/extractors]**: buscar las filas agrupadas con `ObjectRows.for_object(nombre)`, nunca con `.get()`: tolera
  diferencias de mayúsculas como los antiguos filtros por tabla.
- **[release]**: la v0.21.0 incluye un cambio incompatible (D2) en una versión menor, amparado en que las series 0.x son pre-estables (roadmap); la tabla SemVer de `sync.instructions.md` pediría MAJOR. Decidirlo explícitamente en cada release que rompa API mientras se siga en 0.x.
- **[migrate/plan]**: `WarningCategory` tiene 11 valores (se añadieron `COMMENT` y `TABLE`, compatible). Un `ERROR`
  del plan impide `execute()`: usarlo para todo lo que haría fallar el DDL a mitad.

## Veredicto final
Veredicto: CLOSED — condiciones de la auditoría cumplidas (C1, H1, H2). Liberado en v0.21.0 (2026-09-30), junto con D1, D2, D3 y el hotfix de FK de Oracle.
