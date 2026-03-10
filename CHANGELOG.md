# Changelog

Todos los cambios notables en este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/).

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

[0.2.0]: https://github.com/tu_org/util_bbdd/releases/tag/v0.2.0
[0.1.0]: https://github.com/tu_org/util_bbdd/releases/tag/v0.1.0
