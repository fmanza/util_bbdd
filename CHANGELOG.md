# Changelog

Todos los cambios notables en este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- El soporte oficial de runtime pasa a ser Python 3.12+.
- Se alinean CI, metadatos de paquete y documentación pública con el nuevo rango soportado.
- Los enlaces públicos del paquete y del README pasan a apuntar al repositorio real de `fmanza/util_bbdd`.

## [0.6.3] - 2026-03-31

### Added
- Nueva capa de agentes especializados de VS Code en `.github/agents` para clasificación, planificación, implementación, hotfix, auditoría, seguridad y cierre de versión.

### Changed
- La política transversal de Copilot incorpora el modelo combinado de instrucciones, prompts y agentes.
- README, guía de `.github` y ejemplo integral documentan el flujo recomendado de trabajo con Copilot y el mapeo rápido prompt-agente.
- El cierre de v0.6.3 excluye explícitamente `docs/v0.6.4`, que permanece como trabajo futuro fuera del alcance de la release.

## [0.6.2] - 2026-03-26

### Added
- Nuevas fuentes de verdad compartidas para diagramas documentales:
  - `src/util_bbdd/doc/diagram_legend.py`
  - `src/util_bbdd/doc/diagram_summary.py`
- Copia de assets offline con subcarpeta `icons/` para páginas HTML exportadas y prueba dedicada de regresión.
- Ejemplo completo y comentado del contrato `imprimir_config` en `docs/examples/imprimir_config_full_example.toml`.
- Notas de release específicas de v0.6.2 en `docs/v0.6.2/RELEASE_NOTES_v0.6.2.md`.

### Changed
- El detalle HTML de diagramas pasa a consumir SVG inline para garantizar navegación offline con zoom, paneo, ajuste y reset sin depender de `contentDocument`.
- HTML y Word comparten ahora payloads comunes para resumen de niveles, ayudas de lectura y leyenda visual.
- Las páginas globales `Ver todo` muestran acciones de exportación con iconografía local y tooltips consistentes en la salida offline.
- La documentación pública se alinea a v0.6.2 e incorpora el contrato comentado de `imprimir_config` como referencia principal.

### Fixed
- Los tooltips de exportación de `Ver todo` ya no quedan recortados por el contenedor del toolbar.
- La exportación HTML offline incluye los iconos SVG necesarios para paginación y acciones de exportación.
- La experiencia interactiva de diagramas en HTML se mantiene operativa fuera de VS Code y en navegadores externos.

## [0.6.1] - 2026-03-24

### Added
- Tipología visual de tablas en el análisis de grafos con tres estados iniciales:
  - `entity`
  - `association`
  - `hierarchy`
- Leyenda HTML ampliada para exponer tipo de tabla, cardinalidad y tipo de relación soportado por el renderer actual.
- Nota pública preliminar de v0.6.1 en `docs/v0.6.1/RELEASE_NOTES_v0.6.1.md`.

### Changed
- `GraphvizRelationshipGraphExt` deja de colorear nodos solo como principal vs relacionada y pasa a una paleta visual por tipología de tabla.
- La heurística de `association` mejora la detección de tablas puente reales al considerar PK compuesta basada en columnas FK.
- La documentación pública aclara que la tipología visual de tablas es heurística y no una taxonomía absoluta del modelo de datos.
- La política de diagramado de vistas se documenta explícitamente como `exclude` en el estado actual del renderer enriquecido.
- Word y HTML pueden reutilizar el mismo generador Graphviz en una misma ejecución multi-formato.

### Fixed
- El detalle HTML refleja de forma explícita la leyenda de tipos de tabla realmente soportados por el modelo actual.
- La semántica de niveles ocultos queda alineada entre SVG, HTML y Word.

## [0.6.0] - 2026-03-22

### Removed
- **Breaking Change**: el contrato de configuración de grafos deja de depender de `first_level_only` y `show_columns` como parámetros principales.
- **Breaking Change**: la representación HTML antigua de diagramas como lista plana deja paso al modelo por sentido y por nivel.
- **Breaking Change**: `util_bbdd.bulk.base` deja de existir; el núcleo de grafos queda consolidado en `util_bbdd.analysis.base`.

### Added
- Nuevo dominio de análisis multinivel en `analysis/base.py`:
  - `GraphDocument`
  - `GraphLevel`
  - `GraphNode`
  - `GraphEdge`
  - `HiddenLevelsSummary`
  - `LevelDirection`
  - `ColumnVisualizationMode`
