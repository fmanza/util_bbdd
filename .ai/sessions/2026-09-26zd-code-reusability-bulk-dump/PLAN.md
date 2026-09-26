# PLAN y AUDIT_PLAN — refactor de reutilización en `bulk/` y `dump/`

- **Fecha**: 2026-09-26 · **Base**: `v0.16.1` (`develop`, `53e29da`)
- **Origen**: [REPORT.md](REPORT.md) (propuestas 1–5 y roadmap)
- **Flujo**: `/refactor` — este documento cubre PLAN y AUDIT_PLAN. IMPLEMENT solo tras aprobación.
- **Fuera de alcance**: el defecto `DumpConfig(chunk_size=0)` que vacía el destino antes de fallar va por `/hotfix`
  y **debe cerrarse antes** del incremento R5 (toca la misma zona de `run()`).

---

## PLAN

### Objetivo

Reducir la duplicación y el acoplamiento por atributos privados en `bulk/` y `dump/` **sin cambios funcionales**:
mismo SQL ejecutado, mismos resultados, mismos logs a nivel WARNING o superior y la misma API pública.

### Reclasificación respecto al informe

Al contrastar las propuestas con la regla «sin cambios funcionales», varios puntos del informe **cambian
comportamiento** o **amplían la API**, así que salen de este refactor:

| Punto del informe | Por qué sale | Destino |
|---|---|---|
| Unificar la capacidad del pool (`size` frente a `size + max_overflow`) | Cambia cuántos workers o rangos se usan y los WARNING | `/new-feature` o decisión aparte |
| `rows_committed` contando también el DELETE | Cambia un valor público (`BulkCrud.rows_committed`, `PartitionResult.rows`) | `/new-feature` |
| Mover `AuditError` bajo `_core/exceptions.py` | `except DatabaseException` pasaría a capturar errores de auditoría | `/new-feature` con nota en CHANGELOG |
| Deprecar `BulkInserter` con `DeprecationWarning` | Aviso nuevo y observable (rompe `-W error`) | Decisión D-2 |
| `AuditCounters`, `BulkLoadOptions` y `DumpWriter` **públicos** | API nueva | Se implementan **privados** (R4, R15); publicarlos, en `/new-feature` |
| API en inglés con alias | API nueva y deprecaciones | Fuera |
| Quitar los wrappers privados de `BulkCrud` | 4 de ellos los usan tests por name-mangling (`_BulkCrud__ejecutar_batch_stmt` ×6, `__prepare_insert_operation` ×5, `__actualizar_df` ×3, `__validar_y_generar_path_sql` ×3) | Se descarta: poco valor y reescribe tests |
| Limpiar `_sql_template_cache` / `get_min_max_allowed_packet` | Método público con tests propios; beneficio casi nulo | Se descarta |

### Rutas afectadas

| Ruta | Incrementos |
|---|---|
| `src/util_bbdd/bulk/crud.py` | R6, R9, R12, R13, R14, R15 |
| `src/util_bbdd/bulk/_execution/batch.py` → `insert_strategies.py`, `delete_strategies.py`, `staging_update.py`, `executors.py`, `_driver_quirks.py`, `session.py` (nuevos) | R8, R10b, R14 |
| `src/util_bbdd/bulk/_execution/parallel_loader.py` | R4, R7, R12, R13, R15 |
| `src/util_bbdd/bulk/_support/pk_sync.py`, `validation.py`, `sql_quoting.py` (nuevo), `excel.py` (nuevo), `dialect.py` (nuevo) | R1, R2, R6, R11, R12 |
| `src/util_bbdd/bulk/_audit/repository.py`, `exporters.py`, `record.py`, `service.py`, `counters.py` (nuevo); `bulk/audit.py` | R2, R3, R4, R6 |
| `src/util_bbdd/dump/orchestrator.py` → `_source_reader.py`, `_fk_graph.py`, `_audit_summary.py`, `_concurrency.py`, `_cleanup.py` (nuevos) | R3–R5, R7, R10a, R15 |
| `src/util_bbdd/dump/_constraints.py`, `_indexes.py`, `_sql_utils.py`, `reporters.py`, `_protocols.py` | R1, R2, R11, R12, R15 |
| `src/util_bbdd/metadata/{postgresql,sqlserver,oracle,mariadb}/` (funciones `fetch_*_sql` nuevas; `postgresql/indexes.py` nuevo) | R11 |
| `tests/unit/bulk/`, `tests/unit/dump/` (solo destinos de `patch` y tests nuevos) | R10, R11, R14 |

