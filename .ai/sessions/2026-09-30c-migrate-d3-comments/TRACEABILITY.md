# TRACEABILITY

## Session metadata
- id: 2026-09-30c-migrate-d3-comments
- fecha: 2026-09-30
- rama: develop
- skill: new_feature (D3 de la deuda de `migrate/`)
- fase: PLAN → AUDIT_PLAN (aprobado: «IMPLEMENT») → IMPLEMENT → AUDIT_CODE → VERSION (commit sin push)

## Prompt issued
- «D3»: comentarios desde y hacia PostgreSQL y SQL Server (PLAN de deuda de `2026-09-29d-migrate-audit`).

## Context supplied
- `.github/prompts/new_feature.prompt.md`; hallazgo previo: los emisores de PostgreSQL y SQL Server solo escribían los
  comentarios como `--` (y B1 los limpió de saltos de línea).

## AI output summary
- PLAN/AUDIT_PLAN (GO): origen (SQL en `metadata/`, comentario añadido al final de las consultas) y destino
  (`COMMENT ON` en PostgreSQL; una sola sentencia `DECLARE @schema … ; EXEC sys.sp_addextendedproperty …` en SQL Server,
  porque el script de `emit()` es un único lote y un `DECLARE` repetido fallaría).
- Test-first: el e2e comprueba el comentario de tabla (`Tabla ñ 'd3'`) y de columna (`C:\datos\x'q`) en el catálogo de
  los 5 destinos desde los 5 orígenes (`_comments`) → 14 pares fallaban (todos con PostgreSQL o SQL Server), 6 pasaban.
- Origen: `fetch_tables_for_extract_sql` y `fetch_columns_for_schema_sql` de PostgreSQL (`obj_description`,
  `col_description` con `quote_ident` y `ORDINAL_POSITION` = `attnum`); `fetch_tables_sql` y
  `fetch_columns_for_schema_sql` de SQL Server (`sys.extended_properties`, `class = 1`, `QUOTENAME`, `ColumnId`).
  Extractores: comentario desde la columna nueva (antes `""`).
- Destino: `PostgreSQLDDLEmitter._emit_comments` + `_pg_literal`; `SQLServerDDLEmitter._emit_comments` + `_ss_literal`
  (`N'…'`); fuera los `-- COMMENT:` y el comentario de columna en `--` (los avisos de migración siguen en `--`).
- Tests: 2 del comportamiento antiguo adaptados; nuevos de escapado (comillas, barra, salto de línea, Unicode), de
  una sola sentencia en SQL Server y de lectura en los dos extractores. e2e 20/20.
- Validación: ruff, format, mypy (385), pytest 5669/226, integración 365.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Origen | `src/util_bbdd/metadata/{postgresql,sqlserver}/tables.py`, `src/util_bbdd/migrate/extractors/{postgresql,sqlserver}.py` | completado |
| Destino | `src/util_bbdd/migrate/emitters/{postgresql,sqlserver}.py` | completado |
| Tests | `tests/integration/test_migrate_views_e2e.py`, `tests/unit/migrate/test_{emitter,}_{postgresql,sqlserver}*.py` | completado |
| Docs | `docs/guides/ddl_migration_guide.md`, `docs/functional/migrate_postgresql_source.md`, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **[migrate/comentarios]**: los comentarios de tabla y columna se migran en los 20 pares: `COMMENT` (MariaDB/MySQL),
  `COMMENT ON` (PostgreSQL, Oracle), `MS_Description` con `sp_addextendedproperty` (SQL Server, schema por defecto del
  usuario destino). Nunca como `--`: el texto del catálogo solo va tras `--` pasado por `one_line()` (B1).
- **[migrate/sqlserver]**: el script de `emit()` de SQL Server es un único lote (sentencias separadas por `;`, sin
  `GO`): un `DECLARE` solo puede aparecer una vez; lo que necesite variables va en una sola sentencia.
- **[migrate/tests]**: `_comments()` del e2e lee el comentario de tabla y columna del catálogo de cada destino; úsalo
  para cualquier comprobación nueva de comentarios.

## Veredicto final
Veredicto: GO — D3 implementado y verificado, commit sin push. Con D1, D2 y D3 la 0.21.0 queda lista para
`/version-closure`.
