---
title: Documentation Architecture Audit — Complete Workflow Prompt
description: >
  Comprehensive prompt for auditing util_bbdd documentation generation architecture
  across all database motors. Covers 6 phases with structured inputs, tasks, outputs,
  and quality gates. Supports per-phase execution and full workflow orchestration.
keywords: [architecture, audit, documentation, motors, refactoring, consolidation]
---

# Documentation Architecture Audit — Complete Workflow

**Skill:** `.github/skills/documentation-architecture-audit/SKILL.md`
**Entry point:** `/documentation-architecture-audit` (Claude Code)
**Audience:** Senior Python engineer
**Breakability:** May break public APIs (big-bang refactor, major version)

---

## 🎯 Objective

Audit `src/util_bbdd/doc/` and `src/util_bbdd/analysis/` modules across **all database motors** (PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake) to:

1. **Consolidate** related modules into clean packages with single responsibility
2. **Eliminate** duplicities and promote motor-agnostic reuse
3. **Improve** security, performance, and testability per motor
4. **Propose** architectural alternatives with full traceability (git commits, CHANGELOG)
5. **Refactor** with no backward compatibility constraints (major version bump if approved)

---

## 📋 Inputs (User Provides)

### Required
- **Phase(s) to execute:** `PLAN` | `AUDIT_ARCH` | `AUDIT_CODE` | `IMPROVE_PLAN` | `IMPLEMENT` | `VERIFY`
  (or `ALL` for complete workflow)

### Optional
- **Motor focus:** Which motors to audit first (default: PostgreSQL → MySQL → … → Snowflake, sequential)
- **Performance baseline:** `--with-benchmark` to collect perf metrics (else conditional, only if needed)
- **Test strategy:** `docker-live` for real databases | `fixtures-only` for unit tests
- **Constraints:** e.g., "maintain __init__.py public imports" (overrides default breakability policy)

---

## Phase 1: PLAN

**Mode:** Read-only
**Duration:** ~2–4 hours (all motors)
**Output location:** `docs/audits/` + `build/logs/`

### Tasks

1. **Map module dependencies** across `doc/`, `analysis/`, and driver integration:
   - Scan `src/util_bbdd/doc/` and `src/util_bbdd/analysis/` structure
   - Build dependency tree (imports, wiring, test relationships)
   - Identify tight coupling points (motor-specific code in shared modules)

2. **Inventory motor-specific features** (PostgreSQL → MySQL → … → Snowflake):
   ```
   For each motor:
     - Doc rendering paths (HTML gen, Mermaid, asset handling)
     - Metadata extraction (introspection queries, field types, constraints)
     - Constraint/permission documentation (SQL dialects, role-based features)
     - Connection pooling (motor-specific tuning, dialect quirks)
     - Type mappings (e.g., Snowflake virtual columns, Oracle LOBs)
   ```

3. **Identify consolidation candidates:**
   - Common base classes/protocols (e.g., `DocRenderer`, `MetadataExtractor`, `ConstraintParser`)
   - Motor-agnostic vs. motor-specific code boundaries
   - Duplicated query logic (search for copy-pasted introspection queries)
   - Dialect translation patterns (unified approach vs. scattershot)

4. **Define quality gate:**
   - Success criteria for "audit complete" (coverage, documentation, test coverage ≥80%)
   - Blockers vs. nice-to-have improvements
   - Timeline realism (which motors block, which can parallelize)

5. **Scope refactoring & API impact:**
   - Proposed module hierarchy (e.g., `doc/motors/{postgres,mysql,oracle}/` vs. current)
   - Which public APIs change and why
   - Deprecation path (if any; default: none, big-bang)

### Outputs

**Markdown:**
- `docs/audits/doc_audit_plan_{date}.md`
  - Executive summary (1 page)
  - Dependency map (textual or Mermaid)
  - Motor feature inventory (table: Motor | HTML Rendering | Metadata Extraction | Constraints | Pooling | Type System)
  - Consolidation candidates (ranked by impact)
  - Proposed new package structure (ASCII tree)
  - Risks & timeline

**JSON:**
- `build/logs/doc_audit_plan_{date}.json`
  ```json
  {
    "phase": "PLAN",
    "motors": ["postgres", "mysql", "mariadb", "oracle", "sqlserver", "sqlite", "snowflake"],
    "consolidation_candidates": [
      {
        "title": "Unify constraint parsing",
        "current_locations": ["doc/pg/constraints.py", "doc/mysql/constraints.py"],
        "proposed": "doc/motors/common/constraint_parser.py",
        "impact": "high",
        "effort": "medium"
      }
    ],
    "quality_gate": {
      "coverage_target": 80,
      "test_strategy": "hybrid",
      "blockers": []
    }
  }
  ```

