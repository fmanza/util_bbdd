# Ejecución de drivers-connections-audit SKILL en Claude Code

**Versión SKILL:** 1.0.5 (auditoría cerrada)  
**Ubicación SKILL:** `.github/skills/drivers-connections-audit/SKILL.md`  
**Estado:** FASE 1 ejecutada el 2026-10-08 con `/audit-code` → veredicto **RECHAZADO** (5 bloqueantes P0).
✅ P0 corregidos en **v0.35.5** con `/hotfix` (`.ai/sessions/2026-10-08b-hotfix-drivers-p0/`) y P1 en **v0.35.6**
(`.ai/sessions/2026-10-08c-fix-drivers-p1/`); P2 S3/M2/G1 en **v0.35.7** (`.ai/sessions/2026-10-08d-fix-drivers-p2/`) y el resto de P2 en **v0.35.8**
(`.ai/sessions/2026-10-08e-fix-drivers-p2b/`). Todos los hallazgos de FASE 1 cerrados. FASE 2-3 ejecutadas el 2026-10-09
(`.ai/sessions/2026-10-09-drivers-connections-audit-fase2/`): Opción B acotada, readiness gate **GO_CONDICIONAL**.
FASE 4 ejecutada el 2026-10-09: B6 (v0.35.9), B5 (v0.35.10), B4 (v0.35.11), B3 (v0.36.0), hotfix del pool async de
Oracle (v0.36.1), B1 (v0.37.0), CS (v0.38.0) y B2 (v0.39.0); sesiones `.ai/sessions/2026-10-09-*`.
FASE 5 (`/audit-code`, 2026-10-09): **APROBADO CON CONDICIONES**; F1/F2 corregidos en **v0.39.1**. FASE 6: ADR-005
(`docs/adr/ADR-005-conexiones-multimotor.md`) y deuda F3–F5, M5, H1 en `docs/roadmap.md`. **Auditoría cerrada.**

### Resultado de FASE 1 (resumen)

| P0 | Hallazgo | Ubicación |
|---|---|---|
| S1 | Usuario/contraseña sin escapar en 9 URLs de engine: una contraseña con `@` redirige la conexión a otro host (reproducido) | `src/util_bbdd/factory/sqlalchemy_engine_factory.py`, `async_sqlalchemy_engine_factory.py` |
| B1 | La lista blanca de `database_types.json` rechaza `oracle_thick_mode`, `close_timeout`, `pool_name`, `options`, `target_session_attrs` (reproducido) | `src/util_bbdd/_drivers/validator.py`, `connection/builder.py:74` |
| B2 | `oracle_thick_mode` no llega a `OracleConnection.connect`; el pool inicializa thick por su cuenta | `connection/config.py`, `connection/oracle/pool_connection_oracle.py:110` |
| S4 | El camino SQLAlchemy (bulk, dump, comparar) ignora TLS y charset (`create_engine` sin `connect_args`) | `factory/sqlalchemy_engine_factory.py` |
| T1 | v0.35.4 publicada con 10 tests rojos (5 charset, 5 versión de docs) | `tests/unit/metadata/test_charset_detection.py`, `tests/unit/test_docs_version.py` |

Logs: `build/logs/drivers_audit_fase1_baseline.txt`, `build/logs/drivers_audit_fase1_full_suite.txt`.
Premisas de la skill refutadas y corregidas: `.github/skills/drivers-connections-audit/CORRECTIONS_APPLIED.md`
(sección v1.0.3).

### Comando para corregir los P0 (antes de FASE 2)

`/audit-code` es de solo lectura: no sirve para IMPLEMENT. Los P0 son bugs y fallos de seguridad, no refactor:

```markdown
/hotfix

Bug: P0 de FASE 1 de drivers-connections-audit (S1, B1, B2, S4, T1)
Evidencia: .claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md § Resultado de FASE 1
Alcance: src/util_bbdd/factory/**, src/util_bbdd/_drivers/**, src/util_bbdd/connection/**, src/util_bbdd/data/database_types.json, tests/unit/**
```

