# ADR-004: Resoluci\u00f3n Perezosa de Versi\u00f3n para Selecci\u00f3n de Dialecto de Oracle

## 1. Contexto y Problema

Las versiones de Oracle tienen diferencias significativas en sus APIs que requieren consultas de metadatos distintas:

- **Oracle 11g (11.2.x)**: Carece de vista `ALL_TAB_IDENTITY_COLS` (a\u00f1adida en 12c); no hay introspeci\u00f3n de columnas identity
- **Oracle 12c y posterior**: Soporte completo de columnas IDENTITY mediante `ALL_TAB_IDENTITY_COLS`

La implementaci\u00f3n anterior asumia que todas las conexiones de Oracle eran 12c+, causando que las consultas de metadatos fallaran en 11g con `ORA-00942: table or view does not exist` al intentar consultar `ALL_TAB_IDENTITY_COLS`.

Adem\u00e1s, la inicializaci\u00f3n de la conexi\u00f3n de Oracle tiene limitaciones de rendimiento y compatibilidad:
- **Thin mode** (predeterminado en python-oracledb): Python puro, solo asincr\u00f3nico, solo Oracle 12c+
- **Thick mode** (requiere Instant Client): Solo sincr\u00f3nico, soporta Oracle 11g a 23c, requiere inicializaci\u00f3n global

La librer\u00eda necesitaba una forma de:
1. Detectar autom\u00e1ticamente la versi\u00f3n del servidor Oracle y seleccionar el dialecto correcto (OracleCatalog vs Oracle11Catalog)
2. Soportar tanto thin mode (asincr\u00f3nico) como thick mode (sincr\u00f3nico con soporte de 11g)
3. Minimizar el costo de las consultas de metadatos y la inicializaci\u00f3n de conexiones
4. Garantizar inicializaci\u00f3n segura para hilos y asincr\u00f3nica

## 2. Decision

### 2.1 Lazy Version Resolution

Implement **lazy version resolution** in `CatalogSource` and `AsyncCatalogSource`:

1. **On first metadata query** (`current_schema()` or `_load(kind, schema, tables)`), check if the dialect implements the optional `VersionedCatalogDialect` protocol:
   - `server_version_sql()` → Returns a SQL query to fetch the server version
   - `for_server_version(version_tuple)` → Returns the appropriate dialect variant based on version

2. **Execute the version query** if the protocol is implemented:
   ```python
   version_sql = dialect.server_version_sql()  # "SELECT version FROM product_component_version..."
   rows = executor.fetch_all(version_sql, {})
   version_tuple = tuple(int(x) for x in str(rows[0][0]).split("."))  # (11, 2, 0, 4, 0)
   ```

3. **Resolve the dialect variant** by calling `for_server_version()`:
   ```python
   resolved_dialect = dialect.for_server_version(version_tuple)
   self.dialect = resolved_dialect
   ```

4. **Cache the resolution** using `_version_resolved` flag to prevent repeated queries

**Rationale:**
- Defers server introspection to first actual metadata use, not connection establishment
- Single database query per connection (amortized over schema lifetime)
- No changes to public API for version detection (automatic and transparent)
- Maintains compatibility with dialects that don't implement `VersionedCatalogDialect`

### 2.2 Oracle Dialect Variants

Define two OracleCatalog implementations:

- **OracleCatalog** (12c+): Full SQL suite in `_SQL` including `Kind.IDENTITY`
- **Oracle11Catalog** (11g): SQL suite in `_SQL_11G` omitting `Kind.IDENTITY` and associated queries

Version detection: `for_server_version((11, 2, 0, 4, 0)) → Oracle11Catalog()` ; `for_server_version((19, 0, 0, 0, 0)) → OracleCatalog()`

### 2.3 Thick Mode Architecture

Separate thick mode initialization from connection establishment to support both sync and async patterns:

1. **Central module** (`src/util_bbdd/connection/oracle/_thick_mode.py`):
   - Single-call guarantee via global `ORACLE_THICK_MODE_INITIALIZED` flag
   - Thread-safe initialization via `threading.Lock`
   - Function: `init_oracle_thick_mode(client_path: str) → None`

