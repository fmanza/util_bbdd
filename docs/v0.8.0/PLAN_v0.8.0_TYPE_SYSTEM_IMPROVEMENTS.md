# PLAN — v0.8.0: Advanced Type System Improvements

**Document Type:** Technical Plan (ADR-style)
**Version:** 0.1 (Draft)
**Date:** 2026-04-21
**Proposer:** Development Team
**Status:** 📋 PLANNED (Awaiting Approval)

---

## 1. Executive Summary

**Goal:** Enhance type system to support advanced/complex database types (composite types, JSON schemas, semi-structured data) across PostgreSQL, MySQL, Snowflake.

**Scope:** 3 improvement phases, 24+ test cases, ~3-4 weeks total effort
**Priority:** 🟡 MEDIUM (improves API richness, not blocking)
**Impact:** 5-8 new capabilities + improved type precision

| Metric | Current (v0.7.0) | Target (v0.8.0) | Change |
|---|---|---|---|
| Type Mappings | 100+ base types | 100+ + 15 advanced | +15% |
| Supported Complex Types | 3 (ARRAY, ENUM, JSON) | 6 (+ Composite, OBJECT, partial JSON schema) | +100% |
| Test Coverage | 1,881 tests | 1,905 tests | +24 tests |
| Drivers with Advanced Type Support | 3 (PostgreSQL, Snowflake, MySQL) | 3/3 | No change drivers, +depth |
| Documentation | Basic mappings | Basic + Advanced Guide | +1 guide |

---

## 2. Problem Statement

### Current Limitations

#### 2.1 PostgreSQL Composite Types
**Problem:** User-defined composite types (e.g., `address_type (street TEXT, city TEXT, zip VARCHAR(10))`) currently mapped to generic `"object"` type.

**Impact:**
- Lost precision: clients cannot determine field structure
- Workaround: users must write custom SQL or use raw results
- Example: `SELECT col FROM table LIMIT 0` for column inference

**Example:**
```sql
-- PostgreSQL: User-defined composite type
CREATE TYPE address_type AS (
    street TEXT,
    city TEXT,
    zip VARCHAR(10),
    country TEXT
);

CREATE TABLE users (
    id INT PRIMARY KEY,
    address address_type
);

-- Current v0.7.0 output:
{
    "name": "address",
    "type": "object",        -- ← Lost field structure
    "nullable": true
}

-- Desired v0.8.0 output:
{
    "name": "address",
    "type": "composite",
    "nullable": true,
    "fields": [
        {"name": "street", "type": "text"},
        {"name": "city", "type": "text"},
        {"name": "zip", "type": "varchar", "max_length": 10},
        {"name": "country", "type": "text"}
    ]
}
```

#### 2.2 JSON/JSONB Schema Introspection (MySQL & PostgreSQL)
**Problem:** JSON columns have no schema metadata; mapped to `"object"` with no field hints.

**Impact:**
- Clients cannot validate JSON structure programmatically
- No IDE autocomplete support for JSON fields
- Documentation must be manual or in code comments

**Example:**
```sql
-- MySQL: JSON column with implicit structure
CREATE TABLE api_responses (
    id INT PRIMARY KEY,
    payload JSON
);

INSERT INTO api_responses VALUES (1, '{"user_id": 1, "status": "active"}');

-- Current v0.7.0:
{
    "name": "payload",
    "type": "json",
    "nullable": true
    -- No schema info
}

-- Desired v0.8.0:
{
    "name": "payload",
    "type": "json",
    "nullable": true,
    "schema_hint": {
        "type": "object",
        "properties": {
            "user_id": {"type": "integer"},
            "status": {"type": "string", "enum": ["active", "inactive"]}
        }
    }
}
```

#### 2.3 Snowflake OBJECT & ARRAY Introspection
**Problem:** Snowflake semi-structured types (OBJECT, ARRAY) are opaque; currently mapped to `"object"` with no element type info.

**Impact:**
- Query builders cannot generate type-safe access patterns
- ARRAY element type unknown → unsafe JSON path traversal
- OBJECT schema completely lost

