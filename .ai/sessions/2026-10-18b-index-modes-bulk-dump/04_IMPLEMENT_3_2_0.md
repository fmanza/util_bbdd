# IMPLEMENT — entrega 3.2.0 (G1, G2, G3, G4, G6)

Alcance confirmado por el usuario (2026-10-19): G6 (InnoDB) sube a 3.2.0; `ParallelOptions.disable_indexes` se aplica en
todos los motores y avisa donde G0 midió que empeora. `"all"` (G5), `validate_fks_after` (G5b) y el evento de auditoría
de índices (G7) quedan fuera de esta entrega.

## Cambios por fichero

| Grupo | Fichero | Cambio |
|---|---|---|
| G1 | `src/util_bbdd/bulk/_support/secondary_indexes.py` (nuevo) | `IndexMode`, `resolve_index_mode`, `IndexStep`, `SecondaryIndexPlanner` (DDL por motor), `restore_batches` (InnoDB: un `ALTER TABLE … ADD INDEX` por tabla), `IndexDdlRunner` (autónomo: commit/rollback por sentencia; en sesión: savepoint por sentencia) |
| G1 | `src/util_bbdd/bulk/_models.py` | `IndexActionResult` (trasladado desde `dump`); `MaintenanceScopeResult.index_results` |
| G1/G6 | `src/util_bbdd/metadata/mariadb/tables.py`, `metadata/facts.py` | `fetch_nonunique_index_columns_sql`, `fetch_table_fk_columns_sql`; `secondary_nonunique_indexes` para MariaDB/MySQL (BTREE simples, sin los que empiezan por columnas de una FK propia o referenciada) |
| G2 | `src/util_bbdd/dump/_indexes.py` | `IndexManager` como adaptador (misma API pública) |
| G2 | `src/util_bbdd/dump/_models.py` | Reexporta `IndexActionResult`; `manage_indexes: bool \| IndexMode` validado en `__post_init__` |
| G3/G6 | `src/util_bbdd/bulk/_execution/maintenance.py`, `bulk/crud.py` | `maintenance_scope(disable_indexes: bool \| IndexMode)` con la estrategia común en la conexión de la sesión; SQL Server ya no exige heap; InnoDB solo con `commit_every_n_chunks` (F1) |
| G4 | `src/util_bbdd/bulk/options.py`, `bulk/_execution/parallel_loader.py` | `ParallelOptions.disable_indexes`; `_hoist_indexes_for_workers` (dentro del de constraints: se reconstruyen los índices antes de reactivar constraints); `ParallelLoadResult.index_results`; WARNING en PostgreSQL y MariaDB con más de un hilo |
| — | `src/util_bbdd/dump/orchestrator.py` | Anotación `val: Any` en `_count_rows` (mypy con SQLAlchemy 2.1.5, actualizado por el usuario) |

## Tests

- Unitarios nuevos: `tests/unit/bulk/test_secondary_indexes.py` (15), `TestParallelBulkLoaderIndexHoist` (5),
  `TestMaintenanceScopeIndexStrategy` (5) y 2 de SQL Server en `test_maintenance_scope.py`; `tests/unit/dump/test_indexes.py`
  reescrito a la nueva estructura (MariaDB/MySQL InnoDB y MyISAM; identidad de `IndexActionResult`).
- Integración nuevos (banco, 5 motores): `test_maintenance_scope_disable_indexes_restores_them`,
  `test_maintenance_scope_innodb_recreates_indexes_with_commit_cadence`,
  `test_maintenance_scope_disable_indexes_rolls_back_with_the_session` (PostgreSQL/SQL Server),
  `test_parallel_disable_indexes_restores_them`; `test_dump_engines.py::test_manage_indexes_restores_secondary_indexes`
  (6 destinos).
- Comprobación manual en MySQL 8.4 y MariaDB 11.4 de la exclusión de índices (prefijo, DESC, comentario, FK propia y
  referenciada): MySQL 8.4 no permite una FK hacia un índice no único (error 6125); MariaDB sí.

## Correcciones al AUDIT_PLAN

- **T5**: decía que el bloque de índices debe «envolver» al de constraints. Lo correcto (y lo implementado): constraints
  fuera e índices dentro, para que al salir se reconstruyan los índices **antes** de reactivar las constraints.
- **G4**: el empeoramiento de MySQL con 4 hilos era del modo `"all"`; con `"secondary"` MySQL gana un 4–6 %. El aviso
  se emite solo en PostgreSQL y MariaDB.

## Pendientes (3.3.0)

- G5 `"all"` (con las salvaguardas del AUDIT_PLAN), G5b `validate_fks_after`, G7 evento de auditoría de índices.
- Medir `unique_checks=0` con `sec2u`, el coste de `validate_fks_after` y de `WITH CHECK CHECK CONSTRAINT` (T2).
