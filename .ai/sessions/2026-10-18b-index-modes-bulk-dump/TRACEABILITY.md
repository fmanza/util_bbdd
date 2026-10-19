# TRACEABILITY

## Session metadata
- id: 2026-10-18b-index-modes-bulk-dump
- fecha: 2026-10-18
- rama: develop
- skill: new_feature + hotfix (×3) + version_closure
- fase: PLAN + AUDIT_PLAN + G0 (medición) + IMPLEMENT 3.2.0/3.3.0 + hotfix 3.1.1/3.1.2/3.2.1 + VERSION

## Prompt issued
Ver `00_REQUEST.md` (solicitud inicial y cuatro ampliaciones en la misma sesión).

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`
- `src/util_bbdd/dump/_indexes.py`, `dump/_constraints.py`, `dump/orchestrator.py`, `dump/_models.py`
- `src/util_bbdd/bulk/_execution/maintenance.py`, `bulk/_execution/parallel_loader.py`, `bulk/crud.py`, `bulk/options.py`
- `src/util_bbdd/metadata/facts.py`
- `.ai/DECISIONS_LOG.md`, `.ai/sessions/2026-09-26ze-code-reusability-bulk-dump/IMPLEMENT.md`
- `.github/prompts/new_feature.prompt.md` (contrato de AUDIT_PLAN)
- Contenedores del banco (`docker ps`): MariaDB 11.4, MySQL 8.4, PostgreSQL 17, Oracle Free 23, SQL Server 2022, HSQLDB

## AI output summary
- Diagnóstico: `bulk` ya tenía `maintenance_scope(disable_indexes=True)` con semántica distinta de `dump`
  (SQL Server `ALL DISABLE` solo en heaps; nada en Oracle/PostgreSQL; MyISAM/Aria `DISABLE KEYS`).
- PLAN: estrategia compartida en `bulk/_support/secondary_indexes.py` con ejecución autónoma (`dump`, paralelo) y en
  sesión (`maintenance_scope`).
- Explicación de por qué no se tocan PK/UNIQUE/clustered y por qué MariaDB/MySQL no se soportaba.
- Ampliación: modos `False` / `"secondary"` / `"all"`, salvaguardas de `"all"`, G0 de medición por motor.
- `FOREIGN_KEY_CHECKS`: ya usado en la ruta de constraints; añadidos medición, `validate_fks_after` compartido y
  exclusión de índices requeridos por FK en InnoDB.
- AUDIT_PLAN: `GO_CONDICIONAL` con 7 riesgos funcionales, 9 técnicos, 4 de seguridad; corrección F1 (no romper
  InnoDB en sesión atómica).
- Decisiones D1–D7 confirmadas por el usuario.
- Sin cambios en `src/`, `tests/` ni `docs/`; sin tests ejecutados (fase de planificación).

- G0 (2026-10-18/19): `scripts/bench_index_modes.py` + `tests/unit/test_bench_index_modes_script.py` (13 tests).
  Comprobaciones en el banco (`build/logs/bench_index_modes_probes_20261018.md`) y primera tanda de 1M filas en serie
  (`build/logs/bench_index_modes_1m_serial_*20261018.*`); segunda tanda 2026-10-19 (confirmación de Oracle, FK
  checks, orden aleatorio, 4 hilos, 3,5M). Resultados y consecuencias para el PLAN en `03_G0_MEDICION.md`.
- Hallazgo G0: Oracle + `ParallelOptions(disable_constraints=True)` deja la UNIQUE deshabilitada y sin índice
  (intermitente, 4 de 6 tandas); pendiente de RCA.
- Hotfix v3.1.1 (2026-10-19), ver § Hotfix.

## Hotfix v3.1.1 — `maintenance_scope(disable_indexes=True)` en heaps de SQL Server

- **Evidencia**: `--probes` en el banco: tras `ALTER INDEX ALL ON <heap> DISABLE` la PK NONCLUSTERED queda
  `is_disabled=1`, se acepta un INSERT con PK duplicada y la FK entrante de otra tabla pasa a `is_disabled=1,
  is_not_trusted=1`; tras `ALTER INDEX ALL … REBUILD` la PK vuelve pero la FK sigue deshabilitada.
- **RCA**: `TableMaintenance._disable_indexes` (`bulk/_execution/maintenance.py`) usaba `ALL`, que incluye los índices
  que hacen cumplir PK/UNIQUE; SQL Server deshabilita las FK que referencian una PK deshabilitada y `REBUILD` no las
  reactiva.
- **Fix mínimo**: misma condición (solo heaps); se deshabilitan y reconstruyen uno a uno los NONCLUSTERED no únicos de
  `facts.secondary_nonunique_indexes` (consulta de `dump.IndexManager`). Sin cambios en otros motores ni en la API.
- **Ficheros**: `src/util_bbdd/bulk/_execution/maintenance.py`, docstrings de `bulk/crud.py` y
  `metadata/sqlserver/indexes.py`, `docs/guides/performance_audit_constraints_guide.md`, `CHANGELOG.md`, campos de
  versión (3.1.1), `tests/unit/bulk/test_maintenance_scope.py` (7 tests que fallaban antes del fix),
  `tests/integration/test_bulk_engines.py` (2 tests SQL Server: PK y FK entrantes intactas; PK duplicada rechazada).
- **Verificación**: ruff y `mypy src tests/unit/test_protocol_conformance.py` sin errores (340 ficheros); `pytest` sin
  URLs 6282 passed, 544 skipped; con el banco 6811 passed, 8 skipped (+ 7 de HSQLDB con `JAVA_HOME`); `zensical build
  --strict` limpio; `gen_arquitectura_capas.py` sin cambios (340 ficheros).
- **Rollback**: revertir el commit del hotfix (no hay migración de datos). Tablas afectadas por cargas anteriores:
  `ALTER TABLE <hija> WITH CHECK CHECK CONSTRAINT <fk>` en las FK con `is_disabled = 1` o `is_not_trusted = 1`.

## Hotfix v3.1.2 — `ParallelOptions(disable_constraints=True)` en Oracle

- **Evidencia**: G0, 4 hilos, 1M filas: «Restaurado: no» en 4 de 6 tandas de `none`/`secondary` (UNIQUE `DISABLED`,
  `NOT VALIDATED`, sin índice). Reproductor con el log visible (200K filas, 3 intentos): `ORA-00054` en
  `ALTER TABLE … DISABLE CONSTRAINT` (workers 2–4) y en `ENABLE VALIDATE CONSTRAINT` (el worker que la desactivó).
- **RCA**: en Oracle no había desactivación previa al pool (`_hoist_constraints_for_workers` solo SQL Server y
  PostgreSQL); cada worker usaba `maintenance_scope`, cuyo DDL necesita la tabla sin transacciones de otros. Los que no
  la desactivaron no la reactivan; la reactivación del que sí, choca con los demás insertando. El fallo solo era un aviso.
- **Fix mínimo**: `_hoist_oracle_constraints` en `bulk/_execution/parallel_loader.py`: mismas constraints que
  `maintenance_scope` (`TableMaintenance._oracle_fetch_constraint_names`), `DISABLE` una vez antes del pool y
  `ENABLE VALIDATE` al terminar; si una reactivación falla se intentan las demás y se propaga el primer error (si la carga
  no falló antes). Los workers omiten `maintenance_scope`, como en SQL Server/PostgreSQL.
- **Ficheros**: `src/util_bbdd/bulk/_execution/parallel_loader.py`, docstring de `bulk/options.py`,
  `docs/api/bulk_parallel.md`, `docs/guides/performance_audit_constraints_guide.md`, `CHANGELOG.md`, campos de versión
  (3.1.2), `tests/unit/bulk/test_parallel_loader.py` (3 tests; fallan sin el fix), `tests/integration/test_bulk_engines.py`
  (Oracle, 4 hilos, 200K filas: sin el fix falla en 3 de 4 ejecuciones por ser una carrera; con el fix 4 de 4 pasan).
- **Verificación**: ruff y mypy sin errores (340 ficheros); `pytest` sin URLs 6285 passed, 545 skipped; con el banco
  y `JAVA_HOME` 6822 passed, 8 skipped; `zensical build --strict` limpio.
- **Rollback**: revertir el commit. Constraints dejadas deshabilitadas por cargas anteriores:
  `SELECT constraint_name FROM user_constraints WHERE status = 'DISABLED'` y `ALTER TABLE <t> ENABLE VALIDATE CONSTRAINT <c>`.

## IMPLEMENT v3.2.0 (2026-10-19)

- Alcance y cambios por fichero en `04_IMPLEMENT_3_2_0.md` (G1, G2, G3, G4 y G6; G5, G5b y G7 a 3.3.0).
- Decisiones del usuario: G6 (InnoDB) en 3.2.0; en paralelo, aplicar y avisar donde empeora.
- SQLAlchemy 2.1.5 instalado por el usuario a las 08:15 (intencionado): mypy pedía anotación en
  `dump/orchestrator.py::_count_rows`; corregida sin cambio funcional.
- Correcciones al AUDIT_PLAN: T5 (orden de los context managers) y cifras de MySQL en paralelo (ver `04_…`).

## Hotfix v3.2.1 — SQLAlchemy 2.1 en la lectura por lotes de SQL Server

- **Evidencia**: con SQLAlchemy 2.1.5 (actualizado por el usuario, intencionado) falla
  `test_prefetch_matches_per_table_reflection[mssql]`, también en `274f563d` (anterior a 3.2.0).
- **RCA**: `metadata/reflection.py` copia las reglas de `MSDialect` de SQLAlchemy 2.0. En 2.1: `Float` hereda de
  `NumericCommon` y no de `Numeric` (se perdía la precisión), `TEXT`/`NTEXT` sin longitud y `get_indexes` sin
  `include_columns`.
- **Fix mínimo**: constantes de versión (`_SQLALCHEMY_2_0`, `_MSSQL_INDEX_HAS_INCLUDE_COLUMNS`,
  `_MSSQL_TEXT_HAS_LENGTH`) y `_NUMERIC_BASE = getattr(sqltypes, "NumericCommon", sqltypes.Numeric)`; el resultado
  reproduce la versión instalada (2.0 o 2.1).
- **Tests**: 5 unitarios en `tests/comparar/test_prefetch.py` (fallan sin el fix; cada regla con 2.0 y 2.1 simuladas);
  `test_comparar_prefetch_engines.py` 5 de 5 contra el banco.
- **Verificación**: mypy sin errores (341 ficheros); `pytest` sin URLs 6320 passed, 567 skipped; con el banco y
  `JAVA_HOME` 6879 passed, 8 skipped; `zensical build --strict` limpio.
- **Rollback**: revertir el commit (no hay datos afectados; solo la forma de los metadatos leídos).

## IMPLEMENT v3.3.0 (2026-10-19)

- Mediciones pendientes de G0 completadas (`unique_checks` descartado; validar FK ≈1 % de la carga).
- `"all"`, `IndexRebuildError`, `validate_fks_after` y eventos `index`: ver `05_IMPLEMENT_3_3_0.md` (condiciones del
  AUDIT_PLAN, cambios por fichero, hallazgos y tests).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/00_REQUEST.md` | emitido |