2. **Sync connection flow**:
   - User sets `oracle_thick_mode=True, oracle_client_path="/path/to/instant/client"`
   - ConnectionFactory calls `init_oracle_thick_mode()` before engine creation
   - All subsequent connections use thick mode

3. **Async connection flow**:
   - Guard: `AsyncConnectionFactory` raises `ConnectionError` if `oracle_thick_mode=True`
   - Rationale: Async uses thin mode only; thick mode is inherently sync

4. **Version detection with thick mode**:
   - Thick mode is initialized before engine creation
   - Version query executes via normal connection flow
   - Dialect resolution is lazy and unaffected by thick mode choice

**Thread Safety:**
- `_THICK_MODE_LOCK` (threading.Lock) guards initialization
- First thread to call `init_oracle_thick_mode()` initializes; others skip
- No race conditions; initialization idempotent

## 3. Consequences

| Type | Description |
|---|---|
| **Advantage** | Automatic version detection: no manual dialect selection required |
| **Advantage** | Single metadata query per connection for version detection; cached after first use |
| **Advantage** | Minimal latency: version query deferred to first metadata use (not connection startup) |
| **Advantage** | Oracle 11g support via thick mode with Instant Client 19 |
| **Advantage** | Transparent to existing code: version resolution is automatic, lazy, and cached |
| **Advantage** | Thread-safe and async-safe: thick mode initialization cannot race or block async |
| **Trade-off** | Small latency on first metadata query (one additional database round-trip for version detection) |
| **Trade-off** | Thick mode requires explicit configuration; user must provide `oracle_client_path` |
| **Breaking Change** (Minor) | Async applications cannot use thick mode; must use thin mode (12c+ only). Raises clear `ConnectionError` on attempt. |

## 4. Alternative Approaches Considered

| Alternative | Pros | Cons | Reason Rejected |
|---|---|---|---|
| **Eager version detection** (at connection time) | Detects version early; fails fast on 11g+ without Instant Client | Blocks connection startup for all applications; overhead for non-Oracle users; no benefit for async (fails early rather than lazy) | Eager initialization defeats async benefits; unacceptable overhead |
| **Manual dialect selection** (user specifies) | No version query required; transparent to library | API burden on users; easy to select wrong dialect; requires version awareness from application | Non-deterministic; user error-prone |
| **Embedded version number** (config-based) | Single source of truth | Duplicates Oracle documentation; requires update per version; no automatic detection | Manual maintenance; not self-documenting |
| **Re-initialization on each query** (no caching) | Simplifies code; no flag needed | N queries per connection; significant performance degradation on large schemas | Unacceptable for large schemas (100+ tables × 10+ metadata queries each) |
| **Global registry of versions** (semaphore-based) | Prevents any thick mode re-init | Complex locking; no benefit over single-initialization flag | Unnecessary complexity |

## 5. Implementation Details

### 5.1 Changes to CatalogSource (src/util_bbdd/metadata/source.py)

```python
class CatalogSource:
    def __init__(self, dialect, executor, source_id=None, cache=None, default_schema=None):
        self.dialect = dialect
        self.executor = executor
        self._version_resolved = False  # Flag: version detected and dialect resolved
        self._default_schema = default_schema
        ...

    def _resolve_dialect(self) -> None:
        """Resolve dialect variant based on server version (e.g., Oracle 11g vs 12c+)."""
        if self._version_resolved:
            return  # Already resolved; skip
        self._version_resolved = True

        # Check if dialect implements VersionedCatalogDialect protocol
        if not hasattr(self.dialect, "server_version_sql") or not hasattr(self.dialect, "for_server_version"):
            return  # Not versioned; use as-is

        # Query server version
        version_sql = self.dialect.server_version_sql()
        rows = self.executor.fetch_all(version_sql, {})
        if not rows or not rows[0]:
            return  # Version unavailable; keep default

        # Parse version: "11.2.0.4.0" → (11, 2, 0, 4, 0)
        version_str = str(rows[0][0]).strip()
        try:
            version_tuple = tuple(int(x) for x in version_str.split("."))
        except (ValueError, AttributeError):
            return  # Malformed version; keep default

        # Resolve variant
        resolved_dialect = self.dialect.for_server_version(version_tuple)
        self.dialect = resolved_dialect

    def current_schema(self) -> str:
        self._resolve_dialect()  # Lazy resolution on first call
        ...
```

