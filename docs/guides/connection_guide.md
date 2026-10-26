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
| `postgresql` | `psycopg` (v3) + `psycopg-pool` | `asyncpg` | extra `postgresql` |
| `mariadb` | `mariadb` (MariaDB Connector/Python) | `aiomysql` | extra `mariadb` |
| `mysql` | `pymysql` | `aiomysql` | extra `mysql` |
| `oracle` | `oracledb` | `oracledb` | extra `oracle` |
| `sqlserver` | `pymssql` (por defecto) / `pyodbc` | `aioodbc` | `pip install pymssql` o `pip install pyodbc`; async: `pip install aioodbc`. `pyodbc` y `aioodbc` necesitan el ODBC Driver de Microsoft |
| `sqlite` | `sqlite3` (stdlib) | `aiosqlite` | `pip install aiosqlite` |
| `hsqldb` | `jaydebeapi` | N/A (sin async) | `pip install jaydebeapi` + Java |

Un extra se instala desde el repositorio (no está en PyPI):
`pip install "util_bbdd[postgresql] @ git+https://github.com/fmanza/util_bbdd.git@v4.1.0"`.

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

# SQL Server  (driver pymssql por defecto; con pyodbc, driver_name = "ODBC Driver 17 for SQL Server" por defecto)
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
driver no está instalado, lanza `DriverError` (ver §5). Un fallo de credenciales o red aparece al
abrir el manager: `DatabaseConfigurationError` si falla la creación del pool (lo habitual, `use_pool=True`) o
`ConnectionError` con conexión única.

## 5. Variantes y Solución de Problemas

### Referencia de `conn_params` por motor

| Motor | Claves requeridas | Opcionales habituales |
|---|---|---|
| `postgresql` | `host`, `user`, `password`, `database` | `port`=5432, `schema` (→ `search_path`; nombres sin comillas separados por comas), `sslmode` (también en async: asyncpg recibe el modo de libpq), `connect_timeout`, `application_name`, `pool_size` |
| `mariadb` | `host`, `user`, `password`, `database` | `port`=3306, `charset`=utf8mb4, `init_command`=`"SET NAMES utf8mb4"`, `catalog_charset_mode`=`"auto"`, `connect_timeout`, `read_timeout`, `write_timeout`, `pool_size`, `ssl`/`ssl_ca`/`ssl_cert`/`ssl_key`, `ssl_verify_cert` (sin `ssl_verify_identity`: límite del driver, ver §6). `encoding_errors` se acepta pero no tiene efecto |
| `mysql` | `host`, `user`, `password`, `database` | `port`=3306, `charset`, `connect_timeout`, `read_timeout`, `write_timeout`, `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`, `ssl_ca`/`ssl_cert`/`ssl_key`, `ssl_verify_cert`, `ssl_verify_identity` (sync y async: con CA se verifican certificado y hostname salvo que se desactiven) |
| `oracle` | `user`, `password` + **uno de** `service_name` / `sid` / `dsn` / `database` | `host`=localhost, `port`=1521, `protocol` (`tcp`/`tcps`; sin `dsn`), `oracle_client_path`, `oracle_thick_mode`, `pool_size`, `schema` (owner por defecto de los metadatos; sin él, el usuario. Desde 4.1.0; no cambia `CURRENT_SCHEMA`) |
| `sqlserver` | `host`, `user`, `password`, `database` | `port`=1433, `sql_server_driver` (`pymssql`/`pyodbc`), `driver_name` (pyodbc), `encryption` (`mandatory`/`optional`/`off`; con pymssql se traduce a `require`/por defecto de FreeTDS/`off`), `trust_cert` y `use_mars` (solo pyodbc/aioodbc; con pymssql, `trust_cert=True` avisa una vez de que no se aplica) |
| `sqlite` | `database` (ruta al fichero) | `timeout`, `isolation_level` (`""`/`DEFERRED`/`IMMEDIATE`/`EXCLUSIVE`), `check_same_thread`, `cached_statements` |
| `hsqldb` | `user`, `jdbc_url`, `jdbc_jar` | `password`, `jdbc_driver`, `connection_properties` (propiedades JDBC). Sin Engine de SQLAlchemy ni pool: conexión nativa única |

