# Documentation Architecture Audit Skill

**Version:** 1.0  
**Status:** Complete (ready for use with CLAUDE Code)

---

## Files Created

### Skill Definition
- **[`SKILL.md`](SKILL.md)** — Core skill definition with 6 phases (PLAN → AUDIT_ARCH → AUDIT_CODE → IMPROVE_PLAN → IMPLEMENT → VERIFY)

### CLAUDE Code Integration
- **[`.claude/commands/documentation-architecture-audit.md`](../../.claude/commands/documentation-architecture-audit.md)** — Slash command entry point (`/documentation-architecture-audit`)

### Prompt & Workflow
- **[`.github/prompts/doc_architecture_audit.prompt.md`](../../prompts/doc_architecture_audit.prompt.md)** — Complete workflow prompt with detailed tasks, inputs, outputs per phase

### Updated Files
- **[`CLAUDE.md`](../../CLAUDE.md)** — Added new command to slash commands table

---

## Quick Start (CLAUDE Code)

### Invoke the Skill

Open Claude Code and type:

```text
/documentation-architecture-audit

Objetivo: Auditoría y refactorización de arquitectura doc
Fases: PLAN → AUDIT_ARCH → AUDIT_CODE → IMPROVE_PLAN → IMPLEMENT → VERIFY
Motores: PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake (todos)
Módulos: src/util_bbdd/doc/ + src/util_bbdd/analysis/
Alcance: Consolidación módulos + eliminación duplicidades + mejoras seguridad + perf
Breakability: Sí (API pública puede romperse, major version)
Validación: docker-compose (test DBs reales)
Benchmark: Condicional (si AUDIT_CODE lo detecta)
```

Or start with a single phase:

```text
/documentation-architecture-audit

Fase: PLAN
Objetivo: Mapear dependencias y detectar candidatos de consolidación
Alcance rápido: Sí (PostgreSQL + MySQL)
```

---

## Workflow Overview

### Phase 1: PLAN (2–4 hours)
- Map dependencies across `doc/`, `analysis/`, driver integration
- Inventory motor-specific features per motor (PostgreSQL → MySQL → … → Snowflake)
- Identify consolidation candidates + quality gate definition
- **Outputs:** `docs/audits/doc_audit_plan_{date}.md` + JSON metadata

### Phase 2: AUDIT_ARCH (4–6 hours)
- Build dependency graph (Mermaid diagrams)
- Deep duplicity analysis (find copy-paste, shared patterns)
- Per-motor architecture scoring (cohesion, coupling, extensibility)
- Security & performance concerns
- **Outputs:** `docs/audits/doc_audit_audit_arch_{date}.md` + graphs + JSON

### Phase 3: AUDIT_CODE (6–8 hours)
- Type-check + linting per motor
- Security audit (SQL injection, secrets, input validation)
- Performance profiling (metadata queries, rendering latency)
- Test coverage gaps
- Optional: Performance baseline (if perf concerns found)
- **Outputs:** `docs/audits/doc_audit_audit_code_{date}.md` + JSON + perf logs

### Phase 4: IMPROVE_PLAN (4–6 hours)
- Propose refactoring strategy (new module hierarchy, abstractions)
- API breakage map (current → new)
- Per-motor improvement checklist
- Timeline & risk assessment
- **Outputs:** `docs/audits/doc_audit_improve_plan_{date}.md` + JSON

### Phase 5: IMPLEMENT (16–24 hours)
- Consolidate modules per IMPROVE_PLAN
- Extract abstractions for each motor
- Fix bugs & security issues
- Optimize performance (batch queries, pooling, caching)
- Update documentation
- Validation: mypy, ruff, pytest after each motor
- **Outputs:** Refactored source + test results + git commits + CHANGELOG draft

### Phase 6: VERIFY (4–6 hours)
- Completeness check (all findings addressed)
- Performance validation (vs. baseline)
- Motor-specific validation (all motors pass type-check + tests)
- API stability review
- Traceability audit (git commits linked to findings)
- **Outputs:** `docs/audits/doc_audit_verify_report_{date}.md` + VERDICT

---

## Key Decisions

| Aspect | Decision | Rationale |
|---|---|---|
| **Audience** | Senior Python engineer (manual execution) | Deep architecture knowledge required |
| **Scope** | Complete `src/util_bbdd/` (doc/ + analysis/) | Full impact analysis needed |
| **Motor sequence** | Sequential (PG → MySQL → … → Snowflake) | Depth-first; learning feeds into abstraction design |
| **Testing** | Hybrid (pytest fixtures + docker-compose) | Unit tests fast, integration tests real |
| **API breakage** | Big-bang refactor (major version) | Cleaner codebase justifies disruption |
| **Perf baseline** | Conditional (only if AUDIT_CODE flags it) | Avoid unnecessary benchmarking overhead |
| **Output format** | Markdown (human) + JSON (machine) | Readable reports + dashboard integration |

---

## Related Skills & Documentation

- **[`.github/skills/drivers-connections-audit/SKILL.md`](../drivers-connections-audit/SKILL.md)** — Complements this skill; audits connection pooling architecture
- **[`.github/prompts/doc_architecture_audit.prompt.md`](../../prompts/doc_architecture_audit.prompt.md)** — Full workflow prompt (use as reference)
- **[`.claude/commands/documentation-architecture-audit.md`](../../.claude/commands/documentation-architecture-audit.md)** — CLAUDE slash command entry

---

## Quality Gates

✅ All findings from AUDIT_ARCH and AUDIT_CODE addressed (fixed or deferred)  
✅ Test coverage ≥80% per motor (maintained or improved)  
✅ Type-safe: `mypy src/util_bbdd/doc/ --strict` passes  
✅ No linting issues: `ruff check` passes  
✅ Performance: Doc gen latency ±5% vs. baseline (or improved)  
✅ Security: No SQL injection, secrets, or validation gaps  
✅ Traceability: git commits linked to findings, CHANGELOG updated  
✅ All 7–8 motors validate (sample doc generation passes)  

---

## References

- **Main prompt:** `.github/prompts/doc_architecture_audit.prompt.md`
- **CLAUDE command:** `.claude/commands/documentation-architecture-audit.md`
- **Project instructions:** `.github/SHARED_INSTRUCTIONS.md`
- **Main documentation:** `docs/architecture.md`

---

**Created:** 2026-10-09  
**Status:** Ready for execution
