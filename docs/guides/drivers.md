# Guía de Configuración de Drivers de Bases de Datos

## Descripción General

Esta guía cubre la selección y configuración de drivers para cada base de datos soportada en util_bbdd, con énfasis en los requisitos únicos de Oracle y sus limitaciones de compatibilidad.

---

## Oracle: Requisitos de la Librería Cliente

### Introducción

Las conexiones a Oracle requieren una librería cliente de Oracle. util_bbdd soporta dos modos:

- **Thin Mode** (predeterminado): Python puro, requiere Python 3.8+, solo asincrónico, Oracle 12c en adelante
- **Thick Mode** (recomendado para 11g): Requiere Oracle Instant Client, solo sincrónico, soporta Oracle 11g a 23c

### Thin Mode

**Recomendado para:**
- Aplicaciones asincrónicas con Oracle 12c o posterior
- Desarrollo y pruebas
- Entornos donde Instant Client no está disponible

**Configuración:**
```python
from util_bbdd import AsyncDatabaseManager

manager = AsyncDatabaseManager(
    db_type="oracle",
    conn_params={
        "user": "scott",
        "password": "tiger",
        "dsn": "oracle-host:1521/ORCL",
        "oracle_thick_mode": False,  # Predeterminado; explícito para claridad
    },
)

# Funciona con async/await
snapshot = await manager.get_schema_metadata()
```

**Limitaciones:**
- Sin soporte para Oracle 11g (usa protocolo Python puro; Oracle 11g es anterior a este protocolo)
- Solo asincrónico (sin conexión sincrónica)

---

### Thick Mode

**Recomendado para:**
- Soporte de Oracle 11g (requerido)
- Cargas de trabajo sincrónicas
- Aplicaciones que necesitan características completas del cliente Oracle

**Requisitos:**
1. **Oracle Instant Client 19** o versión compatible (ver tabla de compatibilidad más abajo)
2. **python-oracledb** 1.0+
3. **Solo código sincrónico** (asincrónico no es compatible con thick mode)

#### Matriz de Compatibilidad de Oracle Instant Client

| Versión de Base de Datos Oracle | Versión de Instant Client | Versión de python-oracledb | Notas |
|---|---|---|---|
| 11g (11.2.0.x) | 19.x | 1.0+ | Recomendado para soporte de 11g |
| 11g (11.2.0.x) | 23.x | 1.0+ | Puede funcionar pero 19.x es preferido |
| 12c (12.1.x) | 19.x–23.x | 1.0+ | Soporte completo |
| 12c R2 (12.2.x) | 19.x–23.x | 1.0+ | Soporte completo |
| 19c | 19.x–23.x | 1.0+ | Soporte completo |
| 21c | 21.x–23.x | 1.0+ | Soporte completo |
| 23c | 23.x | 1.0+ | Soporte completo; driver debe ser 23.x o posterior |

**Puntos clave:**
- La versión de Instant Client debe ser ≥ versión mínima soportada por la base de datos destino
- Para Oracle 11g, Instant Client 19 es la opción recomendada
- Instant Client 23 puede funcionar con 11g pero recibe menos pruebas

#### Instalación

1. **Descargar Oracle Instant Client:**
   - Visita [Descargas de Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client/downloads.html)
   - Selecciona tu SO (Linux, Windows, macOS)
   - Descarga el paquete "Basic" para tu arquitectura (x86_64, ARM64, etc.)

2. **Extrae el paquete:**
   ```bash
   # Linux / macOS
   mkdir -p ~/oracle/instantclient_19_x
   unzip instantclient-basic-linux.x64-19.*.zip -d ~/oracle/

   # Windows
   REM Extrae a C:\oracle\instantclient_19_x
   ```

3. **Configura la ruta de la librería (solo Linux/macOS):**
   ```bash
   export LD_LIBRARY_PATH=$HOME/oracle/instantclient_19_x:$LD_LIBRARY_PATH
   ```

