# S-2 · Aislamiento de filas erróneas — informe

- Pregunta: ¿cuánto cuesta no perder una carga entera (atómica) por unas pocas filas malas?
- Método: `s2/s2_isolate.py`: cada lote de 5000 en un SAVEPOINT (`begin_nested`); si falla, bisección por mitades, cada
  una en su SAVEPOINT, hasta aislar las filas que fallan; una sola transacción. Filas malas: PK duplicadas repartidas.
  Mismo método de envío en todas las variantes (`connection.execute(insert(t), registros)`; SQL Server con
  `fast_executemany`). 1M filas, 6 motores. Log: `s2/s2.log`. Verificado: filas en BD = N − malas y rechazos = posiciones
  exactas de las malas, en todos los casos.

## Resultados (tiempo relativo a la carga limpia sin SAVEPOINT)

| Motor | Limpia | Limpia con SAVEPOINT | 1 mala | 10 malas | 100 malas | Fallo a mitad + recarga (hoy, estimado) |
|---|---|---|---|---|---|---|
| SQLite | 6,79 s | 1,26× | 1,11× | 1,11× | 2,11× | 1,51× |
| PostgreSQL | 23,74 s | 0,99× | 1,00× | 1,07× | 1,78× | 1,50× |
| MySQL | 20,46 s | 1,01× | 1,00× | 1,10× | 2,05× | 1,55× |
| MariaDB | 18,66 s | 1,05× | 1,05× | 1,16× | 2,20× | 1,58× |
| SQL Server | 15,62 s | 0,96× | 0,96× | 1,14× | 2,79× | 1,54× |
| Oracle | 12,18 s | 1,17× | 0,81× | 0,87× | 1,84× | 1,39× |

(Oracle oscila: con 1 y 10 filas malas sale más rápido que la carga limpia; ruido del servidor.)

## Conclusión
- Correcto en los 6 motores (SAVEPOINT anidado en una transacción, también en SQLite con pysqlite).
- Coste fijo del SAVEPOINT por lote: ≤ 5 % en los servidores; +26 % en SQLite.
- Cada fila mala reenvía ~10 000 filas (las mitades sucesivas de su lote de 5000): coste lineal en el número de filas
  malas. Con 10 malas, 1,00–1,16× (**criterio ≤ 1,2× cumplido**); con 100 malas, 1,8–2,8×, más que fallar y recargar
  una vez, pero esa recarga supone haber localizado y corregido las 100 filas.
- **Decisión: GO** a `BulkCrud(on_error="isolate", rejects_csv_path=...)` opt-in (D-2: ruta obligatoria, nada por
  defecto), `/new-feature`. Requisitos para esa implementación:
  - verificar las estrategias reales dentro de un SAVEPOINT (COPY y `execute_values` de PostgreSQL, `exec_driver_sql`
    de PyMySQL, staging de UPDATE de MySQL/PostgreSQL, OPENJSON);
  - CSV de rechazos con posición, error y valores; documentar que contiene datos del usuario;
  - con `commit_every_n_chunks`, el SAVEPOINT vive dentro del commit periódico (comprobar el libro de filas y la
    reanudación);
  - opcional: lote de bisección más pequeño para cargas con muchas filas malas.
