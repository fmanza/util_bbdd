# Informe de validación — performance-audit de `dump`

- Fecha: 2026-09-25 · Banco: `bench/bench_dump_real.py` (DumpOrchestrator real), `bench/bench_read_path.py`, `bench/bench_many_tables.py`
- Entorno: Windows 11 (32 CPU lógicas, 16 GB), Python 3.14.2, pandas 3.0.3, SQLAlchemy 2.0.50; psycopg 3.3.3, PyMySQL 1.4.6, pyodbc 5.3.0 + ODBC Driver 18, python-oracledb 4.0.1 (modo thin). Servidores en Docker local (`docker-compose.bench.yml`): PostgreSQL 17, MySQL 8.4, MariaDB 11.4, SQL Server 2022, Oracle 23 Free; SQLite en fichero local (destino, con PostgreSQL de origen).
- Volumen `large`: 500K + 1M + 2M = 3,5M filas. Configuración por defecto de `DumpConfig` en la línea base (`chunk_size=5000`, `collect_row_counts=True`, sin paralelismo, sin `manage_indexes`).
- Cada medición: subproceso propio, destino recreado antes (fuera del tiempo), verificación de COUNT y SUM(PK) origen/destino y sonda de identidad.
- Datos crudos: `baseline/large/results.jsonl`, `variants/large/results.jsonl` (1 repetición), `validation/large/results.jsonl` (repeticiones), `validation/read_path.jsonl`, `validation/many_tables_*.jsonl`.

## 1. Línea base (mediana de 3)

| Motor | Mediana (s) | Repeticiones (s) | Filas/s | RSS pico | Lectura | Preparación | Escritura | Resto (constraints, conteos, análisis, informe…) |
|---|---|---|---|---|---|---|---|---|
| PostgreSQL | **25,5** | 25,5 · 24,7 · 25,5 | 137K | 400 MB | 6,8 s | 5,0 s | 13,2 s | 0,5 s |
| SQLite (desde PG) | **25,6** | 24,2 · 25,6 · 26,1 | 137K | 404 MB | 6,4 s | 6,0 s | 11,7 s | 0,2 s |
| MariaDB | **57,2** | 55,6 · 58,9 · 57,2 | 61K | 842 MB | 20,9 s | 5,0 s | 29,1 s | 0,6 s |
| MySQL | **61,9** | 61,9 · 65,2 · 60,5 | 57K | 841 MB | 21,3 s | 5,3 s | 34,8 s | 0,5 s |
| Oracle | **67,0** | 65,0 · 67,3 · 67,0 | 52K | 154 MB | 27,5 s | 4,9 s | 31,2 s | 1,4 s |
| SQL Server (pyodbc) | **69,0** | 71,5 · 69,0 · 67,2 | 51K | 146 MB | 12,0 s | 5,5 s | 52,3 s | 1,7 s |

Fases de la primera repetición. Dispersión entre repeticiones: ±5 %. Todas las mediciones de la línea base pasan la verificación de datos. La **sonda de identidad falla** en PostgreSQL y Oracle en el 100 % de los casos (PD-02).

## 2. Configuraciones recomendadas, validadas con 3 repeticiones

| Motor | Configuración (sin cambiar código) | Mediana (s) | Repeticiones | Δ vs línea base | RSS pico |
|---|---|---|---|---|---|
| PostgreSQL | `stream_results` + `chunk_size=20000` + solape lectura/escritura (prototipo) + sin conteos | **14,0** | 14,2 · 14,0 · 14,0 | **−45 %** | 182 MB (−55 %) |
| MySQL | `stream_results` + solape (prototipo) + sin conteos | **42,6** | 42,1 · 42,4 · 43,4 · 42,8 | **−31 %** | 147 MB (−83 %) |
| MariaDB | ídem | **42,8** | 41,6 · 42,2 · 43,4 · 48,5 | **−25 %** | 147 MB (−83 %) |
| SQL Server | `parallel_pk_ranges=4` + `stream_results` + sin conteos | **35,7** | 42,7 · 35,7 · 33,9 | **−48 %** | 174 MB |
| Oracle | `create_engine(..., arraysize=5000)` en el origen | **47,7** | 40,8 · 52,8 · 47,7 | **−29 %** | 156 MB |
| SQLite (destino) | `stream_results` (origen PG) + `chunk_size=20000` + solape + sin conteos | **21,4** | 21,4 · 21,5 · 21,3 | **−16 %** | 200 MB (−50 %) |

Todas pasan la verificación de datos en todas las repeticiones.

- El solape lectura/escritura («prefetch») es un **prototipo del banco** (`bench_dump_real.py::prefetch`), no una opción de `DumpConfig`: sirve para dimensionar la propuesta Q3.
- «Sin conteos» (`collect_row_counts=False`) aporta ≤ 1 % en estas tablas grandes. Se incluyó para aislar el efecto del resto.