### Example Run

```text
Phase: PLAN
Objective: Map doc architecture and find consolidation opportunities
Scope: PostgreSQL + MySQL (rapid baseline)
Output: docs/audits/doc_audit_plan_20261009.md + JSON metadata
```

---

## Phase 2: AUDIT_ARCH

**Mode:** Read-only
**Prerequisite:** PLAN completed
**Duration:** ~4–6 hours
**Output location:** `docs/audits/` + `build/logs/`

### Tasks

1. **Build dependency graph:**
   - Create Mermaid diagram showing module relationships
   - Identify import cycles (if any)
   - Highlight tight coupling (e.g., `doc/core` importing motor-specific logic)

2. **Deep duplicity analysis:**
   - Compare introspection queries across motors (line-by-line)
   - Find repeated parsing/rendering functions
   - Rank by impact: "Remove this duplication saves X LOC, improves Y %"

3. **Architecture scoring per motor:**
   - **Cohesion:** Is motor code self-contained?
   - **Coupling:** How tightly wired to core?
   - **Extensibility:** Adding a new motor requires changes to how many files?
   - **Testability:** Are motor-specific functions unit-testable in isolation?

4. **Security & performance concerns:**
   - SQL injection vectors in dynamic constraint queries
   - Secrets exposure in generated docs (passwords, connection strings)
   - Metadata query efficiency (N+1 queries, index usage)
   - Pooling overhead (connection reuse patterns)

5. **Motor-specific findings:**
   For each motor in sequence:
   - Identify pain points (e.g., MariaDB charset handling, Oracle LOB rendering)
   - Compare against reference impl (PostgreSQL)
   - Flag edge cases (virtual columns, role-based constraints, dialect quirks)

### Outputs

**Markdown:**
- `docs/audits/doc_audit_audit_arch_{date}.md`
  - Dependency graph (Mermaid)
  - Duplicity report (ranked list with file locations, line counts)
  - Per-motor architecture assessment (cohesion/coupling/extensibility scores)
  - Security findings (by severity)
  - Performance hotspots (metadata queries, rendering latency)

**Mermaid diagrams:**
- `docs/audits/doc_dependency_graph.mmd` (module relationships)
- `docs/audits/doc_motor_architecture.mmd` (per-motor structure)

**JSON:**
- `build/logs/doc_audit_audit_arch_{date}.json`
  ```json
  {
    "phase": "AUDIT_ARCH",
    "findings": [
      {
        "motor": "mysql",
        "category": "duplication",
        "severity": "high",
        "title": "Constraint parsing duplicated",
        "evidence": {
          "files": ["src/util_bbdd/doc/mysql/constraints.py:45-120", "src/util_bbdd/doc/pg/constraints.py:30-105"],
          "impact": "120 shared LOC, 2x maintenance burden"
        },
        "remediation": "Extract to doc/motors/common/constraint_parser.py"
      }
    ],
    "architecture_scores": {
      "postgres": {"cohesion": 8, "coupling": 3, "extensibility": 7},
      "mysql": {"cohesion": 6, "coupling": 5, "extensibility": 5}
    }
  }
  ```

### Example Run

```text
Phase: AUDIT_ARCH
Prior: PLAN complete (docs/audits/doc_audit_plan_20261009.md)
Motores: PostgreSQL → MySQL → MariaDB (deep dive)
Deliverables: Dependency graph + duplication ranking + per-motor scores
```

---

## Phase 3: AUDIT_CODE

**Mode:** Read-only
**Prerequisite:** PLAN, AUDIT_ARCH completed
**Duration:** ~6–8 hours
**Output location:** `docs/audits/` + `build/logs/`

### Tasks

1. **Type-check & linting per motor:**
   ```bash
   mypy src/util_bbdd/doc/postgres/ --strict
   mypy src/util_bbdd/doc/mysql/ --strict
   # ... repeat for each motor

   ruff check src/util_bbdd/doc/ src/util_bbdd/analysis/
   ```
   - Collect type errors, missing annotations, unused imports

2. **Security audit (selective):**
   - Scan constraint/metadata extraction for SQL injection (dynamic queries)
   - Check for secrets in template strings, logs
   - Validate input sanitization (user-supplied SQL fragments)
   - Permission boundaries (who can generate docs for sensitive schemas?)

