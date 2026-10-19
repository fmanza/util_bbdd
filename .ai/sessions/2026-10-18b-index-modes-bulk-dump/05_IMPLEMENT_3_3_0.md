# IMPLEMENT — entrega 3.3.0 (G5 `"all"`, G5b `validate_fks_after`, G7 auditoría de índices)

## Mediciones previas (completan G0, 2026-10-19)

| Medida (1M filas) | Resultado | Decisión |
|---|---|---|
| `unique_checks=0`, `sec2u`, MySQL | sin índices: 22,94 → 24,61 s (+7 %); con `"secondary"`: 21,06 → 20,75 s (−1,5 %) | **No se implementa** (D3: < 5 %) |
| `unique_checks=0`, `sec2u`, MariaDB | sin índices: 19,80 → 20,39 s (+3 %); con `"secondary"`: 18,31 → 18,80 s (+2,7 %) | Ídem |
| Huérfanos `NOT EXISTS`, 2 FK | PostgreSQL 0,06 s · MySQL 0,20 s · MariaDB 0,23 s · SQL Server 0,08 s · Oracle 0,00 s (0,0–1,1 % de la carga) | `validate_fks_after` barato |
| Revalidación nativa, 2 FK | PostgreSQL `VALIDATE` 0,15 s · SQL Server `WITH CHECK` 0,06 s · Oracle `ENABLE VALIDATE` 0,15 s | T2 resuelto: coste despreciable |

Ficheros: `build/logs/bench_index_modes_uc_20261019.*`, `build/logs/bench_index_modes_fkval_20261019.*`.

## Condiciones del AUDIT_PLAN

| Condición | Cómo queda |
|---|---|
| D1 `"all"` exige `disable_constraints` | `maintenance_scope` y `ParallelOptions` → `ValueError` |
| D2 `IndexRebuildError` | `maintenance_scope` y `ParallelBulkLoader.load` (tras restaurar todo y, en paralelo, tras escribir la auditoría); `dump` deja el índice `"failed"` con las claves en `error_msg` |
| F2 `"all"` + `isolate` | `ValueError` en `maintenance_scope`, `BulkOptions` y `DumpConfig` |
| F3 destino con datos | `dump`: exige `truncate_target=True`; `bulk`: WARNING si la tabla tiene filas |
| F4 reintentos × commits | Resuelto en el diseño: el reintento reanuda tras `rows_committed`; queda el hueco del commit ambiguo, que detectaría la reconstrucción |
| F5 UNIQUE de Oracle | Solo se planifican PK/UNIQUE **`ENABLED`**: si ya la desactivó la ruta de constraints, sigue a su cargo |
| S2 permisos | Lo desactivado se restaura siempre; un paso que falla deja su objeto como estaba (seguro) |

## Cambios por fichero

| Fichero | Cambio |
|---|---|
| `src/util_bbdd/_core/exceptions.py`, `exceptions.py`, `docs/api/exceptions.md` | `IndexRebuildError` |
| `src/util_bbdd/metadata/{sqlserver/indexes,oracle/indexes,postgresql/tables,mariadb/tables}.py` | SQL de únicos y FK entrantes |
| `src/util_bbdd/metadata/facts.py` | `unique_indexes`, `inbound_foreign_keys`, `UniqueIndexFact`, `InboundForeignKeyFact`; filtro de MariaDB/MySQL compartido |
| `src/util_bbdd/bulk/_support/secondary_indexes.py` | Modo `"all"`: prioridades, dependencias, pasos solo de restauración, diagnóstico de duplicados, `rebuild_error` |
| `src/util_bbdd/bulk/_support/fk_orphans.py` (nuevo) | `orphan_check_sql` por motor |
| `src/util_bbdd/bulk/_execution/maintenance.py`, `bulk/crud.py` | `index_mode`, `validate_fks_after`, aviso de `"all"`, `IndexRebuildError` tras restaurar constraints |
| `src/util_bbdd/bulk/options.py` | `ParallelOptions` (D1) y `BulkOptions.__post_init__` (F2) |
| `src/util_bbdd/bulk/_execution/parallel_loader.py` | Modo en la desactivación previa, avisos por motor y modo, error diferido tras la auditoría, eventos `index` |
| `src/util_bbdd/bulk/_audit/events.py` | `BulkAuditEvents.index` |
| `src/util_bbdd/dump/_models.py`, `_indexes.py`, `_constraints.py`, `orchestrator.py` | `manage_indexes="all"` (F2/F3), `validate_fks_after` |
| `scripts/bench_index_modes.py` | `--fk-validation` |

## Hallazgos

- **SQL Server**: un `ALTER INDEX … REBUILD` de un único que falla por duplicados hace que el **servidor** deshaga la
  transacción de la sesión (el rollback al savepoint da 3903). El resultado es el de PostgreSQL (carga y DDL deshechos)
  pero las claves duplicadas no se pueden listar. En modo autónomo (paralelo, `dump`) sí.
- **MariaDB/MySQL**: un índice UNIQUE referenciado por una FK no se toca nunca (ni en `"all"`); el duplicado falla en el
  propio INSERT.
- **Oracle**: los índices únicos sin constraint no se tocan en `"all"` (no hay DDL fiable para recrearlos sin
  `DBMS_METADATA`); PK y UNIQUE sí.

## Tests

- Unitarios: `tests/unit/bulk/test_secondary_indexes_all.py` (19), `TestMaintenanceScopeAllMode` (3),
  `TestMaintenanceScopeValidateFksAfter` (3), `test_index_results_are_audited_and_rebuild_error_comes_after`,
  `test_validate_fks_after_checks_orphans_per_fk` (dump), 2 del script.
- Integración (banco): `test_maintenance_scope_all_restores_uniques_and_inbound_fks` (5 motores),
  `test_maintenance_scope_all_duplicates_raise_and_roll_back` (PostgreSQL, SQL Server),
  `test_maintenance_scope_all_duplicates_raise_with_keys_when_ddl_committed` (Oracle, MySQL, MariaDB),
  `test_parallel_all_restores_uniques_and_inbound_fks` (SQL Server, Oracle, PostgreSQL),
  `test_maintenance_scope_validate_fks_after_detects_orphans` (MySQL, MariaDB),
  `test_dump_engines.py::test_manage_indexes_restores_indexes` (6 destinos × 2 modos).

## Verificación

ruff, `ruff format --check` y mypy sin errores (342 ficheros); `pytest` sin URLs 6354 passed, 588 skipped; con el
banco y `JAVA_HOME` 6934 passed, 8 skipped; `zensical build --strict` limpio; diagrama de capas sin cambios (342).

## Pendientes

- Decisión: `validate_fks_after=True` por defecto, ahora que su coste está medido (≈1 %).
- Oracle: índices únicos sin constraint en `"all"` (con `DBMS_METADATA.GET_DDL`).
