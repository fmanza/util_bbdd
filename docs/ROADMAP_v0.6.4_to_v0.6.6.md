# Roadmap: v0.6.4 → v0.6.6

**Planning Date:** 9 de abril de 2026
**Current Version:** v0.6.3 (Phase 3C.4 Complete - 8 SQL Drivers)
**Target Version:** v0.6.6 (Advanced Features & Optimization)

---

## Release Strategy

### v0.6.3 (Released ✅)
- **Phase 3C.4 Complete:** MySQL, Redshift, Snowflake drivers
- **Total Drivers:** 8 SQL engines
- **Tests:** 1,688 passing (410+ new)
- **Status:** Stable, backward-compatible, production-ready

### v0.6.4 (Next - Phase 4A & 3C.5a)
- **Target:** Q2 2026
- **Primary Goal:** Expand drivers + add caching layer
- **Expected Duration:** 2 weeks

#### Phase 4A: Redis Caching Layer
**Objective:** Optional metadata caching for improved performance

**Scope:**
- `CacheBackend` protocol (abstract interface)
- `RedisBackend` implementation (redis-py)
- `MemoryBackend` fallback (built-in)
- Integration with existing manager layer (no manager changes needed)
- Cache invalidation strategies (TTL, manual flush)

**Estimated Effort:** 5-7 hours
- Implementation: 3-4 hours
- Testing: 60-80 tests
- Documentation: docs + examples

**Files to Create/Modify:**
- `src/util_bbdd/core/cache/` (new module)
  - `__init__.py`
  - `protocol.py` (CacheBackend Protocol)
  - `redis_backend.py` (RedisBackend with fallback)
  - `memory_backend.py` (in-memory strategy)
  - `cache_manager.py` (cache orchestration)
- `src/util_bbdd/managers/sync_manager.py` (add cache parameter, optional)
- `src/util_bbdd/managers/async_manager.py` (add cache parameter, optional)
- `tests/unit/test_cache_*` (60-80 tests)

**Architecture Decision:**
- **Pattern:** Strategy Pattern (pluggable backends)
- **Integration:** Manager-level injection (non-breaking)
- **Fallback:** Memory cache always available (no external dependency required)
- **Opt-in:** Redis is optional dependency (`pip install util_bbdd[redis]`)

**Risk Assessment:**
- **Low:** Strategy pattern proven, manager layer stable
- **Mitigation:** Cache bypass option, comprehensive unit tests

**Backward Compatibility:**
- ✅ 100% (cache is optional parameter, zero breaking changes)

---

#### Phase 3C.5a: BigQuery Driver
**Objective:** Google Cloud BigQuery metadata introspection

**Scope:**
- 10-module driver structure (consistent with MySQL/Redshift/Snowflake)
- Multi-level schema support (Project.Dataset.Table)
- 40+ type mappings (BigQuery extended types)
- Advisory constraints (metadata-only, like Snowflake)
- UDF/procedure introspection
- Sync adapter (google-cloud-bigquery)
- Async adapter (executor-based wrapper)

**Estimated Effort:** 3-4 hours
- Implementation: 2-2.5 hours
- Testing: 100-120 tests
- Documentation: driver guide

**Files to Create/Modify:**
- `src/util_bbdd/metadata/bigquery/` (new driver)
  - `__init__.py` (auto-registration)
  - `common.py` (40+ type mappings)
  - `_bigquery_models.py` (dataclasses)
  - `_adapter_helpers.py` (SQL builders)
  - `tables.py` (schema/table/column introspection)
  - `constraints.py` (advisory only, empty stubs)
  - `indexes.py` (advisory, clustering key hints)
  - `routines.py` (UDF/stored procedure support)
  - `sync_adapter.py` (google-cloud-bigquery)
  - `async_adapter.py` (executor wrapper)
- `tests/unit/test_bigquery_*` (100-120 tests)
- Registry auto-registration (add "bigquery" to driver list)

**Type Mappings (40+):**
- Numeric: INT64, FLOAT64, NUMERIC, BIGNUMERIC
- String: STRING, BYTES
- Date/Time: DATE, TIME, DATETIME, TIMESTAMP
- Complex: STRUCT, ARRAY, JSON, GEOGRAPHY
- Advanced: INTERVAL, DECIMAL

**Architecture Decision:**
- **Pattern:** Adapter pattern (consistent with existing drivers)
- **Schema Model:** Three-level (project.dataset.table) with normalization
- **Constraints:** Advisory only (return empty, log recommendations)
- **Indexes:** Clustering keys as optimization hints

**Risk Assessment:**
- **Medium:** Multi-level schema requires careful normalization
- **Mitigation:** Unit tests for schema transformation, parity tests

**Backward Compatibility:**
- ✅ 100% (new driver, zero impact on existing code)

---

### v0.6.5 (Phase 4B - Async Optimizations)
- **Target:** Q3 2026
- **Primary Goal:** Performance optimization for async operations
- **Expected Duration:** 1-2 weeks

