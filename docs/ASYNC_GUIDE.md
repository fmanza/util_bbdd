# Guía de Programación Asincrónica con util_bbdd

## Introducción

`AsyncDatabaseManager` permite ejecutar operaciones de BD sin bloquear el event loop, facilitando aplicaciones concurrentes de alto throughput.

## Conceptos de Async/Await

### ¿Por qué async?

- 🚀 **Concurrencia:** Múltiples queries simultáneamente en una sola thread
- 📉 **I/O Efficiency:** No espera a que termine cada query
- 🔗 **Integración:** Compatible con asyncio, FastAPI, Starlette

### Async vs Sync

| Aspecto | Sync | Async |
|--------|------|-------|
| Bloqueo de I/O | ✅ Sí | ❌ No |
| Concurrencia | ❌ No | ✅ Sí (1 thread) |
| Complejidad | Baja | Media |
| Latencia | Puede ser alta | Baja |
| Ideal para | Cron jobs, scripts | Web servers, APIs |

## Configuración del Pool

### Pool Básico

```python
from util_bbdd import AsyncDatabaseManager

manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "database": "mydb"
    },
    use_pool=True,
    pool_size=10
)

await manager.init()
```

### Tuning de Pool

```python
manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={...},
    pool_size=20,         # Para 2000 req/s de 100ms cada una
    pool_recycle=3600,    # Reciclar conexiones cada hora
    pool_pre_ping=True,   # Verificar conexión antes de usar
    max_overflow=40,      # Conexiones extra si pool lleno
)

await manager.init()
```

### Reglas de Tamaño

- **API Web:** `pool_size = concurrent_users * avg_query_time`
- **Batch jobs:** `pool_size = num_workers`
- **Producción:** Empezar con 5-10, monitorear CPU/memory

## Patrones de Concurrencia

### Patrón 1: Gather (Parallelizar múltiples queries)

```python
import asyncio

results = await asyncio.gather(
    manager.get_tables(),
    manager.get_views(),
    manager.execute_custom_many("SELECT ..."),
)
```

### Patrón 2: Loop (Ejecutar lista de queries)

```python
queries = [
    "SELECT * FROM users WHERE age > 18",
    "SELECT COUNT(*) FROM orders",
    "SELECT MAX(price) FROM products"
]

tasks = [manager.execute_custom_many(q) for q in queries]
results = await asyncio.gather(*tasks)

for query, result in zip(queries, results):
    print(f"{query}: {result}")
```

### Patrón 3: Producer-Consumer (Procesamiento en streaming)

```python
import asyncio

async def producer(queue):
    """Generar queries."""
    for i in range(1000):
        query = f"SELECT * FROM table WHERE id = {i}"
        await queue.put(query)
    await queue.put(None)  # Signal done

async def consumer(manager, queue):
    """Consumir y procesar resultados."""
    while True:
        query = await queue.get()
        if query is None:
            break
        result = await manager.execute_custom_many(query)
        print(f"Procesando: {len(result)} filas")

async def main():
    manager = AsyncDatabaseManager(...)
    await manager.init()

    queue = asyncio.Queue(maxsize=10)

    await asyncio.gather(
        producer(queue),
        consumer(manager, queue)
    )

    await manager.close()

asyncio.run(main())
```

## Mejores Prácticas

### ✅ DO:

- Usar `await manager.init()` antes de queries
- Cerrar pool con `await manager.close()`
- Manejar timeouts con `asyncio.timeout()` o `asyncio.wait_for()`
- Usar `gather()` para parallelizar queries independientes
- Monitorear el pool con statslocales

### ❌ DON'T:

- No usar `manager.close()` sin `await`
- No ignorar `PoolExhaustedError` (aumentar `pool_size`)
- No mezclar sync y async en mismo thread
- No hacer queries bloqueantes (CPU-bound) en async context
- No olvidar cerrar el manager en handlers de excepciones

## Errores Comunes

### 1. "RuntimeError: no running event loop"

```python
# ❌ INCORRECTO
result = asyncio.run(manager.execute_custom_many(...))
result = asyncio.run(manager.execute_custom_many(...))  # Error!

# ✅ CORRECTO
async def main():
    await manager.execute_custom_many(...)
    await manager.execute_custom_many(...)

asyncio.run(main())
```

### 2. "PoolExhaustedError: Connection pool is empty"