**Example:**
```sql
-- Snowflake: Semi-structured types
CREATE TABLE events (
    id INT,
    event_data OBJECT,              -- {"name": "...", "tags": [...], "metadata": {...}}
    event_list ARRAY,               -- List of event objects
    event_nested ARRAY<OBJECT>      -- Typed arrays
);

-- Current v0.7.0:
{
    "name": "event_data",
    "type": "object"    -- ← No structure, no field names
}

-- Desired v0.8.0:
{
    "name": "event_data",
    "type": "object",
    "schema": {
        "name": {"type": "varchar"},
        "tags": {"type": "array", "element_type": "varchar"},
        "metadata": {"type": "object", "properties": {...}}
    }
}
```

#### 2.4 Cross-Database Type Precision Loss
**Problem:** Some drivers map types inconsistently, losing precision.

**Examples:**
- MySQL `ENUM('a','b','c')` → `"enum"` (loses values)
- MySQL `SET('x','y','z')` → `"string"` (loses set semantics)
- PostgreSQL `numeric(10,2)` → `"decimal"` (loses precision hint: `numeric(10,2)` vs `numeric(10,1)`)

---

## 3. Goals & Non-Goals

### ✅ Goals (In Scope)

1. **PostgreSQL Composite Types**
   - Parse user-defined types via `pg_type` + `pg_attribute`
   - Return field-level structure (name, type, ordinal position)
   - Support nested composites (type containing composite type)

2. **JSON Schema Introspection (MySQL & PostgreSQL)**
   - Extract JSON schema from CHECK constraints (if present)
   - Provide "schema_hint" field with inferred structure
   - Support sampling (introspect 100 rows to infer types) as fallback

3. **Snowflake OBJECT & ARRAY**
   - Parse `OBJECT<k1: T1, k2: T2>` syntax
   - Extract element types from `ARRAY<T>`
   - Detect nested OBJECT within ARRAY

4. **Type Precision Documentation**
   - Add `max_length`, `numeric_precision`, `numeric_scale` fields for applicable types
   - Normalize `numeric(p,s)` parsing across drivers

5. **Backwards Compatibility**
   - All existing type mappings remain unchanged
   - New fields (`fields`, `schema_hint`, `precision`) are optional/nullable
   - No breaking changes to existing API

### ❌ Non-Goals (Out of Scope)

- ❌ Full JSON Schema validation (out of scope; use JSON Schema validator lib)
- ❌ Query builder integration (separate feature, Phase 5)
- ❌ Real-time schema change notifications (deferred to Phase 4A)
- ❌ Non-Relational DBs (MongoDB, Cassandra) — v0.9.0+
- ❌ Generated TypeScript/Python dataclasses (separate feature)

---

## 4. Solution Architecture

### 4.1 Type System Enhancement

#### New Types & Subtypes

```python
# Existing types (v0.7.0)
BASIC_TYPES = ["integer", "string", "boolean", "date", "timestamp", "decimal", "float", "json", "enum"]

# NEW types (v0.8.0)
ADVANCED_TYPES = [
    "composite",        # PostgreSQL: user-defined composite types
    "object",           # Snowflake: semi-structured OBJECT (replaces generic "object")
    "array",            # Typed arrays (replaces generic "array" mapping)
]

# NEW type attributes (optional, nullable)
class TypeInfo:
    name: str
    type: str                           # e.g., "composite", "object"
    nullable: bool
    # NEW:
    precision: int | None               # numeric(10, 2) → precision=10, scale=2
    scale: int | None
    max_length: int | None              # varchar(255) → max_length=255
    fields: list[TypeInfo] | None       # Composite type fields
    element_type: str | None            # ARRAY element type
    schema_hint: dict[str, Any] | None  # JSON schema suggestion
```

#### Driver-Specific Implementations

**PostgreSQL:**
```python
# src/util_bbdd/metadata/postgresql/types_advanced.py (NEW)

def parse_composite_type(type_oid: int, adapter) -> TypeInfo | None:
    """
    Query pg_type + pg_attribute for composite type structure.

    SELECT
        pg_type.typname,
        pg_attribute.attname,
        pg_attribute.atttypid,
        pg_attribute.attnum
    FROM pg_type
    JOIN pg_attribute ON pg_attribute.attrelid = pg_type.typrelid
    WHERE pg_type.oid = %s
    ORDER BY pg_attribute.attnum
    """
    pass

def parse_json_schema_from_check_constraint(
    schema: str, table: str, column: str, adapter
) -> dict[str, Any] | None:
    """Extract JSON schema from CHECK constraint if present."""
    pass

def sample_json_column_for_schema(
    schema: str, table: str, column: str, adapter, sample_size: int = 100
) -> dict[str, Any] | None:
    """Sample column values to infer JSON schema (fallback)."""
    pass
```

