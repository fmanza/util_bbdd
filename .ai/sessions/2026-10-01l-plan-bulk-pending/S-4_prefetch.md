# S-4 · Prefetch de bloques — informe

- Pregunta: ¿es estable la ganancia de preparar el bloque N+1 mientras se escribe el N? (E3 de la auditoría, una sola
  medición: +17 % SQL Server, +9 % MySQL, +5 % MariaDB, −18 % Oracle).
- Método: `s4/s4_prefetch.py` (parche de instancia de `__record_blocks` y `__sql_blocks` con
  `dump._source_reader._prefetch`, cola de 2), código de v0.25.1, 1M filas, 3 repeticiones alternando variantes,
  resultados verificados con SQL. Log: `s4/s4.log`.

## Resultado (segundos; cambio de la mediana; todos con rangos disjuntos)

| Motor | Operación | Secuencial | Prefetch | Cambio |
|---|---|---|---|---|
| SQL Server (pyodbc) | INSERT | 13,95 / 13,97 / 14,19 | 12,80 / 12,39 / 12,48 | **−10,6 %** |
| SQL Server (pyodbc) | UPDATE | 22,42 / 22,16 / 22,17 | 20,68 / 20,84 / 20,80 | −6,2 % |
| MySQL 8.4 | INSERT | 16,36 / 16,32 / 16,09 | 15,05 / 15,38 / 15,55 | −5,7 % |
| MySQL 8.4 | UPDATE | 22,43 / 22,63 / 23,37 | 21,34 / 22,13 / 22,41 | −2,2 % |
| MariaDB 11.4 | INSERT | 14,90 / 14,86 / 15,18 | 14,61 / 14,06 / 14,00 | −5,6 % |
| MariaDB 11.4 | UPDATE | 20,99 / 20,99 / 20,83 | 19,94 / 19,84 / 19,90 | −5,2 % |

## Decisión
- Ganancia estable y pequeña (2–11 %), máxima en el INSERT de SQL Server (≥ 10 %, criterio del PLAN cumplido).
- **GO a una opción opt-in** `BulkCrud(prefetch_blocks=False)` (`/new-feature`): no por defecto, porque Oracle empeoró
  en la auditoría (−18 %, sin repetir) y la ganancia en el resto es ≤ 6 %. Reutilizar `dump._source_reader._prefetch`
  (moverlo a `bulk/_support/` si `bulk` lo importa, para no invertir la dependencia `bulk → dump`).
- Riesgo a cubrir en esa implementación: cerrar el hilo lector si la escritura falla (`_prefetch` ya hace `join` en el
  `finally`), y no combinarlo con `ParallelBulkLoader` (hilos × 2).
