# documentation-architecture-audit

Auditoría arquitectónica de módulos de documentación por motor de base de datos. Identifica consolidaciones, duplicidades, mejoras de seguridad y rendimiento, con propuestas de refactoring. Flujo de 6 fases con salida: PLAN → AUDIT_ARCH → AUDIT_CODE → IMPROVE_PLAN → IMPLEMENT → VERIFY.

## Contexto obligatorio

Lee y aplica, **en este orden**:
1. `.github/SHARED_INSTRUCTIONS.md` — Canónico: arquitectura, SOLID, Conventional Commits
2. `.github/skills/documentation-architecture-audit/SKILL.md` — Definición del skill: fases, motor sequencing, outputs
3. `.github/prompts/doc_architecture_audit.prompt.md` — Contrato de entrada/salida de cada fase

## Reglas de ejecución

- **Motor sequencing:** Secuencial (PostgreSQL → MySQL → MariaDB → Oracle → SQL Server → SQLite → Snowflake), a menos que especifiques `--focus-motors=subset`
- **Testing:** Hibrido (pytest fixtures para unit + docker-compose para integration)
- **API breakage:** Big-bang refactor sin compat (major version bump)
- **Outputs:** Markdown (legible) + JSON (máquina-readable en `build/logs/`)
- **Traceability:** Todo linked a git commits y CHANGELOG

## Fases disponibles

| Fase | Modo | Descripción |
|---|---|---|
| PLAN | Read-only | Mapeo de dependencias, inventario de features por motor, candidates de consolidación |
| AUDIT_ARCH | Read-only | Grafo de dependencias, análisis de duplicidad, scoring arquitectónico |
| AUDIT_CODE | Read-only | Type-check, lint, seguridad, perf hotspots, cobertura |
| IMPROVE_PLAN | Read-only | Estrategia de refactoring, mapa de breaking changes, timeline |
| IMPLEMENT | Read-write | Consolidar módulos, extraer abstracciones, fijar bugs, optimizar |
| VERIFY | Read-only | Validar completeness, perf, motor-specific correctness, traceability |

## Ejemplo de entrada (completa: todas las fases)

```text
/documentation-architecture-audit

Objetivo: Auditar y refactorizar arquitectura de documentación
Fases: PLAN → AUDIT_ARCH → AUDIT_CODE → IMPROVE_PLAN → IMPLEMENT → VERIFY
Motores: PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake (todos)
Módulos: src/util_bbdd/doc/ + src/util_bbdd/analysis/
Scope: Consolidación módulos + eliminación duplicidades + mejoras perf + security review
Breakability: Sí (API pública puede romperse, major version bump)
Validación: Con docker-compose (integration tests reales)
Benchmark: Sí si AUDIT_CODE detecta perf concerns
Outputs: Markdown + JSON (build/logs/)
Timeline: Sin límite, profundidad máxima
```

## Ejemplos de entrada (por fase)

### Solo PLAN
```text
/documentation-architecture-audit

Fase: PLAN
Objetivo: Mapear dependencias y detectar candidatos de consolidación
Alcance rápido: Sí (PostgreSQL + MySQL, skip análisis profundo)
```

### Solo AUDIT_ARCH (asumiendo PLAN previo)
```text
/documentation-architecture-audit

Fase: AUDIT_ARCH
Anterior: Plan completado (ver docs/audits/doc_audit_plan.md)
Motores: PostgreSQL, MySQL (comenzar por estos dos)
Duplicity deep-dive: Sí
Dependency visualization: Sí (generar Mermaid)
```

### IMPLEMENT (asumiendo PLAN + AUDIT_ARCH + AUDIT_CODE completados)
```text
/documentation-architecture-audit

Fase: IMPLEMENT
Anterior: IMPROVE_PLAN aprobado (ver docs/audits/doc_audit_improve_plan.md)
Estrategia: Comenzar con consolidación de MySQL (menor riesgo)
Refactor agresivo: Sí (romper API, crear nuevas abstracciones)
Tests: Ejecutar pytest tras cada motor
```

## Validación de entrada

Antes de comenzar:
- ✅ Especificas fase(s) a ejecutar o solicitas flujo completo
- ✅ Si `--focus-motors`, son válidos (postgres, mysql, mariadb, oracle, sqlserver, sqlite, snowflake)
- ✅ Docker-compose está listo (si integración requerida)
- ✅ SHARED_INSTRUCTIONS.md y SKILL.md han sido leídos

## Salida esperada

**Por fase:**
- Markdown report: `docs/audits/doc_audit_{fase}.md` (legible)
- JSON metadata: `build/logs/doc_audit_{fecha}_{fase}.json` (estruturado)
- Console summary: Resumen de hallazgos y siguientes pasos

**Veredicto final (VERIFY):**
- `READY_FOR_RELEASE` — Todos los hallazgos abordados, tests pass, traceability completa
- `NEEDS_REWORK` — Hallazgos críticos pendientes de resolver
- `BLOCKED` — Riesgos identificados que requieren decisions de arquitecto

---

**Version:** 1.0  
**Referencia:** `.github/skills/documentation-architecture-audit/SKILL.md`
