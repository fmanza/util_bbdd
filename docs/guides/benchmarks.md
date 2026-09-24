# Performance y Benchmarks

## 1. Objetivo

Configurar el pool de conexiones y las opciones de bulk insert para obtener el rendimiento óptimo según el motor de base de datos y el volumen de datos.

## 2. Requisitos Previos

- `util_bbdd` instalado con el motor a benchmarkear configurado
- Para benchmarks de bulk insert: `pandas` instalado
- Para benchmarks de concurrencia async: `asyncpg` o driver async del motor objetivo
- Entorno de prueba: los valores de referencia se midieron en AWS t3.large (2 vCPU, 8GB RAM) con PostgreSQL 15 y Python 3.12

## 3. Pasos

### Configuración de pool recomendada por throughput

| pool_size | max_overflow | Throughput (req/s) | CPU Usage | Cuándo usarlo |
|---|---|---|---|---|
| 5 | 0 | ~22 | 15% | Desarrollo local |
| 10 | 5 | ~43 | 28% | API pequeña |
| **20** | **10** | **~87** | **52%** | **Producción estándar (recomendado)** |
| 40 | 20 | ~109 | 78% | API de alto tráfico |

**Sweet spot**: `pool_size=20, max_overflow=10` da el mejor ratio throughput/CPU.

### Tuning de carga masiva (bulk)

Punto único de referencia para acelerar inserciones masivas. Las palancas se combinan; empieza por
`chunk_size` y `commit_every_n_chunks`, y recurre a la carga paralela solo si una sola tabla domina
el tiempo total.

| Palanca | Dónde | Efecto | Cuándo usarla |
|---|---|---|---|
| `chunk_size` | `BulkCrud` / `ParallelBulkLoader` | Filas por lote (default 5000) | Bajar a ≤500 si el destino MariaDB tiene `TEXT`/`JSON` (`max_allowed_packet`) |
| `commit_every_n_chunks` | `BulkCrud` / `ParallelBulkLoader` | Commit cada N lotes; acota el undo log | **Crítico** en MariaDB/MySQL con millones de filas (evita degradación exponencial) |
| `update_via_staging` | `BulkCrud` | UPDATE vía tabla temporal + un `UPDATE ... JOIN` por lote en lugar de un UPDATE por fila (~12,5×) | Activo por defecto en MySQL/MariaDB; requiere `CREATE TEMPORARY TABLES` (sin él, vuelve al UPDATE fila a fila con un WARNING) |
| `enable_fast_executemany` | `BulkCrud` / `ParallelBulkLoader` | Activa `fast_executemany` en el dialecto pyodbc (como `create_engine(..., fast_executemany=True)`) | SQL Server + ODBC 17/18: INSERT ~12× más rápido |
| Vía nativa por motor | Automática | COPY / multi-row / fast_executemany (tabla abajo) | Siempre activa con `BulkCrud(insert_resolver=None)` (default) |
| Carga paralela | `ParallelBulkLoader` | Inserta particiones disjuntas en paralelo, una `BulkCrud` por hilo | Tablas muy grandes; el pool debe tener capacidad ≥ `max_workers` |

Configuración base con `BulkCrud`:

```python
from util_bbdd.bulk import BulkCrud

bulk = BulkCrud(
    engine=engine,
    chunk_size=5_000,              # filas por lote
    commit_every_n_chunks=20,      # commit cada 100K filas (MariaDB)
    enable_fast_executemany=True,  # SQL Server + pyodbc: INSERT ~12× más rápido
)
```

#### Estrategia INSERT por motor (automática)

`BulkCrud` elige la vía nativa más rápida por motor sin configuración (`insert_resolver=None`, default):

| Motor | Estrategia | Ganancia típica |
|---|---|---|
| PostgreSQL + psycopg3 | `COPY ... FROM STDIN` | La más rápida |
| PostgreSQL + psycopg2 | `execute_values` multi-row | 3–5× sobre `executemany` |
| MySQL / MariaDB + PyMySQL | `executemany` del driver (multi-fila en el cliente) | ~2× sobre la vía multi-fila anterior (medido en MySQL 8.4 y MariaDB 11.4) |
| MySQL / MariaDB + otro driver | INSERT multi-fila sub-loteado | — |
| SQL Server + pyodbc | `fast_executemany=True` (con ODBC Driver 17/18) | ~12× medido en SQL Server 2022 + ODBC Driver 18 |
| SQL Server + pymssql | `executemany` estándar (insertmanyvalues) | — (~2.700 filas/s en INSERT; usa pyodbc para cargas masivas) |
| Oracle, SQLite, HSQLDB | `executemany` estándar | — |