- Soporte de relaciones de `n` niveles mediante `max_depth`.
- Dirección configurable de recorrido: `incoming`, `outgoing` y `both`.
- Modos de columnas para diagramas:
  - `compact`
  - `relations`
  - `all`
- Cardinalidad representada por extremos en Graphviz.
- HTML con pestañas por sentido y por nivel.
- Word con resumen de niveles visibles y no visibles bajo cada diagrama.
- Nueva guía específica de migración en `docs/v0.6.0/MIGRATION_GUIDE_v0.6.0.md`.
- Cobertura nueva para payloads HTML tabulados, resumen Word y traversal multinivel.

### Changed
- `GraphvizRelationshipGraphExt` consume `GraphDocument` en lugar de listas planas como fuente principal de renderizado.
- `PrintConfigManager` normaliza el nuevo bloque `grafo` con:
  - `max_depth`
  - `direction`
  - `columns.mode`
  - `columns.max_items`
  - `columns.show_data_types`
  - `cardinality.show_constraint_name`
- HTML y Word consumen el nuevo contrato de configuración de grafos.
- `MatplotlibRelationshipGraph` se alinea con el nuevo traversal multinivel y ya puede renderizar profundidad y dirección configurables.
- README y guías de migración actualizados a v0.6.0.

### Fixed
- La generación HTML de diagramas conserva fallback cuando no hay pestañas disponibles.
- El resumen de niveles ya se refleja también en la salida Word.
- Se estabilizan pruebas unitarias para payloads documentales y renderizado de detalle.

## [0.5.6] - 2026-03-16

### Removed
- **Breaking Change**: `DatabaseManager` deja de publicarse como alias sync compatible.
  - Usa `SyncDatabaseManager` desde `util_bbdd` o `util_bbdd.managers`.
  - `AsyncDatabaseManager` mantiene su nombre y contrato público.
- **Breaking Change**: se elimina `ficheros_fisicos_adicional` del catálogo SQL en todos los motores.
  - El inventario de almacenamiento deja de modelarse como `primary`/`secondary`.
  - SQLite deja de exponer un falso bloque de “ficheros adicionales”.

### Added
- Soporte MariaDB para metadatos temporales:
  - `temp_tablespaces` desde `information_schema.FILES` cuando hay acceso.
  - `temp_storage_variables` para exponer `innodb_temp_data_file_path`.
- Nueva capacidad explícita `sqlite_file_summary` para documentar `page_count`, `page_size` y `size_bytes` del fichero SQLite principal.
- Cobertura adicional de tests para tipado, contratos sync/async y paridad estructural entre managers.
- Refactorización Jinja2 standalone para la documentación HTML:
  - `TemplateEngine` dedicado
  - `templates/layouts`, `templates/macros` y `templates/pages`
  - pruebas unitarias específicas del motor de plantillas
- Páginas HTML globales `Ver todo` con búsqueda, ordenación, paginación y exportación filtrada.

### Changed
- La lógica específica de MariaDB se reorganiza bajo `metadata/mariadb/` con helpers puros y adaptadores sync/async.
- `SyncDatabaseManager` pasa a ser el nombre canónico de la API sync en código, tests y documentación.
- La obtención de DDL y metadatos de MariaDB prioriza `information_schema` y datasets batched por esquema frente a `SHOW CREATE` como ruta principal.
- `get_storage_inventory()` pasa a devolver claves explícitas por capacidad:
  - `primary`
  - `temp_tablespaces` cuando aplica
  - `temp_storage_variables` en documentación MariaDB
  - `sqlite_file_summary` para SQLite
- Word, Excel y HTML dejan de generar la sección global `Ficheros físicos adicionales`; SQLite integra ahora ese contenido como ampliación del bloque de físicos.
- La documentación HTML deja de usar plantillas monolíticas en `src/util_bbdd/doc/data` y pasa a una estructura modular Jinja2.
- Word aplica defaults de grafo más conservadores para documentación:
  - `show_columns=False`
  - `images_paginated=True`
  - `max_subnodes=5`
  - `dpi=150`
- El análisis de relaciones reutiliza un índice cacheado de relaciones entrantes por contexto para reducir recorridos repetidos.

