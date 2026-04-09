# PLAN: Phase 3C.5a (BigQuery SQL Driver)

**Date:** 9 de abril de 2026
**Agent:** Plan Architect
**Status:** 🟢 GO CONDICIONAL

---

## Objetivo

Implementar **driver #9 para BigQuery** en util_bbdd, manteniendo pattern proven de Phase 3C.4 (MySQL/Redshift/Snowflake). BigQuery es data warehouse cloud-native con SQL estándar, schema multi-nivel (Project.Dataset.Table) y constraints advisory (como Snowflake). Agregar ~100-120 tests en 6 archivos, 10 módulos, auto-registración en AdapterRegistry, sin refactorización de managers.

---

## Scope In

✅ **10 nuevos módulos bajo `src/util_bbdd/metadata/bigquery/`:**

| Módulo | LOC (est.) | Responsabilidad |
|--------|-----------|-----------------|
| `__init__.py` | 30 | Auto-registration en AdapterRegistry (patrón MySQL/Snowflake) |
| `common.py` | 120 | 35+ tipo mappings (SQL estándar + STRUCT, ARRAY, GEOGRAPHY, JSON), escaping, normalización |
| `_bigquery_models.py` | 60 | BigqueryRoutineDetail dataclass (para UDFs/Stored Procedures) |
| `_adapter_helpers.py` | 200 | SQL builders: `build_bigquery_*_query()` functions, info_schema queries |
| `tables.py` | 150 | `fetch_datasets_sync()`, `fetch_tables_sync()`, `fetch_columns_sync()` |
| `constraints.py` | 80 | `fetch_primary_keys_sync()`, `fetch_foreign_keys_sync()` (advisory only, empty stubs) |
| `indexes.py` | 100 | `fetch_indexes_sync()` (clustering keys + partitioning info) |
| `routines.py` | 130 | `fetch_routines_sync()`, `fetch_routine_parameters_sync()` (UDFs, Stored Procs) |
| `sync_adapter.py` | 130 | `BigquerySyncAdapter` (SourceAdapter + RoutineAdapter, duck-typing) |
| `async_adapter.py` | 130 | `BigqueryAsyncAdapter` (executor wrapper, patrón PostgreSQL/Snowflake) |

**Total: ~1,130 LOC (similar MySQL ~1,100 LOC)**

✅ **~100-120 tests en 6 archivos, ~100-150 test cases que validen:**

| Test File | # Tests | Coverage |
|-----------|---------|----------|
| `test_bigquery_common.py` | 35-40 | Type mappings (35 tipos), identifier quoting, normalization |
| `test_bigquery_tables.py` | 15-20 | Dataset fetching, tables, columns (multi-level Project.Dataset.Table) |
| `test_bigquery_constraints.py` | 8-10 | PK/FK advisory handling (empty stubs, warnings logged) |
| `test_bigquery_indexes.py` | 10-12 | Clustering keys, partitioning, index detection |
| `test_bigquery_routines.py` | 15-18 | UDFs, Stored Procedures, parameter extraction |
| `test_bigquery_adapter_parity.py` | 15-20 | Adapter protocol validation, sync/async parity |

**Total: ~100-120 tests (fixture-based, sin servicios Google Cloud)**

✅ **Auto-registración idéntica a Phase 3C.4:**
- `_register_bigquery_adapters()` en `__init__.py`
- `registry.register_source_adapter_sync("bigquery", BigquerySyncAdapter)`
- `registry.register_source_adapter_async("bigquery", BigqueryAsyncAdapter)`
- Alias opcional: `"bigquery-gcp"`, `"bq"`

✅ **Cumplimiento de SourceAdapter Protocol:**
```
✅ fetch_tables_sync(schema: str | None = None) -> list[tuple]
✅ fetch_columns_sync(schema: str, table: str) -> list[tuple]
✅ fetch_primary_keys_sync(schema: str, table: str) -> list[tuple]  # advisory stub
✅ fetch_foreign_keys_sync(schema: str, table: str) -> list[tuple]  # advisory stub
✅ fetch_indexes_sync(schema: str, table: str) -> list[tuple]
✅ fetch_routines_sync(schema: str | None = None) -> list[tuple]
```

