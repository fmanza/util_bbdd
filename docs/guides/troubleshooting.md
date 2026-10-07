# Troubleshooting — util_bbdd

## 1. Objetivo

Diagnosticar y resolver los errores más frecuentes de conexión, pool, drivers y operaciones bulk en `util_bbdd`.

## 2. Requisitos Previos

- `util_bbdd` instalado y el driver del motor configurado (ver [Guía de Instalación](../installation.md))
- Acceso al log de Python habilitado (`logging.basicConfig(level=logging.DEBUG)`) para diagnóstico de errores de pool y conexión
- Para errores de pool async: Python 3.10+ con `asyncio`

## 3. Pasos

### Habilitar logging de diagnóstico

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
```

### Verificar conexión básica antes de ejecutar operaciones

```python
from util_bbdd import SyncDatabaseManager

try:
    mgr = SyncDatabaseManager("postgresql", conn_params)
    mgr.get_database_version()
    print("Conexión OK")
    mgr.close()
except Exception as e:
    print(f"Error de conexión: {e}")
```

### Aumentar tamaño del pool para errores de concurrencia

```python
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "...", "database": "...", "user": "...", "password": "...",
        "pool_size": 20,
        "max_overflow": 10,
    },
)
```

## 4. Verificación

```bash
# Verificar que el driver del motor está instalado
python -c "import psycopg2; print('psycopg2 OK')"   # PostgreSQL
python -c "import mariadb; print('mariadb OK')"      # MariaDB (Connector/Python)
python -c "import pymysql; print('pymysql OK')"      # MySQL
python -c "import pyodbc; print('pyodbc OK')"        # SQL Server

# Verificar conectividad básica con util_bbdd
python -c "
from util_bbdd import SyncDatabaseManager
with SyncDatabaseManager('sqlite', {'database': ':memory:'}) as m:
    print('util_bbdd OK:', m.get_tables())
"
```

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `PoolExhaustedError: Pool agotado` | `pool_size` insuficiente para la concurrencia real | Aumentar `pool_size`; para async usar `asyncio.Semaphore(n)` para limitar |
| `PoolTimeoutError: Timeout esperando conexión` | Pool agotado + timeout de espera; o queries lentas bloqueando | Aumentar `pool_timeout`; optimizar queries lentas; revisar índices |
| `ConnectionError: No se pudo conectar` | Servidor no alcanzable, credenciales incorrectas, listener apagado | Verificar host/port/credenciales; ejecutar `telnet host port` para probar conectividad |
| `InvalidDatabaseType` | `db_type` escrito incorrectamente | Usar exactamente: `mariadb`, `oracle`, `postgresql`, `sqlite`, `hsqldb`, `sqlserver` |
| `DriverError: No module named 'psycopg2'` | Driver no instalado en el entorno virtual activo | `pip install psycopg2-binary` en el entorno virtual correcto |
| `pyodbc.Error: ('IM002'...)` SQL Server | ODBC driver nativo no instalado en el SO | Instalar Microsoft ODBC Driver for SQL Server (ver installation.md) |
| `Lost connection to server` MariaDB bulk | `max_allowed_packet` del servidor es insuficiente | Reducir `chunk_size` a 500 o aumentar `max_allowed_packet` en el servidor |
| `Server has gone away` MariaDB | Conexión ociosa cerrada por el servidor | Usar `SyncDatabaseManager.get_sqlalchemy_engine()` que incluye `pool_pre_ping=True` |
| `UnicodeDecodeError: 'latin1' codec can't decode...` MariaDB | Servidor configurado en `latin1` pero cliente intenta leer UTF-8 de `information_schema` | Verificar `init_command` y `encoding_errors` en `conn_params` (ver [Guía: Conexión § 6](connection_guide.md#6-parámetros-especiales-de-mariadb-init_command-y-encoding_errors)); por defecto están activos en v0.35.0+ |
| `PythonFinalizationError` al cerrar | Conexiones no cerradas explícitamente | Usar `with SyncDatabaseManager(...) as m:` o llamar `manager.close()` explícitamente |
| `InterfaceError: Lost connection` durante INSERT MariaDB | `chunk_size` demasiado alto para columnas TEXT/JSON extensas | Reducir `chunk_size` a 100–500 para tablas con columnas `TEXT`, `BLOB` o `JSON` |
| `GraphRenderError` / `FileNotFoundError` en grafos | Binarios de Graphviz no en PATH | Instalar Graphviz del sistema (`apt install graphviz` / `brew install graphviz`) |