### Componentes implicados

`BulkCrud`, `BatchStatementExecutor`, `DeleteBatchExecutor`, las 6 estrategias INSERT, `MySQLStagingUpdateStrategy`,
`ParallelBulkLoader`, `PKSequenceSyncer`, `AuditCsvRepository`, `AuditExporters`, `DumpOrchestrator`,
`ConstraintManager`, `IndexManager`, `DumpReporter`, y las funciones `fetch_*_sql` de `metadata/`.

### Incrementos (un commit `refactor:` por incremento; la suite completa en verde tras cada uno)

**R0 — Línea base (sin commit).** Anotar: número de tests (`pytest -q`), cobertura de ramas de `bulk/` + `dump/` (92 %,
con `coverage run --source=src/util_bbdd/bulk,src/util_bbdd/dump`), `tests/integration` (331) y
`scripts/bench_dump.py` en los 6 motores, estos dos solo si hay servidores del banco disponibles.

**Fase 1 — extracciones de bajo riesgo (4–6 h)**

| # | Cambio | Detalle que preserva el comportamiento |
|---|---|---|
| R1 | `bulk/_support/sql_quoting.py` con `quote_identifier` y `quote_table` | `pk_sync._qi/_qt` y `dump/_sql_utils.py` pasan a re-exportar; mismo cuerpo |
| R2 | `bulk/_support/excel.py: neutralize_formulas(worksheet)` | `exporters` lo llama igual; `DumpReporter` recorre `wb.worksheets` como hoy (defensa H12 en todas las hojas) |
| R3 | `AuditCsvRepository.parse_frame(df)` (estático) con las conversiones de `timestamp` y `tiempo_seg` | Lo usan `leer_auditoria` y `orchestrator._read_audit_csv`; se mantiene el envoltorio de errores de cada llamador |
| R4 | `bulk/_audit/counters.py: AuditCounters` (privado, **no** exportado) = el `_AuditCounters` actual + `as_dict()` | `dump` lo importa; `ParallelBulkLoader._partition_result` usa `**AuditCounters.of(crud).as_dict()`. `PartitionResult`, `ParallelLoadResult` y `DumpAuditSummary` conservan sus campos planos (API) |
| R5 | `_compute_range_bounds` delega en `RangePartitioner.partition_ranges` y convierte `(lo, hi)` inclusivo a `(lo, hi + 1, False)` salvo el último | **Mismo SQL** (`>= :lo AND < :hi`) y mismas tuplas: los 5 tests de `_compute_range_bounds` pasan sin cambios |
| R6 | Constantes `MYSQL_FAMILY` (en `bulk/_support/dialect.py`) y `AUDIT_OPERATIONS` (en `_audit/record.py`); `is_identity_pk(column)` en `validation.py`, usado por `get_insert_columns` y `pk_sync._get_identity_pk_cols` | Sustitución literal de las 17 apariciones y de los 3 `in ("INSERT","UPDATE","DELETE")` |
| R7 | `orchestrator._load_whole_table` usa `_closing_iterable` de `parallel_loader` (importado de un módulo común `bulk/_support/iterables.py`) | Mismo orden: cerrar el generador (join del hilo de prefetch) antes de salir del `with` de la conexión (A1) |
| R8 | `_RawInsertStrategy` base para las 4 estrategias de driver + `_row_placeholders(n_rows, n_cols, prefix)` | Mismos nombres de parámetro (`p{i}_{j}`, `pk_{i}_{j}`) y mismas claves de caché: `test_insert_strategies_cache.py` sin cambios |
| R9 | `BulkCrud.__resolve_insert(df, tabla, …)` común a `__resolve_stream_insert` y `__prepare_insert_operation` | Mismo mensaje del `ValueError`; se conserva `__prepare_insert_operation` (5 tests lo llaman) |

