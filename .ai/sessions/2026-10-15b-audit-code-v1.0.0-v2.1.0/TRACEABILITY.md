# TRACEABILITY

## Session metadata
- id: 2026-10-15b-audit-code-v1.0.0-v2.1.0
- fecha: 2026-10-15
- rama: develop (HEAD `0c0e6a65`)
- skill: audit_code → tech_debt
- fase: audit_code (PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION, solo lectura); tech_debt (PLAN + AUDIT_PLAN + AUDIT_CODE; IMPLEMENT de la Fase 1 + VERSION, sin commit)

## Prompt issued
`/audit-code auditar todo desde la versión v1.0.0 hasta lo último. Pregunta lo que necesites`

Respuestas del usuario: alcance src + tests + docs; foco todo; comprobaciones también con el banco; entrega en
terminal + fichero de sesión.

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, `.github/prompts/audit_code.prompt.md`,
  `.github/agents/code-auditor.agent.md`
- `git log/diff v1.0.0..HEAD`, `CHANGELOG.md`, memorias del banco (contraseña desde contenedores, puerta sin URLs)

## AI output summary
- ruff, ruff format --check y mypy en verde; pytest en shell limpio 5816 passed / 531 skipped.
- Contenedores del banco arrancados (estaban parados); `util_bbdd_bench_mssql` no arranca: el puerto 51433 está en un
  rango excluido por Windows (51336–51435). pytest con banco sin SQL Server: 6195 passed / 152 skipped.
- `zensical build --strict` sin incidencias.
- Sonda fuera del repo (scratchpad) que confirma A-01, A-02 y A-03.
- Informe `AUDIT_REPORT.md`: 11 hallazgos de código y 4 de documentación; veredicto APROBADO CON CONDICIONES.
- `/tech-debt` (sin inputs: supuestos explícitos en `TECH_DEBT.md`): 13 ítems, veredicto DEUDA_MENOR. El usuario autorizó
  «IMPLEMENT»; se implementó la Fase 1 ofrecida (T-01, T-02, T-05, T-12, T-13).
- A-11 resultó falso positivo (el nombre automático lleva siempre `-<fecha_hora>`); corregido en `AUDIT_REPORT.md`.
- Ficheros: `src/util_bbdd/dump/reporters.py`, `src/util_bbdd/dump/orchestrator.py` (solo comentarios),
  `src/util_bbdd/doc/database_documentation.py`, `tests/unit/dump/test_reporters.py`,
  `tests/unit/test_database_documentation.py`, `docs/api/engine_readiness_advisor.md` (nueva),
  `docs/api/dump_reporter.md`, `docs/api/database_documentation.md`, `docs/examples/dump_data_export.md`,
  `docs/guides/performance_readiness_guide.md`, `docs/guides/engine_readiness_usage_guide.md`, `mkdocs.yml`,
  `CHANGELOG.md` ([Unreleased]), `.ai/CURRENT_STATE.md`, `.ai/sessions/INDEX.md`.
- Puerta tras IMPLEMENT: ruff format (1 test reformateado), ruff y mypy (336) limpios, `zensical build --strict` sin
  incidencias; pytest limpio 5826 passed / 531 skipped; con banco (sin SQL Server) 6205 passed / 152 skipped.
- Sin commit (lo decide el usuario). Commit propuesto:
  `refactor: deuda técnica fase 1 tras audit-code v1.0.0..v2.1.0` (o separado: `fix(dump)`, `fix(doc)`, `docs`, `refactor(dump)`).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Informe | `.ai/sessions/2026-10-15b-audit-code-v1.0.0-v2.1.0/AUDIT_REPORT.md` | emitido |
| Logs | `build/logs/audit_v1_v2_*.txt`, `build/logs/techdebt_f1_*.txt` | generados |
| Inventario de deuda | `.ai/sessions/2026-10-15b-audit-code-v1.0.0-v2.1.0/TECH_DEBT.md` | emitido; Fase 1 implementada |

## Directrices para Futuras IAs
- **[dump]**: `DumpAuditEvents.run` (`dump/_audit_events.py`) decide el estado del evento de cierre; cualquier campo nuevo
  de fallo en `DumpResult` debe reflejarse ahí o `audit_sink` dirá `ok`.
- **[dump]**: el orden de hojas de `DumpReporter.generate` es un contrato («opcionales al final»); `_autowidth` pisa
  los anchos fijados antes de llamarlo.
- **[banco]**: en Windows, los puertos del banco pueden caer en rangos excluidos de `winnat`
  (`netsh interface ipv4 show excludedportrange protocol=tcp`); comprobar antes de culpar al código.
- **[advisor]**: las recomendaciones con comandos (`SET GLOBAL`, `ALTER SYSTEM`) deben verificarse contra la
  documentación del motor: no todas las variables son dinámicas.
- **[doc]**: el nombre automático de la carpeta de `DatabaseDocumentation` lleva siempre `-<fecha_hora>`: los nombres
  reservados de Windows (`CON`, `NUL`…) no pueden darse; no volver a «arreglarlo».
- **[docs]**: `docs/api/dump_reporter.md` numera las hojas suponiendo que están todas; el orden real es fijas → Índices
  → Auditoría Bulk → Secuencias PK → Errores de Reactivación → Condiciones del motor.

## Rollback
- Sin commit: `git restore` de los ficheros listados y borrar `docs/api/engine_readiness_advisor.md`. Con commit:
  `git revert`. No hay migraciones ni datos.