---

## Procedimiento de Ejecución

### **Opción 1: Con Slash Command (Recomendado)**

Abre Claude Code y usa `/audit-code`:

```markdown
/audit-code

Objeto: drivers-connections-audit SKILL de util_bbdd
Fases: FASE 1 (RECONNAISSANCE) — Inventario de drivers, duplicidades, auditoría por motor
Alcance: src/util_bbdd/connection/**, src/util_bbdd/metadata/**, src/util_bbdd/_drivers/**, src/util_bbdd/managers/**
Motores: MariaDB, MySQL, PostgreSQL, Oracle, SQL Server, SQLite, HSQLDB
Aspectos: Seguridad, Rendimiento, Bugs Residuales, Duplicidades, Charset Strategy

Entregar:
1. Tabla resumen de motores (inventario de drivers/configs/metadata)
2. Matriz de duplicidades (% LoC, ubicaciones, prioridad)
3. Hallazgos de auditoría por motor (seguridad, rendimiento, bugs)
4. Matriz de dependencias (bulk, dump, managers vs connection/metadata)
```

### **Opción 2: Lenguaje Natural Directo**

Sin slash command, escribe en Claude Code:

```markdown
Usa drivers-connections-audit SKILL.

FASE 1: RECONNAISSANCE (lectura)

Objetivo: Inventariar drivers, analizar duplicidades, auditar seguridad/rendimiento por motor

Entrega:
- Tabla: Motores (Config, Sync, Async, Pool, Metadata, Validator, Drivers, Special Params)
- Matriz: Duplicidades (Aspecto, Duplicado, Ubicaciones, % Código, Prioridad)
- Auditoría por motor: Seguridad + Rendimiento + Bugs
- Matriz de dependencias: bulk, dump, managers vs connection/metadata

Motores: MariaDB, MySQL, PostgreSQL, Oracle, SQL Server, SQLite, HSQLDB
Scope: src/util_bbdd/connection/**, metadata/**, _drivers/**, managers/**
```

### **Opción 3: Invocación Directa sin Slash Command**

```markdown
Ejecuta la FASE 1 (RECONNAISSANCE) del SKILL drivers-connections-audit.

Lee primero:
- .github/SHARED_INSTRUCTIONS.md (arquitectura canónica)
- pyproject.toml (drivers opcionales por motor)

Luego genera:
1. test_phase_1_motor_inventory.md — Tabla de inventario con 7 motores
2. test_phase_1_duplicities.md — Matriz de duplicación (boilerplate, config, async, pool)
3. test_phase_1_security_audit.md — Hallazgos de seguridad por motor
4. test_phase_1_performance_audit.md — Hallazgos de rendimiento (charset detection, pool sizing)
5. test_phase_1_dependencies_matrix.md — Matriz: bulk, dump, managers vs layers bajos
```

---

## Por Qué Opción 1 (Recomendada)

✅ Claude Code entiende `/audit-code` nativo  
✅ Hooks PostToolUse automático: `ruff`, `mypy`, `pytest` (recogida de tests)  
✅ Salida formateada según contrato AUDIT_CODE  
✅ Puede ejecutar pytest para verificar hallazgos (FASE 1 lo hizo; salida en `build/logs/`)  
✅ Flujo conocido hacia FASE 2-6 posterior  

⚠️ `/audit-code` solo vale para fases de lectura (1, 2, 3, 5). Para FASE 4 (IMPLEMENT) usa `/refactor` (duplicidades,
sin cambio funcional) o `/hotfix` / `/new-feature` según el tipo de cambio.

---

## Fases Subsecuentes (Con Opción 1 por Cada FASE)

### **FASE 2: PLANNING (Design 2B + Risk Assessment 2C)**

