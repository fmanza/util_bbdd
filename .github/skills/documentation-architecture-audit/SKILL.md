# Documentation Architecture Audit Skill

**Scope:** Complete `src/util_bbdd/` with emphasis on `doc/`, `analysis/`, and their motor-specific implementations.

**Audience:** Senior Python engineer executing this skill manually.

**Purpose:** Audit documentation generation architecture across all database motors (PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake, etc.) to:
1. Consolidate related modules into clean, single-responsibility packages
2. Identify and eliminate duplicities for motor-agnostic reuse
3. Audit motor-specific implementations for performance, security, bugs, connection pooling improvements
4. Propose architectural alternatives with full traceability

**Breakability:** May break public APIs if architectural improvements justify it. Full CHANGELOG and rationale required.

---

## Workflow Phases

### Phase 1: PLAN

**Inputs:**
- Current project state (read-only scan of `src/util_bbdd/`)
- Motor inventory (PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake)
- Existing motor-specific doc generation features (HTML rendering, Mermaid diagrams, constraints, permissions, indexes, etc.)

**Tasks:**
1. **Map module dependencies** across `doc/`, `analysis/`, and driver wiring
2. **Inventory motor-specific features:**
   - Doc rendering paths (HTML generation, Mermaid, asset handling)
   - Metadata extraction strategies (introspection queries vary by motor)
   - Constraint and permission documentation
   - Connection pooling and dialect-specific optimizations
3. **Identify candidate consolidations:**
   - Common abstractions (DocRenderer, MetadataExtractor, ConstraintParser)
   - Motor-agnostic core vs. motor-specific variants
   - Duplicated query logic, dialect translations
4. **Scope refactoring:**
   - Which modules move/merge (e.g., `doc/pg/`, `doc/mysql/` → `doc/motors/{postgres,mysql}/`)
   - Which APIs break and why
   - Proposed new public interface
5. **Define quality gate:** What evidence proves the audit is complete?

**Outputs:**
- `plan.md` (scope, dependencies, risks, timeline)
- `motor_inventory.md` (feature matrix by motor)
- `quality_gate.md` (completion criteria)

---

### Phase 2: AUDIT_ARCH

**Inputs:**
- PLAN phase outputs
- Source code in `src/util_bbdd/`
- git history (for traceability of motor-specific decisions)

**Tasks:**
1. **Dependency graph:** Build a visual/textual dependency map:
   ```
   doc/
     ├── core/         (motor-agnostic base)
     ├── renderers/    (HTML, Mermaid, text outputs)
     ├── motors/       (postgres/, mysql/, oracle/, ...)
     └── assets/       (CSS, JS, templates)

   analysis/
     ├── metadata/     (introspection wrappers)
     ├── constraints/  (parse and document)
     └── motors/       (motor-specific extraction logic)
   ```

2. **Duplicity analysis:**
   - Scan for copy-pasted query logic across motor dirs
   - Find repeated parsing/rendering functions
   - Flag module-level imports that reveal tight coupling
   - Example: `doc/pg/constraints.py` vs. `doc/mysql/constraints.py` — common base?

3. **Motor-specific audit per engine:**
   - **Performance:** Connection pooling efficiency, metadata query cost, bulk doc generation throughput
   - **Security:** SQL injection in dynamic constraint queries, sensitive field exposure, auth boundaries
   - **Bugs:** Known issues in motor-specific code (e.g., charset handling in MariaDB, LOB rendering in Oracle)
   - **Design smells:** Violation of SOLID, over-coupling, hard-coded dialect assumptions

4. **Architecture score:**
   - Cohesion: Are doc modules grouped logically?
   - Coupling: How tightly are motors wired into core logic?
   - Extensibility: Adding a new motor requires changes to how many files?
   - Maintainability: Is motor-specific code isolated and testable?

**Outputs:**
- `audit_architecture.md` (findings, risk matrix, per-motor summaries)
- `dependency_graph.md` or `.mmd` (Mermaid diagram)
- `duplication_report.md` (copy-paste analysis + reuse candidates)

---

### Phase 3: AUDIT_CODE

**Inputs:**
- AUDIT_ARCH findings
- Source files identified in phase 2

**Tasks:**
1. **Per-motor code review:**
   - Pylance type-check + mypy strict mode on each motor dir
   - Linting (ruff) for style and imports
   - Coverage gaps in motor-specific tests
   - Thread-safety in pooling scenarios

2. **Security review (selective):**
   - Scan constraint/metadata extraction for SQL injection vectors
   - Check for secrets in doc rendering (passwords in examples, connection strings)
   - Validate input sanitization for user-supplied SQL fragments

3. **Performance hotspots:**
   - Metadata extraction queries: Are they using indexes? Bulk queries vs. N+1?
   - Rendering: Is HTML generation streaming or buffering entire doc?
   - Caching: Are motor introspection results cached appropriately?