**Fase 2 — reestructuración (1–2 días cada bloque)**

| # | Cambio | Detalle que preserva el comportamiento |
|---|---|---|
| R10a | Dividir `orchestrator.py`: `_source_reader.py` (`_read_chunks`, `_execute_read`, `_prefetch`, `_rebatch`), `_fk_graph.py`, `_audit_summary.py`, `_concurrency.py`, `_cleanup.py` | Los **llamadores** (`_load_whole_table`, `_load_in_pk_ranges`) se quedan en `orchestrator.py` e importan los nombres en su espacio: siguen funcionando los 24 `patch("…orchestrator._read_chunks")` y el de `_prefetch`. Los métodos estáticos (`_topological_sort`, `_build_audit_summary`…) quedan como delegados en `DumpOrchestrator`. Los 3 `patch("…orchestrator.event")` pasan a `…dump._source_reader.event` |
| R10b | Dividir `batch.py` en los 5 módulos listados; `batch.py` queda como fachada de re-exportación | El `patch("…bulk._execution.batch.text")` pasa al módulo que usa `text` |
| R11 | SQL de catálogo a `metadata/`: privilegio de PG, motor de almacenamiento MySQL, índice clustered e índices secundarios de SQL Server, índices de Oracle (owner/user) y de PG, definición de FK de PG, identity de Oracle | **Texto SQL idéntico carácter a carácter** y mismos bind params (patrón de `fetch_schema_fk_references_sql`, `d2729f8`) |
| R12 | `bulk/_support/dialect.py`: funciones `disable_constraints_sql(dialect, quoted)` / `enable_constraints_sql(...)` + `can_disable_triggers(conn, table)` para SQL Server, PostgreSQL y MySQL | Cada consumidor conserva su **política**: `maintenance_scope` (en la sesión), el hoist (transacción propia antes del pool) y `ConstraintManager` (por tabla con commit, listeners del pool en MySQL, validación en PG y Oracle). Oracle sigue solo en `ConstraintManager` |
| R13 | `bulk/_support/reflection.py: TableReflector` (casing, esquema, caché, `reflect_foreign_keys`), usado por `BulkCrud.reflect_table` y `ParallelBulkLoader._resolve_table` | `_resolve_table` deja de construir una `BulkCrud`; ver riesgo F-6 |
| R14 | `bulk/_execution/session.py`: `SessionScope` (conexión y `commit_hook` compartidos) y `CommitCadence` | Una cadencia **por ejecutor** con su semántica actual (ver riesgo F-2); se eliminan los 24 accesos privados desde `BulkCrud` |

**Fase 3 — opcional (≈ 1 día)**

| # | Cambio |
|---|---|
| R15 | `_BulkLoadOptions` (privado) que `DumpOrchestrator` construye una vez y pasa a `BulkCrud` / `ParallelBulkLoader`, cuyos constructores no cambian; `DumpWriter` Protocol **interno** en `dump/_protocols.py` para tipar el colaborador del orquestador, con conformidad en `tests/unit/test_protocol_conformance.py`; `crud._table_cache` → `BulkCrud.cached_table_names()` (método nuevo sin `_`; ver D-2) |
| R16 | `self.logger = logging.getLogger(__name__)` en `DumpOrchestrator`, `ConstraintManager`, `IndexManager`, `DumpReporter`, `ParallelBulkLoader` y `PKSequenceSyncer`, sustituyendo el `_log` de módulo (mismo nombre de logger ⇒ mismos registros) |