!!! note "MySQL/MariaDB con el conector `mariadb`"
    Con PyMySQL, `BulkCrud` usa el `executemany` del driver (P-02: unas 2 veces más rápido que la vía multi-fila
    anterior). Con el conector `mariadb` (`mariadbconnector`) se mantiene la vía multi-fila: su envío masivo exige el
    mismo tipo Python en cada columna para todas las filas, y un DataFrame puede mezclarlos (p.ej. `bytes` y `str`).

!!! note "SQL Server + pyodbc: versiones anteriores a la corrección de P-18"
    Hasta [Unreleased], `enable_fast_executemany=True` activaba `fast_executemany` solo en el cursor, a espaldas de
    SQLAlchemy: el INSERT no se aceleraba y `bulk_update_from_df` fallaba con columnas `DATETIME`. En esas versiones,
    crea el engine con `create_engine(..., fast_executemany=True)`.

#### Carga paralela por particiones

Cuando una sola tabla domina el tiempo, `ParallelBulkLoader` inserta particiones **disjuntas** en
paralelo (una `BulkCrud` por hilo). El pool del engine debe tener capacidad ≥ `max_workers`:

```python
from util_bbdd.bulk import ParallelBulkLoader

loader = ParallelBulkLoader(engine, max_workers=4, chunk_size=5_000, commit_every_n_chunks=20)
result = loader.load("ventas", partition_readers)   # un callable por partición disjunta
print(result.total_rows, result.partition_errors)
```

Escalado medido con 200K filas en 4 particiones (tabla de 10 columnas, servidores en Docker local):

| Motor | 1 hilo | 4 hilos | Aceleración |
|---|---|---|---|
| PostgreSQL 17 (psycopg 3) | 2,65 s | 1,00 s | 2,6× |
| MySQL 8.4 (PyMySQL) | 3,60 s | 1,91 s | 1,9× |
| MariaDB 11.4 (PyMySQL) | 2,89 s | 1,80 s | 1,6× |
| SQL Server 2022 (pymssql) | 49,08 s | 12,68 s | 3,9× |
| Oracle 23 Free (oracledb) | 3,06 s | 1,68 s | 1,8× |
| SQLite | 1,24 s | 1,34 s | 0,9× |

SQLite admite un solo escritor a la vez: en paralelo no gana nada, así que usa `max_workers=1` o `bulk_insert_from_df`.
El coste de arranque de cada partición (su `BulkCrud` y la lectura de la estructura de la tabla) es de 1 a 66 ms
según el motor, menos del 2% de la carga medida.

Detalle y políticas de particionado: [Carga Masiva Paralela (funcional)](../functional/bulk-parallel-loading.md),
[API ParallelBulkLoader](../api/bulk-parallel.md) y el ejemplo [Carga Masiva Paralela](../examples/parallel_bulk_insert.md).
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
| MariaDB 11.4 | `util_bbdd_bench_mariadb` | 53307 (`UTIL_BBDD_BENCH_MARIADB_PORT`) | `bench` |
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

### Tiempos de referencia por tipo de operación (PostgreSQL 15)

| Operación | Tiempo promedio | Notas |
|---|---|---|
| `SELECT 1` (ping) | 2–3 ms | Validación de pool |
| `SELECT *` (100 filas) | 8–12 ms | Index scan |
| `SELECT *` (10K filas) | 45–80 ms | Full table scan |
| `INSERT` (1000 filas bulk) | 120–150 ms | Via `execute_values` |
| `UPDATE` (1 fila por PK) | 4–7 ms | Index lookup |

## 4. Verificación

```bash
# Ejecutar benchmark de commit cadence incluido en docs/examples/
python docs/examples/benchmark_commit_cadence.py --size small
```

Output esperado (SQLite in-memory):

```
Test 1: SIN cadencia — X.XXs
Test 2: CON cadencia — X.XXs
Speedup: ~1.07× (mínimo en SQLite; en MariaDB real: 3–8×)
```

Para pool:

