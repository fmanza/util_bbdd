# Q8 — medición previa de la etapa pandas del volcado (2026-09-26)

Código de `v0.16.1` (`3d4e52d`). Datos `large` del banco (3,5M filas: `customers` 500K, `orders` 1M,
`order_items` 2M). Objetivo: acotar lo que ganaría la ruta sin pandas (roadmap 3.1) antes de implementarla.

## 1. Volcado completo (`scripts/bench_dump.py run --variants baseline --repeat 2`)

Resultados en `results/results.jsonl`. 12/12 con verificación e identidad correctas.

| Motor | Total (mediana) | RSS pico |
|---|---|---|
| PostgreSQL | 12,6 s | 195 MB |
| MariaDB (Connector/Python) | 30,6 s | 158 MB |
| MySQL (PyMySQL) | 39,0 s | 163 MB |
| Oracle | 43,1 s | 175 MB |
| SQL Server (pymssql) | 59,1 s | 166 MB |
| SQLite | 19,8 s | 176 MB |

Desde Q3 (lector en paralelo), las fases `read` y `write` se solapan, así que `prep_derived` sale negativo. El desglose
por fases del banco ya no sirve para aislar la preparación; solo el total es comparable (deuda del banco, ver §4).

## 2. Coste de la etapa pandas, aislado (script de la sesión `q8_pandas_cost.py`, sin escribir)

Para cada tabla, se lee el origen con `_execute_read` y `fetchmany(5000)` y se mide el tiempo de CPU de cada paso:

- `df`: `pd.DataFrame(rows, dtype=object)` (hoy en el hilo lector);
- `rebatch`: agrupa en lotes de `write_batch_size` (20 000 en PG; en el resto no agrupa nada);
- `records`: `dataframe_to_sql_records(strip_strings=False)` (hoy en el hilo principal);
- `tuples`: la alternativa sin pandas, `[dict(zip(keys, row))]`.

Resultados en segundos, para `order_items` (2M filas):

| Origen | fetch | df | rebatch | records | pandas (df+rebatch+records) | tuples | diferencia |
|---|---|---|---|---|---|---|---|
| PostgreSQL | 2,06 | 0,63 | 0,12 | 1,56 | 2,32 | 0,71 | 1,61 |
| MySQL | 9,34 | 0,64 | 0,07 | 1,62 | 2,33 | 0,75 | 1,58 |
| MariaDB | 1,35 | 0,52 | 0,06 | 1,59 | 2,17 | 0,75 | 1,42 |
| SQL Server | 5,28 | 0,54 | 0,07 | 1,58 | 2,19 | 0,76 | 1,42 |
| Oracle | 2,79 | 0,55 | 0,06 | 1,56 | 2,17 | 0,88 | 1,29 |

El coste es lineal en filas y casi no depende del motor. Para las 3 tablas juntas (3,5M filas), la diferencia es
≈ 2,4–2,7 s. De eso, ≈ 1,3 s es `df`, que ya corre en el hilo lector, solapado con la escritura. En el hilo principal
(el camino crítico) quedan ≈ 1,5 s (`records` − `tuples`), más 0,2 s de `rebatch` en PG.

## 3. Cota superior de la ganancia de Q8

| Motor | Total | Ganancia máxima en el camino crítico | % |
|---|---|---|---|
| PostgreSQL | 12,6 s | ≈ 1,7–2,0 s | ≈ 13–16 % |
| MariaDB | 30,6 s | ≈ 1,5–2,0 s | ≈ 5–7 % |
| MySQL | 39,0 s | ≈ 1,5–2,0 s | ≈ 4–5 % |
| Oracle | 43,1 s | ≈ 1,5–2,0 s | ≈ 4 % |
| SQL Server | 59,1 s | ≈ 1,5–2,0 s | ≈ 3 % |

Es una cota superior: una ruta con tuplas tendría que seguir haciendo lo que hoy hace la de DataFrames:

- alinear columnas por nombre (PD-01);
- quitar la PK autoincremental;
- restaurar los binarios (P-21);
- normalizar los valores `NaN`/`numpy` que no vengan del driver.

`dataframe_to_sql_records` ya usa la vía rápida de PD-05 para las columnas `object` que se pueden pasar tal cual. Lo que
queda es el recorrido por columnas y la trasposición con `zip(*columns)`; no hay ninguna mejora barata dentro de pandas.

**Esfuerzo y riesgo**: una segunda entrada de `BulkCrud` (tuplas) paralela a `bulk_insert_from_chunks`, que habría que
llevar a las 4 estrategias de INSERT, a `ParallelBulkLoader` y a los tests de fidelidad. Riesgo medio-alto por
duplicar la lógica de columnas e identidad.

## 4. Conclusión

- **Q8 no compensa hoy salvo en PostgreSQL** (≈ 15 %). En el resto, la escritura del driver pesa 20–50 veces más que la
  preparación.
- Recomendación: **aparcar Q8** y volver a medirlo si otro cambio acerca la escritura al coste de la lectura (hoy solo pasa
  en PostgreSQL con `COPY`).
- Deuda del banco: con el lector en paralelo, `read`/`write` se solapan. Para aislar la preparación habría que
  cronometrar `dataframe_to_sql_records` dentro de `bulk_insert_from_chunks`, o medir con `_PREFETCH_SOURCE_DIALECTS`
  vacío.
