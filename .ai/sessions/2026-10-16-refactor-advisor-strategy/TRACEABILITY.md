# TRACEABILITY

## Session metadata
- id: 2026-10-16-refactor-advisor-strategy
- fecha: 2026-10-16
- rama: develop (base `1c4b07b4`)
- skill: refactor (+ dos `fix:`)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (F0–F3) + AUDIT_CODE + VERSION (sin release ni push)

## Prompt issued
«PLAN de T-06» y, tras el PLAN, «si» (empezar por F0). Decisiones del usuario en `PLAN_AUDIT_PLAN.md` § Decisiones.

## Context supplied
- `.ai/sessions/2026-10-15b-audit-code-v1.0.0-v2.1.0/TECH_DEBT.md` (T-06, T-07, T-08, T-11)
- `.github/prompts/refactor.prompt.md`, `connection/performance_advisor.py` y validadores por motor

## AI output summary
- SQL Server del banco recreado en 51833 (copia `util_bbdd_bench_mssql_backup:2026-10-16`); línea base con los 6
  motores sobre `1c4b07b4`: 6371 passed, 7 skipped (primera validación real de SQL Server en esta tanda).
- F0 `394462f1` (`test:`): caracterización de `check()` — 205 casos (8 motores × 5 `conn_params` × respuestas del
  servidor) con conexión falsa por SQL y guarda contra SQL no previsto.
- F1 `e1e87c53` (`refactor:`): Protocol `ReadinessValidator` + registro perezoso; `MySQLReadinessValidator` interno;
  `SQLServerVariableValidator.check_dynamic` en helpers. Advisor 732 → 501 líneas; caracterización intacta.
- F2 `4102765f` (`fix:`, T-07): `ConnParamReader`; inválido → CRITICAL por parámetro; 51 casos del dorado cambian
  (escenarios «invalidos» y «texto»), revisados uno a uno.
- F3 `fa6347da` (`fix:`, T-08): red de seguridad en WARNING con traza; dinámicos aislados de estáticos; MySQL dinámico
  solo `SQLAlchemyError`. Escaneo de logs: 21 avisos, todos de tests unitarios que inyectan fallos; 0 en integración.
- T-11 cerrado sin cambios (decisión).
- Puertas por fase (limpio / 6 motores): F1 6053 / 6577; F2 6060 / 6584; F3 6063 / 6587.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-16-refactor-advisor-strategy/PLAN_AUDIT_PLAN.md` | aprobado |
| Caracterización | `tests/unit/connection/test_advisor_characterization.py`, `tests/unit/connection/data/advisor_characterization.json` | 205 casos |
| Logs | `build/logs/t06_*.txt` | generados |

## Riesgos residuales
- `MySQLVariableValidator.read_variables` (API pública) no tolera filas con forma inesperada (`ValueError` al
  desempaquetar); ahora aflora como WARNING «error interno» en lugar de quedar en DEBUG. Solo visto con engines
  `MagicMock` en `tests/unit/test_bulk_crud_helpers.py`.
- En MySQL 8.0.30+ el check sigue leyendo `innodb_log_file_size` (obsoleta) y no `innodb_redo_log_capacity`.

## Rollback
- `git revert fa6347da 4102765f e1e87c53 394462f1` (en ese orden); F1 es independiente de F2/F3 a nivel de API.
- Contenedor de SQL Server: la imagen `util_bbdd_bench_mssql_backup:2026-10-16` conserva el anterior.

## Directrices para Futuras IAs
- **[advisor]**: para añadir un motor, una fábrica en `_VALIDATORS` (`performance_advisor.py`) y un validador que cumpla
  `ReadinessValidator` (`_advisory.py`); `SUPPORTED_DB_TYPES` sale del registro.
- **[advisor]**: los checks estáticos leen `conn_params` con `ConnParamReader` (`as_int`/`as_float`/`as_bool`); nunca
  `int()`/`bool()` directos.
- **[advisor]**: los validadores capturan solo `SQLAlchemyError` y errores de interpretación; cualquier otra excepción es
  un error interno que `_run_validator` registra en WARNING con traza. Un aviso «error interno» en un test de
  integración es un bug.
- **[tests]**: un cambio en hallazgos del advisor se valida contra `advisor_characterization.json`; regenerar solo a
  propósito (`UTIL_BBDD_REGEN_ADVISOR_GOLDEN=1`) y revisar el diff caso a caso.
- **[banco]**: SQL Server en 51833 (`UTIL_BBDD_BENCH_MSSQL_PORT`); ver la memoria `reference-mssql-bench-port-51833`.