3. **Performance profiling:**
   - **Metadata extraction:** Are queries using indexes? Bulk vs. N+1?
   - **Rendering:** Streaming vs. buffering? Memory footprint?
   - **Caching:** Appropriate TTL for introspection results?
   - **Pooling:** Connection reuse efficiency per motor

4. **Test coverage & gaps:**
   ```bash
   pytest tests/ -k doc --cov=src/util_bbdd/doc --cov=src/util_bbdd/analysis
   ```
   - % coverage per motor
   - Branch coverage (edge cases)
   - Integration test matrix (real databases)
   - Known edge cases (self-referential FKs, virtual columns, etc.)

5. **Conditional performance baseline:**
   - If perf issues found, snapshot metrics before IMPLEMENT:
     - INSERT/UPDATE/DELETE throughput
     - Doc generation latency per motor
     - Memory usage (peak, sustained)

### Outputs

**Markdown:**
- `docs/audits/doc_audit_audit_code_{date}.md`
  - Per-motor type-check findings (errors, warnings)
  - Security findings (by severity: critical, high, medium, low)
  - Performance hotspots (with profiler snapshots)
  - Test coverage summary (% by motor, gaps)
  - Baseline metrics (if benchmark triggered)

**JSON:**
- `build/logs/doc_audit_audit_code_{date}.json`
  ```json
  {
    "phase": "AUDIT_CODE",
    "type_errors": [{"motor": "mysql", "file": "constraints.py:45", "error": "..."}],
    "security_findings": [{"severity": "high", "category": "sqli", "location": "..."}],
    "coverage": {"postgres": 85, "mysql": 72, "mariadb": 68},
    "perf_baseline": {
      "metadata_extraction_ms": {"postgres": 45, "mysql": 52, ...},
      "doc_gen_latency_ms": {"postgres": 320, "mysql": 290, ...}
    }
  }
  ```

**Performance logs** (if triggered):
- `build/logs/doc_perf_baseline_{motor}_{date}.json`

### Example Run

```text
Phase: AUDIT_CODE
Prior: AUDIT_ARCH complete
Foco: Seguridad (SQL injection, secrets), rendimiento (metadata queries)
Validación: docker-compose (test DBs reales)
Benchmark: Sí (recolectar baseline si perf concerns)
```

---

## Phase 4: IMPROVE_PLAN

**Mode:** Read-only (planning, no code changes)
**Prerequisite:** PLAN, AUDIT_ARCH, AUDIT_CODE completed
**Duration:** ~4–6 hours
**Output location:** `docs/audits/` + `build/logs/`

### Tasks

1. **Refactoring strategy:**
   - Propose new module hierarchy (package structure)
   - Design abstraction layer (base classes, protocols for motor implementations)
   - Dependency injection approach (reduce wiring complexity)
   - Test organization (shared tests + motor-specific variants)

2. **API breakage map:**
   - List all public APIs that change (with before/after comparison)
   - Justify each break (improves cohesion/coupling/testability)
   - Migration guide for users
   - CHANGELOG entry template (per motor, per improvement)

3. **Per-motor improvement checklist:**
   ```
   For each motor:
     ☐ Consolidate constraint parsing (merge duplicates)
     ☐ Optimize metadata extraction (batch queries, cache)
     ☐ Security hardening (input validation, audit logging)
     ☐ Fix known bugs (from AUDIT_CODE)
     ☐ Improve test coverage (target: 80%+)
     ☐ Verify edge cases (motor-specific quirks)
   ```

4. **Timeline & risk assessment:**
   - Estimated effort per motor (hours)
   - Dependency order (which motors must be done first?)
   - Rollback strategy (branch per motor, smoke tests, CI gates)
   - Quality validation plan (type-check, tests, integration)

### Outputs

**Markdown:**
- `docs/audits/doc_audit_improve_plan_{date}.md`
  - Refactoring strategy (architecture diagrams, abstraction design)
  - API breakage table (current → new, justification, migration step)
  - Per-motor improvement checklist (with effort estimates)
  - Timeline & dependencies (Gantt-style or text)
  - Risk mitigation (rollback, smoke tests, CI gates)

**JSON:**
- `build/logs/doc_audit_improve_plan_{date}.json`
  ```json
  {
    "phase": "IMPROVE_PLAN",
    "api_breaks": [
      {
        "current": "from util_bbdd.doc.pg import PostgresDocGenerator",
        "new": "from util_bbdd.doc.motors.postgres import PostgresDocGenerator",
        "justification": "Cleaner hierarchy, motor isolation",
        "migration": "Update imports in 1.0 docs"
      }
    ],
    "motor_tasks": {
      "postgres": [
        {"task": "Consolidate constraint parsing", "effort_hours": 8, "priority": "high"}
      ]
    },
    "timeline": {"total_effort_hours": 120, "critical_path_motors": ["postgres", "mysql"]}
  }
  ```

