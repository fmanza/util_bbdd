# TRACEABILITY

## Session metadata
- id: 2026-05-21-audit-metadata-transformers
- fecha: 2026-05-21
- rama: develop
- skill: audit-code → PLAN completo ejecutado
- fase: AUDIT_CODE + PLAN + IMPLEMENT + VERSION

## Prompt issued
`/audit-code` sobre `src/util_bbdd/` completo.
Objetivo: bugs, edge cases, compatibilidad, tests faltantes.
Homogenizar acceso a metadata entre motores (Oracle, PostgreSQL, MariaDB, SQLite, MySQL, SQL Server).

Tras el informe, el usuario solicitó: **Ejecutar PLAN completo**.

## Context supplied
- Repositorio completo `src/util_bbdd/`
- Sesiones anteriores de migrate/ (referencia de patrones)

## AI output summary

### AUDIT_CODE — Hallazgos P1/P2 detectados

| # | Severidad | Área | Descripción |
|---|---|---|---|
| 1 | P1 | `oracle/sync_adapter.py`, `oracle/async_adapter.py` | Cache de rutinas usaba `getattr(db_cache, {}).get(...)` — `db_cache` no es dict → caché nunca funcionaba |
| 2 | P1 | `postgresql/sync_adapter.py`, `postgresql/async_adapter.py` | Mismo bug de caché; `_build_parameters_query` hardcodeaba `'FUNCTION'` → excluía PROCEDUREs |
| 3 | P1 | `postgresql/sync_adapter.py`, `postgresql/async_adapter.py` | `fetch_primary_keys` retornaba 2-tuple (column_name, ordinal) — faltaba `constraint_name` |
| 4 | P2 | `sqlite/sync_adapter.py` | `fetch_procedures/functions_sync` accedía `self.manager.connection` directamente sin fallback a `.db` |
| 5 | TD | `mysql/`, `sqlite/`, `sqlserver/` sync adapters | `__init__` y `_get_conn()` duplicados en los 3 adaptadores |
| 6 | TD | 13 transformers migrate/ | `transform()`, `_transform_table()`, `_transform_view()`, `_transform_fk()`, `_transform_index()` duplicados en 13 archivos |

### IMPLEMENT — Cambios aplicados

**Bugs P1/P2:**
- `oracle/sync_adapter.py` + `async_adapter.py`: acceso directo a `db_cache._routine_metadata_context_cache` (como ya hacía MariaDB correctamente); Protocol type wired
- `postgresql/sync_adapter.py` + `async_adapter.py`: mismo fix caché; `_build_parameters_query` corregido con JOIN a `information_schema.routines`; PK decoder → 3-tuple `(constraint_name, column_name, ordinal_position)`
- `postgresql/tables.py`: SQL de PK actualizado con `JOIN pg_constraint c ON c.conindid = i.indexrelid AND c.contype = 'p'` para exponer `constraint_name`
- `sqlite/sync_adapter.py`: `fetch_procedures/functions_sync` usan `self._get_conn()` con fallback; import circular diferido movido al top
- Protocols Oracle y PostgreSQL: `execute_custom_many(sql, params=...)` y `execute_custom_one` actualizados para incluir `params`

**Refactors TD:**
- `metadata/_base_adapter.py` (nuevo): `BaseConnectionAdapter` con `__init__(manager)` y `_get_conn()` (`connection` → `db` fallback)
- `mysql/sync_adapter.py`, `sqlserver/sync_adapter.py`: heredan `BaseConnectionAdapter`, eliminan `__init__` y `_get_conn()` duplicados
- `migrate/transformers/_base_transformer.py` (nuevo): `BaseTransformer` con `transform()`, `transform_views()`, `_transform_table()`, `_transform_view()`, `_transform_fk()`, `_transform_index()`, `_adapt_identifiers()` + hook `_extra_fk_warnings()` (no-op sobreescribible)
- 13 transformers (`mariadb→*`, `oracle→*`, `postgresql→*`, `sqlserver→*`): heredan `BaseTransformer`, eliminan ~1.500 líneas duplicadas; `_extra_fk_warnings` sobreescrito en transformers con Oracle como destino (ON UPDATE no soportado)

**Tests:**
- `tests/unit/test_metadata_cache_bug_fixes.py` (nuevo): 20 tests unitarios para los 4 bugs P1 corregidos

### AUDIT_CODE post-implement

- `ruff check`: 0 errores
- `mypy src/`: 0 issues
- `pytest`: **3.078 passed, 1 skipped, 0 failed** (sin regresiones)

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Base adapter | `src/util_bbdd/metadata/_base_adapter.py` | nuevo |
| Base transformer | `src/util_bbdd/migrate/transformers/_base_transformer.py` | nuevo |
| Tests cache bugs | `tests/unit/test_metadata_cache_bug_fixes.py` | nuevo |
| Oracle sync adapter | `src/util_bbdd/metadata/oracle/sync_adapter.py` | fix P1 + Protocol |
| Oracle async adapter | `src/util_bbdd/metadata/oracle/async_adapter.py` | fix P1 + Protocol |
| Oracle protocol | `src/util_bbdd/metadata/oracle/_manager_protocol.py` | params añadido |
| PostgreSQL sync adapter | `src/util_bbdd/metadata/postgresql/sync_adapter.py` | fix P1 ×3 + Protocol |
| PostgreSQL async adapter | `src/util_bbdd/metadata/postgresql/async_adapter.py` | fix P1 ×3 + Protocol |
| PostgreSQL protocol | `src/util_bbdd/metadata/postgresql/_manager_protocol.py` | params añadido |
| PostgreSQL tables | `src/util_bbdd/metadata/postgresql/tables.py` | SQL PK + constraint_name |
| SQLite sync adapter | `src/util_bbdd/metadata/sqlite/sync_adapter.py` | fix P2 + herencia base |
| MySQL sync adapter | `src/util_bbdd/metadata/mysql/sync_adapter.py` | herencia BaseConnectionAdapter |
| SQL Server sync adapter | `src/util_bbdd/metadata/sqlserver/sync_adapter.py` | herencia BaseConnectionAdapter |
| 13 transformers migrate/ | `src/util_bbdd/migrate/transformers/*.py` | herencia BaseTransformer |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. ruff clean, mypy 0 issues, 3.078/3.078 tests passed.
- Bugs P1 de caché de rutinas Oracle/PostgreSQL resueltos.
- Deuda técnica TD eliminada: BaseConnectionAdapter + BaseTransformer reducen ~1.500 líneas de código duplicado.
