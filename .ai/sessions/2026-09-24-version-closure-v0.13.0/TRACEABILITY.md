# TRACEABILITY

## Session metadata
- id: 2026-09-24-version-closure-v0.13.0
- fecha: 2026-09-24
- rama: develop
- skill: version_closure
- fase: VERSION

## Prompt issued
```
/version-closure
```
(Tras el hotfix de `ParallelBulkLoader` y del paquete de tests; se había propuesto 0.13.0 por los cambios de comportamiento.)

## Context supplied
- `git log v0.12.0..HEAD` (23 commits: 11 de código/docs y 12 `docs(ai)`)
- `CHANGELOG.md` (`[Unreleased]`), `pyproject.toml`, `.ai/CURRENT_STATE.md`, `.github/instructions/sync.instructions.md`

## AI output summary
- **Versión**: `0.13.0` (MINOR).
  - Sin API pública nueva: `PostgreSQLAnyDeleteStrategy`, `DeleteStrategyResolver(postgresql_strategy=...)` e `iter_identity_insert_sql` son internos (`_execution`, `_support`) y no se exportan en `util_bbdd.bulk`.
  - Sí hay cambios de comportamiento observables (ver abajo), que justifican MINOR frente a PATCH.
- **CHANGELOG**: `[Unreleased]` → `## [0.13.0] - 2026-09-24`, con una introducción y la lista "Cambios de comportamiento a revisar al actualizar". Secciones Changed (5) y Fixed (9); el `[Unreleased]` ya recogía todos los commits.
- **pyproject.toml**: `version = "0.13.0"`.
- **`.ai/CURRENT_STATE.md`**: cabecera, fila `v0.13.0` en la tabla de versiones y cifra de tests.
- **Sincronización** (`sync.instructions.md`): no existen `docs/CHANGELOG.md` ni `COMPATIBILITY.md`; `mkdocs.yml` sin páginas nuevas (solo contenido en `benchmarks.md` y `bulk-parallel.md`).

## Release notes (resumen)
- **Changed**:
  - `generar_sql` por plantilla, 17–50× con salida idéntica (P-06);
  - preparación, ejecución y escritura por bloques: memoria adicional 70–176 MB → 4–7 MB con 200K filas (P-07);
  - DELETE de PostgreSQL por arrays: 2,3–2,8× con psycopg 3 y 24–27× con psycopg2 (P-10);
  - UPDATE solo con PK + columnas actualizables (P-09);
  - docs: escalado de `ParallelBulkLoader` y P-08 descartado.
- **Fixed**:
  - P-25 (columna `pk_<PK>` sobrescrita);
  - P-26 (DELETE fuera de `bulk_session`);
  - **P-27 (PostgreSQL + `commit_every_n_chunks` perdía todas las filas)**;
  - P-28 (errores del driver sin envolver);
  - P-13 (65.535 parámetros con el conector `mariadb`);
  - P-29 (`RETURNING`/`OUTPUT` en el INSERT generado; Oracle no ejecutable);
  - `%(nombre)s` → `?` (Known issue de 0.12.0);
  - `ParallelBulkLoader` aborta por errores no-BD;
  - paquete de tests que tapaba el driver `mariadb`.

## Impacto en API pública
- Sin cambios de firma ni eliminaciones.
- Comportamiento observable:
  - errores del INSERT de PostgreSQL como `sqlalchemy.exc.*`;
  - DELETE dentro de la transacción de `bulk_session`;
  - `ParallelBulkLoader` anota cualquier excepción en `partition_errors` (mensaje con el tipo para errores no-BD);
  - SQL generado sin `RETURNING`/`OUTPUT` y con `%(nombre)s` intacto;
  - fichero de `generar_sql` escrito vía `<fichero>.tmp`;
  - alias del WHERE del UPDATE con sufijo si coincide con una columna.
- API interna: `_PreparedBulkOperation.generate_sql_lines` devuelve un iterable.

## Migraciones
- Ninguna obligatoria.
- Acciones recomendadas:
  - si se usó `commit_every_n_chunks` con PostgreSQL en versiones anteriores, revisar las tablas cargadas (P-27);
  - revisar columnas `pk_<PK>` actualizadas con `bulk_update_from_df` (P-25);
  - sustituir capturas de `psycopg.errors.*` en torno a `bulk_*` por `sqlalchemy.exc.*` (P-28).

## Compatibilidad
- Motores verificados (integración, 162 passed / 24 skipped): SQLite 3.50, PostgreSQL 17 (psycopg 3.3 y psycopg2 2.9), MySQL 8.4 (PyMySQL), MariaDB 11.4 (PyMySQL y `mariadb` 1.1), SQL Server 2022 (pymssql; pyodbc en P-06 y P-27), Oracle 23 Free (oracledb).
- Python 3.12–3.14 (verificado en 3.14.2; CI cubre 3.12–3.14). SQLAlchemy 2.0 (`render_literal_value`, `coerce_compared_value`, `Insert.inline()`, `DBAPIError.instance`, API pública 2.0).

## Rollback
- **Versión completa**: `git revert --no-commit v0.12.0..HEAD` (o instalar `util_bbdd==0.12.0`). **Riesgo**: reaparecen P-27 (pérdida de filas en PostgreSQL con `commit_every_n_chunks`), P-25 y P-29.
- **Cambio concreto**: cada hallazgo tiene su commit; los `docs(ai)` pueden quedarse. P-06/P-29: `c3141fb`; P-07: `2d99a84`; P-10: `7dc3ae8`; P-13: `446c2b7`; P-27: `9b7a18c`; P-28: `1656d97`; P-25/P-26: `eab996a`; P-09: `088b979`; loader: `bfdc83c`.

## Checklist final
- [x] `ruff check src tests`: sin errores
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores (341 ficheros)
- [x] `pytest`: 4727 passed / 164 skipped
- [x] `python -m build`: `util_bbdd-0.13.0` wheel y sdist
- [x] `pyproject.toml` 0.13.0
- [x] `CHANGELOG.md` actualizado
- [x] Integración de `bulk` en 6 motores: 162 passed / 24 skipped
- [~] `mkdocs build --strict`: los mismos 13 avisos previos (`INSTALLATION.md`/`ROADMAP.md`)

## Pruebas sugeridas antes de publicar
- `scripts/bench_bulk.py --sizes 100000 --repeat 3` para una línea base 0.13.0 comparable con `02_BASELINE_MOTORES_REALES.md`.
- Una carga con `commit_every_n_chunks` contra un PostgreSQL real con datos de producción anonimizados (P-27).

## Directrices para Futuras IAs
- **[release]**: con `v0.11.0` y `v0.12.0` los tags se crearon tras el commit de release (`git tag -a vX.Y.Z <commit> -m "vX.Y.Z - ..."`). Mantener la serie.
- **[bulk]**: las directrices técnicas de esta versión están en las `TRACEABILITY.md` de cada sesión. Las más importantes:
  - medir antes de implementar (P-08 y P-17 descartados; `(a, b) IN (...)` descartado en PostgreSQL);
  - toda escritura por el cursor del driver lleva `_begin_if_needed` y `_wrap_driver_error`;
  - la generación de SQL debe mantener los tests de equivalencia en 8 dialectos;
  - no materializar todo el DataFrame: trabajar por bloques en `__blocks_transaction`.

## Veredicto final
Veredicto: CLOSED — commits `0faf1fa` (release) y `c848e7b` (docs(ai)); tag anotado `v0.13.0` sobre `0faf1fa`; push de `develop` y del tag a `origin`
Pendientes al cierre:
- Contenedores del banco (`docker compose -f docker-compose.bench.yml down -v`).