**Documentación (commits `docs:` separados, en la misma sesión):** `.ai/architecture.md` § bulk/dump,
«Fase 5a/6a» en `DumpConfig`, «3 hojas» en `DumpResult`, «Calidad actual» de `.ai/CURRENT_STATE.md`. La columna
`"exists"` del informe Excel **no** se toca: cambiarla altera la salida (va a `/new-feature`).

### Riesgos de regresión (resumen; detalle en AUDIT_PLAN)

| Incremento | Riesgo | Motivo |
|---|---|---|
| R1–R9 | Bajo | Extracciones puras con tests directos |
| R10a/b | Medio | Destinos de `mock.patch` que dejan de interceptar sin fallo evidente |
| R11 | Bajo-medio | Cualquier diferencia de texto SQL en catálogos de 4 motores |
| R12 | Medio | DDL transaccional distinta por motor; tres políticas que conservar |
| R13 | Bajo-medio | Efectos secundarios de construir una `BulkCrud` que desaparecen |
| R14 | **Alto** | Zona con más regresiones históricas (P-26, P-27, BLK-08, M-1, hallazgo 7) |
| R15–R16 | Bajo | Tipado interno y logging con el mismo nombre de logger |

### Validación por incremento

`python -m ruff check src tests` · `python -m ruff format --check src tests` ·
`python -m mypy src tests/unit/test_protocol_conformance.py` · `python -m pytest` ·
`python scripts/gen_arquitectura_capas.py` (R10–R13: no se crean paquetes de primer nivel; debe pasar sin tocar el
dibujo). R11, R12 y R14, además: `tests/integration` contra los 5 servidores y `scripts/bench_dump.py` (tolerancia
±3 %).

---

## AUDIT_PLAN

### Veredicto: **GO_CONDICIONAL**

Fase 1 (R1–R9): **GO**. Fase 2: **GO** si se cumplen C-1 a C-4. Fase 3: **GO** tras decidir D-2. Condiciones y
decisiones al final.

### Riesgos funcionales

- **F-1 · Cadencia del DELETE distinta de la del INSERT (bloquea el diseño ingenuo de R14).** `BatchStatementExecutor`
  guarda `_chunks_since_commit` en la instancia y lo **arrastra entre llamadas** dentro de `bulk_session`;
  `DeleteBatchExecutor` usa un contador **local que se reinicia en cada `execute()`** (`batch.py:1041`) y no suma a
  `rows_committed`. Una `CommitCadence` compartida cambiaría cuándo se hacen los commits de un DELETE. **Mitigación**:
  una cadencia por ejecutor; la del DELETE se crea por llamada y con `count_rows=False`. Antes de tocar nada, test de
  caracterización: sesión con INSERT (3 lotes) + DELETE (3 lotes) y `commit_every_n_chunks=2` ⇒ commits en los mismos
  puntos que hoy.
- **F-2 · Reinicios del contador que hay que conservar en R14.** Hoy se ponen a 0 en: entrada de `bulk_session` con
  cadencia (`crud.py:1041`), cada `execute()` fuera de sesión con cadencia (`batch.py:952`), commit final de la sesión
  (`1049-1051`) y restauración tras error en `maintenance_scope` (`1181-1182`, solo el del INSERT). Cada uno necesita un
  test que lo fije antes de migrar (varios ya existen en `test_commit_cadence.py`, `test_maintenance_scope.py`,
  `test_delete_commit_cadence.py`).
- **F-3 · El texto de `FOREIGN_KEY_CHECKS` difiere entre consumidores**: `"SET SESSION FOREIGN_KEY_CHECKS=0"` en `crud`
  frente a `"… = 0"` en `dump/_constraints.py`, y los tests asertan cada forma exacta. En R12 **no se unifica el
  texto**: cada consumidor mantiene su cadena (o R12 solo abarca SQL Server y PostgreSQL). Ver D-4.
- **F-4 · Semántica de los rangos de PK (R5).** Equivalencia verificada: con paso `ceil(span/n)`,
  `partition_ranges` da `[lo, lo+step-1]` y `_compute_range_bounds` da `[lo, lo+step)`; mismas particiones para PK
  enteras. Se conserva el SQL con límite exclusivo, así que ni siquiera cambia el texto.
