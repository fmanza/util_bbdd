# Q9 — medición previa del coste fijo por tabla (2026-09-26)

Volcado de 200 tablas pequeñas (100 filas, estrella: t001…t199 → t000) en esquemas propios `zz_q9_src`/`zz_q9_dst`
(borrados al terminar), código tras Fases 0–2 y 3.4. Instrumentación de `scripts/bench_dump.py`. 200/200 `success`.

| Motor | Total | ms/tabla | analysis | reflect (bulk) | cleanup | counts | constraints_enable |
|---|---|---|---|---|---|---|---|
| PostgreSQL | 10,5 s | 53 | 1,77 s | 2,77 s | 0,03 s | 1,30 s | 1,53 s (PD-04: anti-join por FK) |
| SQL Server | 35,4 s | 177 | **9,94 s** | **10,81 s** | **7,76 s** | 1,50 s | 1,11 s |
| MySQL | 13,4 s | 67 | 1,15 s | 1,02 s | **5,71 s** | 1,88 s | — |

## Premisa de Q9 no se sostiene tal como estaba escrita
Q9 proponía `Inspector.get_multi_columns/get_multi_foreign_keys/get_multi_pk_constraint` (una consulta por esquema).
En SQLAlchemy 2.0.50 solo PostgreSQL (7 métodos) y Oracle (8) los implementan de forma nativa; **SQL Server, MySQL y
SQLite no tienen ninguno** y el método por defecto recorre tabla a tabla. El motor que lo justificaba (SQL Server, ≈ 100
ms/tabla en análisis + reflexión) no ganaría nada.

## Alternativas para SQL Server (pendiente de decisión)
- Consultas propias a `sys.columns`/`sys.foreign_keys` por esquema para el análisis (orden topológico, columnas comunes)
  y para detectar tablas referenciadas en la limpieza (`_get_dst_fk_referenced_tables`, hoy `get_foreign_keys` por tabla:
  parte de los 7,8 s de cleanup).
- La reflexión de `BulkCrud.reflect_table` (`Table(..., autoload_with=...)`) seguiría siendo por tabla.