### Combinaciones que no suman (medidas, 3 repeticiones)

| Motor | Configuración | Mediana | Δ | Lectura |
|---|---|---|---|---|
| PostgreSQL | `parallel_pk_ranges=4` + `stream_results` + `chunk_size=20000` | 25,9 s | +2 % | Por separado, `ranges4` −35 % y `chunk20k` −31 % (1 repetición cada una). Combinados, la lectura sumada entre hilos pasa de 19,9 a ~60 s. **Causa no aclarada**: el plan de la consulta por rango es el mismo con y sin cursor de servidor (`EXPLAIN` / `EXPLAIN DECLARE`: Index Scan en ambos). Hasta investigarlo, no combinar rangos y `stream_results` en PostgreSQL. |
| SQL Server | `parallel_pk_ranges=8` | 67,5 s | −2 % | Más de 4 rangos no ayuda (contención en el destino). |
| Oracle | `arraysize=5000` + solape | 54,1 s | −19 % | Peor que `arraysize` solo. Hipótesis sin verificar: python-oracledb en modo thin decodifica en Python, y el hilo lector compite por el GIL con la preparación. |
| Oracle | `arraysize=5000` + `parallel_pk_ranges=4` | 51,8 s | −23 % | Peor que `arraysize` solo. |

### Variantes con una sola repetición (orientativas, ruido ±10 %)

Tabla completa en `bench/summarize.py` → `baseline/summary_large.md`. Las relevantes:

| Variante | PostgreSQL | MySQL | MariaDB | SQL Server | Oracle | SQLite |
|---|---|---|---|---|---|---|
| `stream_results` (solo) | −10 %, RSS 153 MB | +1 %, RSS 143 MB | 0 %, RSS 143 MB | −6 % | ruido | +10 %, RSS 156 MB |
| `chunk_size=20000` | **−31 %** | +5 % | −3 % | **+57 %** | 0 % | −6 % |
| solape (prototipo) solo | −20 % | −3 % | −3 % | −19 % | −29 % | −1 % |
| `parallel_pk_ranges=4` | −35 % | **+14 %** | **+27 %** | **−55 %** | −23 % | **pierde filas** (`database is locked`) |
| `manage_indexes=True` | −23 % | −4 % | +4 % | −16 % | +1 % | −2 % |
| constraints sin revalidar (`nocheck`) | — | — | — | −4 % (0,47 → 0,02 s) | −4 % (0,73 → 0,02 s) | — |

## 3. Coste de la ruta pandas (microbanco de lectura, `order_items`, 2M filas, solo lectura)

| Motor | pandas (`read_sql` + DataFrame + `dataframe_to_sql_records`) | tuplas del cursor (`fetchmany`) | tuplas + cursor de servidor / `arraysize` | Ahorro sin pandas |
|---|---|---|---|---|
| PostgreSQL | 6,2 s · 395 MB | 1,9 s · 391 MB | 2,6 s · **143 MB** | −4,3 s (−69 %) |
| MySQL | 14,0 s · 836 MB | 9,5 s | 9,8 s · **135 MB** | −4,5 s (−32 %) |
| MariaDB | 19,7 s · 838 MB | 12,0 s | 10,2 s · **135 MB** | −7,7 a −9,5 s (−39 a −48 %) |
| SQL Server | 9,5 s · 140 MB | 5,3 s | 5,3 s | −4,2 s (−44 %) |
| Oracle | 16,3 s · 147 MB | 12,0 s | **3,2 s** (`arraysize=5000`) | −4,3 s (pandas) y −8,8 s (`arraysize`) |

- Tiempo hasta el primer chunk con cursor del cliente: PostgreSQL 0,6–0,9 s, MySQL 8,9–9,2 s, MariaDB 11,4–11,8 s (se descarga la tabla entera). Con cursor de servidor: 0,03–0,04 s.
- Extrapolado a las 3,5M filas del volcado (×1,75), la ruta sin pandas (Q8) ahorraría **≈7–8 s de CPU por volcado**, además de corregir PD-05. Esto no incluye el coste de conversión por tipo que la ruta nueva tendría que hacer (p. ej. `Decimal` → driver), así que es una **cota superior**.

## 4. Coste fijo por tabla (`bench_many_tables.py`, 200 tablas × 100 filas)

### 4.1 Topología en estrella (todas las tablas con FK a `zm_000`)

