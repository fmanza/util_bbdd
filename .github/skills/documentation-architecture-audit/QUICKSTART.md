# Quick Start: `/documentation-architecture-audit` en CLAUDE Code

**Creado:** 2026-10-09  
**Status:** ✅ Listo para usar

---

## 1️⃣ Copia y pega esto en CLAUDE Code

### Full Workflow (Todas las fases)

```text
/documentation-architecture-audit

Objetivo: Auditoría y refactorización arquitectónica de módulos de documentación por motor
Fases: PLAN → AUDIT_ARCH → AUDIT_CODE → IMPROVE_PLAN → IMPLEMENT → VERIFY
Motores: PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake
Módulos: src/util_bbdd/doc/ + src/util_bbdd/analysis/
Alcance: Consolidación de módulos + eliminación de duplicidades + mejoras de seguridad + rendimiento
Breakability: Sí (la API pública puede romperse, major version bump)
Validación: docker-compose (bases de datos reales)
Benchmark: Condicional (solo si AUDIT_CODE detecta concerns de performance)
Timeline: Sin límite, profundidad máxima
```

### Fase por fase (Recomendado)

**PLAN: Mapeo de dependencias y candidatos de consolidación**
```text
/documentation-architecture-audit

Fase: PLAN
Objetivo: Mapear dependencias, inventariar features por motor, detectar candidatos de consolidación
Alcance: PostgreSQL + MySQL (comenzar rápido)
```

**AUDIT_ARCH: Análisis arquitectónico y duplicidades**
```text
/documentation-architecture-audit

Fase: AUDIT_ARCH
Prior: PLAN completado (revisar docs/audits/doc_audit_plan_*.md)
Motores: PostgreSQL, MySQL, MariaDB (profundidad total)
Deep-dive: Sí (análisis completo de duplicidades + scoring arquitectónico)
```

**AUDIT_CODE: Revisión técnica, seguridad, performance**
```text
/documentation-architecture-audit

Fase: AUDIT_CODE
Prior: AUDIT_ARCH completado
Validación: docker-compose (integración real)
Benchmark: Sí (recolectar baseline si perf es concern)
```

**IMPROVE_PLAN: Estrategia de refactorización**
```text
/documentation-architecture-audit

Fase: IMPROVE_PLAN
Prior: AUDIT_CODE completado
Deliverable: Plan con esfuerzo estimado, timeline, mapa de API breaks
```

**IMPLEMENT: Refactorización (cambios de código)**
```text
/documentation-architecture-audit

Fase: IMPLEMENT
Prior: IMPROVE_PLAN aprobado
Estrategia: Motor por motor secuencial
Validación: pytest + mypy tras cada motor
```

**VERIFY: Validación final**
```text
/documentation-architecture-audit

Fase: VERIFY
Prior: IMPLEMENT completado
Veredicto esperado: READY_FOR_RELEASE | NEEDS_REWORK | BLOCKED
```

---

## 2️⃣ Qué esperar de cada fase

### PLAN (2–4 horas)
📤 **Outputs:**
- `docs/audits/doc_audit_plan_{fecha}.md` — Resumen ejecutivo + mapa de dependencias
- `build/logs/doc_audit_plan_{fecha}.json` — Metadatos estructurados
- Matriz de features por motor (tabla)
- Propuesta de nuevas estructura de packages

### AUDIT_ARCH (4–6 horas)
📤 **Outputs:**
- `docs/audits/doc_audit_audit_arch_{fecha}.md` — Grafo de dependencias + reporte de duplicidad
- Diagramas Mermaid (dependencias)
- `build/logs/doc_audit_audit_arch_{fecha}.json` — Findings estructurados

### AUDIT_CODE (6–8 horas)
📤 **Outputs:**
- `docs/audits/doc_audit_audit_code_{fecha}.md` — Type errors, security findings, perf hotspots
- `build/logs/doc_audit_audit_code_{fecha}.json` — JSON estruturado
- Opcional: `build/logs/doc_perf_baseline_{motor}_{fecha}.json` (si perf es concern)

