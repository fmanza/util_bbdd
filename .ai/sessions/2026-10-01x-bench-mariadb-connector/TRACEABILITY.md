# TRACEABILITY

## Session metadata
- id: 2026-10-01x-bench-mariadb-connector
- fecha: 2026-10-01
- rama: develop
- flujo: Fase B del plan `../2026-10-01v-plan-pendientes-mariadb-connector/PLAN_AUDIT_PLAN.md` (D-3)

## AI output summary
- `scripts/bench_bulk.py`: motor `mariadb_connector` (en `ENGINES`; `UTIL_BBDD_BENCH_MARIADB_CONNECTOR_URL` o la URL de
  `mariadb` con `mariadb+mariadbconnector`); puerto estándar 3306 en el aviso. Test en `tests/unit/test_bench_bulk_script.py`.
- Medición (`bench/`: `summary.md`, `results.csv`, `environment.json`): 1M filas, 3 repeticiones, MariaDB 11.4.13,
  `baseline`: INSERT 15,18 → 7,97 s (1,9×), UPDATE 21,49 → 12,89 s (1,67×), DELETE 6,76 / 6,85 s. 18/18 sin errores.
- Docs: tabla en `docs/guides/benchmarks.md`; CHANGELOG `[Unreleased]`.

## Validación
`ruff` limpio; `tests/unit/test_bench_bulk_script.py` 38 passed; `zensical build --strict` sin avisos.

## Directrices para Futuras IAs
- **[bench/mariadb]**: el driver por defecto de la librería para MariaDB (Connector/Python) es el más rápido en INSERT y
  UPDATE masivos; las cifras de MariaDB anteriores de `benchmarks.md` son de PyMySQL.

## Veredicto final
Veredicto: CLOSED
