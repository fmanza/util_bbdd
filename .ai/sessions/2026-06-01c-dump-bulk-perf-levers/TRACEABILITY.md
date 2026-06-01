# TRACEABILITY

## Session metadata
- id: 2026-06-01c-dump-bulk-perf-levers
- fecha: 2026-06-01
- rama: develop
- skill: new_feature / refactor / version_closure (multi-incremento)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (por incremento) + cierre de release

## Prompt issued
Optimizar la carga masiva en `bulk` y `dump`: deshabilitar índices/constraints durante la
carga y reconstruir al final, commits por lotes (no por fila) y paralelizar por tabla o por
rangos de PK si el destino lo tolera. Primero solo PLAN y AUDIT_PLAN; luego implementación
incremental, documentación, auditoría thread-safe, rebalanceo bulk↔dump y cierre de versión.

## Context supplied
- `src/util_bbdd/bulk/` (crud.py, _execution/batch.py, _audit/repository.py, audit.py)
- `src/util_bbdd/dump/` (orchestrator.py, _constraints.py, _models.py, reporters.py, _sql_utils.py)
- Tests existentes (`tests/unit/bulk/`, `tests/unit/dump/`) y docs (`docs/api`, `docs/functional`, `docs/examples`, `BENCHMARKS.md`)