### Problemas frecuentes

| Escenario / Error | Causa probable | Solución |
|---|---|---|
| `No module named 'psycopg'` / `'mariadb'` / `'pymysql'` | Driver no instalado | Instalar el extra `postgresql` / `mariadb` / `mysql` (ver §3.1) |
| MySQL 8 contra servidor MySQL con `db_type="mariadb"` | Funciona: el conector de MariaDB también conecta con MySQL | Para usar PyMySQL y el catálogo de MySQL, `db_type="mysql"` |
| `pyodbc.Error: ('IM002'...)` | ODBC driver de SQL Server no instalado en el SO | Instalar el [Microsoft ODBC Driver](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server); usar `pymssql` si no es posible |
| `DPI-1047: Cannot locate a 64-bit Oracle Client library` | Modo thick (`oracle_thick_mode=True`) sin Oracle Instant Client localizable | Indicar `oracle_client_path`, o usar el modo thin (por defecto), que no necesita Instant Client |
| MySQL async con `ssl_*` en Windows: `Can't connect to MySQL server` (`SSLWantReadError`) | aiomysql no negocia TLS con el `ProactorEventLoop` por defecto de Windows (también sin util_bbdd) | `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` antes de crear el loop |
| `encryption='mandatory' pero la sesión pymssql no va cifrada` | El FreeTDS de pymssql (p. ej. el wheel de Windows) acepta `require` y no cifra | `sql_server_driver="pyodbc"` con ODBC Driver 17/18 (`Encrypt=yes`) |
| `Para oracle debe informar 'dsn' o 'service_name' o 'sid' o 'database'` | Falta el identificador de servicio Oracle | Añadir una de esas 4 claves |
| `Parametro invalido para sqlserver: encryption=...` | Valor fuera de `mandatory`/`optional`/`off` | Corregir `encryption` |
| Error async con HSQLDB | HSQLDB no soporta async | Usar `SyncDatabaseManager` (HSQLDB es solo síncrono) |
| `Server has gone away` (MariaDB/MySQL) | Conexión caducada en cargas largas | Obtener el engine con `get_sqlalchemy_engine()` (incluye `pool_pre_ping`) |
| El `schema` PostgreSQL parece ignorado | `schema` no es un parámetro libpq | La librería lo traduce a `options=-c search_path=<schema>` automáticamente |
| `UnicodeDecodeError` en MariaDB al generar documentación | Encoding mismatch: servidor `latin1` vs. cliente `utf8mb4` | Usar `init_command` y `catalog_charset_mode="convert"` (ver §6; `encoding_errors` no tiene efecto) |
| `MetadataError: … SystemError del driver mariadb … fetchrows` con `use_pool=True` y servidor en `latin1` (hasta v0.40.2; el diagnóstico dice `utf8mb4_clean`) | El reset de sesión del pool nativo deshacía `init_command` | Actualizar a v0.40.3 o, en versiones anteriores, `use_pool=False` (ver §6) |
| `ValidationError: … init_command admite una sola sentencia` (o, hasta v0.40.1, `You have an error in your SQL syntax … near 'SET NAMES utf8mb4'`) | `init_command` con varias sentencias separadas por `;` | Un solo `SET` con comas: `SET SESSION character_set_server = utf8mb4, NAMES utf8mb4` (ver §6) |
| `CERT_E_CN_NO_MATCH` (MariaDB sync) o error de conexión TLS (async) con `ssl_ca` | El nombre o la IP de `host` no figura en el certificado del servidor; el conector de MariaDB no permite verificar solo la CA | Conectar con un nombre que esté en el certificado (ver [TLS en MariaDB](#tls-en-mariadb-ssl-ssl_ca-ssl_cert-ssl_key-ssl_verify_cert-desde-v0390)) |
| WARNING `trust_cert no tiene efecto con pymssql` | pymssql no admite `trust_cert`: la validación del certificado depende de FreeTDS | `sql_server_driver="pyodbc"` (ver [TLS en SQL Server](#tls-en-sql-server-encryption-y-trust_cert)) |

### TLS en SQL Server: `encryption` y `trust_cert`

`encryption` (`mandatory`/`optional`/`off`, por defecto `optional`) y `trust_cert` (por defecto `False`) se traducen de
forma distinta según el driver:

| Driver | `encryption` | `trust_cert` |
|---|---|---|
| `pyodbc` (sync) y `aioodbc` (async) | `Encrypt=yes` con `mandatory`; `Encrypt=no` en el resto (ODBC Driver 18 lo trata como `Optional`) | `TrustServerCertificate=yes/no` |
| `pymssql` (sync, por defecto) | `mandatory` → `require`, `off` → `off`; con `optional` manda la configuración de FreeTDS | **Sin efecto** (límite del driver) |

pymssql no tiene ningún parámetro para confiar en el certificado del servidor: la validación depende de FreeTDS (`ca
file` en `freetds.conf`), no de la conexión. Por eso, con pymssql y `trust_cert=True`, la librería no puede aplicar el
parámetro y, desde v0.39.2, emite un WARNING una vez por servidor y proceso (antes se ignoraba sin avisar). Para
controlar la validación del certificado por conexión, usa pyodbc:

```python
conn_params = {"host": "sql.example", "user": "app", "password": "pwd", "database": "ventas",
               "sql_server_driver": "pyodbc", "driver_name": "ODBC Driver 18 for SQL Server",
               "encryption": "mandatory", "trust_cert": True}
```

Con pymssql y `encryption="mandatory"`, la librería comprueba que la sesión va cifrada (requiere `VIEW SERVER STATE`;
sin ese permiso solo avisa) y falla si no lo está: algunos FreeTDS, como el del wheel de Windows, aceptan `require` y no
cifran.

### 6. Parámetros especiales de MariaDB: `init_command` y `encoding_errors`

A partir de **v0.35.0**, `MariaDBConnectionConfig` incluye dos parámetros que mitigan conflictos de charset
común cuando el servidor está configurado en `latin1` pero queremos usar `utf8mb4`:

#### **`init_command`** (string, default `"SET NAMES utf8mb4"`)

SQL ejecutado en cada conexión sync y de pool (MariaDB Connector/Python). Es siempre `SET NAMES utf8mb4` por
defecto: el conector solo trabaja en utf8mb4 y rechaza otras sesiones (`ProgrammingError: Character set 'latin1' is
not supported`, comprobado con 1.1.14). El conector tampoco admite el parámetro `charset`: la librería no se lo envía;
`charset` (solo letras, dígitos y `_`) lo usa la conexión async (aiomysql). v0.35.6 hacía el valor por defecto
`SET NAMES <charset>`, que impedía conectar con `charset="latin1"`; v0.35.7 lo revierte. En async (aiomysql) el valor
por defecto no se envía (pisaría `charset`), pero desde v0.39.2 uno propio sí: p. ej.
`init_command="SET time_zone = '+00:00'"` se aplica en sync, async y pools.

`init_command` admite **una sola sentencia**: MariaDB no ejecuta varias separadas por `;`. Para fijar varias
variables, usa un solo `SET` con comas:

```python
conn_params = {"host": "localhost", "user": "app", "password": "pwd", "database": "ventas",
               # no: "SET SESSION character_set_server = utf8mb4; SET NAMES utf8mb4;"
               "init_command": "SET SESSION character_set_server = utf8mb4, NAMES utf8mb4"}
```

Desde v0.40.2, varias sentencias lanzan `ValidationError` al crear el manager. Antes fallaban al conectar con un error
de sintaxis del servidor («near 'SET NAMES utf8mb4'») que no nombraba el parámetro. Se admiten un `;` final y los `;`
dentro de comillas.

Con `use_pool=True` (pool nativo `mariadb.ConnectionPool`), desde v0.40.3 `init_command` se ejecuta en **cada**
`get_connection()`: el pool reinicia la sesión al reutilizar una conexión y la devuelve al charset del servidor. Hasta
v0.40.2, con el servidor en `latin1`, la segunda lectura del catálogo por la misma conexión fallaba con
`SystemError … fetchrows`.
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
    snapshot = db.get_schema_metadata()  # Sin errores de encoding
```

#### **`catalog_charset_mode`** (MariaDB y MySQL, default `"auto"`, desde v0.38.0)

Cómo leen los managers el catálogo (`information_schema`) en MariaDB y MySQL, sync y async:

| Valor | Qué hace | Cuándo usarlo |
|---|---|---|
| `"auto"` | Diagnostica el charset del servidor (una consulta, una vez por manager; desde v0.39.3) y lee sin `CONVERT` si todo está en utf8mb4, o con `CONVERT` si detecta mezcla o servidores antiguos | Por defecto |
| `"native"` | Lee sin `CONVERT` y sin diagnóstico | Servidores en utf8mb4: ahorra el diagnóstico. Con comentarios guardados en latin1 puede fallar con `UnicodeDecodeError` |
| `"convert"` | Aplica siempre `CONVERT(CAST(... AS BINARY) USING utf8mb4)` a los campos de texto del catálogo, sin diagnóstico | Servidores con charset mezclado o heredado |

Otro valor lanza `ValidationError` al crear el manager. No afecta a la conexión ni a los datos, solo a las consultas de
metadatos de los managers (el Engine de SQLAlchemy de bulk/dump no lo usa). Hasta v0.39.2, con un schema sin tablas
`"auto"` diagnosticaba mezcla y usaba `CONVERT` aunque el servidor estuviera en utf8mb4 (mismo resultado).

```python
conn_params = {"host": "localhost", "user": "app", "password": "pwd", "database": "ventas",
               "catalog_charset_mode": "native"}
```

#### TLS en MariaDB: `ssl`, `ssl_ca`, `ssl_cert`, `ssl_key`, `ssl_verify_cert` (desde v0.39.0)

Sin ninguna de estas claves la conexión no se cifra (como antes de v0.39.0). Cualquiera de ellas activa TLS en la
conexión y el pool sync, la conexión y el pool async y los Engine de bulk/dump. Si el TLS falla, la conexión falla: no
se reintenta sin cifrar.

| Clave | Efecto |
|---|---|
| `ssl=True` | Cifra. En sync, MariaDB 11.4+ verifica el certificado del servidor sin CA (por huella derivada de la contraseña); en async (aiomysql) cifra **sin verificar** y avisa con un WARNING |
| `ssl_ca` | Cifra y **verifica** el certificado del servidor contra esa CA (sync y async) |
| `ssl_cert` + `ssl_key` | Certificado de cliente |
| `ssl_verify_cert` | `False` desactiva la verificación (p. ej. CA de pruebas); con `ssl_ca` vale `True` por defecto |

```python
conn_params = {"host": "db.example", "user": "app", "password": "pwd", "database": "ventas",
               "ssl_ca": "/etc/ssl/mariadb-ca.pem"}
```

Para verificar el certificado también en async, indica `ssl_ca`. Con el conector sync, `ssl_ca` sin verificación no
exige esa CA; por eso la librería activa `ssl_verify_cert` cuando hay `ssl_ca`.

Con `ssl_ca` se verifican la CA **y el hostname**: el nombre o la IP con que conectas debe figurar en el certificado
del servidor (si no, `CERT_E_CN_NO_MATCH` en sync o error de conexión en async). No hay forma de verificar la CA sin el
hostname: MariaDB Connector/Python no tiene equivalente a `ssl_verify_identity`. Excepción del conector sync
(Connector/C 3.4): conectando como `localhost` no comprueba el hostname (sí la CA); aiomysql lo comprueba siempre.
Las rutas de `ssl_ca`, `ssl_cert` y `ssl_key` pueden ser relativas al directorio de trabajo (comprobado con
Connector/Python 1.1.14, aunque su documentación pida rutas absolutas).

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

Para el detalle de drivers PostgreSQL (psycopg 3 y asyncpg, pooling), ver la
[guía de drivers PostgreSQL](postgresql_driver_guide.md). Para el contrato completo de los managers,
ver [Gestión de Conexiones (Sync)](../functional/managers_sync.md) y
[(Async)](../functional/managers_async.md).
