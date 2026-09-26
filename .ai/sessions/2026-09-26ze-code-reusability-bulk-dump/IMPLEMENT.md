# IMPLEMENT — refactor de reutilización en `bulk/` y `dump/`

- **Fecha**: 2026-09-26 · **Base**: `develop` `53e29da` · **Plan**: [PLAN.md](PLAN.md)
- **Decisiones aplicadas** (recomendaciones del AUDIT_PLAN): D-1 fuera de alcance · D-2 `BulkInserter` intacto ·
  D-3 helpers en `bulk/_support/` · D-4 `FOREIGN_KEY_CHECKS` sin unificar · D-5 fase 1 + R10.
- **Sin commits**: los cambios están en el árbol de trabajo.

## Incrementos

| # | Estado | Cambios |
|---|---|---|
| R0 | ✅ | Línea base: 5079 passed / 199 skipped; cobertura de ramas `bulk/`+`dump/` 92 % |
| R1 | ✅ | `bulk/_support/sql_quoting.py`; `pk_sync` y `dump/_sql_utils.py` lo re-exportan |
| R2 | ✅ | `bulk/_support/excel.py: neutralize_formulas`; `_audit/exporters.py` y `dump/reporters.py` lo usan. Test nuevo: fórmulas en las hojas opcionales (`test_reporters.py`) |
| R3 | ✅ | `AuditCsvRepository.parse_frame`; lo usan `leer_auditoria` y la lectura de la cola del CSV en `dump` |
| R4 | ✅ | `bulk/_audit/counters.py: AuditCounters` (privado); `dump` y `ParallelBulkLoader._partition_result` lo usan; `_AuditCounters` queda como alias |
| R5 | ✅ | Tras el hotfix (`9ef505e`): `_compute_range_bounds` delega en `RangePartitioner.partition_ranges`; mismas tuplas y SQL (equivalencia en 39 063 casos). Commit `f5ca1b6` |
| R6 | ✅ | `MYSQL_FAMILY` (15 literales), `AUDIT_OPERATIONS` (3), `is_identity_pk` (2) |
| R7 | ✅ | `bulk/_support/iterables.py: close_if_closable`, `closing_iterable`; `_closing_iterable` queda como alias |
| R8 | ✅ | `_RawInsertStrategy` (Template Method) para las 4 estrategias de driver. El helper de placeholders se descartó (no compensa) |
| R9 | ✅ | `BulkCrud.__insert_columns` común a streaming y `prepare` |
| R10a | ✅ | `dump/orchestrator.py` 1 510 → 1 089 líneas: `_source_reader.py`, `_fk_graph.py`, `_audit_summary.py`. Delegados `staticmethod` en `DumpOrchestrator`; logger explícito `util_bbdd.dump.orchestrator` en los módulos nuevos. `_concurrency.py`/`_cleanup.py` no se crearon: son métodos de instancia que dependen de `self._cfg` |
| R10b | ✅ | `bulk/_execution/batch.py` 1 091 → fachada de 71 líneas: `_driver_quirks.py`, `insert_strategies.py`, `staging_update.py`, `delete_strategies.py`, `executors.py`; logger explícito `util_bbdd.bulk._execution.batch` en `staging_update` |
| R11 | ✅ | (Tras v0.17.1.) 10 consultas de catálogo de `bulk/` y `dump/` pasan a `metadata/`: `postgresql/tables.py` (`fetch_can_disable_triggers_sql`, `fetch_secondary_nonunique_indexes_sql`, `fetch_fk_definition_sql`), `sqlserver/indexes.py` (`fetch_secondary_nonunique_indexes_sql`, `fetch_clustered_index_count_sql`), `oracle/indexes.py` y `oracle/tables.py` (`with_owner`), `mariadb/tables.py` (`fetch_table_storage_engine_sql`). Texto idéntico al de `HEAD` (comparación de los 10 literales extraídos por AST); 0 literales de catálogo en `bulk/`/`dump/`. Nuevo import `bulk → metadata` dibujado en el diagrama de capas. Integración 338/0 y `IndexManager` probado contra SQL Server, PostgreSQL y Oracle |
| R12 | ✅ | `bulk/_support/dialect.py`: `disable_table_integrity_sql` / `enable_table_integrity_sql` (SQL Server `NOCHECK`/`WITH CHECK CHECK`, PostgreSQL `DISABLE`/`ENABLE TRIGGER ALL`) y `can_disable_pg_triggers`. Los usan `maintenance_scope`, el paso previo al pool de `ParallelBulkLoader` y `ConstraintManager`; cada uno conserva su política. MySQL (`FOREIGN_KEY_CHECKS`) sin unificar (D-4). Mismo SQL; sabotaje detectado en los 4 puntos de uso; integración 338/0 |
| R13 | ✖ | Descartado: solo evitaba construir una `BulkCrud` de más en el paso previo al pool (SQL Server/PostgreSQL) y obligaba a reescribir 2 tests de regresión que fijan ese diseño (PL-3: `test_resolve_table_keeps_fast_executemany_disabled`, `test_parallel_loader_passes_the_option_to_its_bulkcruds`) y 2 parches de `util_bbdd.bulk.crud.Table` |
| R14 | ✅ | `bulk/_execution/session.py`: `SessionScope` (conexión y gancho de commit compartidos) y `CommitCadence`. `BulkCrud` ya no toca atributos privados de los ejecutores (eran 24 accesos); el DELETE conserva su cadencia por llamada. Antes: caracterización en `test_commit_cadence_characterization.py` (`ca48fb4`, reforzada en `b6b0269` porque dos sabotajes pasaban), válida contra el código anterior. Refactor `ce00675`: 5094/199, integración 338/0 |
| Docs | ✅ | `.ai/architecture.md` (árbol real de bulk/dump), `.ai/CURRENT_STATE.md` § Calidad actual, `DumpResult.report` («3 hojas»), pie de figura de `docs/architecture.md` (350 ficheros), ruta en `docs/guides/code_reusability_analysis_guide.md` |