**MySQL:**
```python
# src/util_bbdd/metadata/mysql/types_advanced.py (NEW)

def parse_enum_values(type_str: str) -> list[str]:
    """Extract ENUM values from 'enum(\"a\",\"b\",\"c\")' """
    pass

def parse_set_values(type_str: str) -> list[str]:
    """Extract SET values"""
    pass

def parse_json_schema_from_check_constraint(
    schema: str, table: str, column: str, adapter
) -> dict[str, Any] | None:
    """MySQL: Extract JSON schema from CHECK constraint (limited support)."""
    pass
```

**Snowflake:**
```python
# src/util_bbdd/metadata/snowflake/types_advanced.py (NEW)

def parse_snowflake_object_schema(type_str: str) -> dict[str, Any]:
    """
    Parse Snowflake OBJECT syntax: OBJECT<k1: T1, k2: T2, ...>

    Example:
        'OBJECT<customer_id: INTEGER, name: VARCHAR, active: BOOLEAN>'
        → {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "name": {"type": "varchar"},
                "active": {"type": "boolean"}
            }
        }
    """
    pass

def parse_snowflake_array_type(type_str: str) -> dict[str, Any]:
    """
    Parse Snowflake ARRAY syntax: ARRAY<T>

    Example:
        'ARRAY<OBJECT<id: INTEGER, tags: ARRAY<VARCHAR>>>'
        → {
            "type": "array",
            "element_type": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "tags": {"type": "array", "element_type": {"type": "varchar"}}
                }
            }
        }
    """
    pass
```

### 4.2 Integration Points

#### Column Metadata Response (v0.8.0)

**Current (v0.7.0):**
```python
{
    "name": "address",
    "type": "object",
    "nullable": true,
    "default": null,
    "ordinal_position": 3
}
```

**Enhanced (v0.8.0):**
```python
{
    "name": "address",
    "type": "composite",          # or "object", "array", etc.
    "nullable": true,
    "default": null,
    "ordinal_position": 3,

    # NEW (optional, nullable)
    "precision": null,
    "scale": null,
    "max_length": null,
    "element_type": null,
    "fields": [                    # For composite types
        {
            "name": "street",
            "type": "varchar",
            "max_length": 255,
            "nullable": true
        },
        {
            "name": "zip",
            "type": "varchar",
            "max_length": 10,
            "nullable": false
        }
    ],
    "schema_hint": null           # For JSON columns
}
```

#### Module Structure

```
src/util_bbdd/metadata/
├── adapters/
│   ├── shared/
│   │   ├── type_system.py       (NEW) — TypeInfo class, type parsing utils
│   │   └── json_schema.py       (NEW) — JSON schema extraction/inference
│   └── ...
│
├── postgresql/
│   ├── types_advanced.py        (NEW) — Composite, JSON schema
│   ├── common.py                (UPDATED) — Register new parsers
│   └── ...
│
├── mysql/
│   ├── types_advanced.py        (NEW) — ENUM/SET details, JSON schema
│   ├── common.py                (UPDATED)
│   └── ...
│
├── snowflake/
│   ├── types_advanced.py        (NEW) — OBJECT, ARRAY parsing
│   ├── common.py                (UPDATED)
│   └── ...
│
└── manager.py                   (UPDATED) — Pass TypeInfo to callers
```

---

## 5. Implementation Strategy

### Phase 1: PostgreSQL Composite Types (Week 1)

**Objectives:**
- Parse composite types via pg_type + pg_attribute
- Return structured field metadata
- Document limitations

**Tasks:**
1. Create `src/util_bbdd/metadata/postgresql/types_advanced.py`
   - `parse_composite_type_structure()` — Query pg_type, pg_attribute
   - `resolve_field_types()` — Recursively resolve nested composite types
   - Handle edge cases: array fields, nested composites, domains

2. Update `src/util_bbdd/metadata/postgresql/common.py`
   - Register new parser in type mapping registry
   - Add `"composite"` to supported type list