### IMPROVE_PLAN (4–6 horas)
📤 **Outputs:**
- `docs/audits/doc_audit_improve_plan_{fecha}.md` — Estrategia + esfuerzo + timeline
- `build/logs/doc_audit_improve_plan_{fecha}.json` — Plan estructurado
- Mapa de API breaks (tabla before → after)

### IMPLEMENT (16–24 horas)
📤 **Outputs:**
- Código refactorizado en `src/util_bbdd/doc/` y `src/util_bbdd/analysis/`
- `build/logs/test_results_implement_{motor}_{fecha}.txt` — Test results por motor
- Git commits (Conventional Commits) linked a hallazgos
- Draft CHANGELOG entry

### VERIFY (4–6 horas)
📤 **Outputs:**
- `docs/audits/doc_audit_verify_report_{fecha}.md` — Completeness check
- `build/logs/doc_audit_verify_report_{fecha}.json` — Resultados estruturados
- **VERDICT:** `READY_FOR_RELEASE` | `NEEDS_REWORK` | `BLOCKED`

---

## 3️⃣ Ficheros de Referencia

| Fichero | Propósito |
|---|---|
| `.github/SHARED_INSTRUCTIONS.md` | Canónico: arquitectura, SOLID, Conventional Commits |
| `.github/skills/documentation-architecture-audit/SKILL.md` | Definición del skill: fases, motor sequencing |
| `.github/prompts/doc_architecture_audit.prompt.md` | Contrato completo: inputs/tasks/outputs por fase |
| `.claude/commands/documentation-architecture-audit.md` | Entrada CLAUDE: reglas, ejemplos |
| `.claude/commands/` (otros) | Referencia de cómo otros comandos están estructurados |

---

## 4️⃣ Notas Importantes

### ⚠️ Requisitos
- Docker + docker-compose (para test DBs reales en AUDIT_CODE e IMPLEMENT)
- mypy, ruff, pytest instalados (se usan en validación)
- Acceso completo a `src/util_bbdd/`

### 🎯 Motor Sequencing
- **Orden:** PostgreSQL → MySQL → MariaDB → Oracle → SQL Server → SQLite → Snowflake
- **Por qué secuencial:** Cada motor aprende del anterior, mejora las abstracciones
- **Paralelizable:** No (para mantener traceabilidad)

### 🔓 API Breakage
- **Policy:** Big-bang refactor sin backward compatibility
- **Requiere:** Major version bump + CHANGELOG detallado + migration guide

### 📊 Outputs en `build/logs/`
- JSON estructurado + timestamps
- Útil para dashboards, análisis histórico
- Markdown legible para revisión manual

### ✅ Quality Gates
Cada fase MUST PASS:
- Type-check: `mypy --strict`
- Linting: `ruff check`
- Tests: `pytest` (≥80% coverage per motor en IMPLEMENT)
- Traceability: git commits linked a AUDIT findings

---

## 5️⃣ Flujo Recomendado (Full Cycle)

```
Día 1 (Morning):   /documentation-architecture-audit → Fase PLAN
Día 1 (Afternoon): /documentation-architecture-audit → Fase AUDIT_ARCH
Día 2 (Morning):   /documentation-architecture-audit → Fase AUDIT_CODE
Día 2 (Afternoon): /documentation-architecture-audit → Fase IMPROVE_PLAN (aprobación)
Día 3-4:           /documentation-architecture-audit → Fase IMPLEMENT (motor-by-motor)
Día 5 (Morning):   /documentation-architecture-audit → Fase VERIFY (final sign-off)
```

**Total:** ~5 días, dedica 4–6 horas/día

---

## 6️⃣ Troubleshooting

| Problema | Solución |
|---|---|
| "Cannot find module `doc/`" | Asegúrate que `src/util_bbdd/doc/` existe (lectura previa de PLAN) |
| Docker containers fallan | Verifica `docker-compose.yml` en raíz; inicia con `docker-compose up -d` |
| mypy/ruff no ejecutan | Reinstala: `pip install mypy ruff pytest` |
| CLAUDE me pide aprobación | Lee los outputs de fases previas, decide y re-invoca con input explícito |

---

**Status:** ✅ Listo. Copia y ejecuta en CLAUDE Code.
