# TRACEABILITY

## Session metadata
- id: 2026-09-27b-pendientes-bulk-dump
- fecha: 2026-09-27
- rama: develop
- skills: new-feature (PLAN, AUDIT_PLAN, IMPLEMENT) → version-closure (v0.17.4 y v0.18.0)
- origen: los cuatro puntos que el refactor de reutilización de bulk/dump dejó fuera por cambiar comportamiento

## Decisiones (PLAN.md)
- D-1: `max_overflow` negativo (ilimitado) → sin recorte. D-2: `rows_committed` incluye el DELETE. **D-3: retirar
  `BulkInserter` ya** (el usuario eligió retirarlo en lugar de deprecarlo). D-4: exportar `Audit*` en `util_bbdd`.
  D-5: 2a como v0.17.4 y el resto como v0.18.0.

## Commits
- `5dc479d` fix(bulk) 2a: `RowLedger` compartido en `SessionScope`; el commit periódico del DELETE confirma las filas de
  INSERT pendientes. `fb0986b` release v0.17.4 (tag `v0.17.4`).
- `22d2160` feat(bulk)! punto 3: familia `AuditError` en `_core/exceptions.py`.
- `496d5ba` feat(dump)! punto 4: se retira `BulkInserter`.
- `247c400` feat(bulk,dump) punto 1: `pool_capacity` (`size + max_overflow`) + guarda de una conexión por worker.
- `521563e` feat(bulk) 2b: `rows_committed` cuenta el DELETE; `_dml_rows` también.
- `b3e57ac` release v0.18.0 (tag `v0.18.0`).

## Evidencias
- 2a: reproducido (1 fila insertada en BD, `rows_committed` 0) y test que falla sin el fix (`0 == 1`).
- Punto 1: test de conexiones simultáneas por worker (2 antes, 1 ahora) y prueba contra MySQL y MariaDB reales con pool
  2+2 y 4 workers: sin la guarda `QueuePool limit ... reached` (4000 y 0 de 8000 filas); con ella 8000 y 8000.
- Punto 3: 17 tests (identidad de clase entre rutas de import, jerarquía, `str`, `ValueError`, pickle); fallan sin el cambio.
- 2b: test de un DELETE que falla a mitad con lotes confirmados: `unaudited_committed_rows` 2 (antes 0).

## Checklist (`.github/instructions/sync.instructions.md`)
- [x] `ruff check` y `ruff format --check`: limpios.
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores (356 ficheros).
- [x] `pytest` sin URLs de servidor: **5124 passed / 199 skipped**.
- [x] `pytest tests/integration` con las URLs del banco (5 servidores): **338 passed** (tras 2b).
- [x] `python -m build`: `util_bbdd-0.17.4` y `util_bbdd-0.18.0` (con `pool.py`, sin `_protocols.py`).
- [x] `pyproject.toml` → `0.18.0`; `CHANGELOG.md` `[0.17.4]` y `[0.18.0]` (con *Removed* y *Migración*); `[Unreleased]`
  vacío y único.
- [x] `mkdocs build --strict`: sin avisos; diagrama de capas regenerado (356 ficheros, 11 paquetes importan de
  Foundation por `bulk → _core`).

## Impacto en API pública (v0.18.0)
- **Incompatible**: `util_bbdd.dump.BulkInserter` ya no existe.
- `AuditError` y subclases: ahora `DatabaseException`; exportadas en `util_bbdd`.
- `ParallelBulkLoader`: admite hasta `pool_size + max_overflow` workers; texto nuevo del WARNING.
- `BulkCrud.rows_committed` y `unaudited_committed_rows`: incluyen el DELETE.

## Rollback
- Push de `develop` y de los tags `v0.17.4` y `v0.18.0` a `origin`; `main` no se toca.
- Tags, si nadie los ha consumido: `git push origin :refs/tags/v0.18.0` y `:refs/tags/v0.17.4`.
- Por punto: `git revert 521563e` (2b), `247c400` (pool), `496d5ba` (BulkInserter), `22d2160` (AuditError),
  `5dc479d` (2a). 2b depende de 2a: revertir en ese orden.

## Directrices para Futuras IAs
- **[bulk]**: filas pendientes y confirmadas viven en `SessionScope.rows` (`RowLedger`), compartido por los ejecutores de
  una `BulkCrud`; cada ejecutor lleva su contador de lotes (`CommitCadence`). Un commit de cualquiera confirma el libro.
- **[bulk/pool]**: la regla de capacidad es `bulk/_support/pool.py: pool_capacity`. Un worker de `ParallelBulkLoader`
  debe usar una sola conexión a la vez: cualquier reflexión o consulta nueva dentro de su `bulk_session` debe hacerse
  antes de abrirla o sobre la conexión de la sesión.
- **[tests]**: al reescribir un test con un script que corta «desde X hasta el final del fichero», se pierden los tests
  posteriores (pasó con `TestCadenceEndToEnd`); comprobar el número de tests antes y después, y que el diff solo añade.
- **[excepciones]**: toda la jerarquía pública vive en `_core/exceptions.py`; los módulos de dominio re-exportan.

## Veredicto final
Veredicto: CLOSED
