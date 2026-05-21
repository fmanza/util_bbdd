# TRACEABILITY

## Session metadata
- id: 2026-05-21-tech-debt-metadata-async
- fecha: 2026-05-21
- rama: develop
- skill: tech-debt + refactor
- fase: AUDIT_CODE → IMPLEMENT (B-01…B-05, D-01…D-05) + PLAN + AUDIT_PLAN + IMPLEMENT + VERSION (D-01/D-02)

## Prompt issued
Auditoría completa de `src/util_bbdd/` — bugs, edge cases, compatibilidad y tests faltantes.
Homogenizar para un mejor mantenimiento, buscando duplicados en la obtención de metadatos entre motores.
Implementar todos los pasos sugeridos excepto D-01/D-02 (requieren PLAN+AUDIT_PLAN previo).
Posteriormente: D-01/D-02 — PLAN + AUDIT_PLAN + IMPLEMENT aprobados.

## Context supplied
- `src/util_bbdd/metadata/` — 8 motores (mysql, mariadb, oracle, postgresql, sqlserver, sqlite, redshift, snowflake)
- Suite de tests existente (3187 tests antes del inicio)
- Bugs activos detectados en sesión de auditoría

## AI output summary

### Bugs corregidos (B-01…B-05)
- **B-01** — `asyncio.get_event_loop()` → `get_running_loop()` en mysql (8), sqlserver (8), sqlite (9)
- **B-02** — `SqlServerAsyncAdapter.fetch_routine_parameters_async` refactorizado a firma `(schema, routine, routine_type)` conforme al Protocol. Resuelve `object_id` internamente; añade `fetch_routine_parameters_by_id_async` como API interna.
- **B-03** — `MysqlAsyncAdapter.fetch_routine_parameters_async` — añadido `routine_type: str | None = None`
- **B-04** — `RedshiftAsyncAdapter` y `SnowflakeAsyncAdapter` — añadidos wrappers `*_async` sobre `run_in_executor`; métodos `*_sync` son la implementación real. Test de paridad Snowflake actualizado a `issubset`.
- **B-05** — `MariaDBSyncManagerProtocol` y `MariaDBAsyncManagerProtocol` — añadida propiedad `logger` faltante.

### Quick wins implementados (D-03…D-05)
- **D-03** — Cobertura de type maps: 109 tests nuevos en `tests/unit/migrate/test_type_maps.py` cubriendo los 12 mapas cruzados con invariantes de completitud, severity, ddl_comment y case-insensitivity.
- **D-04** — `tests/unit/migrate/__init__.py` creado para empaquetar el directorio.
- **D-05** — `metadata/adapters/shared/identifier_utils.py` creado con `quote_backtick_identifier()`; MySQL y MariaDB `common.py` delegan a ella.

### Deuda estructural implementada (D-01/D-02) — con PLAN + AUDIT_PLAN aprobados
- **D-01** — Centralizados `_get_conn() -> Any` y `_run_sync(fn: Callable[..., _T], *args) -> _T` en `MysqlAsyncAdapter`, `SqlServerAsyncAdapter`, `SqliteAsyncAdapter`. Eliminadas ~92 líneas de boilerplate repetido. TypeVar `_T` preserva tipado en mypy.
  - Casos especiales SQLite preservados: `fetch_schemas_async` (sin conn), `fetch_procedures/functions_async` (pasan `None`).
  - SQL Server: doble call `_run_sync` con matching intermedio en `fetch_routine_parameters_async`.
- **D-02** — Extraídos `BaseSyncManagerProtocol` y `BaseAsyncManagerProtocol` en `metadata/adapters/shared/_base_manager_protocol.py`. Los 8 `_manager_protocol.py` heredan de la base y solo declaran `execute_custom_*` + métodos motor-específicos. Divergencias mantenidas: Oracle/PG tienen `params` opcional; MariaDB tiene 6 métodos adicionales.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Base protocols | `src/util_bbdd/metadata/adapters/shared/_base_manager_protocol.py` | nuevo |
| Identifier utils | `src/util_bbdd/metadata/adapters/shared/identifier_utils.py` | nuevo |
| Test type maps | `tests/unit/migrate/test_type_maps.py` | nuevo (109 tests) |
| Test package init | `tests/unit/migrate/__init__.py` | nuevo |
| MySQL async adapter | `src/util_bbdd/metadata/mysql/async_adapter.py` | refactorizado D-01 + B-01 + B-03 |
| MySQL common | `src/util_bbdd/metadata/mysql/common.py` | delegación D-05 |
| MySQL protocol | `src/util_bbdd/metadata/mysql/_manager_protocol.py` | herencia D-02 |
| MariaDB protocol | `src/util_bbdd/metadata/mariadb/_manager_protocol.py` | herencia D-02 + B-05 |
| MariaDB common | `src/util_bbdd/metadata/mariadb/common.py` | delegación D-05 |
| Oracle protocol | `src/util_bbdd/metadata/oracle/_manager_protocol.py` | herencia D-02 |
| PostgreSQL protocol | `src/util_bbdd/metadata/postgresql/_manager_protocol.py` | herencia D-02 |
| SQL Server async adapter | `src/util_bbdd/metadata/sqlserver/async_adapter.py` | refactorizado D-01 + B-01 + B-02 |
| SQL Server protocol | `src/util_bbdd/metadata/sqlserver/_manager_protocol.py` | herencia D-02 |
| SQLite async adapter | `src/util_bbdd/metadata/sqlite/async_adapter.py` | refactorizado D-01 + B-01 |
| SQLite protocol | `src/util_bbdd/metadata/sqlite/_manager_protocol.py` | herencia D-02 |
| Redshift async adapter | `src/util_bbdd/metadata/redshift/async_adapter.py` | reescrito B-04 |
| Redshift protocol | `src/util_bbdd/metadata/redshift/_manager_protocol.py` | herencia D-02 |
| Snowflake async adapter | `src/util_bbdd/metadata/snowflake/async_adapter.py` | reescrito B-04 |
| Snowflake protocol | `src/util_bbdd/metadata/snowflake/_manager_protocol.py` | herencia D-02 |
| Test paridad Snowflake | `tests/unit/test_snowflake_adapter_parity.py` | `==` → `issubset` B-04 |

## Veredicto final
Veredicto: CLOSED
- mypy src: 3 errores pre-existentes sin relación con estos cambios (`MigrationWarning` en sqlserver.py, `crud.py` conditional signature). 0 errores nuevos.
- ruff check src: 2 errores pre-existentes (`F821 MigrationWarning`). 0 errores nuevos.
- pytest: **3187 passed, 1 skipped** — 0 regresiones.
- API pública: SIN CAMBIOS. Todos los contratos externos preservados.
