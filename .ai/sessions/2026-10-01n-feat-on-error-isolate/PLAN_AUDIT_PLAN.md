# PLAN + AUDIT_PLAN — `BulkCrud(on_error="isolate", rejects_csv_path=...)` (S-2)

- Base: `develop` (`d53834f`). Origen: `../2026-10-01l-plan-bulk-pending/S-2_isolate.md` (prototipo correcto en 6 motores;
  10 filas malas 1,00–1,16×) y `s2/s2_real_strategies.py` (estrategias reales dentro de SAVEPOINT, ver V-1).
- Flujo: `/new-feature`. Sin refactor.

## Inputs (supuestos explícitos)
- **Objetivo**: que unas pocas filas con errores de datos no deshagan una carga entera: se apartan a un CSV de rechazos y
  el resto se aplica. Opt-in (D-2 de la sesión anterior: ruta obligatoria, nada por defecto).
- **Módulos**: `src/util_bbdd/bulk/crud.py`, `src/util_bbdd/bulk/_execution/executors.py`,
  `src/util_bbdd/bulk/_support/rejects.py` **(nuevo)**: escritor del CSV de rechazos e `isolate_batch` (bisección);
  tests `tests/unit/bulk/test_on_error_isolate.py` **(nuevo)** e integración en `tests/integration/test_bulk_audit_20261001.py`;
  docs `docs/api/bulk_crud.md`, `docs/functional/bulk_operations.md`, `docs/guides/benchmarks.md`.
- **API pública**: `BulkCrud(..., on_error: Literal["raise", "isolate"] = "raise", rejects_csv_path: Path | None = None,
  max_rejects: int | None = None)`; propiedad `rows_rejected: int`. Sin cambios en `ParallelBulkLoader` ni `dump`.
- **Contrato de entrada**: igual que hoy. Con `on_error="isolate"` es obligatorio `rejects_csv_path` (si no,
  `ValueError` en el constructor).
- **Contrato de salida**: las filas sin error se aplican; cada fila con `IntegrityError` o `DataError` se omite y se
  escribe en el CSV de rechazos (UTF-8, tabuladores, como la auditoría) con `timestamp`, `tabla`, `operacion`, `fila`
  (posición base 0 en la entrada; en `*_from_chunks`, en la secuencia), `error` (primera línea del error del driver) y
  `valores` (JSON del registro). Cualquier otro error se propaga como hoy.
- **Reglas**: semántica atómica intacta salvo para las filas rechazadas; sin cambio con `on_error="raise"`.
- **Restricciones**: sin dependencias nuevas; solo sync; `BulkCrud` sigue sin ser thread-safe.
- **Motores**: los 6.
- **Migraciones**: no.

## PLAN
1. `bulk/_support/rejects.py`:
   - `RejectsWriter(path)`: crea el directorio, escribe la cabecera si el fichero es nuevo y añade filas; neutraliza en
     las celdas de texto el prefijo de fórmula (`=`, `+`, `-`, `@`, tabulador, retorno de carro) con un `'` delante, porque
     el CSV contiene datos del usuario y se abrirá en Excel.
   - `isolate(run, items, *, first_row, on_reject, max_rejects)`: ejecuta `run(items)` dentro de un SAVEPOINT; si falla
     con `IntegrityError`/`DataError`, vuelve al SAVEPOINT y repite por mitades (cada una en su SAVEPOINT) hasta filas
     sueltas, que se rechazan. Otros errores se propagan.
2. `executors.py`: `BatchStatementExecutor` y `DeleteBatchExecutor` reciben un `isolator` opcional; si está, cada lote
   (registros, bloque por columnas o trozo del DataFrame del DELETE) pasa por él. Un bloque por columnas que falla se
   convierte a registros solo en ese camino. La cadencia y el commit periódico no cambian (el commit va fuera del SAVEPOINT).
3. `crud.py`: validación de parámetros; `RejectsWriter`; posiciones de entrada (los bloques ya conocen su desplazamiento
   y el chunk, como las notas de error); `rows_rejected`; auditoría con las filas **aplicadas** (enviadas − rechazadas).
4. Docs y CHANGELOG (*Added*): cuándo usarlo, coste medido (≈ 2 × el tamaño de lote reenviado por cada fila mala; con 10
   filas malas en 1M, ≤ 1,16×), que el CSV contiene datos y que con `max_rejects` superado la operación falla entera.

## AUDIT_PLAN

