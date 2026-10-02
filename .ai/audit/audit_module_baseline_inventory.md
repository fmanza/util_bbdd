# Inventario de partida — auditoría en `bulk/`, `dump/` y `migrate/`

Línea base **mínima** que el nuevo módulo de auditoría centralizado debe cubrir (o justificar
por qué un elemento se queda en su módulo de origen). Lo consume
[`.github/prompts/audit_module.prompt.md`](../../.github/prompts/audit_module.prompt.md).

- **Fecha del inventario**: 2026-10-02 · versión `0.28.0` (`develop`, commit `12d055c`).
- **Alcance**: solo `src/util_bbdd/bulk`, `src/util_bbdd/dump` y `src/util_bbdd/migrate`.
- **Las referencias `archivo:línea` son de esta fecha**: en PLAN, re-verifícalas contra el árbol real
  antes de citarlas (el código cambia a diario).

Identificadores: `INV-<módulo>-NN`. La matriz de cobertura del PLAN debe recorrerlos todos.

---

## 1. `bulk/` — rastro de operaciones (CSV de auditoría)

| ID | Qué existe hoy | Dónde |
|---|---|---|
| INV-BLK-01 | Fachada pública `AuditManager` (repository + service + exporters). Exportada en `util_bbdd.bulk`. | `bulk/audit.py:36`, `bulk/__init__.py:15` |
| INV-BLK-02 | Registro `AuditRecord` (frozen, slots): `tabla`, `motor`, `operacion`, `rowcount`, `elapsed`, `genero_sql`, `timestamp` (fin de la operación, no de la escritura). `AUDIT_OPERATIONS = (INSERT, UPDATE, DELETE)`. | `bulk/_audit/record.py` |
| INV-BLK-03 | **Formato del CSV (contrato de facto)**: UTF-8, separador tabulador, 7 columnas fijas `timestamp, tabla, motor, operacion, total_filas, tiempo_seg, sql`; `timestamp` `%Y-%m-%d %H:%M:%S` (truncado al segundo, sin zona); `tiempo_seg` con coma decimal; `sql` = `Sí`/`No`. Cabecera si el fichero está vacío (`tell()==0`, H4). | `bulk/_audit/repository.py` (`escribir_registros`) |
| INV-BLK-04 | `rowcount` = filas **enviadas** (`len(df)`), no las afectadas según la BD. | `bulk/audit.py` (`registrar_operacion`, docstring) |
| INV-BLK-05 | Validación de parámetros (`tabla`/`motor` no vacíos, operación válida, `rowcount` int ≥ 0, `elapsed` ≥ 0) → `AuditValidationError`. | `bulk/audit.py` (`_validar_parametros_operacion`) |
| INV-BLK-06 | Auditoría deshabilitada con `audit_csv_path=None`: un único WARNING por instancia; `warn_if_disabled=False` para quien crea muchas instancias (loader, dump). | `bulk/audit.py` (`__init__`, `registrar_operacion`) |
| INV-BLK-07 | Concurrencia: lock por ruta a nivel de proceso (`_FILE_LOCKS`, clave `normcase(abspath)`), cacheado por instancia. **Solo intra-proceso** (sin lock entre procesos). | `bulk/_audit/repository.py` (`_get_file_lock`, `_file_lock`) |
| INV-BLK-08 | Cabecera ajena → el fichero se aparta como `<nombre>.invalid-<fecha><ext>` (sufijo `_2`, `_3`…) con WARNING; validación una vez por (ruta, columnas). | `bulk/_audit/repository.py` (`_asegurar_cabecera`, `_ruta_apartado`) |
| INV-BLK-09 | Lectura con caché (TTL + firma `(st_mtime_ns, st_size)` para detectar escrituras de otras instancias, H6); `parse_frame` reutilizado por `dump`. | `bulk/_audit/repository.py` (`leer_auditoria`, `parse_frame`, `es_cache_valido`) |
| INV-BLK-10 | Analítica: estadísticas globales, conteos por tipo/tabla, operaciones lentas, filtros (operación, tabla, motor, rango temporal, múltiple), agrupaciones para informes. | `bulk/_audit/service.py` |
| INV-BLK-11 | Exportadores: Excel (`agrupar_por` tabla/fecha/tabla_fecha), JSON y HTML (plantilla `string.Template`, tablas con `DataFrame.to_html`). Fallo de escritura → `AuditExportError` (también `OSError`). | `bulk/_audit/exporters.py`, `bulk/_audit/html_template.py` |
| INV-BLK-12 | Setter obsoleto `AuditManager.columnas_auditoria` (`DeprecationWarning`, H7): retirada prevista en la próxima versión menor. | `bulk/audit.py` |
| INV-BLK-13 | Auditoría diferida de `bulk_session`: se acumula y se escribe al confirmar el commit; `audit_strict=True` escribe **antes** del commit. Commits periódicos (`commit_every_n_chunks`) vuelcan por tandas. | `bulk/_support/persistence.py` (`BulkPersistenceManager`, `start_session_audit`, `flush_audit_*`, `end_session_audit`), `bulk/crud.py` (`bulk_session`) |
| INV-BLK-14 | Política de fallo: `audit_strict=False` (default) registra ERROR con los datos perdidos y cuenta `audit_failures`, sin relanzar (relanzar invitaría a duplicar la carga); `True` propaga `AuditError`/`OSError`. | `bulk/_support/persistence.py`, `bulk/crud.py` (constructor, `audit_strict`) |
| INV-BLK-15 | Contadores: `audit_failures`, `audited_rows`, `unaudited_committed_rows`, `audit_uncommitted_records` (propiedades de `BulkCrud`). | `bulk/crud.py` (propiedades), `bulk/_support/persistence.py` |
| INV-BLK-16 | Valor sumable `AuditCounters` + `Protocol` `SupportsAuditCounters` (lo usan `ParallelBulkLoader` y `dump`). | `bulk/_audit/counters.py` |
| INV-BLK-17 | `ParallelBulkLoader`: una `AuditManager` por partición sobre el mismo CSV; contadores por `PartitionResult` y agregados en `ParallelLoadResult`. **Invariante de conciliación**: con auditoría activa, sin `audit_failures`, sin `audit_uncommitted_records` y sin `partition_errors` → `audited_rows + rows_rejected + unaudited_committed_rows == total_rows`. | `bulk/_execution/parallel_loader.py` (`PartitionResult`, `ParallelLoadResult`) |
| INV-BLK-18 | `generar_sql=True`: las operaciones no tocan la BD, se escriben ficheros SQL y se auditan al momento con `sql=Sí`. | `bulk/_support/persistence.py` (`persist_sql`, `register_operation`) |
| INV-BLK-19 | `PKSyncResult` (resincronización de secuencias/identidades tras la carga). | `bulk/_models.py:10` |