| Motor | Total con conteos | ms/tabla | Análisis | Reflexión (`bulk`) | Conteos | Constraints (off + on) | Limpieza | Sin conteos |
|---|---|---|---|---|---|---|---|---|
| SQLite | 5,1 s | 26 | 1,7 s | 0,8 s | 0,7 s | — | 0,0 s | 3,5 s¹ |
| MariaDB | 8,2 s | 41 | 1,3 s | 1,3 s | 1,5 s | — | 1,7 s | 7,5 s |
| MySQL | 13,9 s | 70 | 1,4 s | 1,1 s | 1,6 s | — | **6,6 s** | 13,6 s |
| PostgreSQL | 16,4 s | 82 | 2,0 s | **6,4 s** | 1,6 s | 2,5 s | 0,9 s | 14,4 s¹ |
| Oracle | 24,8 s | 124 | 4,6 s | **6,2 s** | 2,7 s | **5,5 s** | 0,6 s | 26,5 s |
| SQL Server | 31,1 s | 155 | 5,8 s | **13,2 s** | 1,9 s | 1,5 s | 4,1 s | 26,2 s |

¹ La pasada sin conteos fue un volcado repetido: en PostgreSQL falló 1 tabla (PD-03) y en SQLite las 200 (PD-06). El tiempo es orientativo.

- **CB5 (COUNT)**: 3,5–13 ms por tabla (entre el 6 % y el 18 % del total con tablas pequeñas). En un esquema de 1000 tablas pequeñas son 3–13 s.
- **CB6 (introspección + reflexión)**: el mayor coste fijo en SQL Server (95 ms/tabla), Oracle (54 ms/tabla) y PostgreSQL (42 ms/tabla). En un esquema de 1000 tablas, el coste fijo total (a 155/124/82 ms por tabla) sería de ≈ 2,6 min en SQL Server, ≈ 2 min en Oracle y ≈ 1,4 min en PostgreSQL, antes de contar las filas.
- **MySQL**: `TRUNCATE` de InnoDB cuesta ≈ 33 ms por tabla (recrea el tablespace).

### 4.2 Topología en cadena (cada tabla con FK a la anterior): reflexión recursiva

| Tablas en cadena | PostgreSQL total | ms/tabla | Reflexión (`BulkCrud.reflect_table`) |
|---|---|---|---|
| 50 | 14,5 s | 290 | 12,3 s |
| 100 | 50,2 s | 502 | 45,6 s |
| 150 | **RecursionError** (el volcado entero aborta) | — | — |
| 200 | **RecursionError** en PostgreSQL, SQL Server, Oracle y SQLite; en MariaDB, `AttributeError` en el listener de `ConstraintManager` que tapa el error original | — | — |

`Table(..., autoload_with=engine)` refleja también todas las tablas referenciadas por FK, y las referenciadas por esas, y así sucesivamente. Cada `reflect_table` de `bulk` recorre el cierre transitivo de FKs: el coste es cuadrático con la profundidad del grafo, y a partir de ~150 niveles desborda la pila. Nuevos hallazgos PD-08 y PD-09 en el informe de auditoría.

## 5. Incidencias de la propia validación

- 2 mediciones de Oracle `arraysize` se ejecutaron por error cuando `dump_src` aún contenía las 200 tablas `zm_` de la prueba en cadena. Fallaron con `RecursionError` y se **descartaron** (`validation/large/results_discarded_zm_contamination.jsonl`); se repitieron después de borrar las tablas. De paso, demuestran que la recursión aborta el volcado completo: el `RecursionError` no es un `SQLAlchemyError`, así que la carga best-effort por tabla no lo captura.
- La primera medición de Oracle `arraysize` (40,8 s, −37 %) resultó la más favorable de 3. La cifra validada es la mediana: −29 %.
- En las variantes con hilos, las fases de lectura y escritura se suman entre hilos y la «preparación» derivada sale negativa: solo es válido el total.

## 6. Veredicto de la validación

| Propuesta | Estimación del prompt/guía | Medido (mediana) | Estado |
|---|---|---|---|
| Q1 `arraysize` en Oracle | — (no contemplada) | −29 % | ✅ APROBADO |
| Q2 `stream_results` | — | tiempo ±5 %, memoria −55 % a −83 % | ✅ APROBADO (memoria) |
| Q3 solape lectura/escritura | — | −16 % a −45 % combinado (PG, MySQL, MariaDB, SQLite); Oracle no suma con `arraysize` | ✅ APROBADO salvo en Oracle ⚠️ |
| Q4 `parallel_pk_ranges=4` por motor | «PK sync parallelization +20-25 %» (otra cosa) | SQL Server −48 %; MySQL/MariaDB peor; SQLite pierde filas | ✅ en SQL Server, ⚠️ PG (no combinar con `stream_results`), ❌ MySQL/MariaDB/SQLite |
| Q5 lote de escritura por motor | «Dynamic chunk sizing +8-18 % en todos» | PG −31 %, SQL Server +57 %, resto neutro | ⚠️ solo por motor |
| CB4 constraints en lote | «−30 % disable/enable» | < 1 s en total | ❌ sin impacto |
| CB7 PK sync en paralelo | «+20-25 %» | 0 s (no se ejecuta, PD-02) | ❌ sin impacto |