### Verificado
| # | Supuesto | Evidencia | Resultado |
|---|---|---|---|
| V-1 | Las estrategias reales se recuperan tras fallar dentro de un SAVEPOINT | `s2/s2_real_strategies.py`: INSERT (COPY en PG, PyMySQL por columnas, `fast_executemany` en SQL Server, executemany en Oracle/SQLite), UPDATE por staging (PG, MySQL, MariaDB) y DELETE (`= ANY`, `IN` troceado, OPENJSON, executemany) | Correcto en los 5 servidores; SQLite sin FK activas (DELETE no comparable) |
| V-2 | Los errores de datos llegan como `IntegrityError`/`DataError` | Mismo script: PK duplicada → `IntegrityError` en los 6; valor demasiado largo → `DataError` (PG, MySQL, MariaDB); FK → `IntegrityError` | Confirmado |
| V-3 | Coste aceptable | S-2: 10 filas malas en 1M, 1,00–1,16×; SAVEPOINT sin errores ≤ 5 % (SQLite +26 %) | Confirmado con executemany genérico |

### Riesgos y condiciones
- **R-1 Qué se aísla**: solo `IntegrityError` y `DataError`. Un error estructural (columna inexistente, permisos,
  sintaxis) no debe convertirse en «todas las filas rechazadas»: no está en esas clases y se propaga. Límite conocido:
  algunos drivers clasifican errores de datos de otra forma (PyMySQL 1292 «valor incorrecto» como `OperationalError`;
  Oracle ORA-12899 «valor demasiado grande» como `DatabaseError`): con ellos la operación falla como hoy. Documentar;
  no ampliar a clases genéricas.
- **R-2 Coste sin cota**: si casi todas las filas fallan (p. ej. recargar datos ya cargados), la bisección acaba enviando
  fila a fila. `max_rejects` (D-1) corta: superado, se relanza el error y la operación se deshace entera.
- **R-3 Transacción condenada en SQL Server**: con `XACT_ABORT OFF` (por defecto) las violaciones de restricción y los
  truncados terminan solo la sentencia; si el servidor marca la transacción como no confirmable (`XACT_STATE() = -1`),
  el ROLLBACK al SAVEPOINT falla y se propaga el error (sin datos a medias). Test de integración con truncado en SQL Server.
- **R-4 Libro de filas y reanudación**: `rows_committed`/`last_operation_rows_committed` siguen contando **posiciones**
  de la entrada (rechazadas incluidas), porque son el punto de reanudación (B-11). `rows_rejected` aparte. Documentar.
- **R-5 Auditoría**: el CSV de auditoría registra las filas aplicadas (enviadas − rechazadas), coherente con «la
  auditoría no cuenta filas que no están en la BD» (M-1). Cambio solo con `on_error="isolate"`.
- **R-6 Rechazos y rollback de la sesión**: los rechazos se escriben al detectarse; si después la sesión entera se deshace
  por otra causa, el CSV de rechazos conserva las filas rechazadas (son errores de datos igualmente). Documentar.
- **R-7 Datos del usuario en disco** (seguridad): el CSV contiene valores de las filas; solo con ruta explícita;
  neutralización de fórmulas; nada de credenciales (el error del driver no incluye la URL; se toma su primera línea).
- **R-8 Posición de la fila**: con PK repetida dentro de un lote, aislar puede cambiar cuál de las dos se aplica (en
  UPDATE «gana la última»). Documentar como límite.
- **LSP/ISP**: los ejecutores reciben un colaborador opcional; con `on_error="raise"` el camino es el actual (sin
  SAVEPOINT). Sin cambios en interfaces públicas ni en protocolos de estrategias.
- **Simplificaciones**: sin soporte en `ParallelBulkLoader` ni `dump` (requeriría un lock por ruta del CSV de rechazos,
  como la auditoría); sin `batcherrors` de Oracle (la bisección genérica cubre los 6 motores).

### Tests
- Unit (SQLite): INSERT/UPDATE/DELETE con filas malas en distintas posiciones → filas aplicadas exactas, rechazos con
  posición y error; `*_from_chunks` (posición en la secuencia); `max_rejects`; error no aislable se propaga;
  `on_error="raise"` sin cambios; validación de parámetros; neutralización de fórmulas; auditoría con filas aplicadas.
- Integración (5 servidores): INSERT con PK duplicada y UPDATE con valor demasiado largo (staging), DELETE con FK; SQL
  Server con truncado (R-3); con `commit_every_n_chunks`.

### Decisiones para el usuario
- **D-1 `max_rejects` por defecto**: `None` (sin límite) o un tope (p. ej. 1000)? Recomendado: `None`, documentando el
  coste, porque un tope por defecto haría fallar cargas que el usuario pidió aislar.

**Veredicto: GO_CONDICIONAL** (condición: D-1)
