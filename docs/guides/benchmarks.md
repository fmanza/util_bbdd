# Performance y Benchmarks

## 1. Objetivo

Configurar el pool de conexiones y las opciones de bulk insert para obtener el rendimiento óptimo según el motor de base de datos y el volumen de datos.

## 2. Requisitos Previos

- `util_bbdd` instalado con el motor a benchmarkear configurado
- Para benchmarks de bulk insert: `pandas` instalado
- Para benchmarks de concurrencia async: `asyncpg` o driver async del motor objetivo
- Las mediciones de esta página se hicieron con los contenedores del banco (Docker local, ver «Banco de pruebas contra
  motores reales»); cada tabla indica su versión y su sesión

## 3. Pasos

### Tamaño del pool de los managers

El repositorio no tiene un banco de throughput del pool: no hay cifras medidas que recomendar. Qué parámetros acepta
cada motor (`pool_size`, y `max_overflow`/`pool_timeout` solo en MySQL y SQL Server) y qué significa `pool_size` en
cada pool nativo está en la [guía de conexiones](connection_guide.md#7-pools-pool_size-close_timeout-y-el-pool-del-engine).
Mide con tu carga (ver el ejemplo de «Verificación») antes de subir `pool_size` por encima del default (5): cada
conexión del pool es una sesión abierta en el servidor.

### Tuning de carga masiva (bulk)

Punto único de referencia para acelerar inserciones masivas. Las palancas se combinan; empieza por
`chunk_size` y `commit_every_n_chunks`, y recurre a la carga paralela solo si una sola tabla domina
el tiempo total.

| Palanca | Dónde | Efecto | Cuándo usarla |
|---|---|---|---|
| `batch.chunk_size` | `BulkCrud` / `ParallelBulkLoader` | Filas por lote. Por defecto, por motor y operación: 20 000 en INSERT/DELETE de PostgreSQL y DELETE de SQL Server (−10 % a −20 % con 1M filas), 5000 en el resto; con `commit_every_n_chunks`, 5000 | Fijarlo solo si hace falta: bajar a ≤500 si el destino MariaDB tiene `TEXT`/`JSON` (`max_allowed_packet`); lotes de 1000 son más lentos en todos los motores. El `DELETE … IN` de MySQL/MariaDB envía como mucho 5000 filas por sentencia aunque el lote sea mayor |
| `batch.commit_every_n_chunks` | `BulkCrud` / `ParallelBulkLoader` | Commit cada N lotes; acota el undo log | **Crítico** en MariaDB/MySQL con millones de filas (evita degradación exponencial) |
| `execution.update_via_staging` | `BulkCrud` / `ParallelBulkLoader` | UPDATE vía tabla temporal + un `UPDATE` con join por lote en lugar de un UPDATE por fila (MySQL/MariaDB ~12,5×, PostgreSQL 2,35×) | Activo por defecto en MySQL/MariaDB y PostgreSQL; requiere `CREATE TEMPORARY TABLES` o `TEMP` (sin él, vuelve al UPDATE fila a fila con un WARNING) |
| `batch.prefetch_blocks` | `BulkCrud` | Prepara el lote siguiente en un hilo mientras se envía el actual (cola de 2) | SQL Server (INSERT −10,6 %, UPDATE −6,2 %) y, menos, MySQL/MariaDB (−2 % a −6 %); sin efecto en Oracle, PostgreSQL y SQLite. En `ParallelBulkLoader` llega a cada worker y añade un hilo por partición (sin medir en paralelo) |
| `rejects.on_error="isolate"` | `BulkCrud` / `ParallelBulkLoader` | No es una palanca de velocidad: aparta las filas con errores de datos a un CSV en lugar de deshacer la carga. Coste medido (INSERT de 1M filas): sin filas malas, 1,00–1,02× (Oracle: 1,00× y 1,27× en dos repeticiones); con 10 filas malas, 1,13–1,23× (PostgreSQL 1,65×: lotes de 20 000 con COPY, cada fila mala reenvía más; Oracle, con `batcherrors` desde la sesión `2026-10-01s`, 1,04× sin filas malas y 1,08× con 10). Para cargas con muchas filas malas en PostgreSQL, un `chunk_size` menor reduce lo reenviado | Cuando unas pocas filas malas no deben deshacer la carga; con muchas filas malas, `max_rejects` |
| `execution.fast_executemany` | `BulkCrud` / `ParallelBulkLoader` | Activa `fast_executemany` en el dialecto pyodbc (como `create_engine(..., fast_executemany=True)`) | SQL Server + ODBC 17/18: INSERT ~12× más rápido |
| Vía nativa por motor | Automática | COPY / multi-row / fast_executemany (tabla abajo) | Siempre activa con `BulkCrud(insert_resolver=None)` (default) |
| Carga paralela | `ParallelBulkLoader` o `BulkCrud(parallel=ParallelOptions(...))` | Inserta, actualiza o borra particiones disjuntas en paralelo, una `BulkCrud` por hilo; con `mode="auto"` los hilos los decide `ParallelPlanner` con las mediciones de abajo | Tablas muy grandes en SQL Server (≈ 2,7× con 4 hilos), MySQL y MariaDB (≈ 1,7×); no en PostgreSQL con psycopg 3, Oracle ni SQLite (≤ 1,2×). El pool debe tener capacidad ≥ `max_workers` |

Configuración base con `BulkCrud`:

```python
from util_bbdd.bulk import BatchOptions, BulkCrud, ExecutionOptions

bulk = BulkCrud(
    engine=engine,
    # chunk_size: por defecto, el lote por motor y operación
    batch=BatchOptions(commit_every_n_chunks=20),  # commit cada 100K filas (MariaDB)
    execution=ExecutionOptions(fast_executemany=True),  # SQL Server + pyodbc: INSERT ~12× más rápido
)
```

#### Estrategia INSERT por motor (automática)

`BulkCrud` elige la vía nativa más rápida por motor sin configuración (`ExecutionOptions(insert_resolver=None)`, default):

| Motor | Estrategia | Ganancia típica |
|---|---|---|
| PostgreSQL + psycopg3 | `COPY ... FROM STDIN` | La más rápida |
| PostgreSQL + psycopg2 | `execute_values` multi-row | 3–5× sobre `executemany` |
| MySQL / MariaDB + PyMySQL | `executemany` del driver (multi-fila en el cliente) | ~2× sobre la vía multi-fila anterior (medido en MySQL 8.4 y MariaDB 11.4) |
| MySQL / MariaDB + `mariadbconnector` | `executemany` del driver si los tipos del lote son uniformes; si no, multi-fila | 3,7× sobre la vía multi-fila (500K filas, MariaDB 11.4) |
| MySQL / MariaDB + otro driver | INSERT multi-fila sub-loteado | — |
| SQL Server + pyodbc | `fast_executemany=True` (con ODBC Driver 17/18) | ~12× medido en SQL Server 2022 + ODBC Driver 18 |
| SQL Server + pymssql | `executemany` estándar (insertmanyvalues) | — (~2.700 filas/s en INSERT; usa pyodbc para cargas masivas) |
| Oracle, SQLite, HSQLDB | `executemany` estándar | — |

!!! note "MySQL/MariaDB con el conector `mariadb`"
    Con PyMySQL, `BulkCrud` usa el `executemany` del driver (P-02: unas 2 veces más rápido que la vía multi-fila
    anterior). Con el conector `mariadb` (`mariadbconnector`), el envío masivo del driver exige un tipo Python
    compatible en cada columna para todas las filas (falla con `bytes` y `str`, `int` y `float` o `datetime` y `date`).
    `BulkCrud` lo usa lote a lote solo si cada columna tiene un único tipo (sin contar `None`) y, si no, la vía
    multi-fila (PF-09: 3,7 veces más rápido con tipos uniformes).

!!! note "SQL Server + pyodbc: versiones anteriores a la corrección de P-18"
    Antes de la 0.12.0, `enable_fast_executemany=True` activaba `fast_executemany` solo en el cursor, a espaldas de
    SQLAlchemy: el INSERT no se aceleraba y `bulk_update_from_df` fallaba con columnas `DATETIME`. En esas versiones,
    crea el engine con `create_engine(..., fast_executemany=True)`.

#### Carga paralela por particiones

Cuando una sola tabla domina el tiempo, `ParallelBulkLoader` inserta particiones **disjuntas** en
paralelo (una `BulkCrud` por hilo). El pool del engine debe tener capacidad ≥ `parallel.max_workers`:

```python
from util_bbdd.bulk import BatchOptions, ParallelBulkLoader, ParallelOptions

loader = ParallelBulkLoader(
    engine,
    batch=BatchOptions(chunk_size=5_000, commit_every_n_chunks=20),
    parallel=ParallelOptions(max_workers=4),  # o mode="auto": los hilos según las mediciones de abajo
)
result = loader.load("ventas", partition_readers)   # un callable por partición disjunta
print(result.total_rows, result.partition_errors)
```

Escalado de `load()` con 4 particiones, 1 hilo frente a 4 (tabla de 10 columnas, servidores en Docker local; v0.26.0,
lote por motor; mediana de 2–3 repeticiones; `.ai/sessions/2026-10-01q-docs-parallel-pg/`):

| Motor (driver) | 200K: 1 hilo | 200K: 4 hilos | Aceleración | 1M: 1 hilo | 1M: 4 hilos | Aceleración |
|---|---|---|---|---|---|---|
| PostgreSQL 17 (psycopg 3) | 0,77 s | 0,66 s | 1,18× | 3,42 s | 3,26 s | 1,05× |
| MySQL 8.4 (PyMySQL) | 3,39 s | 1,86 s | 1,82× | 15,74 s | 9,14 s | 1,72× |
| MariaDB 11.4 (PyMySQL) | 3,01 s | 1,83 s | 1,64× | 14,98 s | 9,13 s | 1,64× |
| SQL Server 2022 (pyodbc) | 3,12 s | 1,14 s | 2,76× | 14,64 s | 5,38 s | 2,72× |
| Oracle 23 Free (oracledb) | 1,88 s | 1,62 s | 1,16× | 10,46 s | 9,18 s | 1,14× |
| SQLite | 1,43 s | 1,65 s | 0,87× | 6,93 s | 7,08 s | 0,98× |

- **PostgreSQL con psycopg 3 no gana con hilos**: el cuello de botella es el cliente (psycopg2 y PyMySQL sí escalan por la
  misma red; en el UPDATE fila a fila, 4 hilos fueron 2,2× más lentos que 1). Mecanismo probable, sin confirmar:
  contención del GIL en el bucle de E/S de psycopg 3 (spikes S-1 y S-3 de `.ai/sessions/2026-10-01l-plan-bulk-pending/`). Usa `ParallelOptions(max_workers=1)` o `bulk_insert_from_df`; con `mode="auto"`, el INSERT de PostgreSQL va en serie. Con procesos la fase de
  inserción sí escala (1M: 1,25 s con 4 procesos), pero a 1M filas el arranque de cada proceso (1,3–1,8 s en Windows) se
  come la ganancia; `ParallelBulkLoader` no usa procesos.
- **Oracle** apenas gana (≈ 1,15×); la causa no se ha medido.
- Hasta v0.25.x esta tabla (medida el 2026-09-24, antes del INSERT por tuplas y los lotes por motor) daba 2,6× en
  PostgreSQL: lo que escalaba era un envío más lento con un hilo (2,65 s con 200K frente a 0,77 s hoy).

SQLite admite un solo escritor a la vez: en paralelo no gana nada. Desde v3.0.0 `ParallelBulkLoader` usa un solo hilo con SQLite (con un WARNING si se pidieron más); hasta v2.x varios hilos daban `database is locked`.
El coste de arranque de cada partición (su `BulkCrud` y la lectura de la estructura de la tabla) es de 1 a 66 ms
según el motor, menos del 2% de la carga medida.

#### UPDATE y DELETE en paralelo (1M filas)

`ParallelBulkLoader.update()` y `.delete()` siguen el mismo modelo que `load()`: un lector por partición (disjuntas por
PK) y una `BulkCrud` por hilo. Media de 2 repeticiones con 1M filas, tabla de 10 columnas y lotes de 5000 (servidores en
Docker local, 2026-10-01):

| Motor | Operación | 1 hilo | 2 hilos | 4 hilos | Mejor |
|---|---|---|---|---|---|
| PostgreSQL 17 | INSERT | 4,3 s | 3,7 s | 3,8 s | 1,2× |
| PostgreSQL 17 | UPDATE | 10,8 s | 7,0 s | 6,9 s | 1,6× |
| PostgreSQL 17 | DELETE | 1,8 s | 1,0 s | 0,9 s | 2,0× |
| MySQL 8.4 | INSERT | 17,5 s | 10,6 s | 9,7 s | 1,8× |
| MySQL 8.4 | UPDATE | 24,1 s | 16,1 s | 12,9 s | 1,9× |
| MySQL 8.4 | DELETE | 7,2 s | 4,3 s | 4,3 s | 1,7× |
| MariaDB 11.4 | INSERT | 16,4 s | 10,1 s | 9,6 s | 1,7× |
| MariaDB 11.4 | UPDATE | 22,2 s | 14,0 s | 12,6 s | 1,8× |
| MariaDB 11.4 | DELETE | 6,9 s | 4,5 s | 4,6 s | 1,5× |
| SQL Server 2022 (pyodbc) | INSERT | 15,4 s | 8,1 s | 5,9 s | 2,6× |
| SQL Server 2022 (pyodbc) | UPDATE | 22,8 s | 11,5 s | 8,2 s | 2,8× |
| SQL Server 2022 (pyodbc) | DELETE | 3,0 s | 1,8 s | 1,2 s | 2,5× |
| Oracle 23 Free | INSERT / UPDATE / DELETE | 10,3 / 16,2 / 18,1 s | 11,6 / 15,3 / 15,8 s | 11,1 / 17,4 / 19,5 s | ~1× |

- MySQL, MariaDB y PostgreSQL se saturan en 2 hilos; SQL Server, en 4. Oracle 23 Free usa como máximo 2 hilos de CPU:
  no sirve para juzgar el paralelismo en Oracle.
- PostgreSQL sin privilegio `TEMP`: el UPDATE paralelo iría fila a fila y **empeora** con cada hilo (1M: 25,7 s con 1,
  56,8 s con 4), así que `update()` usa un solo hilo y avisa.
- En `dump`, `parallel_pk_ranges` en MySQL/MariaDB casi duplicó el tiempo (cada hilo lee además del origen); aquí los
  datos ya están en memoria.
- InnoDB puede dar deadlock (1213) entre particiones contiguas aunque sean disjuntas (medido: DELETE de 1M con 2 hilos).
  UPDATE y DELETE por PK son idempotentes, así que `update()` y `delete()` reintentan los errores transitorios al menos 2
  veces aunque `parallel.retry.max_retries` sea 0.

#### Hilos automáticos (`mode="auto"`, v3.0.0)

`ParallelPlanner` decide los hilos con las tablas anteriores (ver [API](../api/bulk_parallel.md#planificador-parallelplanner-v300)).
Validación de `BulkCrud(parallel=ParallelOptions(...))` en el banco (v3.0.0, sesión `2026-10-16f`; mediana de 2
repeticiones; tabla de 10 columnas de `scripts/bench_bulk.py`; SQL Server con pyodbc + ODBC Driver 18):

| Motor | INSERT 50K: 1 → 4 hilos | INSERT 200K: 1 → 4 hilos | `"auto"` con 1M: INSERT / UPDATE / DELETE |
|---|---|---|---|
| PostgreSQL 17 | 0,22 → 0,21 s (1,08×) | 0,80 → 0,69 s (1,16×) | en serie / 1,59× (4) / 1,63× (4) |
| MySQL 8.4 | 1,11 → 0,61 s (1,82×) | 3,47 → 2,05 s (1,69×) | 1,77× (4) / 1,86× (4) / 1,95× (2) |
| MariaDB 11.4 | 0,95 → 0,56 s (1,68×) | 3,90 → 1,94 s (2,01×) | 1,64× (4) / 1,78× (4) / 1,55× (2) |
| SQL Server 2022 | 1,02 → 0,40 s (2,57×) | 2,93 → 1,21 s (2,42×) | 2,58× (4) / 2,82× (4) / 1,91× (4) |
| Oracle 23 Free | 1,47 → 1,06 s (1,39×) | 6,24 → 3,29 s (1,89×) | en serie / en serie / en serie |

- Desde 50K filas el INSERT ya gana en MySQL, MariaDB y SQL Server: es el umbral de `"auto"` (antes de esta medición, 200K).
- Oracle con 1M (1, 2 y 4 hilos): INSERT 13,4 / 10,1 / 10,1 s (1,33×), UPDATE 15,5 / 15,3 / 14,8 s, DELETE 16,3 / 15,5 /
  20,8 s. El INSERT en serie tardó 27,3 s en otra tanda del mismo día: con Oracle 23 Free (2 hilos de CPU como máximo)
  las mediciones no son estables, y `"auto"` lo deja en serie.

#### Checkpoints, reanudación y reintentos

Con `commit_every_n_chunks` los lotes se confirman en orden: tras un fallo, `BulkCrud.last_operation_rows_committed` dice
cuántas filas de la entrada quedaron confirmadas, y basta con reanudar desde ahí. En `ParallelBulkLoader`, cadencia y
`parallel.retry.max_retries` se combinan: el reintento de una partición salta sus filas ya confirmadas (el lector debe devolver las
filas en el mismo orden en cada llamada).

```python
from util_bbdd.bulk.options import BatchOptions
crud = BulkCrud(engine, batch=BatchOptions(commit_every_n_chunks=20))          # commit cada 100K filas
try:
    crud.bulk_insert_from_df(df, "ventas", generar_sql=False)
except SQLAlchemyError as exc:
    print(exc.__notes__)                                   # lote y filas donde falló
    hechas = crud.last_operation_rows_committed
    # ...corregir la causa y reanudar sin duplicar:
    crud.bulk_insert_from_df(df.iloc[hechas:], "ventas", generar_sql=False)
```

Medido con 1M filas y un fallo al 60 %: reanudar cuesta 0,94–1,07× la carga limpia; repetir la carga atómica, 1,6×.
El precio del checkpoint es la cadencia:

| INSERT 1M | atómico | commit cada 20 lotes | cada 5 lotes | rollback de 1M (atómico) |
|---|---|---|---|---|
| SQLite | 6,9 s | +14 % | +31 % | 0,06 s |
| PostgreSQL | 5,4 s | ±5 % | ±5 % | 0,001 s |
| MySQL | 17,4 s | ±5 % | +7 % | 2,35 s |
| MariaDB | 16,3 s | +12 % | +22 % | 2,41 s |
| SQL Server | 14,3 s | ±5 % | +3 % | 1,58 s |
| Oracle | 10,0 s | ±5 % | +4 % | 0,48 s |

100K filas por commit (20 lotes de 5000) es un buen punto de partida para cargas reanudables; en SQLite cada commit es un
`fsync`, así que conviene cadencias largas. El rollback se midió con el buffer pool caliente: bajo presión, MySQL advierte
que deshacer una transacción grande puede tardar varias veces lo que la operación original.

Reintentos de `ParallelBulkLoader`: solo errores transitorios, decididos por el código del error (desconexiones,
deadlocks, lock wait timeout, serialización, timeouts), con espera exponencial y jitter (`parallel.retry.backoff`, por defecto
`(0.5, 30.0)`). Los errores de datos, integridad, sintaxis o permisos no se reintentan.

Detalle y políticas de particionado: [Carga Masiva Paralela (funcional)](../functional/bulk_parallel_loading.md),
[API ParallelBulkLoader](../api/bulk_parallel.md) y el ejemplo [Carga Masiva Paralela](../examples/parallel_bulk_insert.md).
Para medir el impacto de la cadencia de commit, ver el ejemplo [Commit Cadence](../examples/benchmark_commit_cadence.md).

### Banco de pruebas contra motores reales

`scripts/bench_bulk.py` mide `bulk_insert_from_df`, `bulk_update_from_df` y `bulk_delete_from_df` (con
`generar_sql=False`) por motor × variante × tamaño × repetición. Después de cada operación comprueba el resultado con
SQL (número de filas y suma de una columna), así que una variante más rápida pero incorrecta aparece como error.
Una operación que falla se registra y el banco continúa.

**Apunta siempre a una base de datos de pruebas.** El banco solo crea y elimina tablas `zz_util_bbdd_*`, pero lo hace
en la base de la URL.

Los servidores de `docker-compose.bench.yml` son independientes de cualquier otro de la máquina.
`docker-compose.yml` lo incluye con el mismo proyecto, así que desde la raíz del repositorio basta con
`docker compose up -d --wait postgres` (o sin nombre de servicio, para los 5 motores).

- **Proyecto propio**: `util_bbdd_bench`. Un PostgreSQL de desarrollo que ya tengas en el 5432 (p.ej. el `postgres_db`
  que definía el antiguo `docker-compose.yml`, en el proyecto `util_bbdd`) queda fuera: compose no lo ve ni lo toca.
- **Contenedores y datos propios**: volúmenes anónimos, que se borran con `down -v`.
- **Puertos no estándar**: solo accesibles desde esta máquina (`127.0.0.1`).

| Motor | Contenedor | Puerto (variable para cambiarlo) | Base de datos |
|---|---|---|---|
| PostgreSQL 17 | `util_bbdd_bench_postgres` | 55432 (`UTIL_BBDD_BENCH_POSTGRES_PORT`) | `bench` |
| MySQL 8.4 | `util_bbdd_bench_mysql` | 53306 (`UTIL_BBDD_BENCH_MYSQL_PORT`) | `bench` |
| MariaDB 11.4 | `util_bbdd_bench_mariadb` | 53307 (`UTIL_BBDD_BENCH_MARIADB_PORT`) | `bench`; además, `bench` puede crear y borrar bases `zz_util_bbdd_*` (lo necesita `test_update_auto_increment_mariadb.py`) |
| SQL Server 2022 | `util_bbdd_bench_mssql` | 51433 (`UTIL_BBDD_BENCH_MSSQL_PORT`) | `bench` (la crea el healthcheck) |
| Oracle 23 Free | `util_bbdd_bench_oracle` | 51521 (`UTIL_BBDD_BENCH_ORACLE_PORT`) | PDB `FREEPDB1`, usuario `bench` |

`scripts/bench_bulk.py` avisa en el log si la URL de un motor usa su puerto estándar (5432, 3306, 1433, 1521), porque
entonces suele apuntar a otro servidor.

1. Levanta los motores que necesites. `docker-compose.bench.yml` no guarda ninguna contraseña: la lee de
   `UTIL_BBDD_BENCH_PASSWORD`.

    ```bash
    export UTIL_BBDD_BENCH_PASSWORD=...          # PowerShell: $env:UTIL_BBDD_BENCH_PASSWORD="..."
    docker compose -f docker-compose.bench.yml up -d --wait postgres mysql mariadb mssql oracle
    ```

2. Define una URL por motor en `UTIL_BBDD_BENCH_<MOTOR>_URL`. Si no existe, se usa `UTIL_BBDD_TEST_<MOTOR>_URL`,
   la misma de los tests de integración. SQLite no necesita URL. Las plantillas del repositorio definen las dos series
   para los contenedores anteriores (y respetan los puertos cambiados), sin guardar la contraseña:

    ```bash
    source scripts/bench_env.example.sh          # PowerShell: . scripts\bench_env.example.ps1
    ```

    | Motor | Variable | URL |
    |---|---|---|
    | PostgreSQL | `UTIL_BBDD_BENCH_POSTGRESQL_URL` | `postgresql+psycopg://bench:<clave>@127.0.0.1:55432/bench` |
    | MySQL | `UTIL_BBDD_BENCH_MYSQL_URL` | `mysql+pymysql://bench:<clave>@127.0.0.1:53306/bench` |
    | MariaDB | `UTIL_BBDD_BENCH_MARIADB_URL` | `mariadb+pymysql://bench:<clave>@127.0.0.1:53307/bench` |
    | SQL Server | `UTIL_BBDD_BENCH_MSSQL_URL` | `mssql+pymssql://sa:<clave>@127.0.0.1:51433/bench` |
    | Oracle | `UTIL_BBDD_BENCH_ORACLE_URL` | `oracle+oracledb://bench:<clave>@127.0.0.1:51521/?service_name=FREEPDB1` |

    Usa `127.0.0.1` y no `localhost`: los puertos solo escuchan en IPv4 y en Windows `localhost` puede resolverse
    primero a `::1`. Para SQL Server con pyodbc (necesario para `fast_executemany`, con el **ODBC Driver 17 o 18 de
    Microsoft**; con el driver antiguo `SQL Server` de Windows no hay aceleración):
    `mssql+pyodbc://sa:<clave>@127.0.0.1:51433/bench?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes`.

3. Ejecuta el banco:

    ```bash
    python scripts/bench_bulk.py                                             # motores con URL, 1K–1M, 3 repeticiones
    python scripts/bench_bulk.py --engines postgresql,mysql --sizes 1000,100000 --repeat 1
    python scripts/bench_bulk.py --ops insert --memory                       # pico de memoria (tracemalloc, más lento)
    python scripts/bench_bulk.py --list-variants
    ```

Cada ejecución escribe en `bench_results/<fecha>/` (ignorado por git):

| Fichero | Contenido |
|---|---|
| `summary.md` | Mediana por motor × operación × filas × variante, filas/s y aceleración frente a `baseline` |
| `results.csv` | Una fila por medición, con el error si la operación falló |
| `environment.json` | Versiones de Python, pandas, SQLAlchemy, driver y servidor; URLs sin contraseña |
| `audit.csv` | CSV de la auditoría integrada de `BulkCrud` |

Variantes A/B disponibles (cada una se aplica solo a los motores indicados):

| Variante | Motores | Qué cambia |
|---|---|---|
| `baseline` | todos | `BulkCrud` por defecto |
| `mysql-multirow-legacy` | MySQL, MariaDB | `insert_resolver` con la vía multi-fila anterior a P-02 (control) |
| `mysql-update-executemany-legacy` | MySQL, MariaDB | `BulkCrud(update_via_staging=False)`: UPDATE fila a fila anterior a P-04 (control) |
| `p01-mssql-engine-fast-executemany` | SQL Server + pyodbc | `create_engine(..., fast_executemany=True)` |

La reflexión de la tabla queda fuera de la medición. Los nombres de tabla y columnas siguen la convención de
`BulkCrud` para cada motor: mayúsculas en SQL Server y minúsculas en el resto.

### Banco de comparación de esquemas

`scripts/bench_compare.py` mide `SchemaComparator.compare()` entre dos esquemas del mismo servidor (`cmp_src` y
`cmp_tgt`), con todas las opciones, sin y con `include_routines`. Para cada motor da el mejor tiempo de `--repeat`
ejecuciones, el número de sentencias que llegan al driver y el número de diferencias encontradas: una optimización que
cambie el resultado se ve en la misma tabla. Usa los contenedores de arriba y `UTIL_BBDD_BENCH_PASSWORD`, sin URLs.

**`setup` y `teardown` borran `cmp_src`/`cmp_tgt` con todo su contenido** (esquemas en PostgreSQL y SQL Server, bases en
MySQL/MariaDB, usuarios en Oracle).

```bash
python scripts/bench_compare.py setup --tables 200                     # los 5 motores; --engines para elegir
python scripts/bench_compare.py run --repeat 3 --out bench_results/compare
python scripts/bench_compare.py run --engines mssql --mssql-driver pyodbc
python scripts/bench_compare.py teardown
```

Con 200 tablas, 20 vistas y 20 funciones por esquema, el resultado esperado es 20 tablas con diferencias (columna
`extra` en el 10 %), 20 vistas y, con routines, las funciones cambiadas. Referencia (auditoría de `comparar`,
2026-10-02, con routines):

| Motor | Antes | Después | Sentencias |
|---|---|---|---|
| PostgreSQL 17 | 4,23 s | 0,18 s | 2.450 → 62 |
| Oracle 23 Free | 5,18 s | 0,26 s | 2.086 → 58 |
| SQL Server 2022 (pymssql) | 12,23 s | 0,88 s | 2.852 → 456 |
| MariaDB 11.4 | 1,24 s | 0,35 s | 488 |
| MySQL 8.4 | 1,37 s | 0,43 s | 488 |

### Banco de extracción de metadatos

`scripts/bench_metadata.py` mide cuánto le cuesta a cada flujo leer el catálogo (managers, `doc`, `comparar`,
`migrate`, `dump`, `bulk`) con schemas de 50, 500 y 5000 tablas. Cuenta las sentencias de catálogo en los dos caminos
de ejecución de la librería (el driver nativo de los managers y SQLAlchemy) y guarda, por medición, tiempos, memoria y
las consultas más frecuentes y más lentas. Usa los contenedores de arriba y `UTIL_BBDD_BENCH_PASSWORD`, sin URLs.

**`setup` y `teardown` crean y borran `zz_md_<N>` (PostgreSQL), las bases `zz_util_bbdd_md_<N>` (MySQL, MariaDB, SQL
Server) y los usuarios `ZZ_MD_<N>` (Oracle).**

```bash
python scripts/bench_metadata.py setup --engines all --volumes 50,500
python scripts/bench_metadata.py run --engines postgresql,sqlserver --volumes 50,500 --repeat 3
python scripts/bench_metadata.py run --engines oracle --volumes 5000 --flows manager_scan --limit 20 --repeat 1
python scripts/bench_metadata.py report        # tablas Markdown desde bench_results/metadata/*.json
python scripts/bench_metadata.py teardown --engines all --volumes 50,500
```

Referencia (baseline de v0.30.0, 2026-10-03, 500 tablas, tiempo de catálogo): leer columnas, índices, PK, FK y UK
tabla a tabla con los managers cuesta 70 s en PostgreSQL 17, 121 s en SQL Server 2022 y 365 s en Oracle 23 Free; la
lectura por schema de `migrate` (9 consultas, incluye vistas y routines), 0,16 s, 0,22 s y 0,27 s. Detalle y causas en
la sesión `2026-10-03-metadata-centralization` (ADR-003).

## 4. Verificación

```bash
# Ejecutar benchmark de commit cadence incluido en docs/examples/
python docs/examples/benchmark_commit_cadence.py --size small
```

Output esperado (SQLite in-memory):

```
Test 1: SIN cadencia — X.XXs
Test 2: CON cadencia — X.XXs
Speedup: ~1.07×
```

Con servidores reales la cadencia no acelera la carga a 1M filas (MariaDB +12 % con commit cada 20 lotes, ver
«Checkpoints, reanudación y reintentos»): lo que aporta es acotar el undo log y poder reanudar tras un fallo.

Para el pool (100 consultas concurrentes con `pool_size` de 5 y 20; `pool_size` va en `conn_params`):

```python
import asyncio
import time

from util_bbdd import AsyncDatabaseManager

conn_params = {"host": "127.0.0.1", "port": 5432, "user": "usr", "password": "pwd", "database": "mydb"}


async def benchmark_pool(pool_size: int) -> None:
    async with AsyncDatabaseManager("postgresql", {**conn_params, "pool_size": pool_size}) as mgr:
        t0 = time.perf_counter()
        await asyncio.gather(*(mgr.execute_custom_one("SELECT 1") for _ in range(100)))
        elapsed = time.perf_counter() - t0
        print(f"pool_size={pool_size}: 100 consultas en {elapsed:.2f} s ({100 / elapsed:.0f} consultas/s)")


for size in (5, 20):
    asyncio.run(benchmark_pool(size))
```

Para el banco de pruebas de bulk, una ejecución corta solo con SQLite (no necesita servidor):

```bash
python scripts/bench_bulk.py --engines sqlite --sizes 1000 --repeat 1
```

La columna `OK/Error` del resumen debe mostrar `1/0` en `insert`, `update` y `delete`. Los tests de integración de
`BulkCrud` usan las mismas variables `UTIL_BBDD_TEST_<MOTOR>_URL` y se saltan los motores sin URL:

```bash
python -m pytest tests/integration/test_bulk_engines.py
```

**MariaDB con sus dos drivers.** La librería usa el conector original de MariaDB (MariaDB Connector/Python,
`mariadb+mariadbconnector`) para `db_type="mariadb"`, y el banco define la URL de MariaDB con PyMySQL. Si el paquete
`mariadb` está instalado, la integración ejecuta los tests de MariaDB con **los dos**: el motor `mariadb_connector` de
`test_bulk_engines.py` y `test_bulk_audit_20261001.py` reutiliza `UTIL_BBDD_TEST_MARIADB_URL` cambiando el driver, y
`test_mariadb_engine_e2e.py` (managers sync con el conector y async con aiomysql) y
`test_update_auto_increment_mariadb.py` también lo cubren. Sin el paquete, esos casos se saltan con el motivo. No hay
nada que configurar.

`bench_bulk.py` admite el motor `mariadb_connector` con la misma regla (o `UTIL_BBDD_BENCH_MARIADB_CONNECTOR_URL`).
Medido con 1M filas (MariaDB 11.4.13, 3 repeticiones, `chunk_size` automático; sesión `2026-10-01x`):

| Operación | PyMySQL | MariaDB Connector/Python | Diferencia |
|---|---|---|---|
| INSERT | 15,18 s | 7,97 s | 1,9× más rápido |
| UPDATE (staging) | 21,49 s | 12,89 s | 1,67× más rápido |
| DELETE | 6,76 s | 6,85 s | igual |

Para cargas masivas en MariaDB, el conector original es la opción más rápida (y el que usa la librería para
`db_type="mariadb"`).

## 5. Variantes y Solución de Problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| Latencia crece exponencialmente en bulk insert > 1M filas | Undo log de MariaDB/MySQL saturado | Activar `commit_every_n_chunks=20` en `BulkCrud` |
| Error 1419 (`You do not have the SUPER privilege and binary logging is enabled`) al crear funciones en el MySQL del banco | Contenedor creado antes de 0.23.1, sin `--log-bin-trust-function-creators=1` (el usuario `bench` no tiene `SUPER`) | `docker compose -f docker-compose.bench.yml up -d --wait mysql` lo recrea con la opción y conserva sus datos (sin `-V`) |
| `fast_executemany` no acelera en SQL Server | pyodbc < 4.0.28 o columnas `NVARCHAR(MAX)` | Actualizar pyodbc o desactivar con `ExecutionOptions(fast_executemany=False)` |
| Pool agotado bajo carga concurrente | `pool_size` insuficiente | Aumentar `pool_size` en `conn_params` y medirlo con el ejemplo de «Verificación» (ver «Tamaño del pool de los managers») |
| PostgreSQL: `COPY` más lento que esperado | psycopg3 no instalado (usa psycopg2) | `pip install psycopg[binary]` para instalar psycopg3 |
| `bench_bulk.py` salta un motor con `SKIP ... sin URL` | Falta `UTIL_BBDD_BENCH_<MOTOR>_URL` (y `UTIL_BBDD_TEST_<MOTOR>_URL`) | Definir la URL del servidor de pruebas |
| `bench_bulk.py` informa `no se pudo preparar el motor` | Driver no instalado, servidor caído o sin permiso de CREATE/DROP TABLE | Revisar `environment.json`; el resto de motores se mide igualmente |
| `bulk_update_from_df` falla en SQL Server + pyodbc con `HY104 Invalid precision value` | Versión anterior a la corrección de P-18: tabla con columna `DATETIME` y `fast_executemany` activado a espaldas de SQLAlchemy | Actualizar; en versiones anteriores, crear el engine con `create_engine(..., fast_executemany=True)` o usar `BulkCrud(..., enable_fast_executemany=False)` |
| WARNING `update_via_staging: el servidor deniega TEMP` y UPDATE lento en PostgreSQL | El usuario no tiene el privilegio `TEMP` sobre la base de datos; `BulkCrud` ha vuelto al UPDATE fila a fila | `GRANT TEMP ON DATABASE <bd> TO <usuario>` para recuperar el UPDATE rápido, o `BulkCrud(..., update_via_staging=False)` para no intentarlo |
| WARNING `update_via_staging: el servidor deniega CREATE TEMPORARY TABLES` y UPDATE lento en MySQL/MariaDB | El usuario no tiene el privilegio `CREATE TEMPORARY TABLES`; `BulkCrud` ha vuelto al UPDATE fila a fila | `GRANT CREATE TEMPORARY TABLES ON <bd>.* TO <usuario>` para recuperar el UPDATE rápido (~12,5×), o `BulkCrud(..., update_via_staging=False)` para no intentarlo |
| INSERT/UPDATE masivos lentos en SQL Server con `mssql+pymssql` (INFO en el log al crear `BulkCrud`) | pymssql no tiene una vía masiva equivalente: ~2.700 filas/s en INSERT y ~1.800 en UPDATE | Usar `mssql+pyodbc` con ODBC Driver 17/18 (~49.000 y ~33.500 filas/s). No usar `bulk_copy` de pymssql: no aplica CHECK ni claves foráneas y las marca como no confiables |
| DELETE lento en SQL Server con lotes pequeños (1K–10K filas en décimas de segundo) | Versión anterior a B-02: `DELETE … IN` con hasta 2000 parámetros, cuyo plan compila SQL Server por cada forma de sentencia. Desde B-02 el lote viaja en un parámetro JSON (`OPENJSON`): 10K filas 0,81 → 0,04 s | Actualizar. Requiere nivel de compatibilidad ≥ 130 (SQL Server 2016); con uno menor se usa la vía anterior (INFO en el log). También se usa la vía anterior si alguna clave no cabe exactamente en el tipo de la PK (cadena más larga, no ASCII en `VARCHAR`, decimales de más, entero fuera de rango): en la 0.24.0 esas claves borraban otras filas |
| DELETE falla en SQL Server con `07002 COUNT field incorrect` o error de sintaxis | Versión anterior a la corrección de P-05: más de 2100 parámetros por lote (pyodbc) o PK compuesta | Actualizar; en versiones anteriores, `BulkCrud(..., chunk_size=2000)` evita el límite de parámetros con PK simple |
| INSERT o DELETE falla en MariaDB/MySQL con `Prepared statement contains too many placeholders` | Versión anterior a la corrección de P-13: conector `mariadb` y más de 65.535 parámetros por sentencia (INSERT con 66 columnas o más, o DELETE con lotes grandes) | Actualizar; en versiones anteriores, usar `mariadb+pymysql` o reducir `chunk_size` |
| Tabla vacía o incompleta en PostgreSQL tras una carga con `commit_every_n_chunks`, sin ningún error | Versión anterior a la corrección de P-27: el INSERT por el cursor del driver no iniciaba la transacción y el commit no hacía nada | Actualizar y repetir la carga; en versiones anteriores, no usar `commit_every_n_chunks` con PostgreSQL |