```markdown
/audit-code

Objeto: drivers-connections-audit SKILL de util_bbdd — FASE 2 PLANNING
Fases: FASE 2A (Code Review), FASE 2B (Design), FASE 2C (Risk Assessment)
Alcance: src/util_bbdd/connection/**, src/util_bbdd/metadata/**, src/util_bbdd/factory/**, src/util_bbdd/managers/**, src/util_bbdd/bulk/**, src/util_bbdd/dump/**
Requisito: P0 de FASE 1 corregidos

Entrega:
1. design_phase_2b_refactor_options.md — Opción A vs Opción B, recalculadas con la duplicidad medida en FASE 1
   (pools: 32 % de similitud media; lo duplicado de verdad es cierre, DSN Oracle, mapeo aiomysql y factories)
2. risk_assessment_phase_2c.md — Matriz de riesgos por motor, breaking changes, rollback strategies
3. dependencies_migration_plan.md — bulk y dump reciben Engine (dependen de metadata/ y factory/, no del pool)
4. decision_matrix_phase_2.md — Charset strategy (alcance: MariaDB/MySQL), paridad de los dos caminos de conexión, Scope
```

---

### **FASE 3: AUDIT_PLAN (Validación del Plan, Decisiones Críticas)**

```markdown
/audit-code

Objeto: drivers-connections-audit SKILL de util_bbdd — FASE 3 AUDIT_PLAN
Fases: FASE 3 (Validación y decisiones de go/no-go)
Alcance: Diseño 2B + Risk 2C + Decisiones críticas

Entrega:
1. audit_plan_validation_checklist.md — Validación de plan completeness
2. critical_decisions_resolution.md — Resolución de C7 (MariaDB charset) y charset strategy (C3 cerrada en FASE 1)
3. implementation_readiness_gate.md — GO / GO_CONDICIONAL / NO_GO verdict
4. clarification_questions_resolved.md — Preguntas de clarificación respondidas
```

---

### **FASE 4: IMPLEMENT (Refactor Efectivo)**

```markdown
/refactor

Objeto: drivers-connections-audit SKILL de util_bbdd — FASE 4 IMPLEMENT
Fases: FASE 4.1 (Charset Strategy), FASE 4.2 (Base Classes), FASE 4.3 (Metadata Executor), FASE 4.4 (Validators)
Alcance: Reescrituras acotadas a scope aprobado en FASE 3

Entrega:
1. implementation_phase_4_charset_strategy.md — Charset strategy (DETECT/UTF8MB4/NATIVE/CUSTOM) con el alcance decidido en FASE 3 (MariaDB/MySQL como mínimo; async y camino SQLAlchemy incluidos)
2. implementation_phase_4_base_classes.md — Base classes refactor (SyncConnection, AsyncConnection, Pool)
3. implementation_phase_4_metadata_executor.md — Metadata executor por motor (catálogos centralizados)
4. implementation_phase_4_validators.md — Validators refactor (consolidación de validación por motor)
5. test_coverage_phase_4.md — Cobertura de tests por subsistema
```

---

### **FASE 5: AUDIT_CODE (Revisión Post-Implement)**

```markdown
/audit-code

Objeto: drivers-connections-audit SKILL de util_bbdd — FASE 5 AUDIT_CODE
Fases: FASE 5 (Auditoría de código post-refactor)
Alcance: Cambios implementados en FASE 4

Entrega:
1. code_review_phase_5_architecture.md — Coherencia arquitectónica, SOLID principles
2. code_review_phase_5_security.md — Hallazgos de seguridad (auth, secrets, validación)
3. code_review_phase_5_performance.md — Rendimiento (charset detection, pool sizing, async)
4. code_review_phase_5_testing.md — Cobertura de tests, edge cases, smoke tests
5. residual_risks_phase_5.md — Riesgos residuales y mitigaciones
6. verdict_phase_5.md — APROBADO / APROBADO CON CONDICIONES / RECHAZADO
```

---

### **FASE 6: VERSION (Changelog + ADR + Observability)**

