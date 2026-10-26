# 🏗️ Arquitectura de util_bbdd

**Versión:** ver `pyproject.toml` y `.ai/CURRENT_STATE.md` (estructura revisada por última vez con v0.10.0)
**Última Actualización:** Junio 2026 · capas e imports vigentes: `docs/architecture.md` (generado por `scripts/gen_arquitectura_capas.py`)
**Estado:** Estable | Completamente Refactorizado
**Motores Soportados:** MariaDB • MySQL • PostgreSQL • Oracle • SQLite • HSQLDB • SQL Server

---

## Visión General

**util_bbdd** es una librería que proporciona abstracción unificada para operaciones con múltiples motores de base de datos:

- **Jerarquía de 3 niveles**: Foundation → Services → Specialization
- **API moderna**: Managers sync/async con soporte nativo para async/await
- **Type-safe**: Full type hints con validación en tiempo de desarrollo
- **Modular**: Cada componente tiene responsabilidad única y clara
- **Metadata canónica**: `metadata/` es el único punto con SQL de catálogo e `Inspector`; se lee por lotes con `CatalogSource`/`SchemaSnapshot` y el SQL de cada motor vive en `metadata/<motor>/catalog.py` (ADR-003; Reglas #1–#6, `architecture.instructions.md`)

---

## Estructura Modular (3 niveles)

```
📦 util_bbdd
│
├─── LEVEL 1: ABSTRACCIONES (Foundation Layer)
│
│    _core/                          ⭐ Core abstractions
│    ├── types.py                    # Type aliases
│    ├── exceptions.py               # DatabaseException y jerarquía completa
│    ├── contracts.py                # Protocols base
│    └── constants.py                # Enums compartidos
│
│    _drivers/                       🔌 Detección de drivers
│    ├── validator.py                # DatabaseTypeValidator
│    ├── driver_validator.py         # DriverValidator
│    └── _config_loader.py
│
│    core/
│    └── capabilities.py             # Capacidades por motor
│
│    models.py                       # Modelos de dominio compartidos (módulo raíz, sin imports de la librería)
│    async_utils.py                  # maybe_await (módulo raíz, sin imports de la librería)
│
├─── LEVEL 2: SERVICIOS (Services Layer)
│
│    connection/                     🔌 Gestión de conexiones
│    ├── factory.py                  # ConnectFactory
│    ├── builder.py                  # build_conn_params()
│    ├── protocols.py
│    ├── close.py                    # cierre común; SyncPoolCloseMixin (pools sync)
│    ├── config.py                   # *Config/*PoolConfig: fuente única de claves y defaults de conn_params (ADR-005)
│    ├── params.py                   # ConnectionParamsManager.allowed_keys / prepare_and_validate (sync y async)
│    ├── _aiomysql.py                # traducción única config → aiomysql.connect (MariaDB y MySQL, TLS)
│    └── <motor>/                    # mariadb (Connector/Python + aiomysql), mysql (PyMySQL + QueuePool + aiomysql),
│                                    # postgresql, oracle, sqlite, hsqldb, sqlserver
│
│    query/                          ❓ Registry y ejecución
│    ├── registry.py                 # QueryRegistry
│    ├── resolver.py                 # QueryResolver
│    └── queries.py                  # DatabaseQueries
│
│    executors/                      ⚡ Ejecución de queries
│    ├── base.py
│    ├── sync_query_executor.py
│    └── async_query_executor.py
│
│    metadata/                       🔍 Lectura del catálogo (ADR-003)
│    ├── source.py                   # CatalogSource: una consulta por tipo de objeto → SchemaSnapshot
│    ├── model.py                    # SchemaSnapshot y modelos neutros
│    ├── snapshot_cache.py           # Caché LRU por schema
│    ├── catalog_registry.py         # CatalogDialect por motor
│    ├── reflection.py               # SQLAlchemy por lotes (comparar, dump, bulk)
│    ├── facts.py / ddl.py / storage.py  # consultas puntuales, DDL, inventario de almacenamiento
│    ├── contracts.py                # MetadataSource, CatalogDialect, Sync/AsyncMetadataProvider
│    └── hsqldb/ mariadb/ oracle/ postgresql/ sqlite/ sqlserver/
│        └── catalog.py              # ← SQL de catálogo del motor (único punto canónico de introspección)
│
│    results/                        📋 Tipos de retorno
│    └── types.py, normalizer.py
│
│    factory/                        🏭 SQLAlchemy engines
│    ├── pool_factory.py, sqlalchemy_engine_factory.py, async_sqlalchemy_engine_factory.py
│    ├── _url.py                     # URL con credenciales escapadas, redacción para logs, test query
│    └── _pool_policy.py             # política de pool común de los Engine sync/async (ADR-005)
│
│    validators/                     ✓ Validadores de queries
│
│    progress/                       ⏱ Progreso y cancelación cooperativa (capa 2; solo importa _core)
│    ├── events.py                   # ProgressEvent
│    ├── contracts.py                # ProgressCallback
│    ├── cancellation.py             # CancellationToken (lanza OperationCancelledError)
│    └── reporter.py                 # ProgressReporter: emitir y comprobar la cancelación dentro de las operaciones
│
│    audit/                          🧾 Auditoría de bulk, dump y migrate (capa 3; solo importa _core)
│    ├── events.py                   # AuditEvent: modelo de evento común
│    ├── contracts.py                # AuditSink (escritura) y AuditEventSource (lectura)
│    ├── sinks.py                    # NullAuditSink, MemoryAuditSink, JsonLinesAuditSink
│    ├── legacy_csv.py               # CSV de auditoría de bulk (formato congelado) + read_since para dump
│    ├── rejects.py                  # CSV de filas rechazadas (formato congelado)
│    ├── analytics.py, exporters.py  # estadísticas y Excel/JSON/HTML del CSV
│    ├── counters.py                 # AuditCounters (4 contadores sumables)
│    └── locks.py, files.py, text.py # lock por ruta (registro único), ficheros, saneado de texto
│                                    # Adaptadores a AuditEvent en cada consumidor: bulk/_audit/events.py,
│                                    #   dump/_audit_events.py, migrate/_audit_events.py (ADR-002)
│
├─── LEVEL 3: ESPECIALIZACIÓN (Specialization Layer)
│
│    managers/                       🎛️ API pública principal
│    ├── sync_mgr.py                 # SyncDatabaseManager
│    └── async_mgr.py                # AsyncDatabaseManager
│
│    bulk/                           📦 Operaciones masivas
│    ├── crud.py                     # BulkCrud — INSERT/UPDATE/DELETE, bulk_session, maintenance_scope, sync_pk_sequences;
│    │                               # con ParallelOptions, bulk_*_from_df delega en ParallelBulkLoader (v3.0.0)
│    ├── options.py                  # Paquetes de opciones (v3.0.0): Batch/Audit/Reject/Execution/Parallel/RetryOptions,
│    │                               # BulkOptions.for_worker (opciones de los workers, sin parallel)
│    ├── audit.py                    # AuditManager (fachada de _audit/)
│    ├── normalize.py                # Normalización de registros y DataFrames para SQL
│    ├── _models.py                  # PKSyncResult
│    ├── _execution/
│    │   ├── executors.py            # BatchStatementExecutor, DeleteBatchExecutor (cadencia de commit)
│    │   ├── session.py              # SessionScope (conexión de bulk_session) + CommitCadence (commit_every_n_chunks)
│    │   ├── insert_strategies.py    # InsertStrategyResolver + estrategias (COPY, execute_values, multi-fila, executemany)
│    │   ├── delete_strategies.py    # DeleteStrategyResolver + estrategias (ANY/unnest en PG, IN troceado)
│    │   ├── staging_update.py       # MySQLStagingUpdateStrategy (UPDATE por tabla temporal)
│    │   ├── _driver_quirks.py       # decimal de pyodbc/pymssql, fast_executemany, límites de parámetros
│    │   ├── batch.py                # Fachada de compatibilidad (re-exporta los módulos anteriores)
│    │   ├── parallel_loader.py      # ParallelBulkLoader — carga paralela por particiones (mecanismo)
│    │   ├── parallel_planner.py     # ParallelPlanner — hilos por motor/operación/volumen (política pura, RULES medidas)
│    │   └── range_partitioner.py    # RangePartitioner (PK entera/datetime, validate_disjoint) + HashPartitioner
│    │                               # (str/UUID/PK compuesta)
│    ├── _support/                   # pk_sync (PKSequenceSyncer), sql_helpers (generar_sql), validation, persistence,
│    │                               # sql_quoting, dialect (MYSQL_FAMILY), excel (H12), iterables, table_utils
│    └── _audit/                     # repository (CSV), service, exporters, record, counters, errors
│    # MySQLVariableValidator + MySQLOptimalConfig viven en connection/mariadb/
│
│    comparar/                       🔍 Comparación de esquemas
│    ├── comparator.py               # SchemaComparator (cross-engine case-insensitive)
│    ├── contracts.py
│    ├── models.py                   # SchemaDiff
│    └── reporters/                  # HTML (Jinja2+Mermaid), Excel, Word, Markdown, SQL, Text
│
│    dump/                           📤 Volcado entre motores (v0.8.0+)
│    ├── orchestrator.py             # DumpOrchestrator (sin SchemaComparator en hot-path)
│    ├── _source_reader.py           # Lectura del origen: cursor por driver, prefetch (Q3), reagrupado de lotes (Q5)
│    ├── _fk_graph.py                # Grafo FK, orden topológico, niveles y ciclos
│    ├── _audit_summary.py           # Resumen del CSV de auditoría de bulk (DumpAuditSummary)
│    ├── _constraints.py             # ConstraintManager (PG savepoints, Oracle batch, SS NOCHECK)
│    ├── _indexes.py                 # IndexManager (índices secundarios no únicos)
│    ├── _models.py                  # DumpConfig, DumpResult, DumpAuditSummary, ConstraintResult, IndexActionResult
│    ├── _sql_utils.py               # Quoting (re-exporta bulk/_support/sql_quoting)
│    └── reporters.py                # DumpReporter (Excel)
│
│    migrate/                        🔄 Migración DDL (v0.8.0+, 4×3 = 12 flujos)
│    ├── planner.py                  # MigrationPlanner
│    ├── ir/models.py                # CanonicalTable, CanonicalView, CanonicalRoutine, MigrationPlan
│    ├── extractors/                 # OracleSchemaExtractor, MariaDBSchemaExtractor, PostgreSQLSchemaExtractor, SQLServerSchemaExtractor
│    ├── transformers/               # 12 transformers (origen×destino)
│    ├── emitters/                   # OracleDDLEmitter, MariaDBDDLEmitter, PostgreSQLDDLEmitter, SQLServerDDLEmitter
│    ├── _compat/                    # type_map_*.py (12 mapas de tipos)
│    ├── charset.py                  # DEFAULT_COLLATION = utf8mb4_uca1400_ai_ci (MariaDB ≥10.10)
│    └── reporters/                  # format_plan_markdown, format_plan_text (con rutinas y body)
│
│    analysis/                       📊 Grafos de relaciones
│    ├── base.py                     # GraphDocument, traversal multinivel
│    ├── graphviz.py + graphviz_ext.py
│    └── matplotlib_graph.py
│
│    doc/                            📄 Documentación de BD
│    └── (Jinja2 templates → HTML/Word/Excel)
│
│    __init__.py                     # API pública (re-exports); módulo raíz sin nivel
│    docs_build_plugin.py            # Plugin MkDocs: documentation_zip (ZIP + SHA256); fuera de la librería
```

---

## Capas (Regla #6)

Cada nivel se divide en capas numeradas. Un paquete importa **solo de paquetes de capas de número menor**; los de
una misma capa son independientes entre sí. La fuente ejecutable de esta tabla es `LAYER` en
`scripts/gen_arquitectura_capas.py` (de ella se derivan el nivel de cada paquete, la figura y la tabla de
`docs/architecture.md`); esta copia hay que mantenerla a mano.

| Capa | Nivel | Paquetes |
|---|---|---|
| 7 | Level 3 · Especialización | `doc/`, `dump/` |
| 6 | Level 3 · Especialización | `analysis/`, `bulk/`, `comparar/`, `managers/`, `migrate/` |
| 5 | Level 2 · Servicios | `executors/`, `factory/`, `metadata/` |
| 4 | Level 2 · Servicios | `connection/`, `query/` |
| 3 | Level 2 · Servicios | `audit/`, `results/`, `validators/` |
| 2 | Level 1 · Foundation | `_drivers/` |
| 1 | Level 1 · Foundation | `_core/`, `core/`, `models.py`, `async_utils.py` |

Las capas se asignan por función, no por la profundidad que tenga hoy el grafo de imports: `comparar/` apenas
importa nada de la librería, pero es Especialización.

---

## Reglas de dependencia (NO violar)

| Regla | Descripción |
|---|---|
| Un paquete importa solo de capas de número menor | Los paquetes de una misma capa son independientes; ver § Capas |
| Level 1 → no importa Level 2/3 | Foundation nunca depende de servicios |
| Level 2 → no importa Level 3 | Services no importa managers ni bulk |
| Level 3 → importa Level 1+2 y capas inferiores de Level 3 | Specialization construye sobre la base |
| `metadata/` = único punto con SQL de catálogo e `Inspector` (ADR-003) | Ningún módulo duplica SQL de introspección; guarda `test_architecture_metadata_rules.py` |
| Sin ciclos de importación | Consecuencia de las capas; los imports perezosos cuentan. Guarda: `tests/unit/test_architecture_import_rules.py` |

---

## APIs Públicas (importes recomendados)

```python
# Raíz (API 3.x; mismos 13 puntos desde v0.43.0): 13 puntos de entrada y sus resultados; el resto, en su submódulo público
from util_bbdd import (
    SyncDatabaseManager, AsyncDatabaseManager,
    BulkCrud, ParallelBulkLoader,
    DumpOrchestrator, DumpConfig, DumpResult,
    MigrationPlanner, MigrationPlan,
    SchemaComparator, SchemaDiff,
    DatabaseDocumentation, DatabaseException,
)
from util_bbdd.metadata import SyncMetadataProvider, AsyncMetadataProvider
from util_bbdd.connection import build_conn_params
from util_bbdd.factory import ConnectionFactory, PoolFactory
from util_bbdd.async_utils import maybe_await

# Bulk operations
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader, AuditManager, PKSequenceSyncer
from util_bbdd.bulk import RangePartitioner, HashPartitioner

# Migration DDL
from util_bbdd.migrate import MigrationPlanner, MigrationPlan

# Dump
from util_bbdd.dump import DumpOrchestrator, DumpConfig, DumpResult

# Exceptions (fuente canónica: _core/exceptions.py)
from util_bbdd.exceptions import DatabaseException, ConnectionError, QueryError, ValidationError
```

---

## Decisiones Arquitectónicas Clave

| ID | Decisión | Motivo |
|---|---|---|
| D1 | 3 niveles en lugar de 1/2 | Separación de concerns; Foundation estable, Specialization evoluciona |
| D2 | `metadata/` punto canónico, lectura por lotes (ADR-003) | Evitar SQL de introspección duplicado y lecturas O(tablas) |
| D3 | Managers en Level 3 | Dependen de TODOS los servicios Level 2; ponerlos en Level 2 causaría ciclos |
| D4 | InsertStrategyResolver | Elegir fast-path (COPY/multi-fila/executemany) sin modificar la API de BulkCrud |
| D5 | DumpOrchestrator sin SchemaComparator en hot-path | Eliminar cascada N+1 queries; skipped_columns se calcula en _common_columns |
| D6 | utf8mb4_uca1400_ai_ci por defecto (MariaDB ≥10.10) | Mejora de UCA 1400; utf8mb4_unicode_ci sigue siendo opción válida para versiones anteriores |
| D7 | PKSequenceSyncer post-bulk | Evitar errores de PK duplicada tras INSERT masivo sin IDENTITY/SERIAL |
| D8 | MigrationPlanner pass-through v1 para rutinas | Las rutinas se extraen con su DDL original; transformación semántica es revisión manual |
| D9 | Conexiones multimotor (ADR-005): `conn_params` validados desde las `*Config` en sync y async; política de pool común de los Engine; `catalog_charset_mode`; TLS en MariaDB | Una sola definición por parámetro y el mismo comportamiento en los dos caminos de conexión (nativo y Engine) |

---

*Documento actualizado: Junio 2026 - alineado a v0.10.0; `connection/` y `factory/` revisados el 2026-10-09 (v0.39.1); imports de la API 1.0 revisados el 2026-10-10 (v0.43.0)*