```python
import asyncio
from util_bbdd import AsyncDatabaseManager

async def benchmark_pool():
    async with AsyncDatabaseManager("postgresql", conn_params, pool_size=20) as mgr:
        import time
        t0 = time.perf_counter()
        import asyncio
        resultados = await asyncio.gather(*[
            mgr.execute_custom_one("SELECT 1") for _ in range(100)
        ])
        elapsed = time.perf_counter() - t0
        print(f"100 queries paralelas: {elapsed:.2f}s ({100/elapsed:.0f} req/s)")

asyncio.run(benchmark_pool())
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

## 5. Variantes y Solución de Problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| Latencia crece exponencialmente en bulk insert > 1M filas | Undo log de MariaDB/MySQL saturado | Activar `commit_every_n_chunks=20` en `BulkCrud` |
| `fast_executemany` no acelera en SQL Server | pyodbc < 4.0.28 o columnas `NVARCHAR(MAX)` | Actualizar pyodbc o desactivar con `enable_fast_executemany=False` |
| Pool agotado bajo carga concurrente | `pool_size` insuficiente | Aumentar `pool_size` siguiendo la tabla de recomendaciones arriba |
| PostgreSQL: `COPY` más lento que esperado | psycopg3 no instalado (usa psycopg2) | `pip install psycopg[binary]` para instalar psycopg3 |
| `bench_bulk.py` salta un motor con `SKIP ... sin URL` | Falta `UTIL_BBDD_BENCH_<MOTOR>_URL` (y `UTIL_BBDD_TEST_<MOTOR>_URL`) | Definir la URL del servidor de pruebas |
| `bench_bulk.py` informa `no se pudo preparar el motor` | Driver no instalado, servidor caído o sin permiso de CREATE/DROP TABLE | Revisar `environment.json`; el resto de motores se mide igualmente |
| `bulk_update_from_df` falla en SQL Server + pyodbc con `HY104 Invalid precision value` | Versión anterior a la corrección de P-18: tabla con columna `DATETIME` y `fast_executemany` activado a espaldas de SQLAlchemy | Actualizar; en versiones anteriores, crear el engine con `create_engine(..., fast_executemany=True)` o usar `BulkCrud(..., enable_fast_executemany=False)` |
| WARNING `update_via_staging: el servidor deniega CREATE TEMPORARY TABLES` y UPDATE lento en MySQL/MariaDB | El usuario no tiene el privilegio `CREATE TEMPORARY TABLES`; `BulkCrud` ha vuelto al UPDATE fila a fila | `GRANT CREATE TEMPORARY TABLES ON <bd>.* TO <usuario>` para recuperar el UPDATE rápido (~12,5×), o `BulkCrud(..., update_via_staging=False)` para no intentarlo |
| INSERT/UPDATE masivos lentos en SQL Server con `mssql+pymssql` (INFO en el log al crear `BulkCrud`) | pymssql no tiene una vía masiva equivalente: ~2.700 filas/s en INSERT y ~1.800 en UPDATE | Usar `mssql+pyodbc` con ODBC Driver 17/18 (~49.000 y ~33.500 filas/s). No usar `bulk_copy` de pymssql: no aplica CHECK ni claves foráneas y las marca como no confiables |
| DELETE falla en SQL Server con `07002 COUNT field incorrect` o error de sintaxis | Versión anterior a la corrección de P-05: más de 2100 parámetros por lote (pyodbc) o PK compuesta | Actualizar; en versiones anteriores, `BulkCrud(..., chunk_size=2000)` evita el límite de parámetros con PK simple |
| INSERT o DELETE falla en MariaDB/MySQL con `Prepared statement contains too many placeholders` | Versión anterior a la corrección de P-13: conector `mariadb` y más de 65.535 parámetros por sentencia (INSERT con 66 columnas o más, o DELETE con lotes grandes) | Actualizar; en versiones anteriores, usar `mariadb+pymysql` o reducir `chunk_size` |
| Tabla vacía o incompleta en PostgreSQL tras una carga con `commit_every_n_chunks`, sin ningún error | Versión anterior a la corrección de P-27: el INSERT por el cursor del driver no iniciaba la transacción y el commit no hacía nada | Actualizar y repetir la carga; en versiones anteriores, no usar `commit_every_n_chunks` con PostgreSQL |
