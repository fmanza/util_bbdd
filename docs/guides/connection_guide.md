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
| `postgresql` | `psycopg` (v3) + `psycopg-pool` | `asyncpg` | `pip install "util_bbdd[postgresql]"` |
| `mariadb` | `mariadb` (MariaDB Connector/Python) | `aiomysql` | `pip install "util_bbdd[mariadb]"` |
| `mysql` | `pymysql` | `aiomysql` | `pip install "util_bbdd[mysql]"` |
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

# MariaDB (db_type="mariadb") y MySQL (db_type="mysql"): mismas claves
maria = {"host": "localhost", "port": 3306, "user": "app",
         "password": "<reemplazar>", "database": "ventas"}
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
| `postgresql` | `host`, `user`, `password`, `database` | `port`=5432, `schema` (→ `search_path`; nombres sin comillas separados por comas), `sslmode` (también en async: asyncpg recibe el modo de libpq), `connect_timeout`, `application_name`, `pool_size` |
| `mariadb` | `host`, `user`, `password`, `database` | `port`=3306, `charset`=utf8mb4, `init_command`=`"SET NAMES utf8mb4"`, `encoding_errors`=`"replace"`, `connect_timeout`, `read_timeout`, `write_timeout`, `pool_size` |
| `mysql` | `host`, `user`, `password`, `database` | `port`=3306, `charset`, `connect_timeout`, `read_timeout`, `write_timeout`, `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, `ssl_ca`/`ssl_cert`/`ssl_key`, `ssl_verify_cert`, `ssl_verify_identity` (sync y async: con CA se verifican certificado y hostname salvo que se desactiven) |
| `oracle` | `user`, `password` + **uno de** `service_name` / `sid` / `dsn` / `database` | `host`=localhost, `port`=1521, `protocol` (`tcp`/`tcps`; sin `dsn`), `oracle_client_path`, `oracle_thick_mode`, `pool_size` |
| `sqlserver` | `host`, `user`, `password`, `database` | `port`=1433, `sql_server_driver` (`pymssql`/`pyodbc`), `driver_name` (pyodbc), `encryption` (`mandatory`/`optional`/`off`; con pymssql se traduce a `require`/por defecto de FreeTDS/`off`), `trust_cert` y `use_mars` (solo pyodbc/aioodbc) |
| `sqlite` | `database` (ruta al fichero) | `timeout`, `isolation_level` (`""`/`DEFERRED`/`IMMEDIATE`/`EXCLUSIVE`), `check_same_thread`, `cached_statements` |
| `hsqldb` | `user`, `jdbc_url`, `jdbc_jar` | `password`, `jdbc_driver`, `connection_properties` (propiedades JDBC). Sin Engine de SQLAlchemy ni pool: conexión nativa única |

### Problemas frecuentes

| Escenario / Error | Causa probable | Solución |
|---|---|---|
| `No module named 'psycopg'` / `'mariadb'` / `'pymysql'` | Driver no instalado | `pip install "util_bbdd[postgresql]"` / `pip install "util_bbdd[mariadb]"` / `pip install "util_bbdd[mysql]"` |
| MySQL 8 contra servidor MySQL con `db_type="mariadb"` | Funciona: el conector de MariaDB también conecta con MySQL | Para usar PyMySQL y el catálogo de MySQL, `db_type="mysql"` |
| `pyodbc.Error: ('IM002'...)` | ODBC driver de SQL Server no instalado en el SO | Instalar el [Microsoft ODBC Driver](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server); usar `pymssql` si no es posible |
| `oracledb.DatabaseError: DPY-2014` | Oracle Instant Client no encontrado | Configurar `oracle_client_path` en `conn_params` |
| MySQL async con `ssl_*` en Windows: `Can't connect to MySQL server` (`SSLWantReadError`) | aiomysql no negocia TLS con el `ProactorEventLoop` por defecto de Windows (también sin util_bbdd) | `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` antes de crear el loop |
| `encryption='mandatory' pero la sesión pymssql no va cifrada` | El FreeTDS de pymssql (p. ej. el wheel de Windows) acepta `require` y no cifra | `sql_server_driver="pyodbc"` con ODBC Driver 17/18 (`Encrypt=yes`) |
| `Para oracle debe informar 'dsn' o 'service_name' o 'sid' o 'database'` | Falta el identificador de servicio Oracle | Añadir una de esas 4 claves |
| `Parametro invalido para sqlserver: encryption=...` | Valor fuera de `mandatory`/`optional`/`off` | Corregir `encryption` |
| Error async con HSQLDB | HSQLDB no soporta async | Usar `SyncDatabaseManager` (HSQLDB es solo síncrono) |
| `Server has gone away` (MariaDB/MySQL) | Conexión caducada en cargas largas | Obtener el engine con `get_sqlalchemy_engine()` (incluye `pool_pre_ping`) |
| El `schema` PostgreSQL parece ignorado | `schema` no es un parámetro libpq | La librería lo traduce a `options=-c search_path=<schema>` automáticamente |
| `UnicodeDecodeError` en MariaDB al generar documentación | Encoding mismatch: servidor `latin1` vs. cliente `utf8mb4` | Usar `init_command` y `encoding_errors` (ver §6) |

### 6. Parámetros especiales de MariaDB: `init_command` y `encoding_errors`

A partir de **v0.35.0**, `MariaDBConnectionConfig` incluye dos parámetros que mitigan conflictos de charset
común cuando el servidor está configurado en `latin1` pero queremos usar `utf8mb4`:

