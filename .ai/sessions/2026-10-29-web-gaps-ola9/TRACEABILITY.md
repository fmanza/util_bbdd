# TRACEABILITY

## Session metadata
- id: 2026-10-29-web-gaps-ola9
- fecha: 2026-10-29
- rama: develop
- skill: new_feature + version-closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION de la ola 9 (v5.1.0)

## Prompt issued
Ola 9 del plan de huecos de util_bbdd_web (Grupo 9, fase U-9.1, G44): `NUMBER` de Oracle sin pasar por `float` en
`execute_custom_*` y `execute_query_*`. Conversor solo en los cursores de las consultas (ni la conexión ni
`oracledb.defaults`); D9-1 (5.1.0 como `fix`, nota del cambio de tipo) y D9-2 (si `AsyncCursor` no admite
`outputtypehandler`, solo síncrono y limitación documentada); un commit. Plan canónico:
`docs/plan/UTIL_BBDD_GAPS_PLAN.md` de util_bbdd_web (Grupo 9 y AUDIT_PLAN de la ola 9).

## Context sources
- `src/util_bbdd/executors/sync_query_executor.py` (`_execute_resolved`, `_execute_custom`, `_is_mariadb_connection`),
  `executors/async_query_executor.py` (`_get_cursor` y sus tres usos), `connection/oracle/` (pool y conexión nativos
  de oracledb: las conexiones son `oracledb.connection.Connection`/`AsyncConnection`).
- oracledb 26.0.1 instalado: `Cursor.outputtypehandler`, `AsyncCursor.outputtypehandler`, `FetchInfo.precision/scale`.
- Banco Oracle 23ai (`util_bbdd_bench_oracle`, 51521, `FREEPDB1`).

## AI output summary
- PLAN + AUDIT_PLAN (veredicto GO), con R9-3 comprobado antes de planificar: un `outputtypehandler` en el cursor
  funciona igual en `Cursor` y `AsyncCursor` (spike en el scratchpad contra el banco). D9-2 no hizo falta.
- U-9.1 `6ccca9ca` G44:
  - `executors/_oracle_numbers.py` (nuevo): `oracle_output_type_handler(cursor, metadata)` (`NUMBER` con escala →
    texto → `Decimal`; sin restricción, precisión 0 y escala 0/-127/`None` → `int` si el exponente del `Decimal` es
    ≥ 0, `Decimal` si no; `FLOAT`, `NUMBER(p)`, `NUMBER(p, s<0)` y el resto → `None`, lo que da el driver) y
    `prepare_query_cursor(conn, cursor)` (solo si `type(conn).__module__` empieza por `oracledb` y la conexión no
    tiene `outputtypehandler` propio).
  - Una llamada tras crear el cursor en `_execute_resolved` y `_execute_custom` (sync) y en las dos consultas async
    (nombradas y personalizadas). No en el prólogo/epílogo de solo lectura ni en el reintento binario de MariaDB.
  - Docs: `CHANGELOG.md` (Fixed con nota del cambio de tipo), `api_5_0_migration.md` § 7, contrato de salida en
    `docs/api/query_execution.md`.
- Evidencias: pytest 6873 passed, 618 skipped (`build/logs/u91_pytest.txt`); mypy limpio (356 ficheros); ruff limpio;
  `zensical build --strict` limpio (`build/logs/u91_docs.txt`, ancla `#7-51-number-de-oracle-como-decimal`
  comprobada). Banco: `tests/integration/test_oracle_numbers.py` 2 passed (sync: `execute_custom_result` con y sin
  `read_only`, `_many`, `_one`, `execute_query_many`; async: `execute_custom_result`, `_many`, `execute_query_many`;
  la conexión del pool sin conversor y columnas del snapshot iguales a las de un manager nuevo); integración de Oracle
  `-k oracle`: 110 passed, 6 skipped (`build/logs/u91_integration_oracle.txt`).
- `scripts/gen_arquitectura_capas.py`: sin aristas nuevas (`_oracle_numbers.py` está dentro de `executors/`); 356
  ficheros; SVG y tabla regenerados.
- VERSION: `release: v5.1.0`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Conversor | `src/util_bbdd/executors/_oracle_numbers.py` (nuevo), `executors/sync_query_executor.py`, `executors/async_query_executor.py` | completado (v5.1.0) |
| Tests | `tests/unit/test_oracle_numbers.py` (38, con dobles), `tests/integration/test_oracle_numbers.py` (banco) | completado |
| Docs | `CHANGELOG.md`, `docs/guides/api_5_0_migration.md` § 7, `docs/api/query_execution.md` | completado |

## Desviaciones del plan
- D9-2 no se aplica: `AsyncCursor` admite `outputtypehandler` (R9-3 verificado en el banco), así que va también en
  asíncrono.
- Si la conexión ya tiene un `outputtypehandler` propio, no se pone el de util_bbdd (decisión de IMPLEMENT, anunciada
  en AUDIT_PLAN; documentada en CHANGELOG y en la guía).
- La «guía de consultas» del plan es `docs/api/query_execution.md` (contrato de salida).
- Integración solo de Oracle con el banco: el cambio no alcanza a conexiones de otros drivers (detección por módulo).

## Notas para las fases W-9 de util_bbdd_web
- W-9.0: con 5.1.0 conviven el conversor y `fetch_decimals` de la web; dan el mismo `Decimal` (R9-6).
- W-9.1: al quitar `fetch_decimals` y `_oracle_number`, `FLOAT` vuelve a salir como `float` (antes, texto), y
  `NUMBER` sin restricción entero como `int` desde util_bbdd. El conversor no toca `oracledb.defaults`.

## Directrices para Futuras IAs
- **[executors]**: los cursores de las consultas de usuario salen de `_execute_resolved`/`_execute_custom` (sync) y de
  las dos llamadas a `_get_cursor` de consulta (async); cualquier ajuste por driver del cursor va justo después, con
  `prepare_query_cursor` como modelo. `_start_read_only`/`_run_statements` crean otros cursores que no deben tocarse.
- **[oracle]**: en oracledb, `FLOAT` llega como `DB_TYPE_NUMBER` con precisión > 0 (126) y escala -127; un `NUMBER`
  sin restricción o una expresión (`1.5`, `COUNT(*)`) tiene precisión 0 y escala -127. Distinguirlos por la precisión,
  no solo por la escala.
- **[oracle]**: `outputtypehandler` del cursor funciona igual en `Cursor` y `AsyncCursor` (oracledb 26.0.1, thin).
  `cursor.var(DB_TYPE_VARCHAR, arraysize=cursor.arraysize, outconverter=...)` no llama al conversor con `NULL`.
- **[tests]**: una sentencia DDL con `execute_custom_many` falla en Oracle (`DPY-1003`, fetch sin filas): en fixtures,
  `execute_custom_result`, que no lee filas sin `description`.
- **[tests]**: para `execute_query_many` en async no hay `queries_file`: sustituir `manager.query_executor` por un
  `AsyncQueryExecutor` con `registry=QueryRegistry(fichero)`.

## Veredicto final
Veredicto: CLOSED (ola 9, v5.1.0)
Pendientes al cierre:
- Push de `develop`, tag `v5.1.0`, fast-forward de `main` y wheel + `.sha256` en GitHub Releases.
- Hacer W-9.0 y W-9.1 en util_bbdd_web y su `release: v1.7.1` (D9-3).
