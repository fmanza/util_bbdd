# Guía de Drivers PostgreSQL

## 1. Objetivo

Instalar y configurar el driver de PostgreSQL (sync y async) para usarlo con `SyncDatabaseManager` y `AsyncDatabaseManager`.

## 2. Requisitos Previos

- `util_bbdd` instalado
- Python 3.10+ para el driver async (`asyncpg`)
- Servidor PostgreSQL accesible (o usar Docker: `docker run -e POSTGRES_PASSWORD=secret -p 5432:5432 postgres:15`)
- Elegir entre `psycopg2` (sync, ampliamente probado) y `asyncpg` (async, mayor rendimiento) o `psycopg3` (sync+async, el más rápido para bulk)

## 3. Pasos

### Paso 1 — Instalar el driver elegido

```bash
# Sync (psycopg2 — el más compatible)
pip install psycopg2-binary

# Async (asyncpg — el más rápido para async)
pip install asyncpg

# psycopg3 — sync y async, más rápido para bulk (psycopg3 usa COPY en bulk_crud)
pip install "psycopg[binary]"
```

### Paso 2 — Conexión síncrona

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "database": "mydb",
    },
)

# Operaciones de metadatos
tablas = manager.get_tables()
columnas = manager.get_columns("users")
pks = manager.get_primary_keys("users")
fks = manager.get_foreign_keys("orders")

# Obtener engine SQLAlchemy para operaciones bulk
engine = manager.get_sqlalchemy_engine()
manager.close()
```

### Paso 3 — Conexión asíncrona

```python
from util_bbdd import AsyncDatabaseManager

async with AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "port": 5432, "user": "u", "password": "p", "database": "db"},
    use_pool=True,
) as mgr:
    tablas = await mgr.get_tables()
    filas = await mgr.execute_custom_many("SELECT * FROM users LIMIT 10")
```

### Paso 4 — Configuración de pool para producción

```python
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "prod-server",
        "database": "mydb",
        "user": "app_user",
        "password": "secret",
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,      # verificar conexión antes de usar
        "pool_recycle": 1800,       # reciclar conexiones cada 30 min
        "connect_args": {"sslmode": "require"},  # SSL en producción
    },
)
```

## 4. Verificación

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "port": 5432, "user": "postgres", "password": "secret", "database": "test"},
)

version = manager.get_database_version()
print(f"PostgreSQL versión: {version}")
# → PostgreSQL versión: PostgreSQL 15.x on ...

tablas = manager.get_tables()
print(f"Tablas encontradas: {len(tablas)}")
manager.close()
```

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `No module named 'psycopg2'` | Driver no instalado | `pip install psycopg2-binary` |
| `fe_sendauth: no password supplied` | Sin contraseña en `conn_params` | Añadir `"password": "..."` en `conn_params` |
| `SSL connection required` en producción | Servidor requiere SSL | Añadir `"connect_args": {"sslmode": "require"}` en `conn_params` |
| `FATAL: role "username" does not exist` | Usuario no existe en PostgreSQL | Crear el usuario: `CREATE USER username WITH PASSWORD '...'` |
| `FATAL: database "dbname" does not exist` | Base de datos no creada | `CREATE DATABASE dbname;` en psql |
| Bulk insert lento con psycopg2 | psycopg2 usa `execute_values` (3–5×); psycopg3 usa `COPY` (mucho más rápido) | `pip install "psycopg[binary]"` para usar psycopg3 |
