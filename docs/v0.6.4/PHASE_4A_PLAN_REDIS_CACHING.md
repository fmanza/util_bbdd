# PLAN: Phase 4A Redis Caching Layer

**Date:** 9 de abril de 2026
**Agent:** Plan Architect
**Status:** 🟢 GO (CONDITIONAL)
**Version Target:** v0.6.4 (backward-compatible)

---

## Objetivo

Agregar soporte **Redis distribuido** como capa de caching opcional encima del caching in-memory existente (`DatabaseMetadataCache` + `RelationshipMetadataCache`) para optimizar performance en escenarios multibase con múltiples procesos. **Fallback automático** a in-memory si Redis unavailable. **Backward-compatible** (API pública sin cambios).

---

## Scope In

### Módulos Nuevos (3)

| Módulo | LOC Est. | Responsabilidad |
|--------|---------|-----------------|
| `src/util_bbdd/backends/__init__.py` | 20 | Package init, exports |
| `src/util_bbdd/backends/cache_backend.py` | 150-200 | CacheBackend Protocol + InMemoryCacheBackend + RedisCacheBackend |
| `src/util_bbdd/backends/redis_client.py` | 100-150 | RedisClientFactory, connection pooling, serialization helpers |

### Refactors (3)

| File | Changes | LOC Impact |
|------|---------|-----------|
| `src/util_bbdd/managers/_manager_cache_service.py` | Add `backend: CacheBackend` param, composition pattern | +30 lines |
| `src/util_bbdd/managers/sync_mgr.py` | Redis backend detection + injection | +10 lines |
| `src/util_bbdd/managers/async_mgr.py` | Redis backend detection + injection | +10 lines |

### Configuration

**`pyproject.toml`:**
```toml
[project.optional-dependencies]
redis = [
    "redis>=5.0",
]
```

### Tests (~60-80 tests)

| Test File | Count | Coverage |
|-----------|-------|----------|
| `tests/unit/test_cache_backend_inmemory.py` | 15-20 | InMemoryCacheBackend (get/set/delete/clear/stats) |
| `tests/unit/test_cache_backend_redis.py` | 20-30 | RedisCacheBackend (TTL, serialization edge cases) |
| `tests/unit/test_redis_client_factory.py` | 10-15 | Connection pooling, retry logic, URI parsing |
| `tests/integration/test_cache_backends_coherence.py` | 15-20 | Multi-manager coherence, invalidation consistency, fallback |

**Total: ~60-80 tests (fixture-based, sin Redis server)**

---

## Scope Out

❌ **Deferred to Phase 4B, 4C, or posterior:**
- Event-driven invalidation (pub/sub) → use TTL + manual clear por ahora
- Query result caching (only metadata caching now, not SQL query results)
- Cluster/Sentinel Redis support (single-node + single-process assumed)
- Cache warming / preload strategies
- Redis Lua scripting for atomic operations
- Per-key configurable TTL (start with uniform TTL)
- Memcached backend (Redis only for Phase 4A)

---

## Caching Architecture (Current)

### Existing Components

| Component | Status | Details |
|-----------|--------|---------|
| **DatabaseMetadataCache** | ✅ Working | 16 in-memory dicts, manual clear(), no TTL |
| **RelationshipMetadataCache** | ✅ Working | 4 analysis dicts, references DB cache (Identity Map) |
| **CacheService** | ✅ Working | Orchestrates both caches, used in managers |
| **Invalidation** | Passive | Manual `clear_all()`, `clear_by_table()`, `clear_context()` |
| **Key Format** | `tuple(str, str)` | (context, table) or context-only |
| **Managers Integration** | ✅ Working | Dependency injection in SyncDatabaseManager, AsyncDatabaseManager |

---

## Architecture Design (New)

### 1. Strategy Pattern — CacheBackend Protocol

```python
# src/util_bbdd/backends/cache_backend.py
from typing import Protocol, Any

class CacheBackend(Protocol):
    """Contrato para backend de caching (in-memory, Redis, etc)."""

    def get(self, key: str) -> Any | None:
        """Retrieve value; return None if not found or expired."""
        ...

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Set value with optional TTL (seconds)."""
        ...

    def delete(self, key: str) -> None:
        """Delete single key."""
        ...

    def clear(self) -> None:
        """Clear all keys (use sparingly)."""
        ...

    def get_stats(self) -> dict[str, int]:
        """Return hit/miss/size stats."""
        ...
```

### 2. Implementations

**`InMemoryCacheBackend`:**
- Wraps existing `DatabaseMetadataCache` (no refactor)
- Exposes Protocol interface
- No TTL (in-memory dict expiry not implemented; deferred)
- Fast path (dict lookup 0.1ms)