3. Tests: `tests/integration/metadata/postgresql/test_composite_types.py`
   - Test case 1: Simple composite (3 fields)
   - Test case 2: Nested composite
   - Test case 3: Composite with ARRAY field
   - Test case 4: Composite with nullable vs not-null fields
   - Test case 5: Multiple composites in single table
   - Test case 6: Composite with domain types
   - Test case 7: Error handling (type not found)
   - Test case 8: Performance (composite with 50+ fields)

**Estimated Effort:** 3-4 days | Risk: Low | Test Coverage: 8 tests

**Deliverables:**
- ✅ PostgreSQL composite type introspection
- ✅ 8 integration tests
- ✅ Docstring with examples

---

### Phase 2: JSON Schema Introspection (Week 1-2)

**Objectives:**
- Extract JSON schema from CHECK constraints (if available)
- Provide sampling-based schema inference as fallback
- Support MySQL & PostgreSQL

**Tasks:**

1. Create `src/util_bbdd/metadata/adapters/shared/json_schema.py` (NEW)
   - `extract_json_schema_from_check_constraint()` — Parse CHECK clause
   - `infer_json_schema_from_sample()` — Sample column values
   - `merge_inferred_schemas()` — Combine multiple sample inferences

2. Update PostgreSQL adapter
   - `src/util_bbdd/metadata/postgresql/types_advanced.py`
   - Add `query_json_column_schema()` function
   - Integrate with column metadata fetcher

3. Update MySQL adapter
   - `src/util_bbdd/metadata/mysql/types_advanced.py`
   - Similar to PostgreSQL, adjust for MySQL syntax

4. Tests: `tests/integration/metadata/*/test_json_schema_introspection.py`
   - PostgreSQL test cases (6):
     1. JSON column with no constraint → sampling
     2. JSON column with CHECK constraint → extraction
     3. JSONB column type variant
     4. Nested JSON schema (object within object)
     5. JSON array schema
     6. Error handling (large table → sampling limit)

   - MySQL test cases (6):
     1. JSON column (no schema available) → sampling
     2. JSON with CHECK (limited MySQL support)
     3. Large JSON object
     4. JSON array
     5. Mixed types in array (schema inference challenge)
     6. Error handling

**Estimated Effort:** 4-5 days | Risk: Medium (sampling accuracy) | Test Coverage: 12 tests

**Deliverables:**
- ✅ JSON schema extraction logic
- ✅ Sampling-based inference (with configurable sample size)
- ✅ 12 integration tests
- ✅ Docstring + examples

---

### Phase 3: Snowflake OBJECT & ARRAY (Week 2-3)

**Objectives:**
- Parse Snowflake semi-structured type syntax
- Extract OBJECT field schema
- Extract ARRAY element types
- Handle nested OBJECT<ARRAY<...>> patterns

**Tasks:**

1. Create `src/util_bbdd/metadata/snowflake/types_advanced.py`
   - `parse_snowflake_object_syntax()` — Parse `OBJECT<k1: T1, k2: T2>`
   - `parse_snowflake_array_syntax()` — Parse `ARRAY<T>`
   - `normalize_snowflake_types()` — Handle Snowflake type aliases (TIMESTAMP_NTZ, etc.)

2. Update Snowflake adapter
   - Modify column metadata fetcher to use new parsers
   - Replace generic `"object"` type with structured metadata

3. Tests: `tests/integration/metadata/snowflake/test_object_array_types.py`
   - Test case 1: Simple OBJECT<k: T>
   - Test case 2: OBJECT with 5+ fields
   - Test case 3: Nested OBJECT
   - Test case 4: Simple ARRAY<T>
   - Test case 5: ARRAY<OBJECT<...>>
   - Test case 6: ARRAY<ARRAY<...>> (deeply nested)
   - Test case 7: Mixed OBJECT + ARRAY + primitives
   - Test case 8: Snowflake function return types (OBJECT/ARRAY)
   - Test case 9: Case sensitivity handling (Snowflake uppercases)
   - Test case 10: Error handling (malformed type syntax)

**Estimated Effort:** 5-6 days | Risk: Medium (syntax complexity) | Test Coverage: 10 tests

**Deliverables:**
- ✅ Snowflake type parser
- ✅ 10 integration tests
- ✅ Docstring + examples
- ✅ Known limitations documentation