4. **Test evidence:**
   - Motor-specific test coverage (% lines, % branches)
   - Integration test matrix (does each motor's doc generation pass?)
   - Edge cases by motor (e.g., self-referential FKs in MySQL, virtual columns in Snowflake)

**Outputs:**
- `audit_code.md` (per-motor findings: bugs, security issues, perf bottlenecks, test gaps)
- Code review notes (inline comments in key files)
- Benchmark baseline (if perf audit required)

---

### Phase 4: IMPROVE_PLAN

**Inputs:**
- AUDIT_ARCH + AUDIT_CODE outputs
- Approved scope (which findings are blockers vs. nice-to-have?)

**Tasks:**
1. **Propose refactoring strategy:**
   - Motor package consolidation (module hierarchy, imports, __init__.py structure)
   - Abstraction layer design (common interfaces for motor-specific implementations)
   - Dependency injection pattern to reduce wiring complexity
   - Suggested test structure (shared tests + motor-specific variants)

2. **Break-API map:**
   - List all public APIs that will change
   - Deprecation path (if partial compat required)
   - Migration guide for users

3. **Per-motor improvement checklist:**
   - Pooling optimization (connection reuse, timeout tuning)
   - Query performance (batch metadata extraction, caching strategy)
   - Security hardening (input validation, audit logging)
   - Bug fixes and edge cases

4. **Timeline and risk:**
   - Estimated effort per motor
   - Rollback strategy (branch per motor, CI gates, smoke tests)
   - Quality validation (type-check, tests, integration)

**Outputs:**
- `improve_plan.md` (strategy, API changes, timeline, risks)
- `motor_specific_improvements.md` (per-motor tasks and rationale)
- `refactoring_architecture.md` (proposed new structure)

---

### Phase 5: IMPLEMENT

**Inputs:**
- IMPROVE_PLAN approval
- Quality gate definition from phase 1

**Tasks:**
1. **Consolidate modules per plan:**
   - Rename/move directories
   - Update imports and __init__.py files
   - Verify no import cycles (use `ruff check --select=F401,F405,F403`)

2. **Extract abstractions:**
   - Define base classes/protocols for motor-specific implementations
   - Implement for each motor, validating against common interface
   - Update tests to use parametrized fixtures per motor

3. **Fix bugs and security issues:**
   - Apply fixes identified in AUDIT_CODE
   - Add regression tests for each fix

4. **Optimize perf and pooling:**
   - Batch metadata extraction where applicable
   - Implement connection pooling improvements
   - Add benchmarks to track progress

5. **Update documentation:**
   - Motor-specific guides (if doc/ API changes)
   - Architecture diagram (updated structure)
   - Migration notes (for users upgrading)

**Validation during IMPLEMENT:**
- Type-check after each major change: `mypy src/util_bbdd --strict`
- Linting: `ruff check src`
- Unit tests: `pytest tests/ -k motor` (motor-specific tests)
- Integration tests: Spawn test databases and run doc generation end-to-end

**Outputs:**
- Refactored source tree
- Updated test suite
- Passing CI (type-check, lint, tests)
- CHANGELOG entry (per motor, per improvement)

---

### Phase 6: VERIFY

**Inputs:**
- IMPLEMENT phase outputs
- Quality gate criteria

**Tasks:**
1. **Validate completeness:**
   - All findings from AUDIT_ARCH and AUDIT_CODE have been addressed (or deferred with ticket)
   - Test coverage maintained or improved
   - No import cycles, no dead code

2. **Performance validation:**
   - Run benchmarks before/after for doc generation
   - Connection pooling stats (pool utilization, wait times)
   - Memory profiling (doc rendering shouldn't leak)

3. **Motor-specific validation:**
   - Test suite passes for all motors (PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake)
   - Sample documentation generated for each motor is correct (HTML, constraints, indexes, permissions)
   - Edge cases from AUDIT_CODE are covered

4. **API stability check:**
   - Public API surface has shrunk or simplified (goal: lower coupling)
   - Imports in `__init__.py` are clean (only re-export what's needed)
   - No circular dependencies

5. **Traceability audit:**
   - git log shows clear commit messages linking to issues/improvements
   - CHANGELOG documents all breaking changes with rationale

**Outputs:**
- `verify_report.md` (pass/fail on quality gates, evidence)
- Benchmark comparison (before/after metrics)
- Motor-specific validation log
- Readiness sign-off (READY FOR RELEASE or blockers)

---

## Motor Sequencing Strategy

**Execution order (sequential, depth-first per motor):**

1. **PostgreSQL** (reference impl, most mature)
2. **MySQL** (similar to PG, helps identify abstractions)
3. **MariaDB** (inherits from MySQL, identifies compat issues)
4. **Oracle** (unique features: LOBs, packages, role-based security)
5. **SQL Server** (T-SQL dialects, cross-database ownership)
6. **SQLite** (minimal, helps identify motor-agnostic core)
7. **Snowflake** (cloud-native quirks, virtual columns)
8. **Other motors** (as defined in `src/util_bbdd/drivers/`)

**Rationale:** Audit order balances learning curve (PG/MySQL easier) with discovery of abstractions (MariaDB compat) and edge cases (Oracle/Snowflake). Allows findings to shape abstraction layer incrementally.

---

## Testing Strategy During AUDIT_CODE & IMPLEMENT

**Hybrid approach:**
- **Unit tests:** Use pytest parametrized fixtures (motor-agnostic test code, parameterized by dialect)
- **Integration tests:** Spin up real databases via `docker-compose.yml` for end-to-end doc generation
- **Coverage gate:** ≥80% per motor (measured after each motor's work completes)

**Commands:**
```bash
# Unit tests with existing fixtures
pytest tests/ -k "doc" --cov=src/util_bbdd/doc --cov-report=html

# Integration tests (requires docker-compose up)
pytest tests/integration/ -k "motor" --docker=live

# Per-motor validation (after IMPLEMENT)
pytest tests/ -k "postgres" --verify-doc-output
pytest tests/ -k "mysql" --verify-doc-output
# ... etc
```

---

## API Breakage Policy

**Strategy: Big-bang refactor (major version bump).**

- Reorganize module hierarchy without backward-compatibility layer
- Update all imports in public `__init__.py` (clean slate)
- Document migration path in CHANGELOG and new architecture guide
- No deprecation warnings (users upgrade major version, docs guide migration)
- Rationale: Cleaner codebase justifies the disruption; doc generation is not core business logic

---

## Performance Baseline

**Policy: Conditional, not automatic.**

- **Trigger:** Only if AUDIT_CODE identifies performance as a concern
- **Baseline collection:** If triggered, snapshot metrics before IMPLEMENT (INSERT/UPDATE/DELETE throughput, doc generation latency, memory)
- **Validation:** After IMPLEMENT, re-run benchmarks and include comparison in VERIFY report
- **Storage:** Benchmark results in `build/logs/doc_perf_*.json` for historical tracking

---

## Output Formats

**All phases produce:**
1. **Markdown reports** (human-readable, for review): `docs/audits/doc_audit_YYYYMMDD_{phase}.md`
2. **JSON metadata** (for tools/dashboards): `build/logs/doc_audit_YYYYMMDD_{phase}.json`
   - Structured findings (motor, severity, category, evidence)
   - Traceability links (git commits, file paths, line numbers)
   - Metrics (LOC, complexity, coverage, perf impact %)

**Example JSON structure:**
```json
{
  "phase": "AUDIT_ARCH",
  "timestamp": "2026-10-09T14:30:00Z",
  "findings": [
    {
      "motor": "mysql",
      "category": "duplication",
      "severity": "high",
      "title": "Constraint parsing duplicated in doc/mysql and doc/core",
      "evidence": {"files": ["src/util_bbdd/doc/mysql/constraints.py:45"], "lines": 120},
      "traceability": {"git_blame": "commit abc123", "related_ticket": "NONE"}
    }
  ],
  "summary": {"total_findings": 24, "by_severity": {"high": 8, "medium": 12, "low": 4}}
}
```

---

## Invocation

**Trigger phrases:**
- "documentation architecture audit"
- "audit doc generation"
- "consolidate doc modules"
- "analyze documentation motor implementations"
- "doc refactoring scope and strategy"
- "motor-specific doc improvements"

**Inputs to provide:**
- Optionally: starting motor (default: PostgreSQL, proceed sequentially)
- Optionally: `--with-benchmark` to force perf baseline collection
- Optionally: `--focus-motors=postgres,mysql` to audit subset
- Constraints: e.g., "maintain backward compat for public imports" (overrides default big-bang policy)

**Expected interaction:**
1. User runs phase (e.g., "Run PLAN phase for doc audit")
2. Skill produces outputs (Markdown reports, graphs)
3. User reviews, asks clarifying questions
4. Skill refines findings or moves to next phase
5. Cycle until VERIFY phase passes

---

## Related Skills / Prompts

- **`drivers-connections-audit`** — Complements this skill; audits connection architecture and pooling
- **`performance-audit-bulk`** — Focuses on bulk INSERT/UPDATE/DELETE (relevant for generated DDL testing)
- **`feature-inventory`** — Catalogs existing doc features (could feed into PLAN phase)
- **`code-auditor` agent** — Peer review after IMPLEMENT for independent verification

---

## Quality Criteria (Phase 1 PLAN output)

✅ **Cohesion:** Doc modules logically organized by responsibility (rendering, extraction, motors).
✅ **Coupling:** Motor-specific code isolated; core doc logic motor-agnostic.
✅ **Extensibility:** Adding a new motor requires ≤3 new files and updates to 1-2 base classes.
✅ **Tests:** ≥80% coverage per motor; integration tests pass end-to-end.
✅ **Performance:** Doc generation latency ±5% vs. baseline; connection pooling efficient.
✅ **Security:** No SQL injection, no secrets in generated docs, input validation present.
✅ **Traceability:** All changes linked to audit findings via git commits and CHANGELOG.

---

**Version:** 1.0
**Last updated:** 2026-10-09
