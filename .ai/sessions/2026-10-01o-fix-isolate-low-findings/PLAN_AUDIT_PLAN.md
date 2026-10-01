# PLAN + AUDIT_PLAN — hallazgos B-1, B-3 y B-4 de `on_error="isolate"`

- Base: `develop` (`64e7585`), sin publicar. Origen: `/audit-code` de `e2ce535..HEAD` (TRACEABILITY de
  `../2026-10-01n-feat-on-error-isolate/`, sección «/audit-code posterior»).
- Flujo: corrección de una funcionalidad aún no publicada → commit `fix(bulk): …` (no `/hotfix`: no hay versión
  afectada). Sin refactor: solo `bulk/_support/rejects.py`, tests y docs.

## Verificación previa (sondas en el scratchpad, sin tocar código)

| # | Sonda | Resultado |
|---|---|---|
| E-1 | SQL Server con `SET XACT_ABORT ON` (evento `connect`), INSERT con una PK duplicada | pyodbc: `ProgrammingError` «Cannot roll back sa_savepoint_1. No transaction or savepoint…»; pymssql: `OperationalError` 3903 «The ROLLBACK TRANSACTION request has no corresponding BEGIN TRANSACTION». El `IntegrityError` original solo en `__context__`. Datos correctos: la operación entera deshecha (`filas=[2]`) |
| E-2 | SQLite, `connect_args={"autocommit": True}` (Python 3.14) | Sin y con fila mala: **otra conexión ve 0 filas y `database is locked`**; al cerrar el engine las filas se pierden. Causa: `_savepoint` emite `BEGIN` (se cumple `isolation_level is not None` e `in_transaction=False`) y en ese modo `commit()` no hace nada |
| E-3 | Lo mismo, simulando «no emitir `BEGIN` si `autocommit` no es el modo heredado» | Sin filas malas, bien (4 filas, sin bloqueo). **Con una fila mala, otra vez 0 filas y bloqueo**: el `ROLLBACK TO SAVEPOINT` no libera el SAVEPOINT más externo, que en autocommit es la propia transacción |
| E-4 | SQLite con `create_engine(..., isolation_level="AUTOCOMMIT")` (SQLAlchemy) | Correcto con y sin fila mala (4 y 3 filas, sin bloqueo): no hay que tocarlo |

**Reclasificación**: B-3 pasa de BAJA (hipótesis) a **MEDIA (confirmado)**: pérdida silenciosa de filas y bloqueo de la
BD, aunque con una configuración poco habitual. B-1 sigue en BAJA (los datos son correctos; el problema es el mensaje).

## Inputs (supuestos explícitos)
- **Objetivo**: B-1, que el error visible sea el error de datos original y explique por qué no se pudo aislar; B-3, que
  `on_error="isolate"` no deje transacciones abiertas ni pierda filas con sqlite3 en `autocommit=True`; B-4, que el CSV
  de rechazos no reciba filas con otra cabecera ni intercale escrituras entre instancias de un mismo proceso.
- **Módulos**: `src/util_bbdd/bulk/_support/rejects.py`; tests `tests/unit/bulk/test_on_error_isolate.py` e integración en
  `tests/integration/test_bulk_audit_20261001.py`; `docs/api/bulk_crud.md`; CHANGELOG (entrada *Added* de `isolate`,
  aún sin publicar).
- **API pública**: sin cambios de firma. Cambia la excepción visible en B-1 y aparece un error nuevo en B-3 (D-2).
- **Motores**: SQL Server (B-1), SQLite (B-3), todos (B-4).

## PLAN

1. **B-1** (`Isolator._run` y `run_columns`): si `savepoint.rollback()` falla tras un error aislable, se relanza el
   **error de datos original** (`raise error from rollback_error`) con una nota: «bulk: no se pudo volver al SAVEPOINT
   tras el error de datos (<clase>: <primera línea>); en SQL Server suele deberse a XACT_ABORT ON, que deshace la
   transacción entera con el primer error: on_error='isolate' no puede aislar filas así». Mismo tipo de error que sin
   aislamiento; sin consulta previa de `XACT_ABORT` (D-1).
