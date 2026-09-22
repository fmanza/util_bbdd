# 🏗️ Arquitectura de util_bbdd

**Versión:** 0.10.0
**Última Actualización:** Junio 2026
**Estado:** Estable | Completamente Refactorizado
**Motores Soportados:** MariaDB • MySQL • PostgreSQL • Oracle • SQLite • HSQLDB • SQL Server • Redshift • Snowflake

---

## Visión General

**util_bbdd** es una librería que proporciona abstracción unificada para operaciones con múltiples motores de base de datos:

- **Jerarquía de 3 niveles**: Foundation → Services → Specialization
- **API moderna**: Managers sync/async con soporte nativo para async/await
- **Type-safe**: Full type hints con validación en tiempo de desarrollo
- **Modular**: Cada componente tiene responsabilidad única y clara
- **Metadata canónica**: `metadata/*/tables.py` es el único punto autorizado para SQL de introspección (Regla #1–#6, `architecture.instructions.md`)

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
│    ├── close.py
│    └── motors/                     # Adaptadores: mariadb, postgresql, oracle, sqlite, hsqldb, sqlserver
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
│    metadata/                       🔍 Esquemas y caché
│    ├── cache.py                    # DatabaseMetadataCache + RelationshipMetadataCache
│    ├── normalizer.py
│    ├── builder.py
│    ├── fetcher.py
│    ├── manager.py                  # MetadataManager
│    ├── contracts.py
│    ├── mariadb/ mysql/ oracle/ postgresql/ sqlserver/ sqlite/
│    │   └── tables.py               # ← ÚNICO punto canónico de SQL de introspección
│    └── providers/                  # SyncMetadataProvider / AsyncMetadataProvider
│
│    results/                        📋 Tipos de retorno
│    └── types.py, normalizer.py
│
│    factory/                        🏭 SQLAlchemy engines
│    └── pool_factory.py, sqlalchemy_engine_factory.py, async_sqlalchemy_engine_factory.py
│
│    validators/                     ✓ Validadores de queries
│
├─── LEVEL 3: ESPECIALIZACIÓN (Specialization Layer)
│
│    managers/                       🎛️ API pública principal
│    ├── sync_mgr.py                 # SyncDatabaseManager
│    └── async_mgr.py                # AsyncDatabaseManager
│
│    bulk/                           📦 Operaciones masivas
│    ├── crud.py                     # BulkCrud — INSERT/UPDATE/DELETE + maintenance_scope
│    ├── audit.py                    # AuditManager, AuditTransaction (thread-safe en paralelo)
│    ├── normalize.py                # Normalización de registros
│    ├── parallel.py                 # ParallelBulkLoader — carga paralela por particiones
│    ├── partition.py                # RangePartitioner (PK entera/datetime) + HashPartitioner (str/UUID)
│    ├── strategies/                 # InsertStrategyResolver — selección automática de fast-path
│    │   ├── postgres_copy.py        # PostgresCopyStrategy (~10× vía psycopg3 COPY)
│    │   ├── mysql_multirow.py       # MySQLMultiRowInsertStrategy (multi-fila + SQL template cache)
│    │   └── default.py              # Fallback executemany
│    ├── pk_sync.py                  # PKSequenceSyncer + PKSyncResult
│    └── mysql_variables.py          # MySQLVariableValidator + MySQLOptimalConfig
│
│    comparar/                       🔍 Comparación de esquemas
│    ├── comparator.py               # SchemaComparator (cross-engine case-insensitive)
│    ├── contracts.py
│    ├── models.py                   # SchemaDiff
│    └── reporters/                  # HTML (Jinja2+Mermaid), Excel, Word, Markdown, SQL, Text
│
│    dump/                           📤 Volcado entre motores (v0.8.0+)
│    ├── orchestrator.py             # DumpOrchestrator (sin SchemaComparator en hot-path)
│    ├── _constraints.py             # ConstraintManager (PG savepoints, Oracle batch, SS NOCHECK)
│    ├── _models.py                  # DumpConfig, DumpResult, DumpAuditSummary, ConstraintResult
│    ├── _protocols.py               # BulkInserter Protocol
│    ├── _sql_utils.py               # Quoting helpers
│    ├── reporters.py                # DumpReporter (Excel + texto)
│    └── (index_manager, parallel)   # IndexManager, paralelización FK-topológica
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
| 3 | Level 2 · Servicios | `results/`, `validators/` |
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
| `metadata/*/tables.py` = único punto canónico SQL | Ningún módulo duplica SQL de introspección |
| Sin ciclos de importación | Consecuencia de las capas; los imports perezosos cuentan. Guarda: `tests/unit/test_architecture_import_rules.py` |

---

## APIs Públicas (importes recomendados)

```python
from util_bbdd import (
    SyncDatabaseManager, AsyncDatabaseManager,
    DatabaseMetadataCache, RelationshipMetadataCache,
    SyncMetadataProvider, AsyncMetadataProvider,
    SchemaComparator, SchemaDiff,
    ConnectionFactory, PoolFactory, build_conn_params,
    maybe_await,
)

# Bulk operations
from util_bbdd.bulk import BulkCrud, ParallelBulkLoader, AuditManager, PKSequenceSyncer
from util_bbdd.bulk import RangePartitioner, HashPartitioner

# Migration DDL
from util_bbdd.migrate import MigrationPlanner, MigrationPlan

# Dump
from util_bbdd.dump import DumpOrchestrator, DumpConfig, DumpResult

# Exceptions (fuente canónica: _core/exceptions.py)
from util_bbdd import DatabaseException, ConnectionError, QueryError, ValidationError
```

---

## Decisiones Arquitectónicas Clave

| ID | Decisión | Motivo |
|---|---|---|
| D1 | 3 niveles en lugar de 1/2 | Separación de concerns; Foundation estable, Specialization evoluciona |
| D2 | `metadata/*/tables.py` punto canónico | Evitar duplicación de SQL de introspección entre migrate/ y metadata/ |
| D3 | Managers en Level 3 | Dependen de TODOS los servicios Level 2; ponerlos en Level 2 causaría ciclos |
| D4 | InsertStrategyResolver | Elegir fast-path (COPY/multi-fila/executemany) sin modificar la API de BulkCrud |
| D5 | DumpOrchestrator sin SchemaComparator en hot-path | Eliminar cascada N+1 queries; skipped_columns se calcula en _common_columns |
| D6 | utf8mb4_uca1400_ai_ci por defecto (MariaDB ≥10.10) | Mejora de UCA 1400; utf8mb4_unicode_ci sigue siendo opción válida para versiones anteriores |
| D7 | PKSequenceSyncer post-bulk | Evitar errores de PK duplicada tras INSERT masivo sin IDENTITY/SERIAL |
| D8 | MigrationPlanner pass-through v1 para rutinas | Las rutinas se extraen con su DDL original; transformación semántica es revisión manual |

---

*Documento actualizado: Junio 2026 - alineado a v0.10.0*