- **F-5 · Fallos de lectura del CSV de auditoría (R3).** `leer_auditoria` envuelve en `AuditDataError`; `dump` captura
  `Exception` y devuelve el resumen «sin entradas». `parse_frame` no debe lanzar tipos nuevos: se limita a las
  conversiones que ya hay (`format="mixed"`, `errors="coerce"`).
- **F-6 · Efectos secundarios que desaparecen con R13.** Hoy `_resolve_table` construye una `BulkCrud`, que con
  `mssql+pyodbc` activa `fast_executemany` en el engine y con pymssql registra un INFO (P-17). Se comprobó que solo se
  llega ahí con SQL Server y PostgreSQL. `fast_executemany` lo activan igualmente las `BulkCrud` de los workers antes
  del primer INSERT, y el hoist solo ejecuta `ALTER TABLE` (no `executemany`), así que el único cambio observable es un
  INFO duplicado menos. **Aceptable**, pero se anota en el commit.
- **F-7 · Orden de cierre en R7.** El cierre del generador debe seguir ocurriendo **dentro** del `with
  source_engine.connect()` (A1). Test existente: `tests/unit/dump/test_prefetch.py` / `test_failure_paths.py`.

### Riesgos técnicos

- **T-1 · Parches que dejan de interceptar (R10).** 24 `patch("util_bbdd.dump.orchestrator._read_chunks")`, 3 de
  `orchestrator.event`, 1 de `orchestrator._prefetch` y 1 de `bulk._execution.batch.text`. Si se mueve la función que
  **usa** el nombre, el parche sustituye un nombre que ya nadie lee y el test puede pasar sin probar nada. Ver C-2.
- **T-2 · Tests acoplados a privados.** 66 referencias a atributos privados de los ejecutores en 7 ficheros de test
  (incluido `tests/integration/test_bulk_engines.py`) y 33 usos de métodos estáticos privados de `DumpOrchestrator`.
  En R10 se mantienen delegados; en R14 los tests que fijan `executor._active_connection` a mano se reescriben contra
  `SessionScope`, en un commit propio y revisado aparte.
