# Troubleshooting — util_bbdd

## 1. Objetivo

Diagnosticar y resolver los errores más frecuentes de conexión, pool, drivers y operaciones bulk en `util_bbdd`.

## 2. Requisitos Previos

- `util_bbdd` instalado y el driver del motor configurado (ver [Guía de Instalación](../installation.md))
- Acceso al log de Python habilitado (`logging.basicConfig(level=logging.DEBUG)`) para diagnóstico de errores de pool y conexión

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

Los parámetros de pool van en `conn_params` y dependen del motor (en PostgreSQL no existe `max_overflow`: daría
`ValidationError`; tabla por motor en la [guía async](async_guide.md#paso-3-configurar-el-pool-segun-el-workload)):

```python
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "...", "database": "...", "user": "...", "password": "...",
        "pool_size": 20,
        "pool_timeout": 60,
    },
)
```

## 4. Verificación

```bash
# Verificar que el driver del motor está instalado
python -c "import psycopg; print('psycopg OK')"     # PostgreSQL (psycopg 3; async: asyncpg)
python -c "import mariadb; print('mariadb OK')"      # MariaDB (Connector/Python)
python -c "import pymysql; print('pymysql OK')"      # MySQL
python -c "import pymssql; print('pymssql OK')"      # SQL Server (por defecto; o pyodbc)

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
| `PoolTimeoutError` (pool sync de PostgreSQL, MySQL o SQL Server) | Pool agotado durante `pool_timeout` segundos: más hilos que conexiones, o consultas lentas que las retienen | Aumentar `pool_size` o `pool_timeout`; optimizar las consultas lentas. En async no hay error por esperar: limitar con `asyncio.Semaphore(n)` |
| `DatabaseConfigurationError` (con pool) o `ConnectionError` (conexión única) al crear el manager | Servidor no alcanzable, credenciales incorrectas, listener apagado | Verificar host/port/credenciales; probar la conectividad de red con el puerto |
| `TypeError: BulkCrud.__init__() got an unexpected keyword argument 'chunk_size'` (o `ParallelBulkLoader` con `max_workers`, `audit_csv_path`…) | Código escrito para 2.x: desde 3.0.0 las opciones de `BulkCrud` y `ParallelBulkLoader` van en paquetes | Pasar las opciones en su paquete, p. ej. `BulkCrud(engine, batch=BatchOptions(chunk_size=5_000))`; tabla de equivalencias en [Migración a la API 3.0](api_3_0_migration.md) |
| `InvalidDatabaseType` | `db_type` escrito incorrectamente | Usar exactamente: `mariadb`, `mysql`, `oracle`, `postgresql`, `sqlite`, `hsqldb`, `sqlserver` |
| `No module named 'psycopg'` | Driver no instalado en el entorno virtual activo | Instalar el extra `postgresql` en el entorno virtual correcto: `pip install "util_bbdd[postgresql] @ git+https://github.com/fmanza/util_bbdd.git@v5.0.0"` (los managers usan psycopg 3, no `psycopg2`) |
| `CERT_E_CN_NO_MATCH` o error de conexión TLS con `ssl_ca` en MariaDB | El hostname de conexión no figura en el certificado. MariaDB Connector/Python no tiene `ssl_verify_identity`: verifica CA y hostname a la vez (límite del driver) | Conectar con un nombre o IP que esté en el certificado (ver [Guía: Conexión § TLS en MariaDB](connection_guide.md#tls-en-mariadb-ssl-ssl_ca-ssl_cert-ssl_key-ssl_verify_cert-desde-v0390)) |
| WARNING `trust_cert no tiene efecto con pymssql` | pymssql no admite `trust_cert`; la validación del certificado depende de FreeTDS (límite del driver) | `sql_server_driver="pyodbc"` (ver [Guía: Conexión § TLS en SQL Server](connection_guide.md#tls-en-sql-server-encryption-y-trust_cert)) |
| `pyodbc.Error: ('IM002'...)` SQL Server | ODBC driver nativo no instalado en el SO | Instalar Microsoft ODBC Driver for SQL Server (ver installation.md) |
| `Lost connection to server` MariaDB bulk | `max_allowed_packet` del servidor es insuficiente | Reducir el tamaño de lote a 500 (`BulkCrud(engine, batch=BatchOptions(chunk_size=500))`; en el volcado, `DumpConfig(chunk_size=500)`) o aumentar `max_allowed_packet` en el servidor |
| `Server has gone away` MariaDB | Conexión ociosa cerrada por el servidor | Usar `SyncDatabaseManager.get_sqlalchemy_engine()` que incluye `pool_pre_ping=True` |
| `UnicodeDecodeError: 'latin1' codec can't decode...` MariaDB | Servidor configurado en `latin1` pero cliente intenta leer UTF-8 de `information_schema` | Verificar `init_command` (por defecto `SET NAMES utf8mb4`) en `conn_params` (ver [Guía: Conexión § 6](connection_guide.md#6-parametros-especiales-de-mariadb-init_command-y-encoding_errors)); activo por defecto desde v0.35.0 |
| `PythonFinalizationError` al cerrar | Conexiones no cerradas explícitamente | Usar `with SyncDatabaseManager(...) as m:` o llamar `manager.close()` explícitamente |
| `InterfaceError: Lost connection` durante INSERT MariaDB | `chunk_size` demasiado alto para columnas TEXT/JSON extensas | Reducir el tamaño de lote a 100–500 para tablas con columnas `TEXT`, `BLOB` o `JSON` (`BatchOptions(chunk_size=…)` en `BulkCrud`; `DumpConfig(chunk_size=…)` en el volcado) |
| `graphviz.ExecutableNotFound` al generar grafos | Binarios de Graphviz (`dot`) no en el PATH | Instalar Graphviz del sistema (`apt install graphviz` / `brew install graphviz`) |
| `ImportError` al crear `GraphvizRelationshipGraphExt` | Falta el paquete `graphviz` de Python | Instalar el extra `analysis` |