---

## 6. Risk Assessment

### Technical Risks

| Risk | Severity | Mitigation | Contingency |
|---|---|---|---|
| JSON sampling accuracy (incomplete schema) | 🟡 Medium | Limit sample size, document assumptions | Users can provide custom schema hints via extension point |
| Snowflake type syntax parsing (errors in large DBs) | 🟡 Medium | Thorough regex testing, fallback to generic "object" | Degrade gracefully, log warning |
| PostgreSQL recursive composite types (infinite loops) | 🟠 High | Depth limit (max 5 levels), cycle detection | Degrade to "composite" without fields |
| Performance: sampling large JSON columns | 🟡 Medium | Make sample size configurable, add LIMIT clause | Skip schema inference if table > 1M rows |

### Non-Technical Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Scope creep (TypeScript codegen, GraphQL) | 🟡 Medium | Strict scope definition (this PLAN only covers introspection) |
| Testing effort underestimated | 🟡 Medium | Allocate 30% buffer, test edge cases early |
| MySQL JSON support complexity (limited CHECK support) | 🟢 Low | Document "best-effort" approach; provide fallback (sampling) |

---

## 7. Testing Strategy

### Unit Tests (Local)

```
tests/unit/metadata/
├── test_type_system.py
│   ├── test_parse_composite_type_structure()
│   ├── test_resolve_field_types_nested()
│   ├── test_parse_snowflake_object_syntax()
│   ├── test_parse_snowflake_array_syntax()
│   ├── test_json_schema_inference()
│   └── ... (15-20 unit tests)
```

### Integration Tests (Live DB)

```
tests/integration/metadata/postgresql/
├── test_composite_types.py (8 tests)
├── test_json_schema_introspection.py (6 tests)

tests/integration/metadata/mysql/
├── test_json_schema_introspection.py (6 tests)

tests/integration/metadata/snowflake/
├── test_object_array_types.py (10 tests)
```

### Test Data Setup

**PostgreSQL:**
```sql
-- tests/fixtures/postgresql_advanced_types.sql
CREATE TYPE address_type AS (
    street TEXT,
    city TEXT,
    zip VARCHAR(10),
    country TEXT DEFAULT 'US'
);

CREATE TABLE users_composite (
    id INT PRIMARY KEY,
    name VARCHAR(255),
    address address_type
);

CREATE TABLE api_logs_json (
    id INT PRIMARY KEY,
    payload JSON CHECK (JSON_VALID(payload))
);
```

**MySQL:**
```sql
-- tests/fixtures/mysql_json_types.sql
CREATE TABLE events (
    id INT PRIMARY KEY,
    event_data JSON,
    tags JSON
);

CREATE TABLE api_responses (
    id INT PRIMARY KEY,
    response_body JSON
);
```

**Snowflake:**
```sql
-- tests/fixtures/snowflake_object_array_types.sql
CREATE TABLE events_typed (
    id INT,
    event_data OBJECT<id: INTEGER, name: VARCHAR, tags: ARRAY<VARCHAR>>,
    event_list ARRAY<OBJECT<timestamp: TIMESTAMP, value: DOUBLE>>
);
```

### Coverage Goals

| Metric | Target |
|---|---|
| Unit test coverage | ≥ 85% for new modules |
| Integration test count | ≥ 24 tests (3 phases × 8+ tests each) |
| Edge case coverage | Recursive types, NULL fields, errors, performance |
| Backwards compatibility | 100% — no breaking changes to v0.7.0 API |

---

## 8. Timeline & Resources

### Estimated Effort Breakdown

| Phase | Duration | FTE | Resources | Delivery |
|---|---|---|---|---|
| **Phase 1: PostgreSQL Composites** | 3-4 days | 1 | 1 backend eng, 1 QA | Commit + tests |
| **Phase 2: JSON Schema** | 4-5 days | 1 | 1 backend eng, 1 QA | Commit + tests |
| **Phase 3: Snowflake OBJECT/ARRAY** | 5-6 days | 1 | 1 backend eng, 1 QA | Commit + tests |
| **Integration & Documentation** | 2-3 days | 1 | 1 backend eng, 1 doc writer | Docs + CHANGELOG |
| **Buffer (contingency)** | 2-3 days | — | — | — |
| **TOTAL** | 16-21 days (~3-4 weeks) | 1 | 1 backend eng + 1 QA | v0.8.0 release |

