# TRACEABILITY

## Session metadata
- id: 2026-10-15b-audit-code-v1.0.0-v2.1.0
- fecha: 2026-10-15
- rama: develop (HEAD `0c0e6a65`)
- skill: audit_code → tech_debt → hotfix
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

- `/hotfix` (2026-10-16) de A-01, A-02, A-04 y D-01, test-first (los tests nuevos fallan sin el fix):
  - A-01 `dump/_audit_events.py`: el evento `run` es `failed` con `constraint_reactivation_error`; atributo
    `constraint_reactivation_failed`. Tests en `tests/unit/dump/test_audit_sink.py`.
  - A-02 `executors/async_query_executor.py`: la regex de asyncpg salta literales, identificadores entre comillas y
    comentarios. 6 casos en `tests/unit/test_async_executor_asyncpg.py`.
  - A-04 `connection/performance_advisor.py`, `connection/sqlserver/_variables.py` y la guía de rendimiento:
    recomendaciones aplicables (`my.cnf`, `innodb_redo_log_capacity`, `sp_configure`/`ALTER DATABASE SCOPED
    CONFIGURATION`). Aserciones en `tests/unit/connection/test_performance_advisor.py`.
  - D-01 `CHANGELOG.md`: `[2.0.0] - 2026-10-14`; entradas `Fixed` en `[Unreleased]`.
  - Puerta: ruff, mypy (336) y `zensical build --strict` limpios; pytest limpio 5834 passed / 531 skipped; con banco
    (sin SQL Server) 6213 passed / 152 skipped; integración async de PostgreSQL 4 passed.
  - Riesgos residuales: asyncpg no reconoce `$$...$$` ni las cadenas `E'...'` con `\'`; en MySQL 8.0.30+ el check sigue leyendo
    `innodb_log_file_size` (obsoleta) en lugar de `innodb_redo_log_capacity`; el aviso de Sonar de complejidad de
    `SQLServerVariableValidator.check_dynamic` ya existía (T-06).

- Decisiones del usuario (2026-10-16), tras explicar cada opción:
  - A-05 «durabilidad primero»: `innodb_flush_log_at_trx_commit` 1 → OK, 2 → INFO (riesgo ~1 s si cae el SO; solo en
    una ventana de carga), 0 → WARNING. Implementado en `performance_advisor.py`; tests y guía de rendimiento
    actualizados. En el banco, MySQL y MariaDB (valor 1) pasan de WARNING a OK.
  - A-07 «mensaje completo y documentar»: coherente con los `error_msg` del informe. Comentario en
    `dump/_constraints.py`, `docs/api/dump.md` y CHANGELOG; T-04 cerrado.
  - Puerta: ruff, mypy y `zensical build --strict` limpios; pytest limpio 5834 passed; con banco 6213 passed.

- T-03 (2026-10-16): criterio «WARNING → se ajusta el texto (sin alarmas nuevas); INFO → se ajusta el umbral al texto».
  `write_timeout` mantiene el mínimo 30 s con texto coherente; `cost threshold for parallelism` INFO por debajo de 50.

- T-09 (2026-10-16): rutas de `DumpConfig` como descriptores. Sonda previa en el scratchpad (`probe_descriptor.py`): con
  mypy 1.19, `__init__` acepta `str | PathLike[str]` (tipo de `__set__`) y la lectura es `Path` (tipo de `__get__`);
  `dataclasses.replace`, `repr`, `==` y `asdict` funcionan. Puerta: pytest limpio 5838 passed; con banco 6217 passed.

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
- **[advisor]**: `innodb_flush_log_at_trx_commit` sigue la política «durabilidad primero» (decisión A-05): el advisor no
  recomienda rebajar la durabilidad de todo el servidor; 2 solo se acepta como medida temporal de una carga.
- **[dump]**: los mensajes de error del informe (`error_msg`, `constraint_reactivation_error`) son el `str(exc)`
  completo por decisión (A-07); el advisor guarda solo el tipo. No unificar sin una nueva decisión.
- **[tipado]**: para un campo de dataclass que acepta un tipo y se lee como otro, usar un descriptor
  (`_core/validation/paths.py`: `PathField`, `OptionalPathField`); mypy toma el `__init__` de `__set__`. Exige
  dataclass sin `slots=True` (guarda en `__dict__`).