### 5.2 Changes to OracleCatalog (src/util_bbdd/metadata/oracle/catalog.py)

```python
class OracleCatalog(CatalogDialect):
    @staticmethod
    def server_version_sql() -> str:
        """SQL to query Oracle version."""
        return "SELECT version FROM product_component_version WHERE product LIKE 'Oracle Database%' AND ROWNUM = 1"

    @staticmethod
    def for_server_version(version_tuple: tuple[int, ...]) -> 'OracleCatalog':
        """Return appropriate catalog variant based on Oracle version."""
        if version_tuple and version_tuple[0] < 12:
            return Oracle11Catalog()
        return OracleCatalog()

class Oracle11Catalog(OracleCatalog):
    """Catalog for Oracle 11g (omits IDENTITY column queries)."""
    _sql = _SQL_11G  # Excludes Kind.IDENTITY
```

### 5.3 Thick Mode Initialization (src/util_bbdd/connection/oracle/_thick_mode.py)

```python
import threading

_THICK_MODE_LOCK = threading.Lock()
ORACLE_THICK_MODE_INITIALIZED = False

def init_oracle_thick_mode(client_path: str) -> None:
    """Initialize Oracle thick mode (thread-safe, single-call)."""
    global ORACLE_THICK_MODE_INITIALIZED
    
    with _THICK_MODE_LOCK:
        if ORACLE_THICK_MODE_INITIALIZED:
            return  # Already initialized
        
        oracledb.init_oracle_client(lib_dir=client_path)
        ORACLE_THICK_MODE_INITIALIZED = True
```

### 5.4 Integration with ConnectionFactory

**Sync (connection_oracle.py):**
```python
if oracle_thick_mode:
    if not oracle_client_path:
        raise ValueError("oracle_client_path required when oracle_thick_mode=True")
    init_oracle_thick_mode(oracle_client_path)
```

**Async (async_connection_oracle.py):**
```python
if ORACLE_THICK_MODE_INITIALIZED:
    raise ConnectionError("Async mode incompatible with Oracle thick mode; use thin mode (12c+ only)")
```

## 6. Testing Strategy

### 6.1 Unit Tests

- **test_oracle_11_catalog_detection.py**: OracleCatalog version detection (for_server_version method)
- **test_catalog_source_oracle_version.py**: CatalogSource lazy resolution with mocked executor

### 6.2 Integration Tests

- Oracle 11g container (docker-compose.bench.yml) with version detection validation
- Thick mode initialization across threads (concurrent connection creation)
- Async guard against thick mode (ConnectionError raised)

### 6.3 Query Count Validation

- Verify single version query per connection (existing test_query_counts.py extended for Oracle)
- No redundant version queries on repeated metadata access

## 7. Status and Review

**Status:** ACCEPTED and IMPLEMENTED (session 2025-01-15, phases 1–8)

**Key Commits:**
- Phase 1–6: Core implementation (version resolution, thick mode, test infrastructure)
- Phase 7: Integration tests (22 tests for version detection and lazy resolution)
- Phase 8: Documentation (drivers.md, ADR-004, runtime.md updates, CHANGELOG.md)

**Testing Results:**
- 5108 tests passing (5086 baseline + 22 new Oracle 11g tests)
- 496 tests skipped
- 0 failures

**Date of Last Review:** 2025-01-15

---

## References

- **CatalogSource Implementation**: [src/util_bbdd/metadata/source.py](../../src/util_bbdd/metadata/source.py)
- **OracleCatalog Variants**: [src/util_bbdd/metadata/oracle/catalog.py](../../src/util_bbdd/metadata/oracle/catalog.py)
- **Thick Mode**: [src/util_bbdd/connection/oracle/_thick_mode.py](../../src/util_bbdd/connection/oracle/_thick_mode.py)
- **Drivers Guide**: [docs/guides/drivers.md](../guides/drivers.md)
- **Test Suite**: [tests/unit/metadata/test_oracle_11_catalog_detection.py](../../tests/unit/metadata/test_oracle_11_catalog_detection.py), [tests/unit/metadata/test_catalog_source_oracle_version.py](../../tests/unit/metadata/test_catalog_source_oracle_version.py)