### Development Timeline

```
Week 1:
  Mon-Wed: Phase 1 implementation + tests (PostgreSQL composites)
  Thu-Fri: Phase 2 start (JSON schema extraction)

Week 2:
  Mon-Wed: Phase 2 continuation (JSON sampling, tests)
  Thu-Fri: Phase 3 start (Snowflake parsing)

Week 3:
  Mon-Wed: Phase 3 continuation (Snowflake ARRAY, tests)
  Thu-Fri: Integration testing, documentation

Week 4 (if needed):
  Mon-Tue: Buffer / contingency fixes
  Wed-Fri: Final validation, CHANGELOG, release prep
```

### Success Criteria

✅ **Definition of Done:**
- All 24+ test cases passing
- Code coverage ≥ 85% for new modules
- Lint & type-check passing (mypy strict mode)
- Documentation complete (docstrings + examples + MIGRATION_GUIDE_v0.8.0.md)
- No breaking changes to v0.7.0 API
- Performance: composite introspection < 500ms, JSON sampling < 1s for 1M row tables
- Backwards compatibility validated (v0.7.0 code works unmodified with v0.8.0)

---

## 9. Backwards Compatibility & Migration

### API Changes

**No breaking changes.** All new fields are **optional** and **nullable**.

**Existing v0.7.0 Code:**
```python
# v0.7.0 — Still works in v0.8.0
column = get_column_metadata("table", "address")
print(column["type"])  # "object" → will be "composite" (soft change)
```

**v0.8.0 Code (New Features):**
```python
# v0.8.0 — Access advanced type info
column = get_column_metadata("table", "address")
if column.get("fields"):
    for field in column["fields"]:
        print(f"  {field['name']}: {field['type']}")
```

### Migration Guide

**For v0.7.0 Users Upgrading to v0.8.0:**

1. **Type name changes (soft breaking):**
   - PostgreSQL composite: `"object"` → `"composite"`
   - MySQL ENUM: `"enum"` → stays `"enum"` but now includes `values` field
   - Snowflake OBJECT: `"object"` → stays `"object"` but now includes `schema` field

   **Action:** Update type checks from `if type == "object"` to `if type in ("object", "composite")`

2. **New optional fields:**
   - `fields` (for composite types)
   - `schema_hint` (for JSON columns)
   - `precision`, `scale`, `max_length` (type precision)

   **Action:** Use `.get()` with defaults: `column.get("fields", [])`

3. **JSON schema sampling:**
   - New default behavior: JSON columns will include `schema_hint` (best-effort)
   - Optional: disable via `enable_json_schema_inference=False` in manager config

**No immediate action required.** Existing code continues to work.

---

## 10. Approval & Sign-Off

| Role | Status | Date |
|---|---|---|
| **Tech Lead** | ⏳ Pending | — |
| **QA Lead** | ⏳ Pending | — |
| **Product Owner** | ⏳ Pending | — |
| **Security Review** | ⏳ Pending | — |

**Next Step:** Present to stakeholders for approval → Proceed with Phase 1.

---

## 11. Appendices

### A. Type Mapping Reference (v0.8.0)

#### PostgreSQL
```python
POSTGRES_TYPE_MAPPINGS = {
    "int2": "integer",
    "int4": "integer",
    "int8": "integer",
    "numeric": "decimal",           # NEW: precision, scale available
    "varchar": "string",            # NEW: max_length available
    "text": "string",
    "date": "date",
    "timestamp": "timestamp",
    "timestamptz": "timestamp",     # NEW: with_timezone: true
    "boolean": "boolean",
    "json": "json",                 # NEW: schema_hint available
    "jsonb": "json",                # NEW: schema_hint available
    "uuid": "string",               # Special format
    "bytea": "binary",
    "composite_*": "composite",     # NEW: fields available
    # ... (70+ types)
}
```

