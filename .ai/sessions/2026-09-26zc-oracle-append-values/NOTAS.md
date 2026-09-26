# 3.3 — hipótesis Oracle `/*+ APPEND_VALUES */` (2026-09-26): descartada

Código de `53c63ea`. Datos `large` (3,5M filas), Oracle Free 23ai del banco (`FREEPDB1`). Variantes nuevas de
`scripts/bench_dump.py`: `append*` añade el hint a los INSERT por lotes (executemany) del destino con un listener
`before_cursor_execute`; `commit1*` hace commit tras cada lote (`commit_every_n_chunks=1`). Resultados en
`results/results.jsonl`.

## Resultados

| Variante | Qué cambia | Run 1 | Run 2 |
|---|---|---|---|
| `baseline` | — | 34,1 s | 35,0 s |
| `append` | hint, una transacción por tabla | 41,1 s | 41,8 s (+20 %) |
| `commit1` | commit cada 5 000 filas, sin hint | 51,8 s | 59,5 s (+50–70 %) |
| `append_commit1` | hint + commit cada 5 000 filas | **no terminó** | — |

`append_commit1` llevaba más de 25 minutos en `ALTER TABLE … ENABLE VALIDATE CONSTRAINT fk_dump_dst_itm_ord`, leyendo la
tabla (`db file scattered read`), sin bloqueos. Los segmentos del destino explicaban por qué:

| Tabla | Origen | Destino con `append_commit1` |
|---|---|---|
| `CUSTOMERS` | 37 MB | 361 MB |
| `ORDERS` | 32 MB | 1 921 MB |
| `ORDER_ITEMS` | 80 MB | **10 158 MB (127×)** |

Cada INSERT directo escribe en bloques nuevos por encima de la high-water mark. Con un commit por lote de 5 000 filas
(400 cargas directas en `order_items`), la tabla acaba llena de bloques medio vacíos y extents nuevos. Todo lo que
después recorre la tabla (la validación de FK, las consultas) paga ese tamaño. La medición se paró, y el destino se
reinició y quedó vacío.

La variante `append` (sin commit por lote) no dio ORA-12838. No se comprobó si Oracle 23ai hizo carga directa en ese
caso; en cualquier caso fue un 20 % más lenta que `baseline`.

Los lotes de 50 000 filas no se midieron (`commit1_50k`, `append_commit1_50k`). Con 40 cargas por tabla la hinchazón
sería menor, pero el commit por lote ya cuesta un 50–70 % sin hint. Además, la carga directa bloquea la tabla en
exclusiva, lo que es incompatible con `parallel_pk_ranges`.

## Conclusión

**Descartada.** El hint no mejora el volcado y, combinado con el commit por lote que Oracle exige para la carga directa
repetida, multiplica el tamaño de las tablas. Las variantes quedan en el banco como referencia. Aviso para quien las
use: `append_commit1` en `large` ocupa ≈ 12 GB en el destino Oracle.