| PLAN | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/01_PLAN.md` | emitido |
| AUDIT_PLAN | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/02_AUDIT_PLAN.md` | emitido (`GO_CONDICIONAL`) |
| G0 | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/03_G0_MEDICION.md` | emitido |
| IMPLEMENT 3.2.0 | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/04_IMPLEMENT_3_2_0.md` | completado |
| IMPLEMENT 3.3.0 | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/05_IMPLEMENT_3_3_0.md` | completado |
| Hotfix 3.1.1 | `5f11ffcb` | commit |
| Hotfix 3.1.2 | `274f563d` | commit |

## Directrices para Futuras IAs
- **[bulk/índices]**: hasta 3.1.x, `BulkCrud.maintenance_scope(disable_indexes=True)` y `dump.IndexManager` eran dos
  implementaciones distintas del mismo concepto; desde 3.2.0 comparten `bulk/_support/secondary_indexes.py`.
- **[oracle/constraints]**: con `disable_constraints=True`, `bulk` y `dump` ya desactivan las UNIQUE en Oracle
  (`bulk/_execution/maintenance.py:383`, `dump/_constraints.py:385`); cualquier gestión de índices únicos debe
  coordinarse con esa ruta.
- **[mysql/FK]**: `FOREIGN_KEY_CHECKS` vive en la ruta de constraints (`bulk` en la conexión de sesión, `dump` con
  eventos `checkout`/`checkin` del pool); no valida retroactivamente (`unverified`) y desactiva los CASCADE.
- **[mysql/innodb]**: `disable_indexes=True` en InnoDB se omite a propósito (commit implícito, hallazgo 8 de
  2026-09-24); no convertirlo en error (rompería la sesión atómica por defecto).
- **[paralelo]**: el DDL de tabla en `ParallelBulkLoader` debe hacerse una vez antes del pool
  (`_hoist_constraints_for_workers`), nunca por worker (lock SCH-M / ACCESS EXCLUSIVE).
- **[bulk/índices]**: desde 3.2.0 el punto canónico es `bulk/_support/secondary_indexes.py` (`SecondaryIndexPlanner` +
  `IndexDdlRunner`); `dump.IndexManager`, `TableMaintenance` y `ParallelBulkLoader._hoist_indexes_for_workers` solo
  eligen conexión y modo (autónomo con commit por sentencia o en sesión con savepoint).
- **[paralelo/orden]**: en `ParallelBulkLoader.load` el context manager de constraints va fuera y el de índices dentro
  (los índices se reconstruyen antes de reactivar constraints).
- **[mssql/tests]**: dentro de una sesión con `ALTER INDEX … DISABLE`, consultar `sys.indexes` desde otra conexión se
  bloquea hasta el commit; usar la conexión de la sesión (`crud._session.connection`).
- **[oracle/paralelo]**: DDL de constraints por worker falla con ORA-00054; siempre una vez antes del pool.
- **[mssql/all]**: un `REBUILD` de un único que falla por duplicados deshace la transacción en el servidor; dentro de
  una sesión, el rollback al savepoint da 3903 y no se pueden leer las claves duplicadas.
- **[índices/all]**: la propiedad de una PK/UNIQUE la tiene quien la desactiva primero (solo se planifican las
  `ENABLED`); así no hay doble gestión con la ruta de constraints de Oracle.
- **[bash]**: heredocs con `\|` o comillas rompen; para Markdown con tablas usar Edit/Write.
- **[sqlalchemy/2.1]**: `metadata/reflection.py` reproduce `MSDialect` según la versión instalada (`_SQLALCHEMY_2_0`):
  en 2.1 `Float` hereda de `NumericCommon` (no de `Numeric`), `TEXT`/`NTEXT` van sin longitud y `get_indexes` no
  devuelve `include_columns`. `test_prefetch_matches_per_table_reflection` es el que detecta estas divergencias.
- **[medición]**: en el banco Oracle Free (2 CPU) dos índices de baja cardinalidad multiplican la carga ×7; las cifras
  de Oracle están infladas, la dirección no. En `dump` la ganancia de índices se mide con lectura solapada (menor que
  en `bulk` directo): no extrapolar entre los dos.
- **[medición/paralelo]**: con 4 hilos desactivar índices empeora en PostgreSQL y MariaDB (y `"all"` también en
  MySQL); la reconstrucción va en serie. Los avisos están en `ParallelBulkLoader._INDEXES_SLOWER_IN_PARALLEL`.
- **[mysql/unique_checks]**: `SET unique_checks=0` medido sin ganancia (≤ 1,5 %, a veces más lento): no ofrecerlo.
- **[banco]**: MariaDB 11.4 no tiene change buffer y MySQL 8.4 lo trae desactivado: el argumento de que InnoDB ya
  amortigua el mantenimiento de secundarios no vale sin medir.

## Veredicto final
Veredicto: CLOSED (v3.3.0, `19596362`; cierre de versión 2026-10-19)

Versiones de la sesión: 3.1.1 (`5f11ffcb`), 3.1.2 (`274f563d`), 3.2.0 (`ef742255`), 3.2.1 (`22d33e6a`) y 3.3.0
(`19596362`); además `0fbabde0` (banco G0), `5e562706` (resultados G0) y `c567e243` (anotación para SQLAlchemy 2.1).
Ninguna publicada: `origin/develop` sigue en 3.1.0 (`ea0507a7`, con su tag `v3.1.0` ya en el remoto) y `main` en 3.0.3.

Verificación de la versión cerrada (3.3.0, con SQLAlchemy 2.1.5): ruff, `ruff format --check` y mypy sin errores
(342 ficheros); `pytest` sin URLs 6354 passed, 588 skipped; con el banco (6 motores y `JAVA_HOME`) 6934 passed,
8 skipped; `zensical build --strict` limpio; `python -m build` genera `util_bbdd-3.3.0.tar.gz` y `.whl`; diagrama de capas
sin cambios (342 ficheros).

Pendientes al cierre:
- Publicación: push de `develop`, tags (al menos `v3.3.0`; opcionalmente `v3.1.1`, `v3.1.2`, `v3.2.0`, `v3.2.1` sobre sus
  commits), fast-forward de `main` y CI en verde; las instrucciones de instalación siguen en `@v3.0.3` (R5 de
  `.ai/CURRENT_STATE.md`).
- Decisión: `validate_fks_after=True` por defecto (coste medido ≈1 %).
- Oracle: `"all"` no toca índices únicos sin constraint (necesitaría `DBMS_METADATA.GET_DDL`).
