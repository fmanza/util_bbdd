# S-5 · `batcherrors` de oracledb para `on_error="isolate"` en Oracle — informe

- Pregunta (P-C de `../2026-10-01p-plan-bulk-pending-2/`): ¿puede Oracle aislar filas con `batcherrors` en lugar de la
  bisección, con los mismos datos, menos coste y aislando también ORA-12899?
- Método: `s5_batcherrors.py`. El prototipo no salta SQLAlchemy: escucha `do_executemany` del engine y, con un colector
  activo, llama a `cursor.executemany(statement, parameters, batcherrors=True)`; los procesadores de bind y
  `setinputsizes` de SQLAlchemy ya se han aplicado (R-5 del plan). En Oracle SQLAlchemy usa `cursor.executemany`
  (`use_insertmanyvalues=False`). oracledb 4.0.1, modo thin, Oracle 23 Free.

## Equivalencia y errores (`s5_types.log`)
- INSERT de 60 filas con NUMBER(18,4)/Decimal, VARCHAR2, NVARCHAR2 (ñ, €), DATE, TIMESTAMP con microsegundos, CLOB de
  hasta 50 000 caracteres, BLOB de hasta 10 KB y NULL: **datos idénticos** a los de SQLAlchemy normal con las filas buenas.
- Errores de fila detectados en su posición: ORA-00001 (PK), ORA-12899 (demasiado largo), ORA-01400 (NOT NULL),
  ORA-02291 (FK), ORA-01438 (precisión). Hoy, con la bisección, ORA-12899, ORA-01400 y ORA-01438 llegan como
  `DatabaseError` y **no se aíslan** (R-1 de S-2).
- UPDATE (executemany, como `BulkCrud` en Oracle): 2 filas con ORA-12899 rechazadas e intactas, las otras 18 aplicadas.
- DELETE: la fila referenciada da ORA-02292 y queda; las demás se borran.
- Un rollback de la transacción deshace lo aplicado con `batcherrors`. Un error de sentencia (ORA-00942) se lanza como
  siempre: `batcherrors` solo recoge errores de fila.

## ORA-03106 (`s5_ora03106.log`, driver puro)
- **UPDATE + bind CLOB de 9000 caracteres + una fila con error + `batcherrors=True` → ORA-03106 «fatal two-task
  communication protocol error»**. Con 100, 3999 o 4001 caracteres funciona; el INSERT con 9000 funciona; sin
  `batcherrors` llega el ORA-12899 normal. Fallo del driver en modo thin (no investigado más allá; candidato a reportar
  a python-oracledb).

## Coste (`s5_bench.log`, INSERT 1M, 3 repeticiones)

| Variante | Tiempos | Mediana | × `raise` |
|---|---|---|---|
| `raise` sin filas malas | 10,24 / 9,16 / 9,06 | 9,16 s | 1,00 |
| bisección (actual), 10 malas | 12,04 / 10,95 / 11,19 | 11,19 s | 1,22 |
| `batcherrors` sin filas malas | 9,32 / 9,20 / 10,68 | 9,32 s | 1,02 |
| `batcherrors`, 10 malas | 9,71 / 9,64 / 9,96 | 9,71 s | 1,06 |

## Conclusión
- Datos idénticos: **sí**. Aísla ORA-12899/01400/01438: **sí** (la mejora funcional más importante). Coste con 10 malas:
  1,06× frente a 1,22× (criterio ≤ 1,05×: **en el límite**, dentro del ruido de `raise`, 9,06–10,24 s).
- Riesgo: ORA-03106 en UPDATE con LOB grande y una fila mala.
- **Veredicto: GO_CONDICIONAL** para INSERT y DELETE; para UPDATE solo si ninguna columna actualizada es LOB (si no,
  bisección). Implementar con `/new-feature` (P-C), con el evento `do_executemany` como en el prototipo.