✅ **Backward compatibility:** Cero breaking changes a managers, adapters, registry.

---

## Scope Out

❌ **No incluido (deferred a Phase 3C.5b+):**
- Native BigQuery Python client full async (`google-cloud-bigquery-async` = no stable)
- Full JSON path introspection (STRUCT nested field details deferred)
- BigQuery ML (BQML) model metadata
- Remote UDFs (UDFs en JavaScript, Python externally hosted)
- Google Cloud authentication integration (delegated a connection layer)
- BigQuery Storage API (lectura optimizada, deferred)
- Scheduled queries metadata

❌ **No refactorizar:**
- Manager, Protocol, Registry (new_feature policy)
- Existing 8 drivers

---

## BigQuery Specifics

### 1. **Project-Level Hierarchy**

BigQuery usa **Project.Dataset.Table** (vs standard SCHEMA.TABLE):
- Queries scope per dataset, require project ID in context
- Pattern: Snowflake `database` parameter → BigQuery `project` parameter
- Query format: `SELECT * FROM project.dataset.information_schema.tables`

**Acción:** Incorporar `project` en contexto de conexión (parámetro opcional)

### 2. **No PK/FK Enforcement (Advisory Only)**

Similar a Snowflake, BigQuery NO implementa constraints:
- Methods return `[]`, docstring warns "BigQuery enforces no constraints"
- Logging: warning emitido en cada llamada
- Pattern: Redshift advisory constraints → reusar mismo patrón

**Acción:** Empty stubs + logging warnings

### 3. **Clustering Keys + Partitioning**

En lugar de indexes tradicionales:
- **Clustering:** fetch from `information_schema.tables` (clustering_ordinal_position)
- **Partitioning:** fetch from `information_schema.tables` (partition_field)
- Normalizar a tuple (index_name, column_name, seq_in_index, is_unique, index_type)

**Acción:** Extender formato tuple con index_type='clustering'|'partition'

### 4. **Type System (SQL standard + semi-structured)**

35+ tipos mapeados:
- Numeric: INT, BIGINT, SMALLINT, TINYINT, FLOAT, DOUBLE, NUMERIC, DECIMAL
- String: STRING, VARCHAR, CHAR, BYTES
- Date/Time: DATE, TIME, TIMESTAMP, DATETIME
- Boolean: BOOL
- Semi-structured: **STRUCT, ARRAY, JSON**
- Geographic: **GEOGRAPHY**
- Fallback: "object"

**Acción:** STRUCT/ARRAY normalizar a "object" (como Snowflake VARIANT)

### 5. **Stored Procedures vs UDFs**

BigQuery soporta ambos en `information_schema.routines`:
- Distinguir via routine_type = 'PROCEDURE' | 'FUNCTION'
- Lenguajes: SQL, JavaScript, Python, Java, Scala
- Parameters: Query `information_schema.parameters`

**Acción:** Fetch rutinas + parámetros (pattern PostgreSQL)

### 6. **information_schema Queries (SQL Standard)**

All queries use information_schema (compatible con standard SQL):
```sql
SELECT * FROM information_schema.tables WHERE table_schema = :schema
SELECT * FROM information_schema.columns WHERE table_schema = :schema AND table_name = :table
SELECT * FROM information_schema.table_constraints WHERE table_schema = :schema
SELECT * FROM information_schema.routines WHERE routine_schema = :schema
```

**Acción:** Parameterized queries, injection-safe

---

## Riesgos & Mitigaciones

### Funcionales

🔴 **Risk 1: Project context missing**
- **Mitigación:** Validar project_id en BigquerySyncAdapter.__init__; fallback environment variable

🔴 **Risk 2: Constraints advisory misalignment**
- **Mitigación:** logging.warning() + docstring explícito + ejemplo en conexión

🟡 **Risk 3: STRUCT nested details incomplete**
- **Mitigación:** Documentado como limitación phases 3C.5b+; actual: atomic type

🟡 **Risk 4: Clustering + Partition semantics**
- **Mitigación:** Extender tuple format con index_type field

### Técnicos