4. **Instala python-oracledb:**
   ```bash
   pip install oracledb
   ```

#### Configuración

Activa thick mode estableciendo `oracle_thick_mode=True` y proporcionando la ruta del cliente:

```python
from util_bbdd import SyncDatabaseManager

# Uso sincrónico
manager = SyncDatabaseManager(
    db_type="oracle",
    conn_params={
        "user": "scott",
        "password": "tiger",
        "service_name": "ORCL",  # Usa service_name para 11g
        "oracle_thick_mode": True,
        "oracle_client_path": "/home/user/oracle/instantclient_19_x",
    },
)

# Funciona con código sincrónico (no-async)
snapshot = manager.get_schema_metadata()
```

**Parámetros:**
- `oracle_thick_mode` (bool, predeterminado=False): Habilita thick mode
- `oracle_client_path` (str): Ruta al directorio de Oracle Instant Client (requerido si oracle_thick_mode=True)

**Identificadores de Conexión:**
Para Oracle 11g, prefiere `service_name` sobre `dsn` o `sid`:
```python
# Recomendado para 11g
conn_params = {
    "user": "scott",
    "service_name": "ORCL",
    ...
}

# Alternativa (11g)
conn_params = {
    "user": "scott",
    "sid": "ORCL",
    ...
}

# No recomendado para 11g
conn_params = {
    "user": "scott",
    "dsn": "oracle-host:1521/ORCL",
    ...
}
```

#### Seguridad de Hilos

La inicialización de thick mode es **segura para hilos** mediante bloqueo interno:
- La primera llamada a `init_oracle_thick_mode()` tiene éxito y bloquea el modo
- Las llamadas posteriores desde otros hilos se devuelven sin re-inicializar
- El código asincrónico no puede inicializar thick mode (lanza `ConnectionError`)

Ejemplo (multi-hilo):
```python
import threading
from util_bbdd import SyncDatabaseManager

def init_oracle(thread_id):
    try:
        manager = SyncDatabaseManager(
            db_type="oracle",
            conn_params={
                "user": "scott",
                "service_name": "ORCL",
                "oracle_thick_mode": True,
                "oracle_client_path": "/ruta/a/instant/client",
            },
        )
        print(f"Hilo {thread_id}: OK")
    except Exception as e:
        print(f"Hilo {thread_id}: Error - {e}")

# Seguro llamar desde múltiples hilos
threads = [
    threading.Thread(target=init_oracle, args=(i,))
    for i in range(5)
]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

#### Resolución de Problemas

| Error | Causa | Solución |
|---|---|---|
| `DPI-1047: Cannot locate a 32-bit Oracle Client` | Arquitectura incorrecta | Descarga Instant Client que coincida con tu intérprete Python (64-bit para x86_64, etc.) |
| `ORA-00000: Oracle client library initialization failed` | Instant Client no encontrado | Verifica que `oracle_client_path` apunte al directorio de Instant Client extraído |
| `ConnectionError: El modo asincrónico no es compatible con thick mode` | Se intentó async con thick mode | Usa código sincrónico o desactiva thick mode (usa thin mode en su lugar) |
| `ORA-12154: TNS:could not resolve the connect identifier` | Nombre de servicio inválido | Verifica el nombre del servicio de base de datos y la configuración de red |

---

## Oracle: Selección de Catálogo Consciente de la Versión

util_bbdd detecta automáticamente la versión de Oracle y carga el dialecto apropiado:

- **Oracle 11g (11.2.x)**: Usa `Oracle11Catalog` (omite soporte de columnas IDENTITY)
- **Oracle 12c y posterior**: Usa `OracleCatalog` (soporte completo de columnas IDENTITY)

Esta detección es **perezosa** (ocurre en la primera consulta de metadatos) y **cacheada** (una sola llamada por conexión).

### Cómo Funciona

1. **Primera consulta de metadatos** desencadena la detección de versión
2. **SQL de versión** se ejecuta: `SELECT version FROM product_component_version WHERE product LIKE 'Oracle Database%' AND ROWNUM = 1`
3. **Selección de dialecto**: Si versión < 12.0, usa Oracle11Catalog; si no, OracleCatalog
4. **Cacheado** para toda la duración de la conexión

No se requieren consultas adicionales ni configuración manual.

---

## Otras Bases de Datos

### PostgreSQL

**Driver:** `psycopg` (v3) + `psycopg-pool` (sync) y `asyncpg` (async). `psycopg2` no lo usan los managers; solo
sirve para Engines propios `postgresql+psycopg2://` (p. ej. la estrategia `execute_values` de `bulk`).