#### Phase 4B: Async Query Optimization
- Batch metadata loading (parallel queries within single connection)
- Connection pool tuning per driver
- Query result streaming (large schema introspection)

**Estimated Effort:** 8-12 hours

---

### v0.6.6 (Phase 4C - Final Polish)
- **Target:** Q3 2026
- **Primary Goal:** Stability, documentation, and release readiness
- **Expected Duration:** 1 week

#### Phase 4C: Production Hardening
- Performance profiling and optimization
- Security audit (dependency check, SQL injection prevention validation)
- Documentation completeness (API stability guarantees)
- Release notes and migration guides

**Estimated Effort:** 5-8 hours

---

## Decision Matrix

### Dependencies to Decide

| Feature | Dependency | Optional | Default | Decision |
|---------|-----------|----------|---------|----------|
| **Redis Caching** | redis-py | ✅ Yes | Not installed | Add to `[dev]` dependencies only |
| **BigQuery Driver** | google-cloud-bigquery | ✅ Yes | Not installed | Add to optional `[bigquery]` dependencies |
| **MongoDB** (v0.7.0+) | pymongo | ✅ Yes | Pending ADR | Blocked until architecture decision |

### Architecture Stability

| Component | Status | Change Required | Timeline |
|-----------|--------|-----------------|----------|
| Manager API | ✅ Stable | Cache parameter injection only | v0.6.4 |
| Registry | ✅ Stable | Add "bigquery" + "redis" entries | v0.6.4 |
| Adapter Protocol | ✅ Stable | No changes (BigQuery follows pattern) | v0.6.4 |
| Type Mapping | ✅ Stable | New drivers add mappings, no breaking changes | v0.6.4 |

---

## Quality Gates (All Versions)

- ✅ 100% backward compatibility (existing tests must pass)
- ✅ Ruff: 0 issues (code quality)
- ✅ Mypy: 0 errors in strict mode (type safety)
- ✅ Pytest: All tests passing (no skips/failures)
- ✅ Docstring coverage: 100% on new code
- ✅ SQL injection prevention: All queries parameterized

---

## Risk Register

| Risk | Phase | Severity | Mitigation |
|------|-------|----------|-----------|
| Redis unavailability | 4A | Low | Built-in memory fallback |
| BigQuery schema complexity | 3C.5a | Medium | Comprehensive unit tests, edge case coverage |
| Breaking change introduction | All | High | Pre-release audit, compatibility matrix |
| Dependency bloat | 4A, 3C.5a | Low | Optional dependencies (pip install extras) |
| Performance regression | 4B | Medium | Profiling before/after, benchmark suite |

---

## Launch Checklist (Per Release)

### Pre-Release (v0.6.4 example)

- [ ] All tests passing (1,688+ target)
- [ ] Ruff: 0 issues
- [ ] Mypy: 0 errors (strict mode)
- [ ] Code review complete
- [ ] Documentation updated
- [ ] CHANGELOG.md populated
- [ ] Version bumped in pyproject.toml
- [ ] Build artifacts created (wheel + sdist)
- [ ] Git tag created and pushed

### Release Day

- [ ] GitHub Release created (with changelog, artifacts)
- [ ] PyPI publication (`twine upload`)
- [ ] Installation verification (`pip install util_bbdd==X.Y.Z`)
- [ ] Release announcement (if applicable)

### Post-Release

- [ ] Monitor for issues (GitHub Issues)
- [ ] Prepare next development version (v0.6.5-dev)
- [ ] Update roadmap if needed

---

## Rollback Plan

If critical issues found post-release:

1. **Hotfix Branch:** `hotfix/v0.6.4-rc1` (if pre-release)
2. **Fix Implementation:** Minimal, targeted fix only
3. **Version Bump:** v0.6.4.1 (patch version)
4. **Republish:** New PyPI release
5. **Communication:** GitHub release notes with incident summary

---

## Success Metrics (End of v0.6.6)

- ✅ 9+ SQL/NoSQL drivers fully supported (8 current + BigQuery + MongoDB ADR approved)
- ✅ 2000+ unit tests (distributed across drivers)
- ✅ <5 second metadata load for standard schemas
- ✅ Optional caching layer reducing repeated queries by 80%
- ✅ 100% API stability (zero breaking changes from v0.6.3)
- ✅ Production-ready for enterprise deployments

---

## Next Session

**Immediate Actions:**
1. ✅ Publish v0.6.3 to PyPI (awaiting user confirmation)
2. ✅ Create GitHub Release v0.6.3 (in progress)
3. ⏳ Start Phase 4A planning if user approves

**Deferred:**
- Phase 3C.5a (BigQuery): Implement in v0.6.4 sprint if Phase 4A completed early
- MongoDB ADR: Schedule architecture decision meeting
- Phase 4B (v0.6.5): Plan after v0.6.4 completes

---

**Document Status:** Ready for review
**Last Updated:** 9 de abril de 2026
**Maintainer:** Francisco (fmanza)