## 2. `bulk/` — rechazos (`on_error="isolate"`)

| ID | Qué existe hoy | Dónde |
|---|---|---|
| INV-REJ-01 | `RejectsWriter`: CSV UTF-8 con tabulador, columnas `REJECT_COLUMNS = (timestamp, tabla, operacion, particion, fila, error, valores)`. Solo se escribe si el usuario da `rejects_csv_path` (contiene datos de filas). | `bulk/_support/rejects.py` |
| INV-REJ-02 | Neutralización de fórmulas (CSV injection): prefijos `= + - @ \t \r` → apóstrofo delante. | `bulk/_support/rejects.py` (`_safe_cell`) |
| INV-REJ-03 | Reutiliza el lock por ruta de la auditoría y el apartado de ficheros con cabecera ajena. **Hoy `rejects` importa un símbolo privado** (`_get_file_lock`) de `_audit.repository`. | `bulk/_support/rejects.py` (imports) |
| INV-REJ-04 | `Isolator` (bisección con SAVEPOINT; errores aislables `IntegrityError`/`DataError`), `max_rejects` (presupuesto), `rejects_scope` (posición y presupuesto comunes a varias operaciones, `partition`, `row_offset`), `rows_rejected`. Nota `_REJECTS_FAILURE_NOTE` para distinguir el fallo del CSV de rechazos del de auditoría. | `bulk/_support/rejects.py`, `bulk/crud.py` (`rejects_scope`, `_REJECTS_FAILURE_NOTE`) |
| INV-REJ-05 | Validación común `validate_isolation` y `optional_non_negative_int` (acepta enteros de numpy). | `bulk/_support/rejects.py` |