🟡 **Risk 5: Async latency (executor wrapper)**
- **Mitigación:** Standard pattern, proven en otros drivers

🟡 **Risk 6: SQL dialect divergence**
- **Mitigación:** Parameterized queries, parity tests

### Seguridad

✅ **No risks:** Parameterized SQL, identifier escaping, no external APIs

---

## Test Strategy (Fixture-Based)

**Patrón Phase 3C.4 aplicado:**
- Mock cursors, parameterized fixtures
- TypeMappings validation (35+ tipos)
- Query builders tested (no SQL injection)
- Adapter protocol compliance
- Sync/async parity
- Sin servicios Google Cloud externos

**Cobertura:** 100-120 tests
- Type system: 35-40 tests
- Tables/Datasets: 15-20 tests
- Constraints (advisory): 8-10 tests
- Indexes/Clustering: 10-12 tests
- Routines: 15-18 tests
- Adapter parity: 15-20 tests

---

## Ruta de Implementación

**Orden secuencial:**

1. `common.py` + `test_bigquery_common.py`
2. `_adapter_helpers.py`
3. `tables.py` + `test_bigquery_tables.py`
4. `constraints.py` + `test_bigquery_constraints.py`
5. `indexes.py` + `test_bigquery_indexes.py`
6. `routines.py` + `test_bigquery_routines.py`
7. `_bigquery_models.py`
8. `sync_adapter.py` + `async_adapter.py` + `test_bigquery_adapter_parity.py`
9. `__init__.py`
10. Validation: pytest, ruff, mypy

---

# AUDIT_PLAN: Phase 3C.5a

## Riesgos Funcionales

1. **PK/FK constraints always empty** → mitigado por warnings + docs
2. **STRUCT field details lost** → fase deferred design (acceptable)
3. **Project context handling** → requiere validación en __init__
4. **Clustering/Partition semantics** → extender tuple con index_type

## Riesgos Técnicos

1. **No native BigQuery async** → executor wrapper (parity existing drivers)
2. **SQL information_schema dialect** → parameterized SQL protege
3. **Connection pooling** → delegado a manager (out-of-scope)

## Riesgos de Seguridad

✅ **Ninguno detectado** (parameterized SQL, identifier escaping)

## Verificaciones Previas a Implementación

- [ ] Validar BigQuery information_schema queries (70%+ coverage esperado)
- [ ] Test project_id parameter handling
- [ ] Documentar BigQuery SQL dialect en _adapter_helpers.py
- [ ] Estructurar tuple format para clustering/partitioning

---

## 🟢 VERDICT: GO CONDICIONAL

### Condiciones

**C1: Pre-implementation validation**
- [ ] Confirm BigQuery information_schema coverage
- [ ] Test project_id in connection context
- [ ] Document SQL dialect

**C2: Test coverage**
- [ ] Minimum 100-120 tests
- [ ] Fixture-based (sin Google Cloud services)
- [ ] Adapter protocol compliance

**C3: Documentation**
- [ ] 100% docstrings on public methods
- [ ] Limitations documented (advisory constraints, STRUCT, project context)
- [ ] CHANGELOG entry

**C4: Code quality**
- [ ] Ruff: 0 issues
- [ ] Mypy: 0 errors (strict)
- [ ] Zero breaking changes

### Success Criteria

✅ **After Phase 3C.5a:**
- 10 modules + 100-120 tests
- Registry auto-registration working
- Protocol compliance verified
- Total: 1,788+ tests passing
- Code quality: Ruff ✅, Mypy ✅

### Timeline

- Implementation: 2-3 hours (sequential)
- Validation + fixes: 1 hour
- **Total: 3-4 hours**

---

## Support: MongoDB Roadmap

**Decision:** MongoDB **deferred to post-v0.6.3** (requires architecture decision + new Protocol `DocumentAdapter`)

**Roadmap Future:**
- Phase 3C.5b: Mercedes Research + ADR (MongoDB + NoSQL support)
- Phase 3C.6: MongoDB implementation (new architecture, option)

---

**Prepared by:** Plan Architect
**Reviewed by:** Workflow Director
**Status:** Ready for Feature Implementer execution
