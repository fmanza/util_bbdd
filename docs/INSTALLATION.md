# Guía de Instalación — util_bbdd

Esta guía proporciona instrucciones detalladas para instalar `util_bbdd` en diferentes sistemas operativos y bases de datos.

**Version:** 0.7.0
**Requisitos:** Python 3.12+

---

## Instalación Rápida

```bash
pip install util_bbdd
```

---

## Internal Dependencies

| Dependencia | Propósito | Ubicación |
|---|---|---|
| `util @ git+https://github.com/fmanza/util.git@develop` | Timing automático en operaciones CRUD bulk | pyproject.toml |

**Nota**: La dependencia `util` es requerida (incluida en `dependencies`, no en optional-dependencies). Proporciona el decorador `@medir_tiempo` para capturar duración de operaciones. Si no está disponible, operaciones continúan funcionando con timing=0 ms (fallback graceful).

**Troubleshooting de instalación de `util`**: Si `pip install util_bbdd` falla al resolver `util @ git+...`
(por ejemplo, en entornos sin acceso a GitHub, CI offline o redes corporativas), instala primero
la dependencia manualmente:

```bash
pip install git+https://github.com/fmanza/util.git@develop
pip install util_bbdd --no-deps
```

---

## Instalación desde Fuente (Desarrollo)

Si deseas contribuir o trabajar con la versión de desarrollo:

```bash
git clone https://github.com/fmanza/util_bbdd.git
cd util_bbdd

# Crear entorno virtual
python -m venv venv

# Activar entorno (Windows)
.\venv\Scripts\Activate.ps1

# Activar entorno (Linux/Mac)
source venv/bin/activate

# Instalar en modo editable con dependencias de desarrollo
pip install -e ".[dev]"
```

---

## Matriz de Dependencias por Motor

`util_bbdd` soporta múltiples bases de datos. Instala directamente el driver del motor que uses
— los drivers **no** forman parte de los extras de `util_bbdd`; se instalan por separado.

### 1. PostgreSQL (recomendado para empezar)

**Driver:** `psycopg2-binary` (sync) o `asyncpg` (async)

```bash
# Sync
pip install psycopg2-binary

# Async
pip install asyncpg

# Ambos
pip install psycopg2-binary asyncpg
```

**Verificación:**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "database": "test_db"
    }
)
print("Conexión OK:", manager.get_tables())
manager.close()
```

---

### 2. MariaDB / MySQL

**Driver:** `pymysql` (sync) o `aiomysql` (async)

```bash
# Sync
pip install pymysql

# Async
pip install aiomysql
```

**Verificación:**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "secret",
        "database": "test_db"
    }
)
print("Conexión OK:", manager.get_tables())
manager.close()
```

---

### 3. SQLite

**Driver:** `sqlite3` (incluido en Python)

SQLite no requiere instalación adicional del driver. Solo instala `util_bbdd`:

```bash
pip install util_bbdd
```

**Verificación (en memoria):**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)
print("Conexión OK:", manager.get_tables())
manager.close()
```

**Verificación (archivo):**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": "./test.db"}
)
print("Conexión OK:", manager.get_tables())
manager.close()
```

---

### 4. Oracle

**Driver:** `oracledb` (sync/async, ya incluido en las dependencias base de `util_bbdd`)

El driver `oracledb` se instala automáticamente con `util_bbdd`. No requiere pasos adicionales
para el driver. Sin embargo, Oracle puede necesitar el **Oracle Instant Client** en el sistema
operativo para conexiones nativas. Consulta [Configuración de Drivers](POSTGRESQL_DRIVER_GUIDE.md)
para detalles de configuración avanzada.

**Verificación:**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="oracle",
    conn_params={
        "host": "localhost",
        "port": 1521,
        "user": "admin",
        "password": "secret",
        "sid": "ORCL"
    }
)
print("Conexión OK:", manager.get_tables())
manager.close()
```

---

### 5. SQL Server

**Driver:** `pyodbc` (sync) o `aioodbc` (async)

```bash
# Sync
pip install pyodbc