#### MySQL
```python
MYSQL_TYPE_MAPPINGS = {
    "TINYINT": "integer",
    "INT": "integer",
    "BIGINT": "integer",
    "DECIMAL": "decimal",           # NEW: precision, scale available
    "VARCHAR": "string",            # NEW: max_length available
    "TEXT": "string",
    "DATE": "date",
    "TIMESTAMP": "timestamp",
    "JSON": "json",                 # NEW: schema_hint available
    "ENUM": "enum",                 # NEW: values available
    "SET": "set",                   # NEW (v0.8.0): values available
    # ... (30+ types)
}
```

#### Snowflake
```python
SNOWFLAKE_TYPE_MAPPINGS = {
    "INTEGER": "integer",
    "DECIMAL": "decimal",           # NEW: precision, scale available
    "VARCHAR": "string",            # NEW: max_length available
    "TIMESTAMP_NTZ": "timestamp",
    "TIMESTAMP_LTZ": "timestamp",   # NEW: with_timezone: true
    "OBJECT": "object",             # NEW: schema available
    "ARRAY": "array",               # NEW: element_type available
    # ... (40+ types)
}
```

### B. Example: PostgreSQL Composite Type Introspection

**User Query:**
```python
from util_bbdd import AsyncDatabaseManager

manager = AsyncDatabaseManager(db_type="postgresql", ...)

# Get column with composite type
columns = await manager.get_columns(schema="public", table="users")
address_col = next(c for c in columns if c["name"] == "address")

print(f"Type: {address_col['type']}")
# Output: Type: composite

if address_col.get("fields"):
    print("Fields:")
    for field in address_col["fields"]:
        print(f"  - {field['name']}: {field['type']}" +
              (f" ({field['max_length']})" if field.get('max_length') else ""))

    # Output:
    # Fields:
    #   - street: varchar (255)
    #   - city: varchar (100)
    #   - zip: varchar (10)
    #   - country: varchar (100)
```

### C. Example: JSON Schema Inference (MySQL)

**User Query:**
```python
# MySQL: JSON column with no explicit schema
columns = await manager.get_columns(schema="test_db", table="events")
payload_col = next(c for c in columns if c["name"] == "payload")

print(f"Type: {payload_col['type']}")
# Output: Type: json

if payload_col.get("schema_hint"):
    schema = payload_col["schema_hint"]
    print(f"Inferred schema (from {schema.get('sample_count', 100)} rows):")
    print(json.dumps(schema, indent=2))

    # Output:
    # Inferred schema (from 100 rows):
    # {
    #   "type": "object",
    #   "properties": {
    #     "user_id": {"type": "integer"},
    #     "timestamp": {"type": "string", "format": "date-time"},
    #     "status": {"type": "string", "enum": ["active", "inactive"]}
    #   },
    #   "required": ["user_id", "status"]
    # }
```

### D. Example: Snowflake OBJECT Introspection

**User Query:**
```python
# Snowflake: OBJECT<...> semi-structured type
columns = await manager.get_columns(schema="raw", table="events")
data_col = next(c for c in columns if c["name"] == "event_data")

print(f"Type: {data_col['type']}")
# Output: Type: object

if data_col.get("schema"):
    schema = data_col["schema"]
    print("Schema properties:")
    for prop_name, prop_type in schema.get("properties", {}).items():
        print(f"  - {prop_name}: {prop_type}")

    # Output:
    # Schema properties:
    #   - customer_id: integer
    #   - name: varchar
    #   - tags: array (of varchar)
    #   - metadata: object
```

---

## 12. References & Further Reading

- **ADR-002: Type System Architecture** (linked in repo)
- **PostgreSQL pg_type documentation:** https://www.postgresql.org/docs/current/catalog-pg-type.html
- **MySQL JSON documentation:** https://dev.mysql.com/doc/refman/8.0/en/json.html
- **Snowflake data types:** https://docs.snowflake.com/en/sql-reference/data-types.html
- **JSON Schema specification:** https://json-schema.org/

---

**End of PLAN document**

---

## Summary

This PLAN formally proposes **v0.8.0: Advanced Type System Improvements** with:

✅ **3 Implementation Phases** (3-4 weeks total)
✅ **24+ Test Cases** (8 PostgreSQL + 6 MySQL + 10 Snowflake)
✅ **0 Breaking Changes** (backwards compatible with v0.7.0)
✅ **Clear Timeline & Risk Assessment**
✅ **Success Criteria & Sign-off Process**

**Next Step:** Review, approve, and proceed with Phase 1 (PostgreSQL composites).
