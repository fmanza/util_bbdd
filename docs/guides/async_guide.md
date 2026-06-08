# Guía de Programación Asíncrona

## 1. Objetivo

Configurar `AsyncDatabaseManager` y usar patrones de concurrencia async/await en aplicaciones Python de alta concurrencia.

## 2. Requisitos Previos

- Python 3.10+ con soporte `asyncio`
- Driver async instalado para el motor objetivo:
  - PostgreSQL: `asyncpg`
  - MariaDB/MySQL: `aiomysql`
  - SQL Server: `aioodbc`
  - SQLite: `aiosqlite`
- Familiaridad con `async/await` y el event loop de Python
- **Diferencia crítica respecto al manager síncrono**: el constructor de `AsyncDatabaseManager` NO conecta. Es obligatorio `await manager.init()` o usar `async with` antes de cualquier operación.

## 3. Pasos

### Paso 1 — Instalar el driver async del motor

```bash
# PostgreSQL
pip install asyncpg

# MariaDB/MySQL
pip install aiomysql

# SQL Server
pip install aioodbc
```

### Paso 2 — Configurar el manager async

```python
from util_bbdd import AsyncDatabaseManager

manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "database": "mydb",
    },
    use_pool=True,
)

await manager.init()
```

### Paso 3 — Configurar el pool según el workload

| Escenario | `pool_size` | `max_overflow` | `pool_recycle` | Throughput aprox. |
|---|---|---|---|---|
| Desarrollo local | 5 | 0 | 3600 | ~100 req/s |
| API pequeña | 10 | 5 | 3600 | ~500 req/s |
| API mediana | 20 | 10 | 1800 | ~2000 req/s |
| API grande | 40 | 20 | 900 | ~5000 req/s |
| Batch job paralelo | 8 | 4 | 600 | 8 workers |

**Regla práctica**: `pool_size = CPU_cores × 2 + conexiones_por_request` para APIs web.

### Paso 4 — Patrones de concurrencia

```python
# Patrón 1: Parallelizar múltiples queries independientes
import asyncio

tablas, vistas, cuenta = await asyncio.gather(
    manager.get_tables(),
    manager.get_views(),
    manager.execute_custom_one("SELECT COUNT(*) FROM pedidos"),
)

# Patrón 2: Semáforo para limitar concurrencia
semaphore = asyncio.Semaphore(10)

async def query_acotada(sql: str):
    async with semaphore:
        return await manager.execute_custom_many(sql)

resultados = await asyncio.gather(*[query_acotada(q) for q in lista_queries])
```

### Paso 5 — Cerrar correctamente

```python
# Opción A: async context manager (recomendado)
async with AsyncDatabaseManager("postgresql", conn_params) as mgr:
    tablas = await mgr.get_tables()
# close() automático al salir

# Opción B: cierre explícito
manager = AsyncDatabaseManager("postgresql", conn_params)
await manager.init()
try:
    tablas = await manager.get_tables()
finally:
    await manager.close()
```

## 4. Verificación

```python
import asyncio
from util_bbdd import AsyncDatabaseManager

async def verificar():
    async with AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={"host": "localhost", "port": 5432, "user": "u", "password": "p", "database": "test"},
    ) as mgr:
        tablas = await mgr.get_tables()
        print(f"Conexión async OK. Tablas: {len(tablas)}")

asyncio.run(verificar())
```

Output esperado: `Conexión async OK. Tablas: N`

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `ConnectionError` en primera operación | Constructor no conecta; se olvidó `await init()` | Usar `async with` o llamar `await manager.init()` antes de operar |
| `PoolExhaustedError` | Más corrutinas concurrentes que conexiones en pool | Aumentar `pool_size` o usar `asyncio.Semaphore(n)` para limitar concurrencia |
| `PoolTimeoutError` | Pool agotado + timeout de espera | Aumentar `pool_timeout` o revisar queries lentas que retienen conexiones |
| Driver no soporta async | Motor configurado sin driver async | Instalar el driver async correspondiente (ver Paso 1) |
| `NotImplementedError` al crear pool | Motor sin soporte pool async | El manager cae automáticamente a conexión directa; comportamiento esperado |
