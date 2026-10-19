# IMPLEMENT

## Approved scope

PLAN de `01_PLAN.md` con veredicto GO_CONDICIONAL (`02_AUDIT_PLAN.md`) y la condición C3 aprobada por el usuario
(diagnóstico de duplicados de Oracle con `ROWNUM`).

## Files changed

| Nivel | Fichero | Cambio |
|---|---|---|
| metadata | `src/util_bbdd/metadata/oracle/indexes.py` | `fetch_unique_indexes_without_constraint_sql()` (con `ALL_IND_EXPRESSIONS`) y `fetch_index_ddl_sql()` (`DBMS_METADATA.GET_DDL`) |
| metadata | `src/util_bbdd/metadata/facts.py` | `UniqueIndexFact.key_sql` y `.ddl_error`; `_oracle_unique_indexes` añade los únicos sin constraint con su DDL o el motivo (`_oracle_index_ddl`) |
| bulk | `src/util_bbdd/bulk/_support/secondary_indexes.py` | `IndexStep.skip_reason`; `_oracle_unique_index` (DROP + DDL con `:` escapados); `disable`/`restore` informan `"skipped"`; `IndexDdlRunner.recovery_ddl`; `rebuild_error` añade el DDL; `duplicates_sql` de Oracle con `ROWNUM` y sin claves todo-NULL; `_find_duplicates` escapa `:` |
| bulk | `src/util_bbdd/bulk/_models.py` | `IndexActionResult.action` admite `"skipped"` |
| core | `src/util_bbdd/_core/exceptions.py` | `IndexRebuildError.recovery_ddl` |
| audit | `src/util_bbdd/bulk/_audit/events.py`, `src/util_bbdd/dump/_audit_events.py` | `"skipped"` → estado `skipped` |
| bulk | `src/util_bbdd/bulk/crud.py` | Docstring de `maintenance_scope` |
| tests | `tests/unit/bulk/test_secondary_indexes_all.py` | 5 tests nuevos (planificación, `skipped`, `recovery_ddl`, `facts` de Oracle) y `duplicates_sql` de Oracle actualizado |
| tests | `tests/integration/test_bulk_engines.py` | 3 tests de Oracle: recreación (con índice basado en función y `'HH24:MI'`), duplicados con `recovery_ddl`, `skipped` sin privilegios (tabla en `SYSTEM`) |
| tests | `tests/integration/test_dump_engines.py` | `ux_big` también se toca en Oracle con `"all"` |
| docs | `CHANGELOG.md`, `docs/guides/performance_audit_constraints_guide.md`, `docs/api/exceptions.md`, `docs/api/bulk_parallel.md`, `docs/api/dump_reporter.md` | Nuevo comportamiento, `"skipped"` y `recovery_ddl` |

Los tres consumidores (`maintenance.py`, `parallel_loader.py`, `dump/_indexes.py`) no cambian: los pasos `skipped`
viajan en la lista de desactivados y salen en `restore()`.

## Validation performed

- `ruff check`, `ruff format --check`, `mypy src tests/unit/test_protocol_conformance.py`: sin errores (342 ficheros).
- `pytest` sin URLs del banco: 6366 passed, 592 skipped (`build/logs/oracle_unique_index_pytest.txt`).
- `tests/integration -m integration` con el banco (5 motores): 642 passed, 7 skipped; los 7 de HSQLDB fallaban solo por
  `JAVA_HOME` y pasan con `JAVA_HOME=jdk-25` (`build/logs/oracle_unique_index_integration.txt`).
- Tras el último ajuste (`_find_duplicates`): integración de índices 94 passed, 6 skipped.
- `zensical build --strict`: sin incidencias. `scripts/gen_arquitectura_capas.py`: sin cambios en el diagrama.
- Banco: diagnóstico de duplicados con expresión `CASE` (sin falso positivo del grupo NULL) y con `TO_CHAR(…,'HH24:MI')`.

## Residual risks

- Oracle 11g no está en el banco: el SQL nuevo no usa sintaxis 12c+, pero no se ha ejecutado contra 11g.
- Índices particionados (`status = 'N/A'`) incluidos sin prueba en el banco: `GET_DDL` los describe completos.
- Un índice único de otro owner sobre la tabla: `GET_DDL` busca el índice en el owner de la tabla, da ORA-31603 y queda
  `"skipped"` (seguro, sin ganancia).

## Out-of-scope observations

- H1 (de `02_AUDIT_PLAN.md`): UNIQUE/PK sobre un índice único previo (`USING INDEX`) conserva el índice al desactivarse.
- `bulk/_support/fk_orphans.py:44` usa `FETCH FIRST 1 ROWS ONLY` en Oracle (12c+), igual que tenía `duplicates_sql`;
  verificar si se usa en Oracle 11g con `validate_fks_after` (activo por defecto desde 3.4.0).
