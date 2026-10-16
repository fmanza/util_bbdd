# Guía de Programación Asíncrona

## 1. Objetivo

Configurar `AsyncDatabaseManager` y usar patrones de concurrencia async/await en aplicaciones Python de alta concurrencia.

## 2. Requisitos Previos

- Python 3.12+
- Driver async instalado para el motor objetivo:
  - PostgreSQL: `asyncpg` (extra `postgresql`)
  - MariaDB (`db_type="mariadb"`) y MySQL (`db_type="mysql"`): `aiomysql` (extras `mariadb` / `mysql`)
  - Oracle: `oracledb` (instalación base)
  - SQL Server: `aioodbc` (y un driver ODBC de Microsoft)
  - SQLite: `aiosqlite`
  - HSQLDB no tiene driver async: `AsyncDatabaseManager("hsqldb", ...)` falla con `NotImplementedError`
- Familiaridad con `async/await` y el event loop de Python
- **Diferencia respecto al manager síncrono**: el constructor de `AsyncDatabaseManager` NO conecta. Conecta en `await manager.init()`, al entrar en `async with` o, si no, en la primera operación. Llamar a `init()` al arrancar hace que un error de conexión aparezca ahí y no en la primera consulta.

## 3. Pasos

### Paso 1 — Instalar el driver async del motor

```bash
# PostgreSQL (psycopg 3 + asyncpg)
pip install "util_bbdd[postgresql] @ git+https://github.com/fmanza/util_bbdd.git@v3.0.3"

# MariaDB / MySQL (incluyen aiomysql)
pip install "util_bbdd[mariadb] @ git+https://github.com/fmanza/util_bbdd.git@v3.0.3"

# SQL Server y SQLite async (no van en ningún extra)
pip install aioodbc aiosqlite
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

Los parámetros del pool van en `conn_params` y dependen del motor; una clave que el motor no admite da
`ValidationError` al crear el manager (p. ej. `max_overflow` o `pool_recycle` en PostgreSQL):

| Motor | Parámetros de pool (default) |
|---|---|
| PostgreSQL | `pool_size` (5), `pool_timeout` (30), `max_idle` (300) |
| MariaDB | `pool_size` (5), `pool_name`, `pool_recycle` (3600) |
| MySQL | `pool_size` (5), `max_overflow` (10), `pool_timeout` (30), `pool_recycle` (3600) |
| SQL Server | `pool_size` (5), `max_overflow` (10), `pool_timeout` (30) |
| Oracle | `pool_size` (5), `max_lifetime` (3600) |
| SQLite | Una sola conexión: las operaciones se serializan |

`pool_size` limita cuántas operaciones van a la base de datos a la vez; dimensionarlo según la concurrencia real
(y el límite de conexiones del servidor). Detalle por motor: [Conexión y Drivers](connection_guide.md).

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
| Error de conexión en la primera consulta | Sin `init()` explícito, el manager conecta en la primera operación | Llamar a `await manager.init()` al arrancar para detectarlo antes |
| Corrutinas que esperan | Más corrutinas concurrentes que conexiones en el pool: esperan a que se libere una (no se lanza error por esperar) | Aumentar `pool_size` o limitar la concurrencia con `asyncio.Semaphore(n)` |
| `ValidationError` al crear el manager | Parámetro de pool que el motor no admite (`max_overflow` en PostgreSQL…) | Usar los parámetros de la tabla del Paso 3 |
| `ModuleNotFoundError` del driver | Driver async no instalado | Instalar el driver correspondiente (ver Paso 1) |
| `NotImplementedError` al inicializar | Motor sin soporte async (HSQLDB) | Usar `SyncDatabaseManager` |