## AI output summary
- **#0 `170487f` refactor(dump)**: FK MariaDB en `ConstraintManager` por listeners `checkout`/`checkin` (`SET SESSION FOREIGN_KEY_CHECKS=0/1`) eliminando `engine.dispose()`. Tests `TestConstraintManagerMariaDB` reescritos.
- **#1 `9edfc32` feat(bulk/dump)**: `commit_every_n_chunks` en `BulkCrud`/`BatchStatementExecutor`/`bulk_session` (commit-as-you-go vía `engine.connect()` cuando activo; `engine.begin()` cuando None). `DumpConfig` lo propaga. Nuevo `tests/unit/bulk/test_commit_cadence.py`.
- **#2 `eff5d62` feat(dump)**: `IndexManager` (`_indexes.py`) + `IndexActionResult`; `manage_indexes` en `DumpConfig`; anidado dentro de `ConstraintManager`; 4ª hoja Excel; `DumpResult.index_results`. Nuevo `test_indexes.py`.
- **#3 `272dd7c` feat(dump)**: paralelización por tabla (`_topological_levels`, `_load_parallel`, `_resolve_max_workers`/`_pool_capacity`) y por rangos de PK (`_load_in_pk_ranges`, `_compute_range_bounds`, `_detect_pk_range_col`, `_resolve_range_count`); `max_parallel_tables`/`parallel_pk_ranges`. Extracción behavior-preserving de `_process_table_with_columns`.
- **`f12ac25` feat(bulk/dump)**: auditoría thread-safe — lock por-ruta en `AuditCsvRepository`; reactivada bajo paralelismo (worker cruds reciben `bulk_audit_path`). Nuevo `test_audit_threadsafe.py`.
- **`b280a47`, `ca031fa` docs**: documentadas las 4 palancas + FK MariaDB en api/functional/benchmarks y ejemplo.
- **`a6777a9` feat(bulk)**: `bulk_insert_from_chunks` (streaming, resuelve columnas/identidad una sola vez). Nuevo `test_bulk_insert_from_chunks.py`.
- **`45ff416` feat(bulk/dump)**: `ParallelBulkLoader` + `ParallelLoadResult` en `bulk/_execution/parallel_loader.py`; `dump._load_in_pk_ranges` delega el mecanismo (política en dump, mecanismo en bulk). Nuevo `test_parallel_loader.py`.
- **`582bb92` docs(bulk)**: `api/bulk-crud.md` + nuevo `api/bulk-parallel.md` + nav mkdocs.
- **`aeaf36c` fix(dump)**: `_pool_capacity` defensivo ante `size()` no numérico (cambio del usuario, validado y commiteado).
- **`fb7beb2` release: v0.9.0**: `pyproject` 0.8.0→0.9.0; CHANGELOG `[Unreleased]`→`[0.9.0] - 2026-06-01` (incluye trabajo previo no versionado + esta sesión); `[Unreleased]` vacío.
- Validación final: `ruff check src tests` OK · `mypy src` (334) OK · `pytest` 3672 passed/1 skipped · `python -m build` → `util_bbdd-0.9.0`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Código bulk | `bulk/crud.py`, `bulk/_execution/{batch.py,parallel_loader.py}`, `bulk/_audit/repository.py`, `bulk/__init__.py` | completado |
| Código dump | `dump/{orchestrator.py,_constraints.py,_indexes.py,_models.py,reporters.py,__init__.py}` | completado |
| Tests | `tests/unit/bulk/{test_commit_cadence,test_audit_threadsafe,test_bulk_insert_from_chunks,test_parallel_loader}.py`, `tests/unit/dump/{test_constraints,test_indexes,test_orchestrator}.py` | completado |
| Docs | `docs/api/{dump,bulk-crud,bulk-parallel}.md`, `docs/functional/dump-data-export.md`, `docs/examples/dump_data_export.md`, `docs/BENCHMARKS.md`, `mkdocs.yml` | completado |
| Release | `pyproject.toml`, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **dump/_constraints (MariaDB)**: NO reintroducir `engine.dispose()` para FK checks. Se usa `checkout`(`SET SESSION FOREIGN_KEY_CHECKS=0`)/`checkin`(`=1`) por-conexión; `dispose()` cierra todo el pool y rompe la paralelización con engine compartido.
- **bulk/BulkCrud**: NO es thread-safe (`_table_cache`, `_active_connection` mutables). Para concurrencia, una instancia por hilo. `ParallelBulkLoader` ya lo garantiza (una `BulkCrud` por worker).
- **Frontera bulk↔dump**: `bulk` = MECANISMO de carga de gran volumen (batching, commit cadence, `bulk_insert_from_chunks`, `ParallelBulkLoader`); `dump` = POLÍTICA (qué tablas, orden FK, qué leer del origen, cómo particionar, constraints/índices). No volver a meter `ThreadPoolExecutor` de inserción en dump.
- **Inspector SQLAlchemy NO es thread-safe**: en `_load_parallel` las columnas comunes y la PK de rango se precomputan EN SERIE (`_precompute_table_meta`) antes de lanzar hilos. No mover esa introspección dentro de los workers.
- **dump PK-sync**: `_sync_pk_sequences` filtra por `crud._table_cache`. En paralelo, las cruds worker NO pueblan esa caché → `_reflect_loaded_tables` refleja las tablas cargadas en la crud compartida. Cuidado: el filtro usa nombre de tabla "pelado" mientras la caché clavea por `schema.tabla` cuando hay schema (quirk preexistente, comportamiento idéntico secuencial/paralelo).
- **bulk/_audit thread-safe**: `auditar_lote_csv` usa lock por-ruta (`_FILE_LOCKS` keyed por `path.resolve()`). Alcance intra-proceso (hilos), no inter-proceso. Permite auditoría bajo volcado paralelo.
- **Índices (manage_indexes)**: solo índices NO únicos secundarios. mssql excluye CLUSTERED (deshabilitarlo deja la tabla inaccesible durante la carga). PostgreSQL es el único path destructivo (DROP+recreate); el DDL de `pg_get_indexdef` se LOGUEA antes del DROP (recuperable si cae el proceso). mariadb/mysql InnoDB → `unsupported`.
- **Guard de concurrencia**: `max_parallel_tables * parallel_pk_ranges` se acota a la capacidad real del pool (`size + max_overflow`) de origen Y destino; degrada con `WARNING`, no falla. Solo se paraleliza intra-nivel topológico; ciclos FK secuenciales.
- **commit_every_n_chunks**: rompe la atomicidad por tabla (commit cada N lotes). Default `None` = una transacción. `bulk_insert_from_chunks` gestiona su propio `bulk_session`; NO invocarlo dentro de un `bulk_session` ya abierto.
- **Release**: la 0.9.0 empaqueta también trabajo previo que estaba en `[Unreleased]` (migrate cross-engine, eliminación de comparación de esquemas en dump, refactor de deuda de bulk). `pyproject` quedó en 0.9.0. **NO se creó el tag git `v0.9.0`** (acción de release pendiente de decisión del usuario). No existe `COMPATIBILITY.md` en el repo.

## Veredicto final
Veredicto: CLOSED (release 0.9.0 consolidada; código + tests + docs verdes)
Pendientes al cierre:
- Crear tag git `v0.9.0` y push (decisión del usuario; no ejecutado).
- (Opcional) endurecer auditoría inter-proceso si se requiere más allá de hilos.