### Fixed
- Los caminos principales de columnas y DDL de rutinas MariaDB evitan depender del fallback de decodificación del driver.
- La documentación Word/Excel/HTML refleja almacenamiento temporal MariaDB y falta de permisos sobre `information_schema.FILES` sin romper la generación.
- Se estabilizan múltiples tests con avisos de tipado en VS Code/Pylance.
- La exportación HTML de colecciones genera CSV y TSV en UTF-8 y Excel en `.xlsx` real.
- La generación Word de diagramas registra tiempos de análisis, render e inserción para diagnosticar bloqueos aparentes.

## [0.5.3] - 2026-03-12

### Added
- Expanded unit coverage for:
  - Bulk CRUD helper behavior
  - Documentation generators (HTML/Excel/Word helper paths)
  - Relationship graph base analysis
  - Metadata cache units and cache invalidation flows

### Changed
- Hardened contract tests for sync/async manager-executor paths:
  - Better validation of query/custom error propagation
  - Explicit verification of wrapping unexpected errors with chained causes
- Reworked documentation legacy-API checks to AST-based assertions to reduce false positives from raw string matching.

### Fixed
- Added edge-case cleanup tests to ensure cursor-close failures do not break query result delivery and connection release paths.

## [0.5.2] - 2026-03-11

### 🎯 Major Cleanup Release

This is a **comprehensive cleanup release** eliminating 27 wrapper files and consolidating the codebase architecture.
No breaking changes - all refactoring is internal. **89% of major refactoring complete (17/19 PRs).**

