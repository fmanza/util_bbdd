# Guía: Conexión y drivers por motor

## 1. Objetivo

Conectar `util_bbdd` a cada motor soportado: qué driver hace falta, qué claves espera el diccionario
`conn_params` de cada motor y cómo abrir un manager **síncrono** o **asíncrono**. Es un how-to
operativo que complementa la [Instalación](../installation.md) (centrada en instalar el paquete y los
drivers) y la guía profunda de [drivers PostgreSQL](postgresql_driver_guide.md).

Motores conectables mediante los managers: **PostgreSQL, MariaDB/MySQL, Oracle, SQL Server, SQLite y
HSQLDB**. HSQLDB solo dispone de modo **síncrono** (sus factorías async lanzan error explícito).

## 2. Requisitos Previos

- Python 3.12+ con `util_bbdd` instalado.
- El driver del motor instalado (ver tabla en §3.1 y [Instalación §3](../installation.md)).
- Datos de conexión del motor (host/puerto/servicio/fichero según el caso) y credenciales.
- El `conn_params` se aporta **externamente**: la librería valida `db_type` y los parámetros, pero
  no persiste secretos.

## 3. Pasos

### 3.1 Instalar el driver del motor

| Motor (`db_type`) | Driver sync | Driver async | Instalación |
|---|---|---|---|
| `postgresql` | `psycopg2-binary` | `asyncpg` | `pip install psycopg2-binary asyncpg` |
| `mariadb` (MariaDB **y** MySQL) | `pymysql` | `aiomysql` | `pip install pymysql aiomysql` |
| `oracle` | `oracledb` (incluido) | `oracledb` (incluido) | — (dependencia base) |
| `sqlserver` | `pyodbc` / `pymssql` | `aioodbc` | `pip install pyodbc aioodbc` + ODBC driver del SO |
| `sqlite` | `sqlite3` (stdlib) | `aiosqlite` | `pip install aiosqlite` |
| `hsqldb` | `jaydebeapi` | N/A (sin async) | `pip install jaydebeapi` + Java |

### 3.2 Construir `conn_params` del motor

Cada motor exige un conjunto mínimo de claves (ver referencia completa en §5):

```python
# PostgreSQL
pg = {"host": "localhost", "port": 5432, "user": "app",
      "password": "<reemplazar>", "database": "ventas"}

# MariaDB / MySQL  (mismo db_type="mariadb" para ambos)
my = {"host": "localhost", "port": 3306, "user": "app",
      "password": "<reemplazar>", "database": "ventas"}

# Oracle  (user + password + UNO de: service_name | sid | dsn | database)
ora = {"host": "ora-host", "port": 1521, "service_name": "ORCLPDB1",
       "user": "hr", "password": "<reemplazar>"}

# SQL Server  (driver pymssql por defecto; pyodbc requiere driver_name)
ss = {"host": "localhost", "port": 1433, "user": "sa",
      "password": "<reemplazar>", "database": "ventas",
      "sql_server_driver": "pymssql"}

# SQLite  (solo ruta al fichero; acepta alias "filepath")
lite = {"database": "data/app.db"}
```

### 3.3 Abrir el manager (sync o async)

Usa el manager como **context manager** para garantizar el cierre. Pasa `db_type` y `conn_params`:

```python
from util_bbdd.managers import SyncDatabaseManager

with SyncDatabaseManager(db_type="postgresql", conn_params=pg) as db:
    row = db.execute_custom_one("SELECT 1")
    print(row)
```

Equivalente asíncrono (no aplicable a HSQLDB):

```python
from util_bbdd.managers import AsyncDatabaseManager

async with AsyncDatabaseManager(db_type="postgresql", conn_params=pg) as db:
    row = await db.execute_custom_one("SELECT 1")
```

## 4. Verificación

Una conexión correcta ejecuta una consulta trivial sin lanzar excepción:

```python
with SyncDatabaseManager(db_type="oracle", conn_params=ora) as db:
    # Oracle requiere FROM DUAL; el resto de motores aceptan "SELECT 1"
    assert db.execute_custom_one("SELECT 1 FROM DUAL") is not None
print("Conexión OK")
```

Si `db_type` no es válido, la librería lanza `InvalidDatabaseType` **antes** de conectar. Si el
driver no está instalado, lanza un error de driver (ver §5). Un fallo de credenciales o red se
manifiesta como `SQLAlchemyError` al abrir el manager.

## 5. Variantes y Solución de Problemas

### Referencia de `conn_params` por motor

| Motor | Claves requeridas | Opcionales habituales |
|---|---|---|
| `postgresql` | `host`, `user`, `password`, `database` | `port`=5432, `schema` (→ `search_path`), `sslmode`, `connect_timeout`, `application_name`, `pool_size` |
| `mariadb` | `host`, `user`, `password`, `database` | `port`=3306, `charset`, `connect_timeout`, `read_timeout`, `write_timeout`, `pool_size` |
| `oracle` | `user`, `password` + **uno de** `service_name` / `sid` / `dsn` / `database` | `host`=localhost, `port`=1521, `oracle_client_path`, `pool_size` |
| `sqlserver` | `host`, `user`, `password`, `database` | `port`=1433, `sql_server_driver` (`pymssql`/`pyodbc`), `driver_name` (pyodbc), `encryption` (`mandatory`/`optional`/`off`), `trust_cert`, `use_mars` |
| `sqlite` | `database` (ruta al fichero) | `timeout`, `isolation_level` (`""`/`DEFERRED`/`IMMEDIATE`/`EXCLUSIVE`), `check_same_thread` |
| `hsqldb` | `user`, `jdbc_url`, `jdbc_jar` | `password`, `jdbc_driver`, `connection_properties` |

### Problemas frecuentes

| Escenario / Error | Causa probable | Solución |
|---|---|---|
| `No module named 'psycopg2'` / `'pymysql'` | Driver no instalado | `pip install psycopg2-binary` / `pip install pymysql` |
| `pyodbc.Error: ('IM002'...)` | ODBC driver de SQL Server no instalado en el SO | Instalar el [Microsoft ODBC Driver](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server); usar `pymssql` si no es posible |
| `oracledb.DatabaseError: DPY-2014` | Oracle Instant Client no encontrado | Configurar `oracle_client_path` en `conn_params` |
| `Para oracle debe informar 'dsn' o 'service_name' o 'sid' o 'database'` | Falta el identificador de servicio Oracle | Añadir una de esas 4 claves |
| `Parametro invalido para sqlserver: encryption=...` | Valor fuera de `mandatory`/`optional`/`off` | Corregir `encryption` |
| Error async con HSQLDB | HSQLDB no soporta async | Usar `SyncDatabaseManager` (HSQLDB es solo síncrono) |
| `Server has gone away` (MariaDB/MySQL) | Conexión caducada en cargas largas | Obtener el engine con `get_sqlalchemy_engine()` (incluye `pool_pre_ping`) |
| El `schema` PostgreSQL parece ignorado | `schema` no es un parámetro libpq | La librería lo traduce a `options=-c search_path=<schema>` automáticamente |

Para el detalle de drivers PostgreSQL (psycopg2 vs asyncpg, pooling), ver la
[guía de drivers PostgreSQL](postgresql_driver_guide.md). Para el contrato completo de los managers,
ver [Gestión de Conexiones (Sync)](../functional/managers_sync.md) y
[(Async)](../functional/managers_async.md).