2. **B-3** (`_savepoint`): en SQLite, `driver.autocommit` decide:
   - `LEGACY_TRANSACTION_CONTROL` (por defecto): como hoy (`BEGIN` si `isolation_level` no es `None` y no hay transacción).
   - `False` (Python ≥ 3.12, siempre en transacción): nada que hacer.
   - `True`: no hay transacción que proteja los SAVEPOINT; se lanza un error claro antes del primer SAVEPOINT de la
     operación (D-2), sin enviar nada de esa operación.
   El modo `AUTOCOMMIT` de SQLAlchemy (`isolation_level=None` en el driver) no cambia (E-4).
3. **B-4** (`RejectsWriter`):
   - Lock por ruta con `_audit.repository._get_file_lock` (el de la auditoría: misma normalización de ruta; `_support`
     ya importa de `_audit`). Cabecera y fila se escriben con el lock tomado.
   - Primera escritura de cada instancia: si el fichero existe y su primera línea no es la cabecera de rechazos, se
     aparta como `<nombre>.invalid-<fecha><ext>` con un WARNING (D-3), como la auditoría
     (`AuditCsvRepository._ruta_apartado`, reutilizado sin modificarlo).
   - Entre procesos no hay lock (igual que la auditoría): documentado.
4. Docs (límites de `isolate` en `docs/api/bulk_crud.md`) y la entrada del CHANGELOG.

## AUDIT_PLAN

### Riesgos y condiciones
- **R-1 (B-1) Error que se relanza**: tras un rollback fallido la conexión puede estar rota (no solo por
  `XACT_ABORT`). Relanzar el `IntegrityError`/`DataError` original con la nota y la causa encadenada (`__cause__`) no
  oculta nada; el reintento automático no aplica (`isolate` no está en `ParallelBulkLoader`). Hay que comprobar en
  integración que la salida de `engine.begin()` no sustituye el error por otro de su propio rollback (E-1 indica que no).
- **R-2 (B-3) Momento del error**: dentro de un `bulk_session`, las operaciones anteriores ya se han aplicado (en
  autocommit no hay atomicidad). El error sale en el primer lote de la operación con `isolate`, antes de enviarlo.
- **R-3 (B-3) Python < 3.12**: no aplica (`requires-python >= 3.12`); `getattr(..., LEGACY)` por si el driver no es
  `sqlite3` (pysqlcipher u otros con el mismo dialecto).
- **R-4 (B-4) Coste**: el lock y la comprobación de cabecera (solo la primera vez) son despreciables frente al reenvío
  por bisección de cada fila mala.
- **R-5 (B-4) Apartar el fichero**: si el fichero tiene otra cabecera y no se puede renombrar (abierto en Excel), la
  escritura falla con `OSError` y la nota de M-1 («no se pudo escribir el CSV de rechazos»): mismo camino ya probado.
- **LSP/ISP**: sin cambios en interfaces; `Isolator` y `RejectsWriter` son internos.

### Tests
- Unit: `Isolator` con un SAVEPOINT cuyo rollback falla → error original, nota y `__cause__` (B-1); SQLite
  `autocommit=True` → error claro, 0 filas enviadas, sin bloqueo para otra conexión (B-3); `isolation_level="AUTOCOMMIT"`
  de SQLAlchemy sigue funcionando y el modo heredado sigue siendo atómico (regresión); cabecera distinta → fichero
  apartado y WARNING; dos `RejectsWriter` en hilos sobre la misma ruta → una cabecera y todas las filas (B-4).
- Integración: SQL Server con `XACT_ABORT ON`, con pyodbc y pymssql → `IntegrityError` con la nota y tabla intacta.

### Decisiones para el usuario
- **D-1 (B-1) ¿Comprobar `XACT_ABORT` antes de empezar?** Recomendado: **no**. Una carga sin filas malas funciona con
  `XACT_ABORT ON`; comprobarlo haría fallar cargas que habrían ido bien y añade una consulta por operación. Basta con el
  error claro cuando ocurre.
- **D-2 (B-3) SQLite con `autocommit=True`**: (a) **error claro** («on_error='isolate' necesita una transacción;
  sqlite3 con autocommit=True no la tiene») — recomendado; o (b) emular la liberación del SAVEPOINT externo tras cada
  `ROLLBACK TO` (frágil: SQL a mano por debajo de SQLAlchemy).
- **D-3 (B-4) Cabecera distinta**: (a) **apartar el fichero** como la auditoría — recomendado, por coherencia; o (b)
  fallar con un error.

**Veredicto: GO_CONDICIONAL** (condiciones: D-1, D-2 y D-3)
