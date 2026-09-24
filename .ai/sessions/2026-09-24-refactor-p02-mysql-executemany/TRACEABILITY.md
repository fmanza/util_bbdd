# TRACEABILITY

## Session metadata
- id: 2026-09-24-refactor-p02-mysql-executemany
- fecha: 2026-09-24
- rama: develop
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "El siguiente paso con más impacto es P-02 [...] ¿Lo hago?")

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-02) y `02_BASELINE_MOTORES_REALES.md`.
- `src/util_bbdd/bulk/_execution/batch.py`, `tests/unit/bulk/test_insert_strategies.py`, `scripts/bench_bulk.py`.
- Contenedores del banco (MySQL 8.4, MariaDB 11.4) y el conector nativo `mariadb` 1.1.14 instalado.

## AI output summary
- **Verificación previa: el plan de la auditoría no era seguro.** Cambiar a `DefaultInsertStrategy` (typed `insert(tabla)`) corrompía las columnas `JSON` en MySQL 8.4: doble serialización y `None` → literal JSON `null`. En MariaDB `JSON` es `LONGTEXT` y no se ve.
- **Diseño**: `MySQLDriverExecutemanyStrategy`, que hace `exec_driver_sql("INSERT … VALUES (%s|?, …)", tuplas)`. Llega al `cursor.executemany` del driver sin procesadores de tipo, igual que la vía `text()` anterior.
- **Conector `mariadb`**: su executemany en bloque rechaza tipos Python distintos en una misma columna (`Invalid parameter type at row 3, column 9`: `bytes` y `str` en BLOB, porque `normalize_sql_literal` decodifica `b""` a `""`). Por eso la nueva vía solo se resuelve para `pymysql`. Los demás drivers (`mariadbconnector`, y `mysqlclient` y `mysql-connector`, no verificados) conservan `MySQLMultiRowInsertStrategy`. Un `mysql_strategy` explícito gana siempre.
- **Bug encontrado en mi propia implementación** por el test unitario: duplicaba otra vez los `%` de los identificadores, que `identifier_preparer` ya escapa con paramstyle `format`/`pyformat`. Confirmado en MySQL real (`%%%%` → tabla inexistente) y corregido.
- **Error de verificación corregido**: la primera sonda de igualdad incluía `%` en un identificador y **las dos vías fallaban**. El "idénticos=True" comparaba dos errores. Repetida sin `%` en identificadores y con recuento de filas: 3/3 filas por vía, valores idénticos en MySQL y MariaDB (JSON, NULL, BIT, ENUM, DECIMAL, DATETIME(6), TIME, BLOB, emoji, `% ?` en datos).
- **Bug latente de la vía anterior**: `MySQLMultiRowInsertStrategy` falla con `%` en el nombre de tabla o columna (`text()` duplica de nuevo el escape del preparer). La nueva vía funciona. Para `mariadbconnector` sigue la vía antigua; no se ha comprobado si su paramstyle `qmark` evita el problema.
- **IMPLEMENT**:
  - `batch.py`: clase `MySQLDriverExecutemanyStrategy`; `InsertStrategyResolver` con `_mysql_strategy` opcional + `_mysql_pymysql_strategy` + `_mysql_multirow_strategy`; `__all__`.
  - `tests/unit/bulk/test_insert_strategies.py`: +7 tests (enrutado por driver, override explícito, inserción en SQLite con `qmark`, JSON sin reprocesar, `pyformat` + `%` en identificadores, lote vacío, fallback de Update).
  - `scripts/bench_bulk.py`: la variante `p02-mysql-executemany` pasa a `mysql-multirow-legacy` (control con la vía anterior); `tests/unit/test_bench_bulk_script.py` actualizado.
  - `CHANGELOG.md` (Changed), `docs/guides/benchmarks.md`, `docs/api/bulk-crud.md`.
- **Validación**:
  - `ruff check src tests scripts` limpio; `mypy src` y `mypy scripts/bench_bulk.py` limpios.
  - Tests unitarios de `bulk`: 230 passed. Suite sin URLs de servidor: 4475 passed / 19 skipped.
  - Con las URLs del banco exportadas aparecen 3 errores en `test_update_auto_increment_mariadb.py` (el usuario `bench` no tiene `CREATE DATABASE`; ajeno al cambio).
  - Integración en los 6 motores: 18 passed.
  - Banco, solo INSERT, `baseline` (nueva) frente a `mysql-multirow-legacy`:

| Filas | MySQL 8.4 | MariaDB 11.4 |
|---|---|---|
| 1K | 1,09× (ruido) | 1,73× |
| 10K | 1,64× | 2,79× |
| 100K | 2,16× | 1,80× |
| 1M | **2,09×** (54,9 s → 26,3 s) | **2,09×** (50,4 s → 24,0 s) |

- **Nuevo hallazgo P-19 (CRÍTICA, previo, no introducido aquí)**: `bulk_update_from_df` corrompe columnas JSON en MySQL (`JSON`) y PostgreSQL (`JSONB`): doble serialización y `None` → `null`. Verificado en los servidores del banco. Registrado en `02_BASELINE_MOTORES_REALES.md` con prioridad 0.

## AUDIT_CODE
- Regresiones potenciales:
  - Solo cambia el INSERT de mysql/mariadb con PyMySQL. Valores idénticos verificados en MySQL y MariaDB reales.
  - PyMySQL trocea las sentencias a 1 MB (`max_stmt_length`), por debajo de `max_allowed_packet` (antes 1000 filas por sentencia).
- Contratos públicos: sin cambios. `InsertStrategyResolver(mysql_strategy=...)` mantiene su significado.
- Cobertura: preservada, más 7 tests nuevos.
- Tipado: mypy limpio.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Estrategia nueva y resolver | `src/util_bbdd/bulk/_execution/batch.py` | completado |
| Tests | `tests/unit/bulk/test_insert_strategies.py`, `tests/unit/test_bench_bulk_script.py` | actualizados |
| Banco | `scripts/bench_bulk.py` (variante `mysql-multirow-legacy`) | actualizado |
| Docs | `CHANGELOG.md`, `docs/guides/benchmarks.md`, `docs/api/bulk-crud.md` | actualizados |
| Hallazgo P-19 | `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` | registrado |

## Directrices para Futuras IAs
- **[bulk/tipos]**: `normalize_sql_literal` ya serializa dict/list a texto JSON. Cualquier ruta que ejecute con parámetros tipados por la columna (`insert(tabla)`, `update(tabla)` con `bindparam`) los serializa dos veces en columnas `JSON`/`JSONB`. Las vías sin tipo (`COPY`, `exec_driver_sql`, `text()`) no.
- **[bulk/MySQL]**: el conector `mariadb` no admite tipos Python mezclados por columna en `executemany`. No lo enrutes a vías de executemany sin normalizar tipos por columna.
- **[verificación]**: en las comparaciones A/B de datos, comprueba siempre que las dos ramas terminaron sin error y cuántas filas devolvieron. Dos errores iguales dan "idénticos=True".

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (no realizado; pendiente de petición del usuario).
- `/hotfix` de P-19.