### Example Run

```text
Phase: IMPROVE_PLAN
Prior: AUDIT_CODE complete
Approvals: API breaks OK?, Security findings blockers?, Perf improvements worth effort?
Scope: Proponer cambios arquitectónicos con esfuerzo + riesgo estimados
```

---

## Phase 5: IMPLEMENT

**Mode:** Read-write (code changes)
**Prerequisite:** IMPROVE_PLAN approved
**Duration:** ~16–24 hours (all motors sequentially)
**Output location:** Git commits + test results + `build/logs/`

### Tasks

1. **Consolidate modules per IMPROVE_PLAN:**
   - Rename/move directories (e.g., `doc/pg/` → `doc/motors/postgres/`)
   - Update imports and `__init__.py` files
   - Verify no import cycles: `ruff check --select=F401,F405,F403`

2. **Extract abstractions (for each motor in sequence):**
   - Define base class/protocol for motor implementations
   - Implement for current motor (e.g., `PostgresDocGenerator(DocGenerator)`)
   - Update tests to use parametrized fixtures
   - Verify against protocol

3. **Fix bugs & security issues (from AUDIT_CODE):**
   - Apply fixes with regression tests
   - Validate type-check after each fix

4. **Optimize performance:**
   - Batch metadata extraction (single query vs. multiple)
   - Implement connection pooling improvements
   - Cache introspection results (with TTL)
   - Run benchmarks and log delta vs. baseline

5. **Update documentation:**
   - Motor-specific guides (if doc/ API changes)
   - Architecture guide (new structure, abstraction layer)
   - Migration notes (for end users)
   - Update `mkdocs.yml`

### Validation During IMPLEMENT

After each motor's work:
```bash
# Type-check
mypy src/util_bbdd/doc/{motor}/ --strict

# Lint
ruff check src/util_bbdd/doc/{motor}/

# Unit tests
pytest tests/ -k "{motor}_doc" -v

# Integration tests (real DB)
pytest tests/integration/ -k "{motor}" --docker=live

# Check coverage
pytest tests/ -k "{motor}" --cov=src/util_bbdd/doc --cov-report=term
```

### Outputs

**Refactored source tree:**
- New package structure on disk
- Updated imports in `src/util_bbdd/doc/__init__.py`
- New abstractions and implementations

**Test results:**
- `build/logs/test_results_implement_{motor}_{date}.txt`
- Coverage reports (`htmlcov/`)

**Benchmarks** (if perf improvements made):
- `build/logs/doc_perf_after_{motor}_{date}.json` (compare vs. baseline)

**Git commits:**
- Conventional Commits per motor (e.g., `refactor(doc/postgres): consolidate constraints`)
- Links to AUDIT findings in commit messages

**CHANGELOG entry** (draft for review):
- Per-motor improvements with rationale

### Example Run

```text
Phase: IMPLEMENT
Estrategia: Motor-by-motor (PostgreSQL → MySQL → MariaDB)
Cambios: Consolidar módulos, extraer abstracciones, fijar bugs
Validación: pytest + type-check tras cada motor
Commits: Conventional Commits con trazabilidad a AUDIT_CODE
```

---

## Phase 6: VERIFY

**Mode:** Read-only (final validation)
**Prerequisite:** IMPLEMENT completed
**Duration:** ~4–6 hours
**Output location:** `docs/audits/` + verification report

### Tasks

1. **Completeness check:**
   - All findings from AUDIT_ARCH and AUDIT_CODE addressed (fixed or deferred with ticket)
   - Test coverage maintained or improved
   - No import cycles or dead code

2. **Performance validation:**
   - Run benchmarks post-IMPLEMENT
   - Compare vs. baseline (delta %)
   - Memory profiling (no leaks)
   - Log results

3. **Motor-specific validation (sequential):**
   For each motor:
   ```bash
   # Type-check
   mypy src/util_bbdd/doc/{motor}/ --strict  # MUST PASS

   # Tests
   pytest tests/ -k "{motor}" --docker=live  # MUST PASS

   # Sample doc generation
   python -c "from util_bbdd.doc import DocGenerator; ..."  # MUST succeed

   # Coverage
   pytest tests/ --cov=src/util_bbdd/doc/{motor} --cov-report=term  # ≥80% target
   ```

4. **API stability:**
   - Public API surface cleaner (imports in `__init__.py` explicit, no dead exports)
   - Coupling reduced (motor code isolated)
   - No circular dependencies
   - Type-safe public interface