```markdown
/version-closure

Objeto: drivers-connections-audit SKILL de util_bbdd — FASE 6 VERSION
Fases: FASE 6 (Cierre de versión)
Alcance: Consolidación, documentación, handoff

Entrega:
1. changelog_phase_6.md — CHANGELOG entry (breaking changes, deprecations, features)
2. adr_phase_6.md — ADR-XXX (Architecture Decision Records — decisiones críticas)
3. migration_guide_phase_6.md — Guía de migración para usuarios (API changes, charset handling)
4. rollback_plan_phase_6.md — Plan de rollback, compatibilidad hacia atrás
5. observability_checklist_phase_6.md — Métricas, logging, tracing para post-release
6. version_closure_summary.md — Resumen ejecutivo, handoff a equipo de mantenimiento
```

---

## Flujo de Ejecución Completo

```
FASE 1: RECONNAISSANCE ← Inventario + Duplicidades + Auditoría por motor
  ↓
FASE 2: PLANNING ← Design options + Risk assessment + Decision matrix
  ↓
FASE 3: AUDIT_PLAN ← Validación de plan + Resolución crítica → GO verdict
  ↓
[Si GO o GO_CONDICIONAL en FASE 3:]
  ↓
FASE 4: IMPLEMENT ← Charset strategy + Base classes + Metadata + Validators
  ↓
FASE 5: AUDIT_CODE ← Revisión arquitectura + Security + Performance + Tests
  ↓
FASE 6: VERSION ← Changelog + ADR + Migration guide + Rollback + Observability
```

---

## Artefactos Esperados por FASE

### **FASE 1 (RECONNAISSANCE)**
- `audit_phase_1_inventory.md` — Tabla de drivers/configs/metadata por motor
- `audit_phase_1_duplicities.md` — Matriz de código duplicado (% LoC por aspecto)
- `audit_phase_1_security.md` — Hallazgos de seguridad categorizados (P0/P1/P2)
- `audit_phase_1_performance.md` — Hallazgos de rendimiento (charset, pool, async)
- `audit_phase_1_risks.md` — Matriz de riesgos por motor

### **FASE 2 (PLANNING)**
- `design_phase_2b_refactor_options.md` — Opción A (35-45h) vs Opción B (15-20h)
- `risk_assessment_phase_2c.md` — Matriz de riesgos detallada, breaking changes, rollback
- `dependencies_migration_plan.md` — Plan de migración de dependencias
- `decision_matrix_phase_2.md` — Decisiones críticas documentadas

### **FASE 3 (AUDIT_PLAN)**
- `audit_plan_validation_checklist.md` — Validación de completeness
- `critical_decisions_resolution.md` — Resolución C3 + C7 + Charset strategy
- `implementation_readiness_gate.md` — Veredicto GO/GO_CONDICIONAL/NO_GO
- `clarification_questions_resolved.md` — Preguntas respondidas

### **FASE 4 (IMPLEMENT)**
- `implementation_phase_4_charset_strategy.md` — Estrategia genérica
- `implementation_phase_4_base_classes.md` — Refactor de clases base
- `implementation_phase_4_metadata_executor.md` — Ejecutor de metadata centralizado
- `implementation_phase_4_validators.md` — Consolidación de validadores
- `test_coverage_phase_4.md` — Cobertura de tests

### **FASE 5 (AUDIT_CODE)**
- `code_review_phase_5_architecture.md` — Coherencia SOLID
- `code_review_phase_5_security.md` — Hallazgos de seguridad
- `code_review_phase_5_performance.md` — Hallazgos de rendimiento
- `code_review_phase_5_testing.md` — Cobertura y edge cases
- `residual_risks_phase_5.md` — Riesgos residuales
- `verdict_phase_5.md` — Veredicto APROBADO/APROBADO CON CONDICIONES/RECHAZADO

### **FASE 6 (VERSION)**
- `changelog_phase_6.md` — CHANGELOG entry (breaking changes, deprecations)
- `adr_phase_6.md` — Architecture Decision Records (decisiones críticas)
- `migration_guide_phase_6.md` — Guía de migración para usuarios
- `rollback_plan_phase_6.md` — Plan de rollback y compatibilidad
- `observability_checklist_phase_6.md` — Métricas, logging, tracing
- `version_closure_summary.md` — Resumen ejecutivo y handoff