**`RedisCacheBackend`:**
- Uses `redis.Redis` client (connection pooled)
- JSON serialization (portable, debuggable)
- TTL via Redis native expiry
- Key namespace: `util_bbdd:{driver}:{context}:{method}:{param_hash}`
- Error handling: missing keys → return None, serialization errors → log + re-fetch

### 3. Composition in CacheService

```python
class CacheService:
    def __init__(
        self,
        db_cache: DatabaseMetadataCache,
        relationship_cache: RelationshipMetadataCache,
        logger: logging.Logger,
        backend: CacheBackend | None = None,  # NEW: optional backend
    ):
        self.db_cache = db_cache
        self.relationship_cache = relationship_cache
        self.logger = logger
        self.backend = backend or InMemoryCacheBackend(db_cache)  # Fallback
        # Rest unchanged
```

### 4. Manager Injection

```python
class SyncDatabaseManager:
    def __init__(self, ...):
        self.db_cache = DatabaseMetadataCache()
        self.relationship_cache = RelationshipMetadataCache(self.db_cache)

        # NEW: Detect Redis via env/config
        backend = None
        if redis_uri := os.getenv("REDIS_URL"):
            try:
                backend = RedisCacheBackend(
                    redis_uri=redis_uri,
                    ttl_seconds=cache_ttl_seconds or 300,
                    logger=self.logger,
                )
                self.logger.info("✅ Redis caching enabled")
            except (ConnectionError, TimeoutError) as e:
                self.logger.warning(f"⚠️ Redis unavailable: {e}, falling back to in-memory")
                backend = None  # Fallback below

        backend = backend or InMemoryCacheBackend(self.db_cache)

        self.cache_service = CacheService(
            self.db_cache,
            self.relationship_cache,
            self.logger,
            backend=backend,
        )
```

### 5. Key Namespace & Serialization

**Key Format:** `f"util_bbdd:{driver}:{context}:{method}:{param_hash}"`
- Example: `"util_bbdd:mariadb:test_db:columns:abc123def"`
- Rationale: legible, multi-driver coherence, namespace isolation

**Serialization:** JSON
- Rationale: portability, human-readable in Redis debuggers
- Edge cases: complex types → custom encoder or log warning + re-fetch from DB

**TTL:**
- Default: 300 seconds (5 minutes)
- Configurable: `AuditManager.cache_ttl_seconds` or `CACHE_TTL_SECONDS` env var
- Per-backend: uniform TTL (per-key deferred to Phase 4B)

### 6. Invalidation (Passive-Only)

- **TTL-based:** Redis native expiry (automatic)
- **Manual clear:** `CacheService.clear_all()` → Redis `FLUSHDB` + in-memory clear (atomic)
- **Per-table:** `CacheService.clear_table(context, table)` → Redis pattern delete `util_bbdd:*:context:table:*` + in-memory clear
- **Atomic:** Both in-memory + Redis cleared together (no race condition)

### 7. Redis Connection & Pooling

```python
# src/util_bbdd/backends/redis_client.py
class RedisClientFactory:
    @staticmethod
    def create(
        redis_uri: str,
        pool_size: int = 10,
        socket_timeout: int = 5,
    ) -> redis.Redis:
        """Create thread-safe connection pool."""
        return redis.Redis.from_url(
            redis_uri,
            decode_responses=True,  # Return str, not bytes
            connection_pool=redis.ConnectionPool(
                ...,
                max_connections=pool_size,
                socket_keepalive=True,
                socket_keepalive_options=...,
            ),
            socket_timeout=socket_timeout,
        )
```

### 8. Error Resilience

**Per-method error handling:**
```python
def get(self, key: str) -> Any | None:
    try:
        return redis.get(key, deserialize=JSON_DECODER)
    except Exception as e:
        self.logger.warning(f"Redis get failed for {key}: {e}, returning None")
        return None  # Fallback: cache miss, re-fetch from DB

def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
    try:
        redis.setex(key, ttl_seconds or 300, JSON_ENCODER(value))
    except Exception as e:
        self.logger.warning(f"Redis set failed for {key}: {e}")
        pass  # Fallback: in-memory will handle next request
```

---

## Files Affected

| File | Type | Impact | LOC Est. |
|------|------|--------|---------|
| `src/util_bbdd/backends/__init__.py` | NEW | Package init | 20 |
| `src/util_bbdd/backends/cache_backend.py` | NEW | Protocol + implementations | 200 |
| `src/util_bbdd/backends/redis_client.py` | NEW | Factory + helpers | 120 |
| `src/util_bbdd/managers/_manager_cache_service.py` | REFACTOR | Backend param | +30 |
| `src/util_bbdd/managers/sync_mgr.py` | REFACTOR | Backend injection | +10 |
| `src/util_bbdd/managers/async_mgr.py` | REFACTOR | Backend injection | +10 |
| `pyproject.toml` | REFACTOR | Optional dependency | +4 |
| `tests/unit/test_cache_*` | NEW | 60-80 tests | 1000 |

