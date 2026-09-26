# Reutilización de código y mantenibilidad — `bulk/` y `dump/`

- **Fecha**: 2026-09-26 · **Versión analizada**: `v0.16.1` (`develop`, `53e29da`)
- **Prompt**: `.github/prompts/code_reusability_architecture.prompt.md`
- **Fase**: análisis estático + mediciones (sin cambios de código ni commits)
- **Alcance real**: `src/util_bbdd/bulk/` (22 ficheros, 6 422 líneas) y `src/util_bbdd/dump/` (8 ficheros, 3 052 líneas).
  El prompt estimaba ~3K líneas; son ~9,5K. Los tres ficheros mayores concentran el 42 %:
  `dump/orchestrator.py` (1 510), `bulk/crud.py` (1 382) y `bulk/_execution/batch.py` (1 091).

**Mediciones propias de esta sesión**

| Medida | Resultado | Cómo |
|---|---|---|
| Cobertura de ramas `bulk/` + `dump/` | **92 %** (3 801 sentencias, 1 146 tests en 12 s) | `coverage run --branch --source=src/util_bbdd/bulk,src/util_bbdd/dump -m pytest tests/unit/bulk tests/unit/dump tests/unit/test_*bulk*…` (`COVERAGE_CORE=sysmon`) |
| Funciones con complejidad ciclomática > 10 | **2** de 398 | `ruff --select C901` (max 10) |
| Parámetros/retornos sin anotar | **2** | `ruff --select ANN001,ANN201,ANN202` |
| Firmas con `Any` | **110** | `ruff --select ANN401` |
| Métodos públicos sin docstring | **6** | `ruff --select D101,D102,D103,D105,D107` |

> Nota de entorno: `pytest --cov` falla en la recogida con Python 3.14 + numpy (`ImportError: cannot load module more than
> once per process`) porque `--cov=util_bbdd.bulk` importa el paquete antes que pytest. Con `coverage run` y
> `--source` **por ruta** funciona.

---

## 1. Ejecutivo

### Hallazgos principales

1. **La misma DDL de «mantenimiento» por motor está escrita tres veces.** Desactivar/reactivar FK y triggers
   (`NOCHECK CONSTRAINT ALL`, `DISABLE TRIGGER ALL`, `FOREIGN_KEY_CHECKS`) y la comprobación de privilegios de
   PostgreSQL viven en `BulkCrud.maintenance_scope` (`bulk/crud.py:1081-1300`),
   `ParallelBulkLoader._hoist_constraints_for_workers` (`bulk/_execution/parallel_loader.py:569-642`) y
   `ConstraintManager` (`dump/_constraints.py`). La consulta de privilegios de PostgreSQL está copiada literalmente
   (`crud.py:1204-1214` y `parallel_loader.py:614-625`). Añadir un motor o corregir una sentencia exige tocar 3 sitios.