---

## Decisiones Críticas por Resolver (FASE 1 → FASE 3)

Estas decisiones se **identifican en FASE 1**, se **diseñan en FASE 2** y se **resuelven y validan en FASE 3**:

| Decisión | FASE | Descripción | Impacto |
|----------|------|-------------|--------|
| **C3: MySQL Introspection** | ✅ cerrada en FASE 1 | `MySQLCatalog(MariaDBCatalog)` ya existe; se mantiene | — |
| **P0 de FASE 1** | antes de 2 | S1, B1, B2, S4, T1 (ver § Resultado de FASE 1) | Bloqueante |
| **C7: MariaDB 11.x Charset** | 2B → 3 | Compatibilidad UTF8MB4 vs LATIN1? (servidor latin1 hoy se clasifica MIXED) | Medio — Afecta charset strategy |
| **Charset Strategy** | 2B → 3 | DETECT vs UTF8MB4 vs NATIVE vs CUSTOM; ¿solo MariaDB/MySQL? (FASE 1 no halló evidencia en el resto) | Alto |
| **Paridad de caminos** | 2B → 3 | Nativo (managers) vs SQLAlchemy (`factory/`): mismos TLS/charset | Alto |
| **Refactoring Scope** | 2C → 3 | Opción A vs Opción B, con esfuerzo recalculado sobre la duplicidad medida | Crítico — Gobierna FASE 4 timeline |
| **Breaking Changes** | 2B → 3 | ¿Cuáles serán public API changes? | Alto — Requiere CHANGELOG + Migration guide |
| **Rollback Strategy** | 2C → 3 | ¿Cómo se hace rollback post-release? | Crítico — Seguridad en producción |

### Flujo de Decisiones

```
FASE 1: RECONNAISSANCE ✅ (2026-10-08, RECHAZADO: 5 P0; C3 cerrada)
  ↓ /hotfix de los P0
  ↓ (Pendientes: C7, Charset, Paridad de caminos, Scope, Breaking changes, Rollback)
FASE 2: PLANNING
  ↓ (Diseña opciones, riesgos, mitigaciones)
FASE 3: AUDIT_PLAN
  ↓ (Valida decisiones, resuelve conflictos, emite veredicto GO)
FASE 4: IMPLEMENT (si GO en FASE 3)
  ↓ (Aplica decisiones)
FASE 5: AUDIT_CODE (si IMPLEMENT completó)
  ↓ (Verifica ejecución de decisiones)
FASE 6: VERSION
  ↓ (Documenta decisiones en CHANGELOG + ADR)
```

---

## Ubicación del SKILL

```
.github/
  skills/
    drivers-connections-audit/
      SKILL.md                    ← Archivo maestro (v1.0.5, cerrada)
      AUDIT_REPORT.md             ← Auditoría de la skill v1.0.0 (histórico; ver anexo FASE 1)
      CORRECTIONS_APPLIED.md      ← Correcciones v1.0.1 y v1.0.3
.claude/
  DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md   ← Este fichero
```

---

## Contexto Previo

✅ SKILL v1.0.1–1.0.2: coherencia interna corregida (AUDIT_REPORT.md)  
✅ FASE 1 ejecutada contra el código real (2026-10-08)  
✅ SKILL v1.0.3: 10 premisas refutadas por FASE 1 y corregidas (MySQL sin catálogo, HSQLDB sin sync, pool ~60 %,
validadores solapados, bulk/dump sobre el pool, tests inexistentes, entre otras)  
⚠️ En v1.0.2 se daba por hecho que "todas las referencias de tests" y "los paths de módulos" estaban validados: no era
así (5 ficheros de tests inexistentes, `metadata/_charset/` inexistente)  

---

**Creado:** 2026-10-08  
**Sesión:** Auditoría + Corrección + Procedimiento de Ejecución en Claude Code