**Total: ~500-650 LOC (excluding tests)**

---

## Test Strategy (Fixture-Based)

### Unit Tests (40-50)

**`test_cache_backend_inmemory.py`:**
- get/set/delete/clear cycles
- stats tracking (hits, misses, size)
- Invalidation methods (clear_all, clear_by_table)

**`test_cache_backend_redis.py`:**
- get/set/delete/clear (mock Redis via `fakeredis` or MagicMock)
- TTL expiry validation
- JSON serialization edge cases (dates, None values, unicode)
- Error handling (Redis unavailable)

**`test_redis_client_factory.py`:**
- Connection pool creation
- URI parsing (redis://, rediss://)
- Socket timeout config

### Integration Tests (15-25)

**`test_cache_backends_coherence.py`:**
- Multi-manager test: manager1 caches, manager2 reads (Redis coherence)
- Invalidation consistency: clear() atomically updates both backends
- Fallback: Redis unavailable → auto-fallback to in-memory
- Backend parametrization: Run same tests for InMemory + Redis

### Fixtures (Fixture-based, no real Redis server)

```python
@pytest.fixture
def mock_redis():
    """Fake Redis using fakeredis or MagicMock."""
    # Option A: fakeredis (better simulation)
    # import fakeredis
    # return fakeredis.FakeStrictRedis()

    # Option B: MagicMock (simpler, lightweight)
    return MagicMock(spec=redis.Redis)

@pytest.fixture
def redis_backend(mock_redis):
    from util_bbdd.backends import RedisCacheBackend
    return RedisCacheBackend(client=mock_redis, logger=logging.getLogger())

@pytest.fixture
def inmemory_backend():
    from util_bbdd.backends import InMemoryCacheBackend
    from util_bbdd.metadata import DatabaseMetadataCache
    cache = DatabaseMetadataCache()
    return InMemoryCacheBackend(cache)

@pytest.mark.parametrize("backend", ["inmemory", "redis"], indirect=True)
def test_backend_parity(backend):
    """Run same test for both backends."""
    # Test code works for both backends
```

---

## Risks & Mitigations

### Functional Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Redis unavailability** | 🟡 Medium | Fallback to in-memory (try/except on init), automatic retry deferred |
| **TTL expiry race** | 🟡 Medium | Accept eventual consistency (5s window), Redis GETEX atomic (6.2+) |
| **Serialization failure** | 🟠 Low-Medium | Log warning, re-fetch from DB on error |
| **Multi-process coherence** | 🟡 Medium | Redis centralizes state; in-memory caches different. Clear both atomically |

### Technical Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Network latency** | 🟡 Medium | Redis adds 1-5ms per key vs 0.1ms dict. Monitor, consider per-method async Phase 4B |
| **Connection pool exhaustion** | 🟠 Low-Medium | pool_size config (default 10), connection pooling, test in high concurrency |
| **Memory growth (Redis)** | 🟠 Low-Medium | TTL enforcement, FLUSHDB on clear, Redis eviction policy (allkeys-lru) |

### Security Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Unauth Redis** | 🟠 Low | Require REDIS_USER + REDIS_PASSWORD env vars if URI present, warn if missing |
| **Metadata leakage via logs** | 🟢 Low | Don't log values, log counts/latency only |
| **Injection into Redis key** | 🟢 Low | Key format hardcoded, values JSON-encoded (safe) |

---

## Conditions & Assumptions

### Explicit Conditions

1. ✅ **Redis optional:** only if `redis` optional-dependency installed; fallback automatic if URI missing or connection fails
2. ✅ **Single Redis instance:** not cluster/sentinel (Phase 4B+)
3. ✅ **Fixture-based testing:** no real Redis server in CI (use `fakeredis` or mock)
4. ✅ **Passive invalidation:** TTL + manual clear (no pub/sub, no event-driven Phase 4B+)
5. ✅ **Uniform TTL:** 300s default, globally configurable (per-key deferred Phase 4B+)
6. ✅ **JSON serialization:** not Pickle (portability + debuggability)

### Preconditions

- ✅ Python 3.12+
- ✅ redis library 5.0+ available if optional-dependency installed
- ✅ Existing `DatabaseMetadataCache` + `RelationshipMetadataCache` unchanged
- ✅ CacheService already in use (no migration needed)

---

## Implementation Roadmap

**Sequential phases:**

1. **Phase 4A.1:** `cache_backend.py` Protocol + InMemoryCacheBackend (wraps existing cache)
2. **Phase 4A.2:** `redis_client.py` (factory, connection pooling, serialization)
3. **Phase 4A.3:** `RedisCacheBackend` (full implementation)
4. **Phase 4A.4:** Manager integration (sync_mgr, async_mgr, cache_service)
5. **Phase 4A.5:** Tests (unit + integration)
6. **Phase 4A.6:** Validation (pytest, ruff, mypy)
7. **Phase 4A.7:** Documentation + CHANGELOG

---

# AUDIT_PLAN: Phase 4A

## Riesgos Funcionales

| Risk | Severity | Details |
|------|----------|---------|
| **Race condition on TTL expiry** | 🟡 Medium | If key expires mid-fetch, could return None instead of stale value. Mitigation: Redis GETEX atomic (6.2+) or accept eventual consistency (< 5s) |
| **Serialization incompleteness** | 🟠 Low-Medium | Some types not JSON-serializable (OrderedDict, datetime). Mitigation: Custom encoder, log warning, re-fetch DB on error |
| **Invalidation timing** | 🟡 Medium | Manual `clear_table()` must clear both Redis + in-memory atomically. Mitigation: Single `CacheService.clear_table()` method handles both |
| **Multi-process staleness** | 🟡 Medium | Process A caches, Process B doesn't see until TTL expires. Mitigation: Acceptable for metadata (stable, infrequent changes) |

## Riesgos Técnicos

| Risk | Severity | Details |
|------|----------|---------|
| **Connection pool leak** | 🟠 Low-Medium | If manager not closed, Redis connections hang. Mitigation: Use `__del__` cleanup, test with pytest fixtures |
| **Redis latency regress** | 🟡 Medium | Network I/O slower than dict. Mitigation: Monitor in tests, consider profiling post-launch |
| **Memory bloat (Redis)** | 🟠 Low-Medium | Expired keys not cleaned until TTL fires + eviction policy. Mitigation: TTL enforcement, FLUSHDB, eviction policy config |

## Riesgos de Seguridad

| Risk | Severity | Details |
|------|----------|---------|
| **Unauth Redis** | 🟠 Low | If Redis exposed without credentials. Mitigation: Require REDIS_USER/REDIS_PASSWORD env vars, warn if missing |
| **Data leakage via logs** | 🟢 Low | Serialized values logged in debug. Mitigation: Only log counts/latency, not values |
| **Redis command injection** | 🟢 Low | Key format hardcoded, values JSON-encoded. Mitigation: No user input in key construction |

## Verificaciones Previas a Implementación

- [ ] Confirm JSON vs Pickle serialization preference (recommend JSON)
- [ ] Confirm TTL config source (AuditManager param vs env var vs both)
- [ ] Confirm error handling: backend methods should return None + log warning on failure (not bubble exception)
- [ ] Test parametrization: mark tests `@pytest.mark.parametrize(backend=["inmemory", "redis"])` to run both
- [ ] Review existing `DatabaseMetadataCache` code to ensure wrapping doesn't break

## Simplificaciones Posibles

✅ **Start simple:**
- Uniform TTL only (no per-key config)
- Error resilience in each method (try/except, log, return None/pass)
- Fixture-based Redis mock (no server in CI)
- Auto-fallback on `ConnectionError` at init

---

## 🟢 VEREDICTO FINAL: GO (CONDITIONAL)

### Condiciones para Authorizar

1. ✅ **Confirm JSON serialization** (not Pickle) — portability + debugging
2. ✅ **Confirm TTL config:** Use `AuditManager.cache_ttl_seconds` or env var + manager param
3. ✅ **Confirm error resilience:** All backend methods swallow exceptions + log warnings (not bubble)
4. ✅ **Confirm test parametrization:** Backend tests run both inmemory + redis (mock)
5. ✅ **Confirm backward-compatibility:** No API changes to public CacheService interface

### Success Criteria

✅ **After Phase 4A:**
- 3 new modules (2 implementations, 1 factory)
- 3 manager refactors (same API, added backend parameter)
- 60-80 tests (all passing, fixture-based)
- Total: 1,748+ tests passing (1,688 + 60 new)
- Code quality: Ruff ✅, Mypy ✅ (strict mode)
- Backward-compatible (v0.6.4 patch release)

### Timeline

- Implementation: 4-5 hours (sequential: backend → factory → managers → tests)
- Validation + tweaks: 1-2 hours
- **Total: 5-7 hours**

### Rollback Plan

If Redis caching proves problematic:
1. Remove `[project.optional-dependencies.redis]` from pyproject.toml
2. Remove manager backend injection code
3. Revert CacheService to default InMemoryCacheBackend
4. Release v0.6.5 (hotfix)

---

**Prepared by:** Plan Architect
**Reviewed by:** Workflow Director (Conditional GO)
**Status:** Ready for Feature Implementer execution pending condition approvals