## 3. `dump/` — auditoría del volcado

| ID | Qué existe hoy | Dónde |
|---|---|---|
| INV-DMP-01 | `DumpConfig.bulk_audit_path` / `bulk_audit_strict` / `on_error` / `rejects_csv_path` / `max_rejects`, propagados a cada `BulkCrud` y `ParallelBulkLoader`. | `dump/_models.py` (`DumpConfig`), `dump/orchestrator.py` (kwargs de `BulkCrud`) |
| INV-DMP-02 | Un solo aviso «auditoría deshabilitada» por volcado (instancias internas con `warn_if_audit_disabled=False`). | `dump/orchestrator.py` (`run`, creación de `BulkCrud`) |
| INV-DMP-03 | Agregación de contadores de todas las `BulkCrud` y loaders del volcado con lock (`_audit_lock`, `_audit_cruds`, `_loader_audit`). | `dump/orchestrator.py` (`_reset_audit_tracking`, `_audit_counters`) |
| INV-DMP-04 | `DumpAuditSummary`: totales del CSV desde el inicio del volcado + los 4 contadores; se devuelve aunque no haya entradas si hay incidencias. | `dump/_models.py` (`DumpAuditSummary`), `dump/_audit_summary.py` (`build_audit_summary`) |
| INV-DMP-05 | Lectura incremental del CSV (solo la cola desde el tamaño inicial, PF-08) con detección de fichero distinto por `(st_dev, st_ino)` y recuperación si se empezó a mitad de fila. | `dump/_audit_summary.py` (`read_audit_csv`, `file_size`, `file_identity`) |
| INV-DMP-06 | Filtro por `timestamp >= desde` con el inicio truncado al segundo (H3); WARNING si las filas del CSV ≠ `audited_rows` (otros procesos en el mismo CSV o registros sin commit). | `dump/_audit_summary.py` (`build_audit_summary`) |
| INV-DMP-07 | **Acoplamiento actual**: `dump` importa `AuditCsvRepository` (privado) y `AuditManager` de `bulk`. | `dump/_audit_summary.py` (imports), `dump/orchestrator.py` (imports) |
| INV-DMP-08 | Informe Excel `DumpReporter`: hojas fijas «Auditoría Tablas», «Tablas Faltantes», «Columnas Inexistentes»; opcionales «Índices», «Auditoría Bulk», «Secuencias PK» (las opcionales siempre al final). | `dump/reporters.py` |
| INV-DMP-09 | Resultados por elemento: `TableDumpResult` (status, filas origen/destino antes/después, columnas omitidas, ciclo, `rows_rejected`), `ConstraintResult` (`enabled`/`failed`/`unverified`), `IndexActionResult` (`rebuilt`/`recreated`/`failed`/`unsupported`), `PKSyncResult`; `DumpResult.rows_rejected`. | `dump/_models.py` |
| INV-DMP-10 | Si el resumen o el Excel fallan, el volcado no aborta: WARNING/ERROR y `audit_summary=None` / sin informe. | `dump/orchestrator.py` (`run`) |

## 4. `migrate/` — trazabilidad de la migración DDL

| ID | Qué existe hoy | Dónde |
|---|---|---|
| INV-MIG-01 | `MigrationWarning` (frozen): `table`, `column`, `category` (`WarningCategory`, 11 valores), `target_type`, `message`, `severity` (`INFO`/`WARNING`/`ERROR`), `source_type`, `proposals`, `code` (`WarningCode`, subtipos estables). | `migrate/ir/models.py` (`WarningSeverity`, `WarningCategory`, `WarningCode`, `MigrationWarning`) |
| INV-MIG-02 | Recolección de avisos de tablas, columnas, vistas y rutinas en el plan; avisos de colisión por mayúsculas con severidad por motor destino; tabla sin columnas activas → ERROR. | `migrate/planner.py` (`_build_plan`, `_case_collision_warnings`) |
| INV-MIG-03 | Avisos descubiertos durante la emisión se sincronizan en `plan.warnings` sin duplicar (`_sync_warnings_from_tables`). | `migrate/ir/models.py` (`MigrationPlan`) |
| INV-MIG-04 | Puerta de calidad: `MigrationPlan.execute` se niega si `error_count > 0` (`ValueError`); contadores `error_count`, `warning_count`, `info_count`. | `migrate/ir/models.py` (`execute`, propiedades) |
| INV-MIG-05 | Ejecución sentencia a sentencia con commit por sentencia; un fallo lanza `DatabaseOperationError` con posición `n/N`, primera línea útil y código `MIGRATE_EXECUTE`. **No queda registro persistente de qué sentencias se aplicaron.** | `migrate/ir/models.py` (`_execute_statements`) |
| INV-MIG-06 | `ViewValidationResult` (`valid`, `method` `transaction`/`syntax`/`none`, `error`). | `migrate/views/validation.py` |
| INV-MIG-07 | Informes del plan en texto y Markdown (secciones por severidad, tablas, rutinas). | `migrate/reporters/text.py`, `migrate/reporters/markdown.py` |

