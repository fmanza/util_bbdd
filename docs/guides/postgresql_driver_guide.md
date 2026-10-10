# Guía de Drivers PostgreSQL

## 1. Objetivo

Instalar y configurar el driver de PostgreSQL (sync y async) para usarlo con `SyncDatabaseManager` y `AsyncDatabaseManager`.

## 2. Requisitos Previos

- `util_bbdd` instalado
- Python 3.12+ (el mismo requisito que `util_bbdd`)
- Servidor PostgreSQL accesible (o usar Docker: `docker run -e POSTGRES_PASSWORD=secret -p 5432:5432 postgres:15`)
- Drivers que usan los managers: **psycopg 3** (`psycopg` + `psycopg-pool`) en sync y **asyncpg** en async. `psycopg2` no
  lo usan los managers; solo aplica si pasas a `BulkCrud` un Engine `postgresql+psycopg2://` creado por ti

## 3. Pasos

### Paso 1 — Instalar el driver elegido

```bash
# Todo lo necesario para PostgreSQL (psycopg 3 + psycopg-pool en sync, asyncpg en async)
pip install "util_bbdd[postgresql]"

# Equivalente a mano
pip install "psycopg[binary]" psycopg-pool asyncpg
```

Con psycopg 3, `BulkCrud` inserta con `COPY ... FROM STDIN`.

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
        "pool_size": 20,            # conexiones del pool (psycopg-pool)
        "pool_timeout": 30,         # segundos esperando una conexión libre
        "max_idle": 600,            # segundos antes de cerrar una conexión ociosa
        "sslmode": "require",       # TLS en producción (parámetro de libpq)
    },
)
```

Parámetros admitidos: los de conexión de libpq que recoge `PostgreSQLConnectionConfig` (`sslmode`,
`connect_timeout`, `application_name`, `keepalives*`, `options`, `target_session_attrs`…) y los de pool de
`PostgreSQLPoolConfig` (`pool_size`, `pool_timeout`, `max_idle`, `close_timeout`). Ver
[Conexión y Drivers por Motor](connection_guide.md).

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
| `Módulo psycopg (psycopg3) no disponible` | Driver sync no instalado | `pip install "util_bbdd[postgresql]"` |
| `No module named 'asyncpg'` | Driver async no instalado | `pip install "util_bbdd[postgresql]"` |
| `fe_sendauth: no password supplied` | Sin contraseña en `conn_params` | Añadir `"password": "..."` en `conn_params` |
| `SSL connection required` en producción | Servidor requiere SSL | Añadir `"sslmode": "require"` en `conn_params` |
| `FATAL: role "username" does not exist` | Usuario no existe en PostgreSQL | Crear el usuario: `CREATE USER username WITH PASSWORD '...'` |
| `FATAL: database "dbname" does not exist` | Base de datos no creada | `CREATE DATABASE dbname;` en psql |
| Bulk insert lento con un Engine `postgresql+psycopg2://` propio | psycopg2 usa `execute_values`; psycopg 3 usa `COPY` (mucho más rápido) | Crea el Engine con `postgresql+psycopg://` o usa `manager.get_sqlalchemy_engine()` |