**Instalación:**
```bash
pip install "util_bbdd[postgresql]"  # psycopg[binary], psycopg-pool y asyncpg
```

**Configuración:**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "user": "postgres",
        "password": "contraseña",
        "host": "localhost",
        "port": 5432,
        "database": "mibd",
    },
)
```

### MySQL / MariaDB

Desde v0.19.0 son dos motores distintos, con las mismas claves de `conn_params`:

| `db_type` | Driver sync | Driver async | Instalación |
|---|---|---|---|
| `mariadb` | `mariadb` (MariaDB Connector/Python) | `aiomysql` | `pip install "util_bbdd[mariadb]"` |
| `mysql` | `pymysql` | `aiomysql` | `pip install "util_bbdd[mysql]"` |

**Limitación del driver (MariaDB):** MariaDB Connector/Python no tiene `ssl_verify_identity`. Con `ssl_ca` verifica
la CA y el hostname a la vez, sin forma de verificar solo la CA: el nombre o la IP con que conectas debe figurar en el
certificado del servidor. Ver [TLS en MariaDB](connection_guide.md#tls-en-mariadb-ssl-ssl_ca-ssl_cert-ssl_key-ssl_verify_cert-desde-v0390).
Con `db_type="mysql"` (PyMySQL) sí existe `ssl_verify_identity`.

**Configuración:**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="mysql",
    conn_params={
        "user": "root",
        "password": "contraseña",
        "host": "localhost",
        "port": 3306,
        "database": "mibd",
    },
)
```

### SQL Server

**Driver:** `pymssql` (sync, por defecto) o `pyodbc` (sync, con `sql_server_driver="pyodbc"`); `aioodbc` en async.
pyodbc y aioodbc necesitan el [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
del sistema operativo.

**Instalación:**
```bash
pip install pyodbc aioodbc
# o, solo sync
pip install pymssql
```

**Configuración:**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlserver",
    conn_params={
        "user": "sa",
        "password": "contraseña",
        "host": "localhost",
        "port": 1433,
        "database": "mibd",
        "sql_server_driver": "pyodbc",
        "driver_name": "ODBC Driver 17 for SQL Server",  # solo pyodbc
    },
)
```

**Limitación del driver (pymssql):** `trust_cert` no tiene efecto con pymssql, porque la validación del certificado
depende de FreeTDS (`freetds.conf`) y no de la conexión. Desde v0.39.2 la librería avisa con un WARNING una vez por
servidor y proceso. Para controlarla por conexión, usa pyodbc o aioodbc. Ver
[TLS en SQL Server](connection_guide.md#tls-en-sql-server-encryption-y-trust_cert).

### SQLite

**Driver:** `sqlite3` integrado

**Configuración:**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={
        "database": "/ruta/a/base_de_datos.db",
    },
)
```

---

## Referencias

- [Documentación de python-oracledb](https://python-oracledb.readthedocs.io/)
- [Descargas de Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client/downloads.html)
- [Documentación de Oracle Database 11g](https://docs.oracle.com/cd/E11882_01/server.112/e10897/toc.htm)
- [Documentación de Oracle Database 12c+](https://docs.oracle.com/en/database/index.html)

---

*Última actualización: 2025-01-15*