5. **Traceability audit:**
   - git log shows clear trail: commit → audit finding → fix
   - CHANGELOG documents breaking changes with rationale
   - All issues created during IMPLEMENT are linked to PRs

### Outputs

**Markdown:**
- `docs/audits/doc_audit_verify_report_{date}.md`
  - Completeness matrix (findings → fixed/deferred)
  - Performance comparison (before → after %)
  - Motor-specific validation results (type-check, tests, coverage)
  - API stability summary
  - Traceability checklist

**JSON:**
- `build/logs/doc_audit_verify_report_{date}.json`
  ```json
  {
    "phase": "VERIFY",
    "completeness": {
      "findings_addressed": 24,
      "findings_deferred": 2,
      "coverage_delta": "+5%"
    },
    "motor_results": {
      "postgres": {"type_check": "pass", "tests": "pass", "coverage": 88},
      "mysql": {"type_check": "pass", "tests": "pass", "coverage": 85}
    },
    "verdict": "READY_FOR_RELEASE | NEEDS_REWORK | BLOCKED"
  }
  ```

### Verdict Options

- **READY_FOR_RELEASE** — All quality gates pass, traceability complete, ready to merge + release notes
- **NEEDS_REWORK** — Blockers found in validation (type errors, test failures, coverage gap)
- **BLOCKED** — Critical issues require architectural re-decision or external approval

### Example Run

```text
Phase: VERIFY
Prior: IMPLEMENT complete (all motors refactored)
Validación: pytest + mypy + perf comparison + API review
Veredicto: READY_FOR_RELEASE | NEEDS_REWORK
Salida: Verification report + readiness sign-off
```

---

## Full Workflow Example

```text
/documentation-architecture-audit

Objetivo: Auditoría y refactorización completa de arquitectura doc
Fases: PLAN → AUDIT_ARCH → AUDIT_CODE → IMPROVE_PLAN → IMPLEMENT → VERIFY
Motores: Todos (PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake)
Módulos: src/util_bbdd/doc/ + src/util_bbdd/analysis/
Alcance: Consolidación, duplicidades, seguridad, rendimiento
Breakability: Sí (major version)
Validación: Docker (test DBs reales) + pytest
Benchmark: Condicional (si AUDIT_CODE lo detecta)
Timeline: Profundidad máxima

---

[PLAN runs: 2-4h]
Outputs: plan.md + motor_inventory.md + quality_gate.md

[AUDIT_ARCH runs: 4-6h]
Outputs: audit_architecture.md + dependency_graph.mmd + duplication_report.md

[AUDIT_CODE runs: 6-8h]
Outputs: audit_code.md + security_findings.md + coverage_report.md (+ baseline if perf)

[IMPROVE_PLAN runs: 4-6h]
Outputs: improve_plan.md + motor_specific_improvements.md + refactoring_architecture.md

[IMPLEMENT runs: 16-24h, per-motor validation]
Outputs: Refactored source + test results + benchmarks + git commits (conventional)

[VERIFY runs: 4-6h]
Outputs: verify_report.md + VERDICT (READY_FOR_RELEASE | NEEDS_REWORK | BLOCKED)

---

Total time: ~36-54 hours (all motors sequentially)
Parallelizable: No (sequential per motor for traceability + learning)
CI/CD: Type-check, lint, tests must pass after each motor
Release: Major version bump (breaking changes) + detailed migration guide
```

---

## Quality Gates & Completion Criteria

✅ **All findings addressed:** AUDIT_ARCH + AUDIT_CODE fixes or deferred with tickets
✅ **Test coverage:** ≥80% per motor (maintained or improved)
✅ **Type-safe:** `mypy src/util_bbdd/doc/ --strict` passes
✅ **Linting:** `ruff check src/util_bbdd/doc/` no issues
✅ **Performance:** Doc gen latency ±5% vs. baseline (or improved)
✅ **Security:** No SQL injection, no secrets in docs, input validation present
✅ **Traceability:** git commits linked to audit findings, CHANGELOG updated
✅ **Motor-specific:** Sample doc generation passes for all 7-8 motors

---

## References

- **Skill definition:** `.github/skills/documentation-architecture-audit/SKILL.md`
- **CLAUDE command:** `.claude/commands/documentation-architecture-audit.md`
- **Project instructions:** `.github/SHARED_INSTRUCTIONS.md`
- **Related skills:** `drivers-connections-audit`, `performance-audit-bulk`

---

**Version:** 1.0
**Last updated:** 2026-10-09