Tests tocados (solo destinos de parche y un test nuevo): `tests/unit/dump/test_dump_fidelity.py` (3 ×
`orchestrator.event` → `_source_reader.event`), `tests/unit/bulk/test_insert_strategies_cache.py` (`batch.text` →
`insert_strategies.text`), `tests/unit/dump/test_reporters.py` (+1 test).

## Verificación

- **Equivalencia del código movido**: comparación por AST de los 33 nombres de `batch.py` (idénticos) y de las 11
  funciones del orquestador (idénticas salvo nombre, llamadas `DumpOrchestrator._x(...)` → `x(...)` y sangría del
  docstring) y de `_source_reader` (idéntico).
- **C-2 (parches que dejan de interceptar)**: script que comprueba que los 24 destinos `patch("util_bbdd.…")` de
  `tests/` se usan en su módulo → ninguno sin uso.
- **Sabotaje**: cada función movida o extraída, sustituida por una que no hace nada, hace fallar sus tests (p. ej.
  `_fk_graph.referred_tables` 37 fallos, `executors._pymssql_plain_decimals` 94, `_RawInsertStrategy.execute` 28,
  `neutralize_formulas` en ambos usos). Lección: parchear el módulo de origen no alcanza a quien importó el nombre ni
  a un `staticmethod(...)` ya capturado; hay que sabotear en el punto de uso.
- **Final**: `ruff check` ✅ · `ruff format --check` ✅ · `mypy src tests/unit/test_protocol_conformance.py` ✅ (355
  ficheros) · `pytest` 5080 passed / 199 skipped · `gen_arquitectura_capas.py` ✅ · `mkdocs build --strict` sin avisos ·
  cobertura de ramas 92 % (259 líneas sin cubrir frente a 266).
- **Integración** (tras los commits, sobre `34aee9f`): `tests/integration` contra los 5 servidores del banco
  (PostgreSQL, MySQL, MariaDB, SQL Server, Oracle) → **338 passed, 0 skipped** en 70 s. URLs de
  `scripts/bench_env.example.sh` con la contraseña de los contenedores (codificada para URL, sin persistirla).

## Pendiente
- ~~**Defecto encontrado en R14**~~ corregido en `bb91612` (`fix(bulk)`, v0.17.2): si una `bulk_session` con `commit_every_n_chunks` falla, las filas pendientes no se descartan y la siguiente sesión que termina bien las suma a `rows_committed` (reproducido: 1 fila en BD, `rows_committed == 2`). Solo afecta a quien reutiliza la `BulkCrud` tras un fallo (`ParallelBulkLoader` prohíbe reintentar con cadencia). Arreglo: `cadence.discard_pending()` en la rama de error de `bulk_session` + test; va por `/hotfix`.

- ~~`/hotfix` de `DumpConfig` y después R5~~: hechos (`9ef505e`, `f5ca1b6`); entrada en `CHANGELOG.md` § Unreleased.
- Fase 2 restante (R11–R14) en otra sesión con el banco; Fase 3 opcional.
- Numeración de fases: `docs/api/dump.md` y `docs/functional/dump-data-export.md` usan «Fase 6/6a»; el código y su log,
  «Fase 5a». Decidir cuál es la canónica (docstring de `DumpConfig.sync_pk_sequences` incluido).
