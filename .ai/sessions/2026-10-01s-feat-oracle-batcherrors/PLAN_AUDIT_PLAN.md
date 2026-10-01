# PLAN + AUDIT_PLAN — `on_error="isolate"` con `batcherrors` en Oracle (P-C)

- Base: `develop` (`2760e10`). Origen: spike S-5 (`../2026-10-01r-spike-oracle-batcherrors/S-5_batcherrors.md`,
  GO_CONDICIONAL; criterio de coste 1,06× aceptado por el usuario).
- Flujo: `/new-feature`. Sin refactor.

## Inputs (supuestos explícitos)
- **Objetivo**: en Oracle con oracledb, aislar las filas con `batcherrors` (un envío por lote, sin bisección), lo que
  además aísla ORA-12899 (demasiado largo), ORA-01400 (NOT NULL) y ORA-01438 (precisión), que hoy hacen fallar la
  operación entera.
- **Módulos**: `bulk/_execution/oracle_batch_errors.py` **(nuevo)**: listener `do_executemany` idempotente por engine y
  colector por `ContextVar`; `bulk/_support/rejects.py` (modo `batch_errors` del `Isolator`); `bulk/crud.py` (cuándo se
  activa); tests `tests/unit/bulk/test_on_error_isolate.py` e integración en `tests/integration/test_bulk_audit_20261001.py`;
  docs `docs/api/bulk_crud.md`, `docs/guides/benchmarks.md`; CHANGELOG.
- **API pública**: sin cambios de firma. Cambio observable solo con `on_error="isolate"` en Oracle: más errores se
  aíslan, y la columna `error` del CSV dice `DatabaseError: ORA-xxxxx: …` (sin la clase de SQLAlchemy).
- **Motores**: Oracle con `oracle+oracledb`. `cx_Oracle` (mismo API, sin probar) y el resto siguen con bisección.

## PLAN
1. `oracle_batch_errors.py`:
   - `supports(engine)`: dialecto `oracle` y driver `oracledb`.
   - `install(engine)`: registra una vez un listener `do_executemany`; si hay un colector activo en el hilo, llama a
     `cursor.executemany(statement, parameters, batcherrors=True)`, añade `cursor.getbatcherrors()` al colector y
     devuelve `True`; si no, `None` (SQLAlchemy sigue como siempre). Los procesadores de bind y `setinputsizes` ya están
     aplicados (S-5).
   - `collect()`: context manager que activa el colector (`ContextVar`, por hilo).
2. `Isolator(batch_errors=...)`:
   - En ese modo, cada lote va en un SAVEPOINT con el colector activo; cada error de fila (offset) se rechaza en
     `first_row + offset` con sus valores (`items[offset]` o `frame.iloc[offset]`) y un `oracledb.DatabaseError(err)` para
     el CSV. Sin bisección.
   - `max_rejects`: si el lote supera lo que queda, se rechazan en orden hasta el tope, se vuelve al SAVEPOINT y se
     reenvía el lote **sin** colector para que el driver lance su error real (clase y mensaje), con la nota habitual.
   - Una excepción (error de sentencia, conexión) se propaga tras deshacer el SAVEPOINT, como hoy.
3. `crud.py`: el `Isolator` usa `batch_errors` si `supports(engine)` y la operación es INSERT o DELETE; en UPDATE solo si
   ninguna columna actualizada es LOB (`Text`, `UnicodeText`, `LargeBinary`, `JSON` y los CLOB/NCLOB/BLOB de Oracle),
   por el ORA-03106 de S-5; si no, bisección.
4. Docs: límites de `isolate` (Oracle ahora aísla también demasiado largo, NOT NULL y precisión salvo en UPDATE con LOB);
   coste medido; CHANGELOG *Added*.

## AUDIT_PLAN

### Verificado (S-5)
| # | Supuesto | Resultado |
|---|---|---|
| V-1 | Mismos datos que la vía normal | 8 tipos + NULL idénticos (`s5_types.log`) |
| V-2 | Errores de fila con su posición, sin aplicar esas filas | ORA-00001/12899/01400/02291/01438 en INSERT; ORA-12899 en UPDATE; ORA-02292 en DELETE |
| V-3 | Transaccional | rollback deshace lo aplicado; error de sentencia se lanza |
| V-4 | Coste | 10 malas 1,06× (bisección 1,22×); limpio 1,02× |
| V-5 | El DELETE de Oracle es executemany fila a fila en el orden del lote | `GenericDeleteStrategy` (`delete_strategies.py:162`) |

### Riesgos y condiciones
- **R-1 ORA-03106** (UPDATE + bind LOB grande + fila mala): se evita con la regla del paso 3. Si aun así ocurre (otra
  combinación no vista), la operación falla con ese error: sin datos a medias (transacción), pero conexión inservible.
  Documentar; test de integración del UPDATE con LOB por bisección.
- **R-2 Listener global en el engine**: inactivo salvo con colector activo en ese hilo; no cambia nada para quien no
  use `isolate`. Idempotente (no duplicar listeners si se crean muchas `BulkCrud`, como en `ParallelBulkLoader`).
- **R-3 Hilos**: `ContextVar` por hilo; cada hilo de `ParallelBulkLoader` tiene su colector (relevante en la Fase 3).
- **R-4 `max_rejects` superado**: el reenvío sin colector cuesta un lote más solo en ese caso; el error real lo da el
  driver (no se fabrica una excepción).
- **R-5 Error del CSV**: `DatabaseError: ORA-00001: …` en lugar de `IntegrityError: …`; es más informativo (código ORA)
  pero distinto del de la bisección. Documentar.
- **R-6 `executemany` partido por SQLAlchemy**: en Oracle SQLAlchemy hace un único `executemany` por lote (sin
  insertmanyvalues); si una versión futura lo partiera, los offsets serían por llamada. Test unitario que fija el
  supuesto (`use_insertmanyvalues` del dialecto) y el de integración lo comprueba de extremo a extremo.
- **LSP/ISP**: `Isolator` gana un modo; los ejecutores no cambian.

### Tests
- Unit: modo `batch_errors` del `Isolator` con un `send` falso que llena el colector (posiciones, valores, sin
  bisección, `max_rejects` con reenvío, excepción propagada); `install` idempotente; `supports`.
- Integración Oracle: INSERT con PK duplicada, demasiado largo, NOT NULL y precisión → aislados; UPDATE sin LOB con
  demasiado largo → aislado; UPDATE con LOB y demasiado largo → bisección (falla como hoy, R-1 de S-2); DELETE con FK;
  `max_rejects`; sesión atómica; el test `test_isolate_value_too_long_is_not_isolated` pasa a SQL Server solo.
- Medición: `bench_isolate.py` de `2026-10-01n` en Oracle.

### Decisiones
Ninguna abierta (alcance y coste aprobados en S-5).

**Veredicto: GO**