```python
# ❌ Problema: pool_size=5 pero 20 requests simultáneos
manager = AsyncDatabaseManager(db_type="postgresql", ...)
await manager.init()

# ✅ Solución 1: Aumentar pool
manager = AsyncDatabaseManager(..., pool_size=25)

# ✅ Solución 2: Usar timeout
try:
    result = await asyncio.wait_for(
        manager.execute_custom_many(...),
        timeout=5.0
    )
except asyncio.TimeoutError:
    print("Query took > 5 segundos")
```

### 3. "AttributeError: No attribute 'async_get_tables'"

```python
# ❌ INCORRECTO (métodos no tienen prefijo "async_")
tables = await manager.async_get_tables()

# ✅ CORRECTO
tables = await manager.get_tables()
```

## Integración con Web Frameworks

### FastAPI

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from util_bbdd import AsyncDatabaseManager

manager: AsyncDatabaseManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global manager
    manager = AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={...}
    )
    await manager.init()
    yield
    # Shutdown
    await manager.close()

app = FastAPI(lifespan=lifespan)

@app.get("/tables")
async def get_tables():
    return await manager.get_tables()

@app.get("/users")
async def get_users():
    return await manager.execute_custom_many("SELECT * FROM users")
```

### Starlette

```python
from starlette.applications import Starlette
from starlette.routing import Route
from util_bbdd import AsyncDatabaseManager

manager: AsyncDatabaseManager

async def startup():
    global manager
    manager = AsyncDatabaseManager(...)
    await manager.init()

async def shutdown():
    await manager.close()

async def get_tables(request):
    tables = await manager.get_tables()
    return JSONResponse({"tables": tables})

app = Starlette(
    debug=True,
    routes=[Route("/tables", get_tables)],
    on_startup=[startup],
    on_shutdown=[shutdown],
)
```

## Monitoreo y Debugging

### Ver estado del pool

```python
# Nota: Esta funcionalidad depende del driver
# Para SQLAlchemy, usar:
if hasattr(manager, 'pool'):
    pool = manager.pool
    print(f"Pool tamaño: {pool.size()}")
    print(f"Conexiones activas: {pool.checkedout}")
    print(f"Conexiones disponibles: {pool.size() - pool.checkedout}")
```

### Habilitar logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# Logger para SQLAlchemy pool
logger = logging.getLogger('sqlalchemy.pool')
logger.setLevel(logging.INFO)

# Logger para util_bbdd
logger = logging.getLogger('util_bbdd')
logger.setLevel(logging.DEBUG)
```

### Profiling de queries

```python
import time
import asyncio

async def execute_with_timing(manager, query, label=""):
    start = time.time()
    result = await manager.execute_custom_many(query)
    elapsed = time.time() - start
    print(f"[{label}] {elapsed:.3f}s: {len(result)} filas")
    return result

async def main():
    manager = AsyncDatabaseManager(...)
    await manager.init()

    await execute_with_timing(
        manager,
        "SELECT * FROM users",
        label="Get users"
    )

    await manager.close()
```

## Casos de Uso Reales

### 1. ETL (Extract, Transform, Load) con async

```python
async def etl_pipeline(manager, source_queries, target_table):
    """Extraer datos de múltiples fuentes en paralelo."""
    # Extract en paralelo
    results = await asyncio.gather(
        *(manager.execute_custom_many(q) for q in source_queries)
    )

    # Transform (local, no async)
    transformed = [transform(r) for r in results]

    # Load en paralelo
    tasks = []
    for batch in chunks(transformed, 100):
        tasks.append(manager.execute_custom_many(
            f"INSERT INTO {target_table} (...) VALUES (...)",
            batch
        ))

    await asyncio.gather(*tasks)
```

### 2. API Gateway con util_bbdd

```python
async def fetch_user_data(user_id):
    """Obtener datos del usuario desde múltiples tablas."""
    tasks = [
        manager.execute_custom_one("SELECT * FROM users WHERE id = ?", (user_id,)),
        manager.execute_custom_many("SELECT * FROM orders WHERE user_id = ?", (user_id,)),
        manager.execute_custom_many("SELECT * FROM preferences WHERE user_id = ?", (user_id,)),
    ]

    user, orders, prefs = await asyncio.gather(*tasks)

    return {
        "user": user,
        "orders": orders,
        "preferences": prefs
    }
```

## Conclusión

La programación async con util_bbdd es poderosa para aplicaciones de alto throughput. Comenzar con patrones simples (gather) y escalar a medida que entiendas los tradeoffs de concurrencia y pool sizing.

Para ejemplos detallados, ver [docs/examples/async_concurrent_queries.py](examples/async_concurrent_queries.py).