# Async
pip install aioodbc
```

**Nota:** SQL Server requiere el ODBC driver nativo instalado en el SO (ver sección de troubleshooting).

**Verificación:**
```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlserver",
    conn_params={
        "host": "localhost",
        "port": 1433,
        "user": "sa",
        "password": "YourPassword123",
        "database": "test_db",
        "driver": "ODBC Driver 17 for SQL Server"
    }
)
print("Conexión OK:", manager.get_tables())
manager.close()
```

---

### 6. HSQLDB

**Driver:** `jaydebeapi` + Java (sync únicamente)

```bash
pip install jaydebeapi
```

**Nota:** HSQLDB requiere Java instalado en el sistema.

**Características:**
- ✅ Sync solamente (sin async)
- ✅ Ideal para testing y prototipos
- ❌ No soporta async

---

## Tabla de Resumen: Dependencias por Motor

| Motor      | Sync Driver          | Async Driver | Instalación del driver         | Notas |
|------------|----------------------|--------------|--------------------------------|-------|
| PostgreSQL | `psycopg2-binary`    | `asyncpg`    | `pip install psycopg2-binary`  | Recomendado |
| MariaDB    | `pymysql`            | `aiomysql`   | `pip install pymysql`          | MySQL compatible |
| SQLite     | `sqlite3` (built-in) | `aiosqlite`  | (incluido en Python)           | No requiere driver externo |
| Oracle     | `oracledb`           | `oracledb`   | (incluido con `util_bbdd`)     | Puede requerir Oracle Instant Client |
| SQL Server | `pyodbc`             | `aioodbc`    | `pip install pyodbc`           | Requiere ODBC driver nativo |
| HSQLDB     | `jaydebeapi`         | ❌ N/A        | `pip install jaydebeapi`       | Solo sync, requiere Java |

---

## Solución de Problemas Comunes

### Error: "No module named 'psycopg2'"

**Causa:** El driver de PostgreSQL no está instalado.

**Solución:**
```bash
pip install psycopg2-binary
```

---

### Error: "No module named 'pymysql'"

**Causa:** El driver de MariaDB/MySQL no está instalado.

**Solución:**
```bash
pip install pymysql
```

---

### Error: "pyodbc.Error: ('IM002'...)" (SQL Server)

**Causa:** ODBC driver no está instalado en el SO.

**Solución (Windows):**
1. Descargar [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
2. Instalar el ejecutable
3. Reiniciar Python/IDE

**Solución (Linux):**
```bash
sudo apt-get install unixodbc-dev
pip install pyodbc
```

---

### Error: "Timeout esperando conexión del pool"

**Causa:** El pool de conexiones se agotó; demasiadas conexiones abiertas.

**Solución:**
```python
# Aumentar el tamaño del pool
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        # ... configuración estándar ...
        "pool_size": 20,  # Aumentar de 10 a 20
        "max_overflow": 40,  # Conexiones adicionales temporales
    }
)
```

Vea [EXCEPTIONS.md](EXCEPTIONS.md) para más detalles sobre excepciones.

---

### Error: "oracledb.DatabaseError: DPY-2014"

**Causa:** No se encontró el client library de Oracle.

**Solución:**
1. Descargar [Oracle Instant Client](https://www.oracle.com/database/technologies/instant-client/downloads.html)
2. Descomprimir y configurar la ruta (ver docs específico Oracle)
3. Usar `oracle_client_path` en `conn_params`

```python
manager = SyncDatabaseManager(
    db_type="oracle",
    conn_params={
        "host": "localhost",
        "port": 1521,
        "user": "admin",
        "password": "secret",
        "sid": "ORCL",
        "oracle_client_path": "/opt/oracle/instantclient_21_0"  # Linux/Mac
        # "oracle_client_path": "C:\\instantclient_21_0"  # Windows
    }
)
```

---

## Verificación de Instalación

Ejecuta este script para verificar que `util_bbdd` está correctamente instalado:

```python
#!/usr/bin/env python
"""Verificar instalación de util_bbdd."""

from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager
from util_bbdd._drivers import get_supported_db_types

print("✅ util_bbdd instalado correctamente")
print("\nMotores soportados:", get_supported_db_types())

# Prueba conexión SQLite (sin configuración externa)
try:
    mgr = SyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": ":memory:"}
    )
    mgr.execute_custom_many("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    tables = mgr.get_tables()
    mgr.close()
    print("✅ SyncDatabaseManager funciona (SQLite)")
except Exception as e:
    print(f"❌ Error en SyncDatabaseManager: {e}")

print("\n✅ Instalación completada exitosamente")
```

Ejecuta con:
```bash
python verify_installation.py
```

---

## Próximos Pasos

1. Consulta [Quick Start](index.md#quick-start-5-minutos) para ejemplos rápidos
2. Lee [EXCEPTIONS.md](EXCEPTIONS.md) para manejo de errores
3. Explora [SchemaComparator](COMPARATOR.md) para comparación de esquemas

---

## Links Útiles

- [Documentación de PostgreSQL](https://www.postgresql.org/docs/)
- [MariaDB Knowledge Base](https://mariadb.com/kb/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Oracle Database Documentation](https://docs.oracle.com/en/database/oracle/oracle-database/)
- [SQL Server Documentation](https://learn.microsoft.com/en-us/sql/sql-server/)
