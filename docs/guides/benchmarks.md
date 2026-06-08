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
| `enable_fast_executemany` | `BulkCrud` / `ParallelBulkLoader` | Activa `fast_executemany` de pyodbc | SQL Server: 5–15× más rápido |
| Vía nativa por motor | Automática | COPY / multi-row / fast_executemany (tabla abajo) | Siempre activa con `BulkCrud(insert_resolver=None)` (default) |
| Carga paralela | `ParallelBulkLoader` | Inserta particiones disjuntas en paralelo, una `BulkCrud` por hilo | Tablas muy grandes; el pool debe tener capacidad ≥ `max_workers` |

Configuración base con `BulkCrud`:

```python
from util_bbdd.bulk import BulkCrud

bulk = BulkCrud(
    engine=engine,
    chunk_size=5_000,              # filas por lote
    commit_every_n_chunks=20,      # commit cada 100K filas (MariaDB)
    enable_fast_executemany=True,  # SQL Server: 5–15× más rápido
)
```

#### Estrategia INSERT por motor (automática)

`BulkCrud` elige la vía nativa más rápida por motor sin configuración (`insert_resolver=None`, default):

| Motor | Estrategia | Ganancia típica |
|---|---|---|
| PostgreSQL + psycopg3 | `COPY ... FROM STDIN` | La más rápida |
| PostgreSQL + psycopg2 | `execute_values` multi-row | 3–5× sobre `executemany` |
| MySQL / MariaDB | INSERT multi-row sub-loteado | 2–4× sobre `executemany` |
| SQL Server + pyodbc | `fast_executemany=True` | 5–15× sobre `executemany` |
| Oracle, SQLite, HSQLDB | `executemany` estándar | — |

#### Carga paralela por particiones

Cuando una sola tabla domina el tiempo, `ParallelBulkLoader` inserta particiones **disjuntas** en
paralelo (una `BulkCrud` por hilo). El pool del engine debe tener capacidad ≥ `max_workers`:

```python
from util_bbdd.bulk import ParallelBulkLoader

loader = ParallelBulkLoader(engine, max_workers=4, chunk_size=5_000, commit_every_n_chunks=20)
result = loader.load("ventas", partition_readers)   # un callable por partición disjunta
print(result.total_rows, result.partition_errors)
```

Detalle y políticas de particionado: [Carga Masiva Paralela (funcional)](../functional/bulk-parallel-loading.md),
[API ParallelBulkLoader](../api/bulk-parallel.md) y el ejemplo [Carga Masiva Paralela](../examples/parallel_bulk_insert.md).
Para medir el impacto de la cadencia de commit, ver el ejemplo [Commit Cadence](../examples/benchmark_commit_cadence.md).

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

## 5. Variantes y Solución de Problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| Latencia crece exponencialmente en bulk insert > 1M filas | Undo log de MariaDB/MySQL saturado | Activar `commit_every_n_chunks=20` en `BulkCrud` |
| `fast_executemany` no acelera en SQL Server | pyodbc < 4.0.28 o columnas `NVARCHAR(MAX)` | Actualizar pyodbc o desactivar con `enable_fast_executemany=False` |
| Pool agotado bajo carga concurrente | `pool_size` insuficiente | Aumentar `pool_size` siguiendo la tabla de recomendaciones arriba |
| PostgreSQL: `COPY` más lento que esperado | psycopg3 no instalado (usa psycopg2) | `pip install psycopg[binary]` para instalar psycopg3 |
