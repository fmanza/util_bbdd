# TRACEABILITY

## Session metadata
- id: 2026-10-09-drivers-connections-audit-fase2
- fecha: 2026-10-09
- rama: develop (`310cf30a`, v0.35.8)
- skill: audit_code
- fase: FASE 2 (2A deuda, 2B diseño, 2C riesgos) de `drivers-connections-audit`: PLAN + AUDIT_PLAN + AUDIT_CODE (solo lectura)

## Prompt issued
```text
/audit-code

Objeto: drivers-connections-audit SKILL de util_bbdd — FASE 2 PLANNING
Contexto: FASE 1 cerrada (P0–P2 corregidos en v0.35.5–v0.35.8). Lee primero:
  .claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md
  .github/skills/drivers-connections-audit/SKILL.md (v1.0.3)
  .ai/sessions/2026-10-08*/TRACEABILITY.md (sección "Directrices para Futuras IAs")
Fases: FASE 2A (deuda restante tras FASE 1), 2B (diseño Opción A vs B con la duplicidad medida), 2C (riesgos)
Alcance: src/util_bbdd/connection/**, metadata/**, _drivers/**, managers/**, factory/**
Entregar: decision_matrix_phase_2 (charset strategy solo MariaDB/MySQL, consolidación de validación de conn_params,
pools), risk_assessment_phase_2c, y preguntas de FASE 3 que requieran mi decisión
```

## Context supplied
- `.github/prompts/audit_code.prompt.md`, `.github/agents/code-auditor.agent.md`
- `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md`, `.github/skills/drivers-connections-audit/SKILL.md` (v1.0.3)
- `.ai/sessions/2026-10-08{,b,c,d,e}-*/TRACEABILITY.md`

## AI output summary
- Baseline: `pytest` 5281 passed, 497 skipped (`build/logs/drivers_audit_fase2_baseline.txt`).
- Medición de capas de validación (JSON / builder / `*Config`): claves alineadas; 4 defaults divergentes; `close_timeout` y `schema` aceptados sin campo en config.
- Reproducido: `AsyncDatabaseManager` acepta claves desconocidas que el sync rechaza (D2).
- Confirmado en código: MariaDB sin parámetros TLS en ningún camino (D1).
- Duplicidad remedida con `difflib` (`build/logs/drivers_audit_fase2_duplicidad.txt`): pools 32 %, `__del__` 72 %, `close_connection` 54 %, factories 42 %; DSN Oracle cerrado.
- Premisas de la skill refutadas: pool genérico (32 %), `metadata/_base/executor.py` (ya existe `CatalogExecutor` en `metadata/contracts.py`), enum de charset de 4 valores (mezcla charset de sesión con estrategia de lectura del catálogo), matriz de versiones MariaDB sin verificar.
- Recomendación: Opción B acotada (B1–B6), 18–24 h + 11,5 h de tests; Opción A descartada.
- Sin cambios en `src/` ni en tests.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| FASE 2A | `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/audit_phase_2a.md` | emitido |
| FASE 2B + preguntas FASE 3 | `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/decision_matrix_phase_2.md` | emitido |
| FASE 2C | `.ai/sessions/2026-10-09-drivers-connections-audit-fase2/risk_assessment_phase_2c.md` | emitido |
| Logs | `build/logs/drivers_audit_fase2_*.txt` | generados |

## Directrices para Futuras IAs
- **[managers/async]**: `AsyncDatabaseManager.__init__` solo valida `db_type`; no pasa por `ConnectionParamsManager.prepare_and_validate` ni por `DriverValidator` (el sync sí, en `_manager_lifecycle_sync.py`).
- **[managers/código muerto]**: `managers/_manager_lifecycle_async.py` no se usa desde MGR-02; no tomarlo como referencia del ciclo de vida async (el real está en `_manager_lifecycle.py::init_async_resources`).
- **[charset/diseño]**: en MariaDB sync no hay charset de sesión que elegir (solo utf8mb4); la decisión real es la estrategia de lectura del catálogo (`native`/`convert`/`failfast` de `select_strategy`).
- **[metadata/abstracciones]**: `CatalogExecutor`, `AsyncCatalogExecutor` y `CatalogDialect` ya existen en `metadata/contracts.py`; no proponer `metadata/_base/`.
- **[factory/pools]**: el Engine sync ignora `pool_size`/`max_overflow`/`pool_timeout` de `conn_params`; el async los lee (y usa `pool_recycle=1800`). El `creator` abre conexiones nuevas, no del pool nativo.
- **[banco/versiones]**: el banco de integración es `mariadb:11.4` (11.4.13) y `mysql:8.4` (`docker ps`); la matriz de versiones MariaDB de la skill (10.4/10.5 "soportadas") no está validada.
- **[técnica]**: el script de medición de capas compara `dataclasses.fields` de `*Config`/`*PoolConfig` con `connection_params` del JSON y la salida de `build_conn_params`; es la forma rápida de detectar divergencias de claves y defaults.

## Veredicto final
Veredicto: CLOSED (sesión de planificación; veredicto técnico APROBADO CON CONDICIONES)
Pendientes al cierre:
- ~~Respuestas Q1–Q9~~ resueltas el 2026-10-09 («usar decisiones recomendadas»): `decision_matrix_phase_2.md` § 6; readiness gate **GO_CONDICIONAL**.
- C7 cerrada con evidencia: banco `mariadb:11.4` (11.4.13) y `mysql:8.4`.
- Actualizar `SKILL.md` a v1.0.4 con las premisas refutadas en esta fase.
- Ficheros de sesión sin versionar; sin commit.
