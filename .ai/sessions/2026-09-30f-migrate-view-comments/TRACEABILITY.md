# TRACEABILITY

## Session metadata
- id: 2026-09-30f-migrate-view-comments
- fecha: 2026-09-30
- rama: develop
- skill: new_feature (deuda E2 de la 0.21.0)
- fase: PLAN + AUDIT_PLAN («Plan y Audit de las deudas») → IMPLEMENT → AUDIT_CODE → VERSION (commit sin push)

## Prompt issued
- «Plan y Audit de las deudas» → «IMPLEMENT» (orden E3 → E2 → E1); tras una pausa por fallos del clasificador,
  «Adelante».

## Context supplied
- `metadata/{postgresql,sqlserver}/tables.fetch_views_sql`, `migrate/extractors/{postgresql,sqlserver}.py`,
  `migrate/emitters/{postgresql,oracle,sqlserver,mariadb}.py`, `emitters/_comment_limits.py`, `ir/models.py`.

## AI output summary
- **Origen**: `fetch_views_sql()` de PostgreSQL (`obj_description(... ::regclass, 'pg_class')`) y SQL Server
  (`LEFT JOIN sys.extended_properties` `MS_Description`, `minor_id = 0`) devuelven el comentario como tercera columna;
  los extractores lo leen (`len(row) > 2`, tolera filas de 2 columnas). Oracle ya lo leía; MySQL/MariaDB no tienen.
- **Destino**, después de crear todas las vistas (orden topológico y circulares):
  - PostgreSQL `COMMENT ON VIEW`; Oracle `COMMENT ON TABLE <vista>` con `fit_comment` (4000 bytes);
  - SQL Server: una sentencia `DECLARE @view_schema sysname = SCHEMA_NAME(); EXEC sp_addextendedproperty ... N'VIEW'`
    con `fit_comment` (3750 UTF-16). Variable propia porque el script de `emit()` es un único lote donde `@schema` ya
    puede estar declarada (comentarios de tablas, D3);
  - MySQL/MariaDB: se mantiene `-- COMMENT:` y se añade a la vista un aviso `COMMENT` (`target_type="(vista)"`),
    idempotente.
- `MigrationPlan._sync_warnings_from_tables` incorpora también `view.warnings` (antes los avisos de emisión de una
  vista no llegaban a `plan.warnings`).
- Tests: `test_view_comments.py` (extractores con 3/2 columnas y NULL, aviso MySQL/MariaDB sin duplicar en dos
  emisiones), emisores actualizados (`test_views_postgresql`, `test_views_sqlserver` + recorte, `test_emitter_oracle`),
  e2e: comentario en `zzvw_inner_join` desde PostgreSQL, SQL Server y Oracle, comprobado en el catálogo del destino en
  los 20 pares (o el aviso con destino MySQL/MariaDB).

## Verificación
- ruff, mypy (386 ficheros): sin errores. `pytest`: 5712 passed, 227 skipped. `tests/integration`: 366 passed.

## AUDIT_CODE
- `fetch_views_sql()` cambia de 2 a 3 columnas: solo lo usan los extractores de `migrate` (verificado con grep).
- Una vista sin reescribir que falle al crearse detiene `execute()` antes del comentario: sin efecto nuevo.
- Veredicto: APROBADO.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Extracción | `src/util_bbdd/metadata/{postgresql,sqlserver}/tables.py`, `migrate/extractors/{postgresql,sqlserver}.py` | completado |
| Emisión | `src/util_bbdd/migrate/emitters/{postgresql,oracle,sqlserver,mariadb}.py`, `ir/models.py` | completado |
| Tests | `tests/unit/migrate/test_view_comments.py` y emisores, `tests/integration/test_migrate_views_e2e.py` | completado |
| Docs | `docs/guides/ddl_migration_guide.md`, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **[migrate/emitters/sqlserver]**: el script de `emit()` es un único lote; cada sentencia que declare variables usa
  un nombre propio (`@schema` para tablas, `@view_schema` para vistas).
- **[migrate/plan]**: los avisos que un emisor añade a `table.warnings`, `col.warnings` o `view.warnings` llegan a
  `plan.warnings` por `_sync_warnings_from_tables`; deben ser idempotentes (`if warning not in ...`).

## Veredicto final
Veredicto: CLOSED — E2 implementado y verificado; liberado en v0.22.0 (2026-09-30).