2. **SQL de introspección fuera de `metadata/` (Reglas #1 y #3).** `dump/_indexes.py` consulta `sys.indexes`,
   `all_indexes`/`user_indexes` y `pg_index` aunque existen `metadata/sqlserver/indexes.py` y
   `metadata/oracle/indexes.py`; también hay SQL de catálogo en `crud.py` (`pg_tables`,
   `information_schema.TABLES`, `sys.indexes`), `dump/_constraints.py:325` (`pg_constraint`) y
   `bulk/_support/pk_sync.py:305-322` (`all_tab_identity_cols`). El commit `d2729f8` (Q9) ya sentó el precedente
   correcto al mover la consulta de FK de SQL Server a `metadata/sqlserver/constraints.py`.
3. **El estado transaccional del ejecutor no está encapsulado.** `BulkCrud` lee y escribe **24 veces** atributos
   privados de `BatchStatementExecutor`/`DeleteBatchExecutor` (`_active_connection`, `_commit_hook`,
   `_chunks_since_commit`, `_rows_pending_commit`…), y la cadencia de commit está implementada dos veces
   (`batch.py:949-991` y `1026-1050`). Es la zona con más fallos corregidos en el historial (P-26, P-27, BLK-08, M-1),
   y la falta de un objeto que la encapsule es la causa estructural.
4. **Contratos e infraestructura duplicados entre capas.** Los 4 contadores de auditoría aparecen en 6 sitios; la
   capacidad del pool se calcula con **dos reglas distintas** (`bulk`: `pool.size()`; `dump`: `size + max_overflow`);
   el `Protocol` `BulkInserter` (`dump/_protocols.py`) no lo usa nadie (el orquestador tipa `BulkCrud` y llama a
   métodos que el Protocol no declara). Helpers pequeños copiados a propósito para «no importar código privado»:
   quoting (`dump/_sql_utils.py` ≡ `pk_sync.py:34-43`) y `_desactivar_formulas`
   (`dump/reporters.py:35` ≡ `bulk/_audit/exporters.py:20`).
5. **Defecto encontrado de paso (no es refactor):** `DumpConfig` solo valida `write_batch_size`. Con
   `chunk_size=0` y `truncate_target=True`, `DumpOrchestrator.run()` **vacía el destino y después falla** con
   `ValueError` al crear la `BulkCrud` (`orchestrator.py:333`, tras `_cleanup` en la línea 325). Reproducido en SQLite:
   destino con 2 filas → 0 filas tras el error. Candidato a `/hotfix` independiente (ver § 8).

### Impacto estimado en mantenibilidad

**Medio-alto.** La calidad por función es buena (cobertura 92 %, 2 funciones con CC > 10, tipado casi completo); la
deuda está en la **arquitectura entre ficheros**: duplicación de políticas por motor, estado compartido por atributos
privados y ficheros de 1 000–1 500 líneas con varias razones de cambio. Proxy medible: hoy un cambio de DDL por motor
toca **3 ficheros**; tras las propuestas 1 y 3, **1**. Se eliminan ~350–450 líneas duplicadas (estimación por recuento
de los bloques citados en § 2) sin cambiar comportamiento.

### Prioridad global: **MEDIA**

No hay urgencia funcional salvo el defecto del punto 5 (**ALTA**, pero va por `/hotfix`, no por este refactor). El
refactor reduce el riesgo de las próximas auditorías de rendimiento, que tocan precisamente estas zonas.

---

## 2. Duplicación y oportunidades de extracción

| Localización | Patrón | Líneas | Candidato a extraer | Beneficio | Riesgo |
|---|---|---|---|---|---|
| `bulk/crud.py:1191-1300`, `bulk/_execution/parallel_loader.py:592-642`, `dump/_constraints.py:150-165,190-271` | DDL desactivar/reactivar FK/triggers por motor | ~190 | `bulk/maintenance/` con una estrategia por motor (`DialectMaintenance`) | Un solo punto por motor; hoy 3 | Medio (DDL transaccional distinto por motor; tests con mocks muy acoplados al SQL) |
| `bulk/crud.py:1204-1214` ≡ `parallel_loader.py:614-625` | Consulta de privilegios PG (`is_superuser` / propietario en `pg_tables`) | 2×11 | `metadata/postgresql/…: fetch_can_disable_triggers_sql()` | Regla #1; una sola consulta | Bajo |
| `dump/_indexes.py:144-161,195-218,251-266` | Descubrimiento de índices secundarios no únicos | ~55 | `metadata/{sqlserver,oracle,postgresql}/indexes.py: fetch_secondary_nonunique_indexes_sql()` | Regla #3 (ya existen esos módulos) | Bajo |
| `crud.py:1242-1248`, `crud.py:1258-1261`, `_constraints.py:325-335`, `pk_sync.py:305-322` | SQL de catálogo inline (motor de almacenamiento, índice clustered, definición de FK, identity Oracle) | ~45 | `metadata/<motor>/` | Regla #1/#3 | Bajo |
| `dump/_sql_utils.py:13-21` ≡ `bulk/_support/pk_sync.py:34-43` | `quote_identifier` / `quote_table` | 2×9 | Un único módulo en `bulk/` importado por `dump` (capa 7 → 6, permitido) | Un helper; hoy dos | Bajo |
| `dump/reporters.py:35-47` ≡ `bulk/_audit/exporters.py:20-30` | Neutralizar fórmulas en openpyxl (H12) | 2×10 | `bulk/audit.py` público o módulo compartido de Excel | Una defensa de seguridad, no dos | Bajo |
| `dump/orchestrator.py:1334-1340` ≡ `bulk/_audit/repository.py:198-204` | Conversión de columnas del CSV de auditoría (`timestamp`, `tiempo_seg` con coma) | 2×7 | `AuditCsvRepository.parse_frame(df)` estático | El formato del CSV se define en un sitio | Bajo |
| `orchestrator.py:180-204`, `parallel_loader.py:106-109,138-156,509-530`, `crud.py:947-982`, `_models.py:216-219`, `orchestrator.py:1371-1376` | Los 4 contadores de auditoría (`audit_failures`, `audited_rows`, `unaudited_committed_rows`, `audit_uncommitted_records`) | ~80 | `bulk.AuditCounters` (hoy `dump._AuditCounters` privado) con `of()`, `__add__`, `as_dict()` | Añadir un contador = 1 cambio; hoy 6 | Bajo |
| `orchestrator.py:755-780,957-984,1018-1032` y `parallel_loader.py:268-297` | Capacidad del pool y recorte de workers | ~85 | `bulk/_execution/concurrency.py: pool_capacity(engine)` | **Unifica dos reglas distintas** (ver § 3 LSP) | Bajo-medio (cambia avisos/recortes) |
| `parallel_loader.py:661-673` y `orchestrator.py:631-637` | Cerrar un generador si la escritura falla (A1/A2) | 13 + 6 | Reutilizar `_closing_iterable` (hacerlo semipúblico) | Una semántica de cierre | Bajo |
| `orchestrator.py:709-730` vs `range_partitioner.py:84-126` | Rangos contiguos de PK (`ceil(span/n)`) | 22 | `RangePartitioner.partition_ranges` + `BETWEEN` inclusivo | Además permite pasar `partition_ranges` a `loader.load()` y validar solapes (hoy no se usa) | Bajo (PK entera) |
| `batch.py:224-241, 276-288, 413-426, 475-485` | Preámbulo de 4 estrategias INSERT: vacío → fallback no-`Insert` → `cols`/`preparer`/`quoted_table`/`quoted_cols` | 4×~12 | Clase base `_RawInsertStrategy` (Template Method) | Menos ruido; la regla de fallback en un sitio | Bajo |
| `batch.py:392-399, 438-443, 764-784` | Construcción de placeholders `:p{fila}_{col}` / `:pk_{fila}_{col}` | ~25 | `_row_placeholders(n_rows, n_cols, prefix) -> (sql, names)` | Una implementación | Bajo |
| `batch.py:949-991` vs `batch.py:1026-1050` | Cadencia de commit + elección `connect()`/`begin()`/conexión activa | ~45 | `CommitCadence` / `SessionScope` (Propuesta 2) | Una sola semántica INSERT/DELETE | Medio |
| `crud.py:553-569` ≡ `crud.py:639-651` | Resolución de columnas + comprobación `GENERATED ALWAYS` en streaming y en prepare | 2×~15 | `_resolve_insert(df, tabla, …) -> InsertPlan` | Un único punto para la regla de identidad | Bajo |
| `validation.py:95-99` ≡ `pk_sync.py:390-400` | Criterio «PK autoincremental/identity» (el propio docstring lo reconoce) | 2×5 | `is_identity_pk(column)` en `validation.py` | Criterio único insert/sync | Bajo |
| `validation.py:47-63` + `crud.py:882,912` | Tablas de casing por dialecto repetidas + excepción MySQL/MariaDB en 2 métodos | ~20 | `IdentifierCasing.for_dialect(name)` | Un mapa de casing | Bajo |
| 17 apariciones en `bulk/` y `dump/` | Literal `("mysql", "mariadb")` | 17 | `MYSQL_FAMILY: frozenset` (en `core/capabilities.py` si encaja) | Evita omisiones al añadir variantes | Bajo |
| `bulk/audit.py:186`, `bulk/_audit/service.py:68,107` | Validación `operacion in ("INSERT","UPDATE","DELETE")` | 3 | `AUDIT_OPERATIONS` en `_audit/record.py` | Un punto | Bajo |
| `pk_sync.py` (12 construcciones) y `_constraints.py:205-223,293-321,405-423` | Construcción repetida de `PKSyncResult` / `ConstraintResult` con los mismos campos fijos | ~120 | Fábricas `_result(table, col, status, …)`; `_run_enable()` análogo al `_run_rebuild` que ya tiene `_indexes.py:279` | −40 % de líneas en esos handlers | Bajo |
| `dump/reporters.py:212-233, 288-312, 352-373, 379-417` | Hoja = cabecera + «sin datos» en cursiva + filas + autowidth | ~80 | `_write_table_sheet(wb, name, headers, rows, empty_msg, color)` | Hojas nuevas en ~5 líneas | Bajo |

---

## 3. Violaciones de SOLID

### SRP

**S-1 · `DumpOrchestrator` (1 510 líneas, 54 métodos)**
- **Ubicación**: `dump/orchestrator.py`.
- **Descripción**: además de orquestar las 5 fases contiene: lectura del origen con ajustes por driver
  (`_read_chunks`, `_execute_read`, `_prefetch`, `_rebatch`), grafo FK y orden topológico (`_build_fk_graph`,
  `_topological_sort/levels`, `_find_cycle_components`, `_mssql_referred_tables`), limpieza por motor (`_cleanup*`),
  política de concurrencia (`_resolve_max_workers`, `_resolve_range_count`, `_pool_capacity`), lectura y resumen del CSV
  de auditoría (`_read_audit_csv`, `_build_audit_summary`) y 4 avisos de configuración.
- **Impacto**: cada auditoría de rendimiento del volcado (Q1–Q9, PD-01…PD-13) tocó este fichero; los tests de
  `_topological_sort` o `_read_audit_csv` tienen que importar el orquestador entero.
- **Propuesta**: Propuesta 4 (división en módulos sin cambiar comportamiento).

**S-2 · `BulkCrud` (1 382 líneas)**
- **Ubicación**: `bulk/crud.py`.
- **Descripción**: API CRUD + reflexión y casing de tablas + gestión de sesión/transacción + `maintenance_scope`
  con DDL por motor (~220 líneas) + diagnóstico de configuración MySQL al construir + detección de driver SQL Server.
- **Impacto**: `ParallelBulkLoader._resolve_table` (`parallel_loader.py:644-658`) instancia una `BulkCrud` completa
  **solo para resolver el nombre de una tabla** (reflexión + casing). Solo se llega ahí con SQL Server y PostgreSQL
  (el hoist sale antes con el resto), así que el coste es la construcción completa de la instancia; con pymssql repite
  además el INFO de P-17. *(Corregido en PLAN: una versión anterior decía que ejecutaba `SHOW VARIABLES` de MySQL;
  no es así.)*
- **Propuesta**: extraer `TableReflector` (reflexión + casing + caché) y `DialectMaintenance` (Propuesta 3).

**S-3 · `bulk/_execution/batch.py` (1 091 líneas)**: peculiaridades de drivers (decimal de pyodbc, `_PlainDecimal` de
pymssql), 6 estrategias INSERT, UPDATE por staging, 4 estrategias DELETE y 2 ejecutores. Propuesta 4.

### OCP

**O-1 · Despacho por motor con `if/elif`** en `ConstraintManager.disable_all/enable_all`
(`_constraints.py:91-126`), `IndexManager.disable_all/rebuild_all` (`_indexes.py:87-125`) y los 4 métodos
`__maintenance_*` de `crud.py`. `PKSequenceSyncer._get_handler` (`pk_sync.py:147-154`) ya usa un registro por
dialecto: es el patrón a extender a los demás. Añadir un motor hoy obliga a modificar cada `if`.

### LSP

**L-1 · `BulkInserter` no es sustituible por lo que el orquestador usa.** El Protocol declara solo
`bulk_insert_from_df` (`dump/_protocols.py:17-33`); el orquestador tipa `BulkCrud` y llama a
`bulk_insert_from_chunks`, `reflect_table`, `sync_pk_sequences`, `_table_cache` y los contadores de auditoría. Un
objeto que cumpla `BulkInserter` rompería el volcado. No tiene usos en `src/` ni en `tests/`: es un contrato muerto
que documenta una dependencia que ya no existe (la decisión 2026-09-21 levantó la prohibición `dump → bulk`).

**L-2 · Dos significados de «capacidad del pool».** `ParallelBulkLoader._resolve_max_workers` recorta a
`pool.size()` (`parallel_loader.py:281-294`); `DumpOrchestrator._pool_capacity` usa `size + max_overflow`
(`orchestrator.py:1018-1032`). Con `pool_size=5, max_overflow=10` y `parallel_pk_ranges=8`, `dump` acepta 8 rangos y el
loader que crea los recorta a 5 con otro WARNING. No es incorrecto, pero dos componentes que colaboran aplican reglas
distintas a la misma pregunta.

### ISP

**I-1 · `BulkCrud` como dependencia de `dump` es demasiado ancha.** `dump` necesita ~6 capacidades (insertar por chunks,
reflejar, sincronizar PK, contadores, caché de tablas); recibe la clase entera. Un Protocol de consumidor
(`DumpWriter`) como los que la decisión 2026-09-22 introdujo en `metadata/`, `analysis/` y `doc/` lo acota.

### DIP

**D-1 · Estado compartido por atributos privados.** `crud.py:1034-1071` y `1169-1182` fijan
`executor._active_connection`, `_commit_hook`, `_chunks_since_commit`, `_rows_pending_commit` en dos ejecutores
(24 accesos). Otros accesos privados entre clases: `persistence.py:268` → `AuditManager._registrar_lote`;
`orchestrator.py:1057` → `crud._table_cache`; `dump/_models.py:15` → `util_bbdd.bulk._models`.
**Impacto**: cualquier cambio en el ejecutor rompe `BulkCrud` sin que mypy lo detecte como cambio de contrato.
**Propuesta**: Propuesta 2.

### Otras desviaciones de `SHARED_INSTRUCTIONS.md`

- **Logging**: «las clases con lógica deben tener `self.logger`». `DumpOrchestrator`, `ConstraintManager`,
  `IndexManager`, `DumpReporter`, `ParallelBulkLoader` y `PKSequenceSyncer` usan un `_log` de módulo; `bulk` mezcla
  f-strings y `%` en los mensajes de log.
- **Excepciones**: `AuditError` y subclases viven en `bulk/_audit/errors.py` y heredan de `Exception`, fuera de la
  jerarquía canónica `_core/exceptions.py` (donde sí están `DumpError`, `DumpConstraintError`, `DumpReportError`).
- **Dependencia opcional no declarada**: `crud.py:83-101` intenta `from util.timing.medir_tiempo import medir_tiempo`
  (paquete externo ajeno a `pyproject.toml`); si está instalado, cambia el comportamiento de los 4 métodos públicos.

---

## 4. Patrones reutilizables no extraídos

### Strategy — mantenimiento de integridad por motor

- **Dónde aparece**: `BulkCrud.__maintenance_*`, `ParallelBulkLoader._hoist_constraints_for_workers`,
  `ConstraintManager`, `IndexManager`.
- **Variantes**: alcance **sesión** (MySQL `FOREIGN_KEY_CHECKS`: `crud` lo ejecuta en la conexión; `dump` lo aplica
  con listeners `checkout/checkin` en el pool) frente a **catálogo** (SQL Server `NOCHECK`, PostgreSQL
  `DISABLE TRIGGER`, Oracle `DISABLE CONSTRAINT`); verificación posterior solo en `dump` (PG `VALIDATE` + búsqueda de
  huérfanos PD-04; Oracle `ENABLE VALIDATE`).
- **Abstracción propuesta**: `DialectMaintenance` (Protocol) con `disable_constraints_sql(table)`,
  `enable_constraints_sql(table)`, `can_disable(conn, table) -> bool`, `scope: Literal["session", "catalog"]` y
  registro `MAINTENANCE_BY_DIALECT`. Las **políticas** (transacción, hoist antes del pool, listeners, validación y
  resultados) se quedan en cada consumidor: solo se comparte el «qué SQL y con qué permisos».
- **Ubicación sugerida**: `bulk/maintenance.py` (capa 6; `dump` en capa 7 puede importarlo) + consultas de catálogo en
  `metadata/<motor>/`.

### Template Method — estrategias INSERT de driver

- **Dónde**: `PostgreSQLExecuteValuesStrategy`, `PostgresCopyStrategy`, `MySQLMultiRowInsertStrategy`,
  `MySQLDriverExecutemanyStrategy` (`batch.py`).
- **Variantes**: solo cambia el cuerpo que escribe las filas (execute_values, COPY, multi-fila, executemany del
  driver). El preámbulo (vacío, fallback de no-`Insert`, columnas y quoting) es idéntico.
- **Abstracción**: `_RawInsertStrategy.execute()` final + `_insert(connection, quoted_table, cols, quoted_cols,
  records)` abstracto.
- **Ubicación**: `bulk/_execution/insert_strategies.py`.

### Unit of Work / Scope — sesión y cadencia de commit

- **Dónde**: `BulkCrud.bulk_session`, `BatchStatementExecutor.execute`, `DeleteBatchExecutor.execute`,
  `BulkCrud.__maintenance_restore_after_error`.
- **Variantes**: atómica (`engine.begin()`), commit-as-you-go (`engine.connect()` + commit cada N), reutilizar la
  conexión de la sesión; el DELETE no cuenta `rows_committed` (documentado como aproximación en `crud.py:978-981`).
- **Abstracción**: `SessionScope` que posee conexión, `commit_hook` y `CommitCadence(n)` con `on_batch(rows)`,
  `on_commit()`, `rows_committed`, `reset_pending()`. Ambos ejecutores lo reciben por constructor.
- **Ubicación**: `bulk/_execution/session.py`.

### Value Object — contadores de auditoría

- **Dónde**: 6 sitios de § 2. **Abstracción**: `AuditCounters` (frozen dataclass con `of()`, `__add__`, `as_dict()`);
  `PartitionResult`, `ParallelLoadResult`, `BulkCrud` y `DumpAuditSummary` lo exponen o lo componen.
- **Ubicación**: `bulk/_audit/counters.py`, re-exportado en `bulk/__init__.py`.

### Parameter Object — opciones de carga

- **Dónde**: `BulkCrud.__init__` (11 parámetros), `ParallelBulkLoader.__init__` (12, reenvía 8 a `BulkCrud`),
  `DumpOrchestrator._make_worker_crud` y `_load_in_pk_ranges` (repiten 7), `ParallelBulkLoader._resolve_table`.
- **Abstracción**: `BulkLoadOptions` (frozen dataclass) con `chunk_size`, `commit_every_n_chunks`, `audit_csv_path`,
  `audit_strict`, `enable_fast_executemany`, `strip_strings`, `reflect_foreign_keys`…; `BulkCrud.from_options()`.
  Los constructores actuales se mantienen (aditivo).
- **Ubicación**: `bulk/_models.py`.

### Registry — casing por dialecto

- **Dónde**: `normalize_identifier`, `normalize_dataframe_columns`, `crud.__actualizar_df`, `crud.reflect_table`.
- **Abstracción**: `IdentifierCasing` (`lower`/`upper`/`preserve`) por dialecto; MySQL/MariaDB = `preserve`, lo que
  elimina los dos `if` especiales de `crud.py:882` y `912`.

---

## 5. Análisis de mantenibilidad por módulo

| Métrica | `bulk/` | `dump/` |
|---|---|---|
| Líneas / ficheros | 6 422 / 22 | 3 052 / 8 |
| Fichero mayor | `crud.py` 1 382 (53 métodos) · `batch.py` 1 091 | `orchestrator.py` 1 510 (54 métodos) |
| Funciones con CC > 10 | 1: `normalize_sql_literal` (11, `normalize.py:322`) | 1: `_prefetch` (11, `orchestrator.py:114`) |
| Cobertura de ramas (medida) | 91 % en `crud.py`, 98 % en `batch.py` y `parallel_loader.py`; **bajas**: `_support/table_utils.py` 33 %, `_audit/exporters.py` 62 %, `audit.py` 80 % | 92 % en `orchestrator.py`, 87 % `_constraints.py`, 92 % `_indexes.py`, 96 % `reporters.py` |
| Cobertura recomendada | ≥ 90 % por fichero; cubrir `table_utils` (`get_max_column_value` sin tests) y los exportadores JSON/HTML | ≥ 90 %; `_constraints.py` (ramas de Oracle y errores de `enable_all`) |
| Docstrings | 4 públicos sin docstring (getters/setters de `AuditManager`, `audit.py:80-115`) | 2 `__init__` sin docstring |
| Type hints | 2 sin anotar (`crud.py:831` `df_cols`, `crud.py:846` retorno); `Any` en 88 firmas, 30 en `batch.py` (`connection: Any`) | `Any` en 22 firmas (`conn: Any`) |
| Tipado mejorable | `connection: Any` → `sqlalchemy.Connection`; `stmt: Any` → `Executable` | `conn: Any` → `Connection` |

### Nombres y documentación

- **Mezcla de idiomas en la API**: `bulk_insert_from_df(tabla_destino, generar_sql, path_sql)`,
  `get_columna_may_min`, `obtener_valor_max_columna` frente a `sync_pk_sequences`, `reflect_table`,
  `maintenance_scope`. Métodos privados que solo delegan (`__validar_y_generar_path_sql`, `__obtener_pk_cols`,
  `__generar_sql_insert`, `__guardar_fichero_sql`, `__ejecutar_delete_batch` con `del numero_registros`,
  `crud.py:337-352, 821-859, 1302-1344`): añaden indirección sin lógica.
- **Código residual**: `MySQLMultiRowInsertStrategy.get_min_max_allowed_packet` (`batch.py:358-365`, dos ramas
  devuelven lo mismo); `_sql_template_cache` guarda una tupla cuyo segundo elemento es siempre `""` (`batch.py:403`);
  comentarios «(sin cambios)» de un refactor antiguo (`batch.py:692, 995`).
- **Documentación desalineada con el código**:
  - `.ai/architecture.md:90-116` describe `bulk/strategies/`, `parallel.py`, `partition.py`, `pk_sync.py` y
    `mysql_variables.py`, que no existen (hoy: `_execution/`, `_support/`, `_audit/`); cabecera «v0.10.0».
  - `.ai/CURRENT_STATE.md` § «Calidad actual» indica 3 826 tests; la cabecera del mismo fichero, 5 067.
  - `DumpConfig` llama «Fase 6a» a la sincronización de PK (`_models.py:87`); el orquestador, «Fase 5a»
    (`orchestrator.py:371`).
  - `DumpResult.report` dice «3 hojas» (`_models.py:231`); el informe tiene hasta 6.
  - Hoja «Columnas Inexistentes»: la columna «Valor/Tipo en Origen» siempre vale `"exists"` (`reporters.py:396,413`).
- **Casos límite sin cobertura**: el defecto de `chunk_size=0` del § 1 (ningún test valida `DumpConfig` más allá de
  `write_batch_size`); `max_parallel_tables`, `parallel_pk_ranges` y `commit_every_n_chunks` tampoco se validan en
  `DumpConfig.__post_init__`.

---

## 6. Propuestas de refactoring (priorizadas por beneficio/esfuerzo)

### Propuesta 1: Extracciones de bajo riesgo (helpers duplicados)

- **Objetivo**: eliminar las copias pequeñas de § 2 sin cambiar comportamiento.
- **Alcance**: `dump/_sql_utils.py`, `bulk/_support/pk_sync.py`, `dump/reporters.py`, `bulk/_audit/exporters.py`,
  `bulk/_audit/repository.py`, `dump/orchestrator.py` (`_AuditCounters`, `_read_audit_csv`, `_compute_range_bounds`,
  cierre del generador), `bulk/_execution/parallel_loader.py`, `dump/_models.py`, `dump/_protocols.py`.
- **Cambio incompatible**: no. `BulkInserter` se mantiene re-exportado con `DeprecationWarning` hasta la siguiente
  versión menor.
- **Esfuerzo**: pocas horas (4–6 h).
- **Beneficio**: ~150 líneas menos; un solo punto para quoting, defensa H12, formato del CSV y contadores;
  `AuditCounters` público para quien use `ParallelLoadResult`. Rendimiento: neutro.
- **Plan de implementación**:
  1. `bulk/_support/sql_quoting.py` con `quote_identifier`/`quote_table`; `pk_sync` y `dump` lo importan;
     `dump/_sql_utils.py` queda como re-export.
  2. `AuditCounters` en `bulk/_audit/counters.py` (mover `_AuditCounters` y añadir `as_dict()`); `PartitionResult`
     lo compone; propiedades de `ParallelLoadResult` y `BulkCrud` delegan.
  3. `AuditCsvRepository.parse_frame(df)` estático; `repository.leer_auditoria` y `orchestrator._read_audit_csv` lo usan.
  4. `neutralize_formulas(worksheet)` en un módulo público de `bulk` (`bulk/audit.py` o `bulk/_excel.py` re-exportado).
  5. `_compute_range_bounds` → `RangePartitioner.partition_ranges` + `BETWEEN :lo AND :hi`; pasar `partition_ranges`
     a `loader.load()`.
  6. Constantes `MYSQL_FAMILY` y `AUDIT_OPERATIONS`; `is_identity_pk()` compartido por `validation` y `pk_sync`.
  7. `pool_capacity(engine)` único; **decidir** si la regla es `size` o `size + max_overflow` (recomendado:
     `size + max_overflow`, que es lo que documenta `DumpConfig.max_parallel_tables`).
- **Tests impactados**: `tests/unit/dump/test_orchestrator.py` (tests de `_compute_range_bounds` y
  `_build_audit_summary` si llaman a privados), `tests/unit/bulk/test_parallel_loader*.py` (recorte de workers si se
  unifica la regla), `tests/unit/test_architecture_import_rules.py` (sin cambios: los imports siguen hacia capas
  inferiores).
- **Rollback**: un commit por paso; `git revert` individual. Sin migración de datos.

### Propuesta 2: `SessionScope` + `CommitCadence` (encapsular el estado transaccional)

- **Objetivo**: que `BulkCrud` no toque atributos privados de los ejecutores y que INSERT/UPDATE y DELETE compartan
  una única implementación de la cadencia de commit.
- **Alcance**: `bulk/_execution/batch.py` (ejecutores), `bulk/crud.py` (`bulk_session`, `__blocks_transaction`,
  `__maintenance_restore_after_error`, `rows_committed`), nuevo `bulk/_execution/session.py`.
- **Cambio incompatible**: no (API pública intacta; cambian clases internas).
- **Esfuerzo**: 1–2 días (incluye el banco de integración de `tests/integration` en los 5 servidores).
- **Beneficio**: elimina los 24 accesos privados; `rows_committed` pasa a contar también el DELETE (hoy aproximado);
  la zona con más regresiones históricas queda en ~120 líneas testeables por separado. Rendimiento: neutro.
- **Plan de implementación**:
  1. Tests de caracterización del estado actual: commits por N lotes, `rows_committed`, `commit_hook` con auditoría
     (M-1), restauración de `maintenance_scope` tras error (ya existen en parte: `test_delete_commit_cadence.py`,
     `test_maintenance_scope.py`, `test_raw_cursor_transaction.py`).
  2. Crear `CommitCadence` y `SessionScope` (§ 7) sin usarlos; tests unitarios propios.
  3. Migrar `BatchStatementExecutor`, luego `DeleteBatchExecutor`, luego `BulkCrud.bulk_session`.
  4. Eliminar los atributos privados antiguos; mypy confirma que no quedan accesos.
- **Tests impactados**: los que parchean `executor._active_connection` o `_commit_every_n_chunks` directamente
  (buscar con `grep -rn "_active_connection\|_chunks_since_commit" tests/`).
- **Rollback**: rama propia; revert del merge. El comportamiento observable no cambia, así que no hay datos que migrar.

### Propuesta 3: `DialectMaintenance` + SQL de catálogo a `metadata/`

- **Objetivo**: un único sitio por motor para la DDL de desactivar/reactivar integridad y cumplir las Reglas #1/#3.
- **Alcance**: `bulk/crud.py` (`maintenance_scope` y 4 helpers), `bulk/_execution/parallel_loader.py`
  (`_hoist_constraints_for_workers`, `_resolve_table`), `dump/_constraints.py`, `dump/_indexes.py`,
  `bulk/_support/pk_sync.py`, `metadata/{postgresql,sqlserver,oracle,mariadb}/`.
- **Cambio incompatible**: no.
- **Esfuerzo**: 1–2 días.
- **Beneficio**: DDL por motor de 3 sitios a 1; −~150 líneas; `dump/_indexes.py` reutiliza
  `metadata/*/indexes.py`; `_resolve_table` deja de construir una `BulkCrud` completa solo para reflejar.
  Rendimiento: neutro.
- **Plan de implementación**:
  1. Mover a `metadata/<motor>/` las consultas: privilegio PG, motor de almacenamiento MySQL, índice clustered y
     descubrimiento de índices SQL Server, índices Oracle/PG, definición de FK PG, identity Oracle
     (patrón de `fetch_schema_fk_references_sql`, commit `d2729f8`).
  2. `bulk/maintenance.py` con `DialectMaintenance` y el registro por motor (§ 7).
  3. Migrar `maintenance_scope` y `_hoist_constraints_for_workers` (misma política, SQL del registro).
  4. `ConstraintManager` usa las sentencias del registro y conserva su política (listeners MySQL, validación PG/Oracle).
  5. `TableReflector` (reflexión + casing) para `BulkCrud.reflect_table` y `ParallelBulkLoader._resolve_table`.
- **Tests impactados**: `tests/unit/bulk/test_maintenance_scope.py`, `test_parallel_loader_hoist.py`,
  `tests/unit/dump/test_constraints.py`, `test_indexes.py` (asertan SQL literal: cambian las rutas de import de los
  mocks, no el SQL). Validación obligatoria con `tests/integration/test_dump_engines.py` en los 5 servidores.
- **Rollback**: un commit por motor; revert individual.

### Propuesta 4: Dividir `orchestrator.py` y `batch.py` en módulos cohesivos

- **Objetivo**: ficheros con una razón de cambio; sin tocar lógica.
- **Alcance**: `dump/orchestrator.py` → `dump/_source_reader.py` (`_read_chunks`, `_execute_read`, `_prefetch`,
  `_rebatch`), `dump/_fk_graph.py` (grafo, orden, niveles, ciclos, consulta de FK por schema), `dump/_cleanup.py`,
  `dump/_audit_summary.py`, `dump/_concurrency.py`. `bulk/_execution/batch.py` → `insert_strategies.py`,
  `delete_strategies.py`, `staging_update.py`, `executors.py`, `_driver_quirks.py`.
- **Cambio incompatible**: no; `orchestrator.py` y `batch.py` re-exportan los nombres que hoy importan los tests.
- **Esfuerzo**: 1 día.
- **Beneficio**: `orchestrator.py` ≈ 1 510 → ~550 líneas; `batch.py` desaparece como fichero de 1 091. Los tests de
  grafo y de lectura dejan de importar el orquestador. Rendimiento: neutro.
- **Plan**: mover función a función con `git mv` lógico (un commit por módulo nuevo), re-exportar, ejecutar
  `python scripts/gen_arquitectura_capas.py` (no cambia paquetes de primer nivel, debe pasar sin tocar el dibujo).
- **Tests impactados**: ninguno si se mantienen los re-exports; opcionalmente actualizar imports a los módulos nuevos.
- **Rollback**: revert de los commits de movimiento.

### Propuesta 5: `BulkLoadOptions` + Protocol `DumpWriter` real

- **Objetivo**: reducir el reenvío de 7–8 parámetros en 4 sitios y sustituir el contrato muerto `BulkInserter` por
  uno que describa lo que `dump` usa.
- **Alcance**: `bulk/_models.py`, `bulk/crud.py`, `bulk/_execution/parallel_loader.py`, `dump/orchestrator.py`,
  `dump/_protocols.py`, `tests/unit/test_protocol_conformance.py`.
- **Cambio incompatible**: no (aditivo; los constructores actuales siguen). `BulkInserter` deprecado.
- **Esfuerzo**: 1–2 días.
- **Beneficio**: una opción nueva de `BulkCrud` = 1 cambio (hoy 4); `dump` depende de un contrato verificable con mypy
  como `metadata/`, `analysis/` y `doc/` (decisión 2026-09-22); `crud._table_cache` → método público
  `cached_tables()`.
- **Plan**: (1) `BulkLoadOptions` + `BulkCrud.from_options`; (2) `ParallelBulkLoader(engine, options=…, max_workers=…)`;
  (3) `DumpWriter` Protocol y conformidad en `test_protocol_conformance.py`; (4) `dump` construye un `BulkLoadOptions`
  una vez en `__init__`.
- **Tests impactados**: los que construyen `ParallelBulkLoader`/`BulkCrud` con kwargs siguen igual; nuevos tests para
  `from_options` y la conformidad.
- **Rollback**: revert; las firmas antiguas nunca se retiraron.

---

## 7. Comparativa antes/después

### Propuesta 3 — mantenimiento por motor

```python
# ANTES — la misma DDL en 3 sitios (crud.py:1224-1226, parallel_loader.py:603-610, _constraints.py:190-203)
if dialect == "mssql":
    conn.execute(text(f"ALTER TABLE {quoted_name} NOCHECK CONSTRAINT ALL"))
...
elif dialect == "mssql" and mssql_disabled:
    conn.execute(text(f"ALTER TABLE {quoted_name} WITH CHECK CHECK CONSTRAINT ALL"))
# + la consulta de privilegios de PostgreSQL copiada en crud.py:1204 y parallel_loader.py:614
```

```python
# DESPUÉS — bulk/maintenance.py
from dataclasses import dataclass
from typing import Literal, Protocol

from sqlalchemy import Connection, Table, text

from ..metadata.postgresql.tables import fetch_can_disable_triggers_sql  # Regla #1


class DialectMaintenance(Protocol):
    scope: Literal["session", "catalog"]

    def disable_sql(self, quoted_table: str) -> str: ...
    def enable_sql(self, quoted_table: str) -> str: ...
    def can_disable(self, conn: Connection, table: Table) -> bool: ...


@dataclass(frozen=True)
class _MssqlMaintenance:
    scope: Literal["session", "catalog"] = "catalog"

    def disable_sql(self, quoted_table: str) -> str:
        return f"ALTER TABLE {quoted_table} NOCHECK CONSTRAINT ALL"

    def enable_sql(self, quoted_table: str) -> str:
        return f"ALTER TABLE {quoted_table} WITH CHECK CHECK CONSTRAINT ALL"

    def can_disable(self, conn: Connection, table: Table) -> bool:
        return True


@dataclass(frozen=True)
class _PostgresMaintenance:
    scope: Literal["session", "catalog"] = "catalog"

    def disable_sql(self, quoted_table: str) -> str:
        return f"ALTER TABLE {quoted_table} DISABLE TRIGGER ALL"

    def enable_sql(self, quoted_table: str) -> str:
        return f"ALTER TABLE {quoted_table} ENABLE TRIGGER ALL"

    def can_disable(self, conn: Connection, table: Table) -> bool:
        params = {"schema": table.schema, "tbl": table.name}
        return bool(conn.execute(text(fetch_can_disable_triggers_sql()), params).scalar())


MAINTENANCE_BY_DIALECT: dict[str, DialectMaintenance] = {
    "mssql": _MssqlMaintenance(),
    "postgresql": _PostgresMaintenance(),
    "mysql": _MysqlMaintenance(),   # análoga, scope="session": SET SESSION FOREIGN_KEY_CHECKS = 0/1
    "mariadb": _MysqlMaintenance(),
    # "oracle": solo lo usa dump (DISABLE/ENABLE VALIDATE por constraint); se añade al migrar ConstraintManager
}
```

```python
# DESPUÉS — ParallelBulkLoader._hoist_constraints_for_workers (la política se queda aquí)
maintenance = MAINTENANCE_BY_DIALECT.get(self._engine.dialect.name)
if maintenance is None or maintenance.scope != "catalog":
    yield False
    return
tabla = self._reflector.reflect(tabla_destino)          # TableReflector: sin crear una BulkCrud
quoted = self._engine.dialect.identifier_preparer.format_table(tabla)
with self._engine.begin() as conn:
    if not maintenance.can_disable(conn, tabla):
        ...  # WARNING y yield False, como hoy
    conn.execute(text(maintenance.disable_sql(quoted)))
try:
    yield True
finally:
    with self._engine.begin() as conn:
        conn.execute(text(maintenance.enable_sql(quoted)))
```

### Propuesta 2 — cadencia de commit y sesión

```python
# ANTES — crud.py:1040-1060: BulkCrud manipula el estado privado de dos ejecutores
if executor._commit_every_n_chunks is not None:
    executor._chunks_since_commit = 0
    with executor._engine.connect() as conn:
        executor._active_connection = delete_executor._active_connection = conn
        executor._commit_hook = delete_executor._commit_hook = persistence.commit
        ...
        executor.rows_committed += executor._rows_pending_commit
        executor._rows_pending_commit = 0
```

```python
# DESPUÉS — bulk/_execution/session.py
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import Connection, Engine


@dataclass
class CommitCadence:
    """Commit cada ``every`` lotes; cuenta filas confirmadas y pendientes (INSERT, UPDATE y DELETE)."""

    every: int | None
    rows_committed: int = 0
    _rows_pending: int = field(default=0, init=False)
    _batches: int = field(default=0, init=False)

    def on_batch(self, rows: int) -> bool:
        """Registra un lote; ``True`` si toca commit periódico."""
        if self.every is None:
            return False
        self._rows_pending += rows
        self._batches += 1
        return self._batches >= self.every

    def on_commit(self) -> None:
        self.rows_committed += self._rows_pending
        self._rows_pending = self._batches = 0

    def discard_pending(self) -> None:
        self._rows_pending = self._batches = 0


class SessionScope:
    """Conexión compartida por los ejecutores de una ``BulkCrud`` y su política de commit."""

    def __init__(self, engine: Engine, cadence: CommitCadence) -> None:
        self._engine = engine
        self.cadence = cadence
        self.connection: Connection | None = None
        self.commit_hook: Callable[[Connection], None] | None = None

    @property
    def active(self) -> bool:
        return self.connection is not None

    @contextmanager
    def open(self, commit_hook: Callable[[Connection], None] | None = None) -> Iterator[Connection]:
        factory = self._engine.connect if self.cadence.every is not None else self._engine.begin
        with factory() as conn:
            self.connection, self.commit_hook = conn, commit_hook
            try:
                yield conn
            finally:
                self.connection = self.commit_hook = None

    def after_batch(self, conn: Connection, rows: int) -> None:
        if self.cadence.on_batch(rows):
            (self.commit_hook or Connection.commit)(conn)
            self.cadence.on_commit()
```

```python
# DESPUÉS — BulkCrud.bulk_session (extracto): sin atributos privados ajenos
scope = self._session                       # compartido por BatchStatementExecutor y DeleteBatchExecutor
with scope.open(commit_hook=persistence.commit if scope.cadence.every else None) as conn:
    persistence.start_session_audit(conn)
    yield
    ...
```

### Propuesta 1 — contadores de auditoría y capacidad del pool

```python
# ANTES — 4 campos repetidos en PartitionResult, ParallelLoadResult (4 properties), _AuditCounters (dump),
# _partition_result, BulkCrud (4 properties) y DumpAuditSummary; y dos cálculos de capacidad del pool.
audit_failures=crud.audit_failures,
audited_rows=crud.audited_rows,
unaudited_committed_rows=crud.unaudited_committed_rows,
audit_uncommitted_records=crud.audit_uncommitted_records,
```

```python
# DESPUÉS — bulk/_audit/counters.py (re-exportado en util_bbdd.bulk)
from dataclasses import asdict, astuple, dataclass
from typing import Protocol


class SupportsAuditCounters(Protocol):  # BulkCrud, ParallelLoadResult
    audit_failures: int
    audited_rows: int
    unaudited_committed_rows: int
    audit_uncommitted_records: int


@dataclass(frozen=True, slots=True)
class AuditCounters:
    audit_failures: int = 0
    audited_rows: int = 0
    unaudited_committed_rows: int = 0
    audit_uncommitted_records: int = 0

    @classmethod
    def of(cls, source: "SupportsAuditCounters") -> "AuditCounters":
        return cls(**{name: getattr(source, name) for name in cls.__dataclass_fields__})

    def __add__(self, other: "AuditCounters") -> "AuditCounters":
        return AuditCounters(*(a + b for a, b in zip(astuple(self), astuple(other), strict=True)))

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


# bulk/_execution/concurrency.py — una sola regla para bulk y dump
def pool_capacity(engine: Engine) -> int | None:
    """``size + max_overflow`` del pool, o ``None`` si no es determinable (NullPool, StaticPool, mocks)."""
```

```python
# DESPUÉS — uso
return PartitionResult(index=index, rows=rows, ..., audit=AuditCounters.of(crud))
summary = DumpAuditSummary(..., **self._audit_counters().as_dict())
```

---

## 8. Roadmap de implementación

**Antes del roadmap (fuera de este refactor)** — `/hotfix`: validar en `DumpConfig.__post_init__` `chunk_size`,
`commit_every_n_chunks`, `max_parallel_tables` y `parallel_pk_ranges` con `validate_chunk_size` y equivalentes, para
fallar **antes** de desactivar constraints y vaciar el destino. Test de regresión: el caso SQLite de § 1. Esfuerzo:
~1 h. No se mezcla con el refactor (regla de `SHARED_INSTRUCTIONS.md`).

### Fase 1 — corto plazo (pocas horas, riesgo bajo)

- Propuesta 1 completa (helpers, `AuditCounters`, `pool_capacity`, rangos vía `RangePartitioner`).
- Limpiezas menores: wrappers privados sin lógica de `crud.py`, código residual de `batch.py`, docstrings de
  `AuditManager`, anotar `crud.py:831,846`.
- Documentación: corregir `.ai/architecture.md` § bulk/dump, «Fase 5a/6a», «3 hojas», columna `"exists"` del informe,
  «Calidad actual» de `.ai/CURRENT_STATE.md`.
- Criterio de salida: `ruff`, `mypy src tests/unit/test_protocol_conformance.py`, `pytest` completo en verde; cobertura
  de `bulk/`+`dump/` ≥ 92 %.

### Fase 2 — medio plazo (1–2 días cada una, riesgo medio)

- Propuesta 4 (dividir ficheros): primero, porque abarata las demás y es mecánica.
- Propuesta 3 (`DialectMaintenance` + SQL a `metadata/`).
- Propuesta 2 (`SessionScope` + `CommitCadence`).
- Criterio de salida adicional: `tests/integration` (331 tests) en verde contra los 5 servidores del banco
  (`scripts/bench_env.example.*`); `scripts/bench_dump.py` sin regresión > 3 % en los 6 motores.

### Fase 3 — largo plazo (≈ 1 semana, opcional)

- Propuesta 5 (`BulkLoadOptions` + `DumpWriter`).
- Mover `AuditError` a `_core/exceptions.py` (conservando alias en `bulk/_audit/errors.py`) y `self.logger` en las
  clases de `dump/` y `ParallelBulkLoader`.
- Valorar una API en inglés con alias en español para `BulkCrud` (`insert_df`, `update_df`, `delete_df`), solo si se
  prevé una `v1.0`; implica deprecaciones y guía de migración en `CHANGELOG.md`.

---

## 9. Referencias

**Commits**

- `d2729f8` — `perf(dump)`: consulta de FK de todo el esquema en SQL Server movida a
  `metadata/sqlserver/constraints.py` (Q9). Precedente de la Propuesta 3.
- `53c63ea` — `perf(bulk,dump)`: `reflect_foreign_keys` (Q9). Origen de `_reflect_without_foreign_keys`.
- `642ae04`, `2f2651b` — `fix(bulk)`: `maintenance_scope` (hallazgo 8; no ocultar el error y restaurar con
  `commit_every_n_chunks`). Casos que la Propuesta 2/3 debe preservar.
- `1b072cf` — `refactor(bulk)!`: retirada de `AuditTransaction` (L-2). Precedente de cambio incompatible documentado.
- `2d99a84`, `d8df978` — `refactor(bulk)`: preparación por bloques (P-07) y por columnas (P-34).
- `3f53e0d` — `refactor(dump)`: resumen de auditoría leyendo solo lo añadido (3.4), origen de la copia de la
  conversión del CSV.

**`.ai/DECISIONS_LOG.md`**

- *2026-05-19 — `metadata/*/tables.py` como punto canónico del SQL de introspección* (Reglas #1 y #3).
- *2026-05-25 — `dump/` y `BulkInserter` Protocol*: motivo del Protocol, ya superado por la decisión siguiente.
- *2026-09-21 — Regla #6* y *2026-09-22 — capas estrictas*: `dump` (capa 7) puede importar `bulk` (capa 6); Protocols
  definidos por el consumidor verificados en `tests/unit/test_protocol_conformance.py` (modelo para `DumpWriter`).
- *2026-06-02 — Paralelismo safe: `_resolve_max_workers` acota a `pool_size`*: origen de la regla de `bulk` que
  diverge de la de `dump` (L-2).

**Otros**

- `.github/instructions/architecture.instructions.md` § Reglas #1–#6.
- `.github/SHARED_INSTRUCTIONS.md` § Logging, § Principios de diseño.
- Issues/PR relacionadas: no se encontraron en el repositorio local (PR #18 y #19 de `CURRENT_STATE.md` no tocan estas
  zonas).