## 5. Transversal

| ID | Qué existe hoy | Dónde |
|---|---|---|
| INV-X-01 | Jerarquía `AuditError(DatabaseException)` → `AuditConfigError` (+`ValueError`), `AuditFileError`, `AuditDataError`, `AuditExportError` (+`OSError`), `AuditValidationError`; re-exportadas en `bulk/_audit/errors.py` y en la API raíz. | `_core/exceptions.py`, `__init__.py` |
| INV-X-02 | Capas (Regla #6): `bulk`=6, `migrate`=6, `dump`=7. Un módulo que consuman los tres debe estar en capa ≤ 5 y no puede importar ninguno de ellos. | `scripts/gen_arquitectura_capas.py` (`LAYER`), `.github/instructions/architecture.instructions.md` |
| INV-X-03 | Tests que fijan el comportamiento actual (deben seguir pasando sin cambios salvo los imports que el ADR declare): `tests/unit/test_audit_subsystem.py`, `tests/unit/test_audit_excel_export.py`, `tests/unit/test_bulk_internal_helpers.py`, `tests/unit/bulk/test_audit_*.py`, `tests/unit/bulk/test_parallel_loader_audit*.py`, `tests/unit/bulk/test_on_error_isolate.py`, `tests/unit/bulk/test_parallel_loader_isolate.py`, `tests/unit/dump/test_audit_summary_offset.py`, `tests/unit/dump/test_orchestrator.py`, `tests/unit/dump/test_reporters.py`, `tests/unit/migrate/test_planner.py`, `tests/unit/migrate/test_reporters.py`; integración `tests/integration/test_bulk_audit_20261001.py`. | `tests/` |
| INV-X-04 | Documentación existente: `docs/functional/bulk_audit.md`, `docs/api/bulk_audit.md`, `docs/api/dump_reporter.md`, `docs/api/exceptions.md`. | `docs/` |

---

## Huecos observados (candidatos, no requisitos)

Hechos verificados que el PLAN debe valorar; incorporarlos o descartarlos con motivo.

- **H-01** No hay un modelo de evento común: `AuditRecord`, filas de rechazo, `*Result` de `dump` y
  `MigrationWarning` describen lo mismo (qué, dónde, cuándo, resultado) con formas distintas.
- **H-02** Sin identificador de correlación: las filas del CSV no se pueden atribuir a un volcado
  o a una carga paralela concreta; `dump` lo aproxima por tiempo y desplazamiento (INV-DMP-05/06).
- **H-03** `migrate` no deja rastro persistente del plan ni de la ejecución (INV-MIG-05).
- **H-04** `timestamp` sin zona horaria y truncado al segundo; `tiempo_seg` con coma decimal
  (dependiente de configuración regional). Cambiarlo rompería el CSV actual: solo en un formato nuevo.
- **H-05** El lock es solo intra-proceso; dos procesos sobre el mismo CSV pueden intercalar filas.
- **H-06** Acoplamiento a privados entre módulos (INV-REJ-03, INV-DMP-07).
- **H-07** Pendiente de verificar: neutralización de fórmulas en el Excel/JSON/HTML de `AuditManager`
  (solo consta en el CSV de rechazos) y escape de los valores sustituidos en la plantilla HTML.