#### **`init_command`** (string, default `"SET NAMES utf8mb4"`)

SQL ejecutado en cada conexión sync y de pool (MariaDB Connector/Python). Es siempre `SET NAMES utf8mb4` por
defecto: el conector solo trabaja en utf8mb4 y rechaza otras sesiones (`ProgrammingError: Character set 'latin1' is
not supported`, comprobado con 1.1.14). El conector tampoco admite el parámetro `charset`: la librería no se lo envía;
`charset` (solo letras, dígitos y `_`) lo usa la conexión async (aiomysql). v0.35.6 hacía el valor por defecto
`SET NAMES <charset>`, que impedía conectar con `charset="latin1"`; v0.35.7 lo revierte.
Replica el comportamiento de PyMySQL/SQLAlchemy:

- **Sin `init_command`**: El handshake fija `charset='utf8mb4'`, pero solo en `character_set_client` y
  `character_set_connection`. El servidor no sabe que debe convertir los datos a utf8mb4 **antes** de
  enviarlos; devuelve bytes en su charset nativo (p. ej. `latin1`).
- **Con `init_command`**: Ejecuta `SET NAMES utf8mb4`, que fija simultáneamente:
  - `character_set_client = utf8mb4`
  - `character_set_connection = utf8mb4`
  - **`character_set_results = utf8mb4`** ← esto es lo importante: le dice al servidor que convierta
    los datos antes de enviarlos.

**Cambio visible**: Elimina `UnicodeDecodeError: 'latin1' codec can't decode...` al leer `information_schema`
con caracteres no-ASCII (comentarios en tablas, etc.).

**Personalización:**

```python
conn_params = {
    "host": "localhost",
    "user": "app",
    "password": "secret",
    "database": "mydb",
    "charset": "utf8mb4",                    # default
    "init_command": "SET NAMES utf8mb4",     # personalizar si es necesario
}

from util_bbdd.managers import SyncDatabaseManager
with SyncDatabaseManager(db_type="mariadb", conn_params=conn_params) as db:
    docs = db.get_database_documentation()  # Sin errores de encoding
```

#### **`encoding_errors`** (obsoleto, sin efecto)

Ningún driver de MariaDB lo admite: MariaDB Connector/Python 1.1.14 (la última versión) rechaza `encoding_errors`
con `TypeError`, igual que `mariadb.ConnectionPool`, y aiomysql no tiene ese parámetro. Hasta v0.35.6 la librería lo
enviaba por defecto (`"replace"`) y el reintento defensivo lo quitaba en cada conexión nueva, así que **nunca llegó a
aplicarse** (ni como red de seguridad ni sustituyendo bytes). Desde v0.35.7 no se envía; si aparece en `conn_params`
se acepta por compatibilidad y emite un `FutureWarning`.

### 7. Pools: `pool_size`, `close_timeout` y el pool del Engine

#### Qué significa `pool_size` en cada motor

Cada motor envuelve un pool nativo distinto, así que `pool_size` no se comporta igual en todos:

| Motor | Pool sync | Qué hace `pool_size` |
|---|---|---|
| MariaDB | `mariadb.ConnectionPool` | tamaño fijo del pool |
| MySQL | `QueuePool` de SQLAlchemy sobre PyMySQL | conexiones base; se suman hasta `max_overflow` (10) |
| Oracle | `oracledb.create_pool` | máximo de un pool que crece de 1 en 1 desde 1 conexión |
| PostgreSQL | `psycopg_pool.ConnectionPool` | mínimo y máximo: abre las `pool_size` conexiones al crearse |
| SQL Server | pool propio | abre `pool_size` conexiones al crearse; se suman hasta `max_overflow` |
| SQLite | conexión única | se ignora (siempre 1) |

#### `close_timeout`

Segundos que espera el cierre del pool (por defecto `10`). Un valor `<= 0` lo desactiva (espera sin límite) y un valor
no numérico vale `10`. Desde v0.36.0 forma parte de la config de pool de cada motor (`<Motor>PoolConfig.close_timeout`)
y lo usan igual los pools sync y async.

#### El Engine tiene su propio pool

`get_sqlalchemy_engine()` (lo usan bulk, dump y comparar) devuelve un Engine cuyo pool es **independiente** del pool
nativo del manager: abre sus conexiones con el driver nativo, pero no las toma del pool del manager. Un manager con
`pool_size=N` que entrega su Engine puede llegar a mantener `N` conexiones nativas más `N + max_overflow` del Engine.
Tenlo en cuenta al dimensionar `max_connections` del servidor.

Desde v0.36.0 los Engine sync y async siguen la misma política, tomada de `conn_params`:

| Parámetro | Por defecto | Notas |
|---|---|---|
| `pool_size` | 5 | |
| `max_overflow` | 10 | |
| `pool_timeout` | 30 | segundos de espera por una conexión libre |
| `pool_recycle` | 3600 | antes: solo MariaDB/MySQL en sync (3600) y 1800 en async |

SQLite no usa estos parámetros (SQLAlchemy le asigna su propio pool). Con `use_pool=False`, el AsyncEngine no usa pool
(`NullPool`); el Engine sync sigue usando el suyo.

Para el detalle de drivers PostgreSQL (psycopg2 vs asyncpg, pooling), ver la
[guía de drivers PostgreSQL](postgresql_driver_guide.md). Para el contrato completo de los managers,
ver [Gestión de Conexiones (Sync)](../functional/managers_sync.md) y
[(Async)](../functional/managers_async.md).
