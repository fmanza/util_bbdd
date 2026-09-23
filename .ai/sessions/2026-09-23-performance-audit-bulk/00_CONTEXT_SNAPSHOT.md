# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `CLAUDE.md` y `.claude/commands/performance-audit.md` (contrato del slash command)
- `.github/prompts/performance_audit_bulk.prompt.md` (10 áreas, formato de hallazgo, criterios de prioridad)
- `.github/agents/performance-auditor.agent.md`
- `src/util_bbdd/bulk/` completo (21 ficheros, ~4.600 líneas): `crud.py`, `normalize.py`, `audit.py`,
  `_execution/{batch,parallel_loader,range_partitioner}.py`,
  `_support/{validation,sql_helpers,persistence,table_utils,pk_sync}.py`, `_audit/{repository,service}.py`, `_models.py`
- Código fuente instalado de SQLAlchemy 2.0.50 (`sql/crud.py`, `engine/default.py`, `engine/base.py`,
  `dialects/mssql/pyodbc.py`) y de PyMySQL 1.1.2 (`cursors.py`) para verificar el comportamiento de los drivers
- `.ai/sessions/INDEX.md` (sesiones previas de bulk: `2026-06-01d`, `2026-06-01f`, `2026-06-01g`, `2026-06-02*`)

## Estado actual observado
- Árbol limpio en `develop` (último commit `f0f221f`).
- Entorno: Windows 11, Python 3.14.2, pandas 3.0.3 (Copy-on-Write por defecto), numpy 2.4.6, SQLAlchemy 2.0.50.
- Drivers instalados: psycopg 3.3.3, PyMySQL 1.1.2, mariadb 1.1.14, oracledb 4.0.1, pyodbc 5.3.0, pymssql 2.3.13.
- Tests de `bulk/`: solo unitarios con mocks (`tests/unit/test_bulk_internal_helpers.py`, etc.);
  **no hay tests de integración ni benchmarks de `bulk/` contra motores reales**.
- Tests/lint/mypy no re-ejecutados: sesión de solo lectura sin cambios en `src/`.

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v0.10.0 (commit de release v0.11.0 `166448a` en historial)

## Hechos previos relevantes
- `MySQLMultiRowInsertStrategy` y `PostgresCopyStrategy` se introdujeron en la sesión `2026-06-01d-bulk-engine-fast-paths`;
  la caché de plantillas SQL de la estrategia MySQL en `2026-06-01f`. Ninguna de las dos sesiones comparó la estrategia
  MySQL con el `executemany` nativo de PyMySQL (que ya reescribe a INSERT multi-fila). Este audit reabre esa decisión (P-02).

## Clasificación metodológica
- Tipo principal: performance-audit (solo lectura)
- Estado real de alcance: acotado a `src/util_bbdd/bulk/`
- Consecuencia: se emite AUDIT_CODE sin IMPLEMENT; las remediaciones se derivan a `/hotfix`, `/refactor` y `/new-feature`.

## Gate G0 · Context Ready
Veredicto: GO_CONDICIONAL
Condiciones pendientes (si aplica):
- Solo hay SQLite disponible para medir; los efectos dependientes del servidor (Oracle, MySQL, PostgreSQL, SQL Server)
  se declaran HIPÓTESIS hasta disponer de un banco de pruebas con motores reales.