- **T-3 · Capas (Regla #6).** Todos los imports nuevos van hacia abajo: `dump` (7) → `bulk` (6) → `metadata` (5).
  Ningún paquete de primer nivel nuevo. La guarda `test_architecture_import_rules.py` lo confirma en cada commit.
- **T-4 · Importar módulos privados de `bulk` desde `dump`.** Ya ocurre (`dump/_models.py` → `bulk._models`) y la
  guarda no lo prohíbe, pero cada helper compartido amplía esa superficie. Ver D-3.
- **T-5 · mypy y Protocols.** El `DumpWriter` interno (R15) debe usar parámetros posicionales donde `BulkCrud` los
  nombra distinto, como ya documenta la decisión 2026-09-22.
- **T-6 · Banco de integración.** R11, R12 y R14 necesitan los 5 servidores. Sin ellos, esos incrementos no se cierran
  (C-3).

### Riesgos de seguridad

- **S-1 · Parametrización del SQL de catálogo (R11).** Las consultas movidas deben conservar los bind params
  (`:tbl`, `:schema`, `:owner`, `:name`) y **no** pasar a f-strings. En `_find_fk_orphan_pg` el nombre de tabla
  llega como parámetro `CAST(:tbl AS regclass)`: se mantiene así.
- **S-2 · Identificadores en DDL (R1, R12).** La DDL sigue componiéndose con identificadores citados por
  `identifier_preparer` (`quote_table` / `format_table`); las funciones de R12 reciben el nombre **ya citado**, nunca
  el nombre crudo. El escape de `'` en `DBCC CHECKIDENT` (`pk_sync.py:226`) no se toca.
- **S-3 · Defensa H12 (R2).** Al compartir `neutralize_formulas`, `DumpReporter` debe aplicarla a **todas** las hojas,
  incluidas las opcionales. Test: `tests/unit/dump/test_reporters.py` (ya cubre `=HYPERLINK`); se añade un caso en la
  hoja «Secuencias PK».
- **S-4 · Recursos (R7, R10a, R14).** Conexiones y el hilo de `_prefetch` deben cerrarse en los mismos puntos (A1, A2,
  P-26). `SessionScope.open` debe restaurar `connection`/`commit_hook` a `None` también ante `BaseException`, como hoy
  el `finally` de `bulk_session`.

### Simplificaciones posibles (aplicadas al PLAN)

1. **Funciones en lugar de un Protocol `DialectMaintenance` con clases (R12).** Lo compartido son 2–3 cadenas SQL por
   motor y una consulta de privilegios; un `dict` de funciones basta y evita una jerarquía para 3 motores.
2. **`AuditCounters` sin cambiar las dataclasses públicas (R4).** Componerlo dentro de `PartitionResult` cambiaría la
   API; se usa solo como valor interno.
3. **R5 sin cambiar el SQL:** se reutiliza el cálculo, no la forma de la consulta.
4. **No quitar los wrappers de `BulkCrud`** ni tocar la caché de plantillas: poco valor frente a reescribir tests.
5. **R10 antes que R12 y R14:** los módulos más pequeños hacen más legibles los diffs de alto riesgo.
6. **R15 opcional:** si la fase 2 elimina ya la mayor parte del reenvío de parámetros (`TableReflector` lo quita de
   `_resolve_table`), `_BulkLoadOptions` puede no compensar; se decide al cerrar la fase 2.

### Condiciones para GO

- **C-1** · El `/hotfix` de `DumpConfig` (validación antes de desactivar constraints y vaciar el destino) está
  integrado antes de R5.
- **C-2** · En R10, script de comprobación (en el scratchpad, no versionado) que para cada `patch("mod.nombre")` de
  `tests/` verifique que `nombre` se **usa** en `mod`, no solo se importa; cero resultados antes de hacer commit.
  Además, sabotear a propósito una vez cada función movida y confirmar que sus tests fallan.
- **C-3** · R11, R12 y R14 se cierran solo con `tests/integration` en verde en los 5 servidores y `bench_dump.py` dentro
  de ±3 %. Sin banco disponible, se implementan en rama y se dejan sin fusionar.
- **C-4** · R14 empieza con los tests de caracterización de F-1 y F-2 en un commit `test:` previo, en verde contra el
  código actual.

### Decisiones pendientes

| ID | Decisión | Recomendación |
|---|---|---|
| D-1 | ¿Se abordan ahora los puntos reclasificados (capacidad del pool, `rows_committed` del DELETE, jerarquía de `AuditError`)? | No en este refactor; abrir `/new-feature` tras la fase 2 |
| D-2 | `BulkInserter`: ¿mantener, deprecar o retirar? `cached_table_names()` sería API nueva | Mantenerlo intacto; en R15 usar `DumpWriter` interno y leer la caché con un accesor privado documentado, sin método público nuevo |
| D-3 | Dónde viven los helpers compartidos con `dump`: módulos privados de `bulk` (`_support/…`) o un módulo con nombre público y fuera de `__all__` | Privados en `bulk/_support/`, con un docstring que nombre a `dump` como consumidor |
| D-4 | Texto de `FOREIGN_KEY_CHECKS` en R12 | No unificar: R12 cubre SQL Server y PostgreSQL; MySQL queda como está |
| D-5 | Alcance de esta sesión | Fase 1 completa + R10; R11–R14 en una sesión con el banco disponible |

### Cambios respecto a REPORT.md

- Corregido en REPORT § 3 (S-2) y en la Propuesta 3: `_resolve_table` **no** ejecuta `SHOW VARIABLES` (solo se llega
  ahí con SQL Server y PostgreSQL).
- Las propuestas 2 y 5 se acotan a su parte sin cambios funcionales (F-1; API privada).