### Removed (Internal Only - No Breaking Changes)
- **27 wrapper files eliminated** (~2,000 lines of duplicate code):
  - **Phase 1 (PR #16):** Removed directory wrappers (`bulk_crud/`, `grafos/` - 9 files)
  - **Phase 2 (PR #16):** Removed root wrappers (5 files)
  - **Phase 3 (PR #16):** Removed connection layer wrappers (8 files):
    - `conn_params_builder.py` → consolidated to `builder.py`
    - `connection_configs.py` → consolidated to `config.py`
    - `connection_params_manager.py` → consolidated to `params.py`
    - `async_close_utils.py` + `sync_close_utils.py` → consolidated to `close.py`
    - `async_protocols.py` + `pool_protocol.py` → consolidated to `protocols.py`
    - `connect_factory.py` → consolidated to `factory.py`
- **40+ files updated** with new import paths
- **Function rename:** `run_sync_close_operation()` → `run_close_operation_sync()`
- **Class rename:** `ConnectFactory` → `ConnectionFactory`

### Changed
- Import paths streamlined for all internal modules
- Connection layer now uses direct imports instead of wrappers
- No circular dependencies in codebase
- Architecture simplified with consolidated module structure

### Architecture
**Old Pattern (v0.5.0):**
```
connection/
├── conn_params_builder.py (wrapper)
├── connection_configs.py (wrapper)
├── connection_params_manager.py (wrapper)
├── async_close_utils.py (wrapper)
├── sync_close_utils.py (wrapper)
├── async_protocols.py (wrapper)
├── pool_protocol.py (wrapper)
├── connect_factory.py (wrapper)
└── [driver modules]
```

**New Pattern (v0.5.2):**
```
connection/
├── builder.py (consolidated)
├── config.py (consolidated)
├── params.py (consolidated)
├── close.py (consolidated async + sync)
├── protocols.py (consolidated async + pool)
├── factory.py (consolidated)
└── [driver modules - updated imports]
```

### Migration
- **100% Backward Compatible** - Old imports still work
- See `docs/MIGRATION_GUIDE.md` for new import paths
- See `RELEASE_NOTES_v0.5.2.md` for detailed migration guide
- **No code changes required** - but refactoring to new imports is recommended

### Quality Metrics
- ✅ 410/410 unit tests passing (100%)
- ✅ All internal references updated
- ✅ No breaking changes
- ✅ All database drivers validated (MariaDB, Oracle, PostgreSQL, SQLite, HSQLDB, SQL Server)
- ✅ Async/sync APIs fully functional

### Commits Included
- **db61c78** - PR #16 Phase 1: Eliminar directorios wrapper legacy
- **dc3584b** - PR #16 Phase 2: Eliminar wrappers en raíz
- **cb7746a** - PR #16 Phase 3: Eliminar 8 wrappers en connection/
- **3d9add4** - Documentación: Actualizar catálogo PR (17/19 = 89%)

---

## [0.5.0] - 2026-03-11

### What's New
- **Architecture Refactoring:** Complete 3-level hierarchical reorganization
  - Level 1: Abstractions (`_core/`, `_drivers/`)
  - Level 2: Core Services (`connection/`, `query/`, `executors/`, `metadata/`, `results/`)
  - Level 3: Specialization (`bulk/`, `analysis/`, `managers/`)
- **9 new modules consolidated** from fragmented codebase
- **16 backward compatibility wrappers** ensuring zero breaking changes
- **Unified documentation** with architecture diagrams and migration guides

### Changed
- All internal imports reorganized for 3-level structure
- DatabaseManager and AsyncDatabaseManager moved to `managers/` module
- Bulk operations consolidated in `bulk/` module
- Relationship graphs consolidated in `analysis/` module

### Migration
- See `docs/MIGRATION_GUIDE.md` for detailed v0.4.0 → v0.5.0 upgrade path
- All existing APIs remain functional through backward compatibility wrappers
- **100% backward compatible** - no code changes required by users

### Performance & Quality
- 443/443 tests passing consistently
- Test execution: 7.59s (avg)
- Full test coverage reports available
- Code organized for better maintainability

## [Unreleased]

### Removed
- **Breaking Change**: Removed legacy execution APIs based on `fetch_one`
  - `DatabaseManager.execute_query(...)`
  - `DatabaseManager.execute_custom_query(...)`
  - `AsyncDatabaseManager.execute_query(...)`
  - `AsyncDatabaseManager.execute_custom_query(...)`
- **Breaking Change**: Removed executor legacy entry points
  - `SyncQueryExecutor.execute_query(...)`
  - `SyncQueryExecutor.execute_custom_query(...)`
  - `AsyncQueryExecutor.execute_query(...)`
  - `AsyncQueryExecutor.execute_custom_query(...)`
- **Breaking Change**: `DatabaseManager.db_queries` is no longer exposed as public API.
- Removed legacy executor class from `database_queries.py`; module remains catalog/resolution only.

### Added
- Public execution contract unified and explicit in sync/async:
  - `execute_query_many(...)`
  - `execute_query_one(...)`
  - `execute_custom_many(...)`
  - `execute_custom_one(...)`

### Changed
- Documentation generators now consume public manager APIs instead of direct catalog access.
- README examples updated to the final split many/one API.

## [0.3.0] - 2026-03-08

### Removed
- **Breaking Change**: `DatabaseQueryError` class removed from `database_queries.py`
  - Use `QueryNotFoundError` from `database_exceptions.py` instead
  - Alias no longer available
- **Breaking Change**: `DatabaseQueries.validate_query_parameters()` method removed
  - Use `QueryResolver.resolve()` directly instead
  - Simplified API by removing deprecated wrapper
- **Breaking Change**: `DatabaseQueries.analyze_query_parameters()` method removed
  - Use `QueryResolver.resolve()` for comprehensive validation
- **Breaking Change**: `DatabaseManager.validate_query_parameters()` wrapper removed
  - Use `manager.db_queries.resolver.resolve()` instead

### Changed
- Internal query validation completely delegated to `QueryResolver`
- All validation errors use specific exception types (QueryNotFoundError, QueryValidationError)
- Simplified DatabaseQueries API surface (-79 lines of deprecated code)

### Tests
- Removed 2 deprecation compatibility tests
- All remaining 239 unit tests passing
- All 19 E2E tests passing (10 sync + 9 async)

### Migration
Users affected by these breaking changes should:
```python
# OLD CODE (v0.2.x):
from util_bbdd.database_queries import DatabaseQueryError
if manager.validate_query_parameters('query', param=value):
    result = manager.execute_query('query', param=value)

# NEW CODE (v0.3.0+):
from util_bbdd.database_exceptions import QueryNotFoundError
try:
    result = manager.execute_query('query', param=value)
except QueryNotFoundError as e:
    print(f"Query error: {e}")
```

See [08_ESTADO_COMPLETO_PR8.md](08_ESTADO_COMPLETO_PR8.md) for detailed migration guide.

## [0.2.0] - 2026-03-07

### Added
- **Query Registry Pattern**: Centralized query loading via `QueryRegistry` class
- **Query Resolver**: Unified validation and parameter resolution via `QueryResolver`
- **New Exception Hierarchy**:
  - `QueryNotFoundError` - Query does not exist for motor
  - `QueryValidationError` - Validation failed for query parameters
  - `QueryParameterError` - Invalid parameter value for motor
  - `QueryTimeoutError` - Query execution timeout
  - `DatabaseTypeNotSupportedError` - Unsupported database motor
- **Advanced Validators**: Motor-specific validation rules
  - MariaDB: Charset, Database parameter validation
  - Oracle: Schema context (max 30 chars), Character restrictions (alphanumeric, _, $, #)
  - PostgreSQL: Reserved schema detection
  - HSQLDB: Table name format (alphanumeric, _, - only)
  - SQL Server: Schema support, 128-char limits
  - SQLite: Minimal parameters
- **New DatabaseManager Methods**:
  - `execute_query(query_name, **params)` - Execute query by name with validation
- **AsyncDatabaseManager Enhancements**:
  - `get_tables()`, `get_views()`, `get_columns()`, `get_routines()` - Full parity with sync
  - `execute_query(query_name, **params)` - Async query execution by name
  - Async/sync contract validation tests
- **Improved Error Handling**:
  - All exceptions use `raise ... from err` pattern
  - Structured logging with DEBUG level details (elapsed_ms, param_count, etc.)
- **Documentation**:
  - Migration guide v0.1.x → v0.2.0
  - Database motor support matrix
  - Exception usage examples

### Changed
- **DatabaseQueries Refactoring** (SRP improvement):
  - Reduced from 2001 → 1042 lines (-48%)
  - Delegates query loading to `QueryRegistry`
  - Delegates resolution to `QueryResolver`
  - Delegates validation to motor-specific validators
  - Maintains `get_query()`, `get_tables_query()`, etc. as convenience layer
- **Exception Inheritance**:
  - `DatabaseQueryError` → `QueryNotFoundError` (Alias maintained for compatibility)
  - All query exceptions inherit from `DatabaseError` base class
- **API Organization**:
  - New `executors` module: `SyncQueryExecutor`, `AsyncQueryExecutor`
  - New `validators` module: Motor-specific validators
  - New `models` module: `QueryDefinition`, `ResolvedQuery`, `DatabaseTypeDefinition`

### Deprecated
- `DatabaseQueries._load_queries()` - Now internal (delegated to QueryRegistry)
- `DatabaseQueryError` - Use `QueryNotFoundError`, `QueryValidationError`, etc.
- `DatabaseQueries.analyze_query_parameters()` - Use QueryResolver for comprehensive analysis

### Fixed
- Query parameter validation consistency across all motors
- Timeout handling in async query execution
- Error context preservation with exception chaining

### Breaking Changes ⚠️
- `DatabaseQueryError` no longer raised directly (use specific exceptions)
- Query parameter validation is stricter (missing required params raise early)
- `DatabaseQueries._load_queries()` is no longer public API
- Some internal method signatures changed (no impact on public API)

### Performance
- Query loading/resolving cached properly via QueryRegistry
- Reduced object instantiation in DatabaseQueries
- Lazy validation (only on demand, not during init)

### Tests Added (v0.2.0)
- Query Registry: 51 tests
- Query Resolver: 91 tests
- Sync Executor: 10 tests
- Async Executor: 17 tests
- Async Database Manager: 16 tests
- Advanced Validators: 20 tests
- DatabaseQueries Refactor: 36 tests
- **Total new tests in v0.2.0: 241 tests** (↑67% from v0.1.x)

---

## [0.1.0] - 2026-03-06 (Legacy)

### Added
- Módulo `bulk_crud_audit`: CRUD masivo (insert/update/delete) desde DataFrames
- Sistema de auditoría automática en CSV con timestamps
- Factory para conexiones con pool singleton
- Validación de tipos por dialecto SQL (MySQL/Oracle/PostgreSQL)
- Gestión de metadatos con caché
- Documentación automática de BD (Word/Excel)
- Tests unitarios con pytest y cobertura
- Documentación en README y docstrings (Google style)
- Infraestructura async base (`AsyncDatabaseManager`, `AsyncDatabaseQueryExecutor`)
- Soporte async para PostgreSQL, SQLite, MariaDB, Oracle, SQL Server

### Fixed
- Normalización de columnas según dialecto (Oracle: lower, MySQL: upper)
- Manejo de valores NULL en operaciones CRUD

### Note
- HSQLDB: No soporte async (decisión explícita, ver v0.2.0 para más detalles)

[0.5.3]: https://github.com/fmanza/util_bbdd/releases/tag/v0.5.3
[0.5.2]: https://github.com/fmanza/util_bbdd/releases/tag/v0.5.2
[0.2.0]: https://github.com/fmanza/util_bbdd/releases/tag/v0.2.0
[0.1.0]: https://github.com/fmanza/util_bbdd/releases/tag/v0.1.0
