# TRACEABILITY

## Session metadata
- id: 2026-06-01d-bulk-engine-fast-paths
- fecha: 2026-06-01
- rama: develop
- skill: tech_debt (PLAN + AUDIT_PLAN) → IMPLEMENT autorizado → version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (release 0.10.0)

## Prompt issued
Optimizar la carga masiva en `src/util_bbdd/bulk` (consumido por `src/util_bbdd/dump`):
implementar la mejor estrategia "fast path" por motor (Oracle, SQL Server, MariaDB,
PostgreSQL). Analizar la estrategia B propuesta (PostgreSQL COPY/psycopg3, SQL Server bcp,
MySQL LOAD DATA INFILE / executemany batch, Oracle executemany). Primero solo PLAN y
AUDIT_PLAN; luego "IMPLEMENTE todo".

## Context supplied
- `src/util_bbdd/bulk/` (crud.py, _execution/batch.py, _execution/parallel_loader.py, normalize.py)
- `src/util_bbdd/dump/orchestrator.py` (consumidor)
- `src/util_bbdd/factory/sqlalchemy_engine_factory.py` (drivers por motor), `pyproject.toml`
- Tests `tests/unit/bulk/`, `tests/unit/dump/`

## AI output summary
- **PLAN + AUDIT_PLAN** (tech_debt): veredicto DEUDA_SIGNIFICATIVA. De la estrategia B, solo
  PostgreSQL-COPY (psycopg3 STDIN) recomendable; `bcp` (SQL Server) y `LOAD DATA INFILE`
  (MySQL) **rechazados** por seguridad/portabilidad; Oracle ya óptimo vía `executemany`.
- **IMPLEMENT** (`feat(bulk)`, commit `0bc634d`):
  - `PostgresCopyStrategy` (nuevo): `COPY ... FROM STDIN` vía psycopg3 `cursor.copy()`.
  - `MySQLMultiRowInsertStrategy` (nuevo): multi-fila parametrizado, sub-loteo por
    `max_rows_per_statement`.
  - `InsertStrategyResolver` reescrito: `psycopg3`→COPY, `psycopg2`→execute_values,
    `mysql`/`mariadb`→multi-fila, resto→default. **Fix**: el path rápido de PostgreSQL era
    código muerto (solo se activaba con psycopg2; el driver real es `postgresql+psycopg`).
  - `dump._load_whole_table` delega en `bulk_insert_from_chunks` (resolución única por tabla).
  - Tests nuevos `tests/unit/bulk/test_insert_strategies.py`; 4 tests de
    `tests/unit/dump/test_orchestrator.py` actualizados al nuevo contrato de delegación.
  - Docs: tabla "Estrategias INSERT por motor" en `docs/api/bulk-crud.md`.
- **VERSION (release 0.10.0)**: `pyproject` 0.9.0→0.10.0; CHANGELOG `[0.10.0] - 2026-06-01`
  (Performance + Fixed); `[Unreleased]` vacío.
- Validación final: `ruff check src tests` OK · `mypy src` (334) OK · `pytest` 3689 passed/
  1 skipped · `python -m build` → `util_bbdd-0.10.0`.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Código bulk | `bulk/_execution/batch.py` | completado |
| Código dump | `dump/orchestrator.py` | completado |
| Tests | `tests/unit/bulk/test_insert_strategies.py` (nuevo), `tests/unit/dump/test_orchestrator.py` | completado |
| Docs | `docs/api/bulk-crud.md` | completado |
| Release | `pyproject.toml`, `CHANGELOG.md` | completado |

## Directrices para Futuras IAs
- **bulk/InsertStrategyResolver**: el driver síncrono de PostgreSQL de la librería es
  `postgresql+psycopg` (psycopg3), NO `psycopg2` (ver `factory/sqlalchemy_engine_factory.py`).
  Cualquier gate por `drivername` debe comprobar `"psycopg2"` ANTES que `"psycopg"` (psycopg2
  contiene la subcadena psycopg). Regresión histórica: el fast path estaba escrito solo para
  psycopg2 y nunca se ejecutaba.
- **PostgresCopyStrategy**: usa `connection.connection.cursor().copy(sql)` (DBAPI crudo de
  psycopg3, STDIN). NO soporta `OVERRIDING SYSTEM VALUE` ni `ON CONFLICT`; hace fallback a
  `connection.execute(stmt, ...)` cuando `stmt` no expone `.table` (TextClause). `COPY` dispara
  triggers pero NO rules (diferencia con executemany) — relevante si un usuario depende de rules.
- **Reutilización de normalize**: NO se tocó `normalize_records_for_sql`. psycopg3 `write_row`
  adapta los valores Python ya normalizados (incluido `None`→NULL). Las estrategias COPY y
  multi-fila consumen los mismos registros normalizados que `executemany`.
- **MySQLMultiRowInsertStrategy**: sub-lotea por `max_rows_per_statement` (default 1000) para
  no exceder `max_allowed_packet`. Combina con el warning preexistente de `chunk_size>1000`
  para destinos MariaDB/MySQL (`dump/orchestrator._warn_chunk_size`).
- **Rechazos de diseño (NO reintroducir sin requisito on-prem explícito)**: `bcp`/`BULK INSERT`
  (SQL Server) y `LOAD DATA [LOCAL] INFILE` (MySQL). Motivos: exigen ficheros accesibles por el
  servidor o `local_infile=1` (lectura de ficheros arbitrarios), staging a disco, privilegios
  elevados y rompen portabilidad cloud. SQL Server ya tiene `fast_executemany`; Oracle ya usa
  la capa C de `oracledb` vía `executemany`.
- **dump↔bulk**: `_load_whole_table` ya NO hace bucle de `bulk_insert_from_df`; delega en
  `bulk_insert_from_chunks` (que abre su propio `bulk_session`). Un fallo en cualquier chunk
  aborta la tabla con una sola excepción propagada (los tests de dump asumen `call_count == 1`).
- **Release**: la 0.10.0 NO crea tag git (acción pendiente de decisión del usuario, como en
  0.9.0). No existe `COMPATIBILITY.md` en el repo (el checklist de `sync.instructions.md` lo
  trata como condicional).

## Veredicto final
Veredicto: CLOSED (release 0.10.0 consolidada; código + tests + docs verdes)
Pendientes al cierre:
- Crear tag git `v0.10.0` y push (decisión del usuario; no ejecutado).
- Medición real de COPY vs executemany y multi-fila vs executemany contra BD reales (CI usa
  solo SQLite; las vías nativas están cubiertas por unit tests con mocks/SQL estándar).
