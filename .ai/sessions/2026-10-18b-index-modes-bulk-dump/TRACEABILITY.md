# TRACEABILITY

## Session metadata
- id: 2026-10-18b-index-modes-bulk-dump
- fecha: 2026-10-18
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN

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
  (`build/logs/bench_index_modes_1m_serial_*20261018.*`); resultados en `03_G0_MEDICION.md` cuando termine G0.
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

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/00_REQUEST.md` | emitido |
| PLAN | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/01_PLAN.md` | emitido |
| AUDIT_PLAN | `.ai/sessions/2026-10-18b-index-modes-bulk-dump/02_AUDIT_PLAN.md` | emitido (`GO_CONDICIONAL`) |

## Directrices para Futuras IAs
- **[bulk/índices]**: `BulkCrud.maintenance_scope(disable_indexes=True)` y `dump.IndexManager` son dos implementaciones
  distintas del mismo concepto; el catálogo común es `metadata.facts.secondary_nonunique_indexes`.
- **[oracle/constraints]**: con `disable_constraints=True`, `bulk` y `dump` ya desactivan las UNIQUE en Oracle
  (`bulk/_execution/maintenance.py:383`, `dump/_constraints.py:385`); cualquier gestión de índices únicos debe
  coordinarse con esa ruta.
- **[mysql/FK]**: `FOREIGN_KEY_CHECKS` vive en la ruta de constraints (`bulk` en la conexión de sesión, `dump` con
  eventos `checkout`/`checkin` del pool); no valida retroactivamente (`unverified`) y desactiva los CASCADE.
- **[mysql/innodb]**: `disable_indexes=True` en InnoDB se omite a propósito (commit implícito, hallazgo 8 de
  2026-09-24); no convertirlo en error (rompería la sesión atómica por defecto).
- **[paralelo]**: el DDL de tabla en `ParallelBulkLoader` debe hacerse una vez antes del pool
  (`_hoist_constraints_for_workers`), nunca por worker (lock SCH-M / ACCESS EXCLUSIVE).
- **[banco]**: MariaDB 11.4 no tiene change buffer y MySQL 8.4 lo trae desactivado: el argumento de que InnoDB ya
  amortigua el mantenimiento de secundarios no vale sin medir.

## Veredicto final
Veredicto: GO_CONDICIONAL
Pendientes al cierre:
- G0: `scripts/bench_index_modes.py` y medición en el banco.
- Verificar F4 (reintentos de partición × commits periódicos) antes de G5.
- Comprobar en banco: `REBUILD` de PK NONCLUSTERED en SQL Server y FK entrantes; DROP de índice requerido por FK en
  MariaDB 11.4 vs MySQL 8.4.
