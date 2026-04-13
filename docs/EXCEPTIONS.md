# Guía de Excepciones — util_bbdd

`util_bbdd` proporciona una jerarquía estructurada de excepciones para facilitar el manejo de errores específicos en operaciones de base de datos.

**Version:** 0.6.7

---

## Jerarquía de Excepciones

```
DatabaseException (base)
│
├── ConnectionError
│   ├── PoolConnectionError
│   │   ├── PoolExhaustedError
│   │   └── PoolTimeoutError
│   └── [otros errores de conexión]
│
├── QueryError
│   ├── QueryTimeoutError
│   ├── QueryExecutionError
│   ├── QueryNotFoundError
│   ├── QueryValidationError
│   └── QueryParameterError
│
├── MetadataError
│   ├── MetadataFetchError
│   ├── MetadataNormalizationError
│   └── DDLBuildError
│
├── ValidationError
│   ├── InvalidDatabaseType
│   ├── InvalidConnectionConfig
│   └── InvalidQueryParameters
│
├── DriverError
│   ├── DriverNotFoundError
│   └── DriverConfigurationError
│
└── DatabaseOperationError
    └── DatabaseConfigurationError
```

---

## Categoría 1: Errores de Conexión y Pool

Estos errores ocurren cuando hay problemas al conectarse a la base de datos o gestionar el pool de conexiones.

### `ConnectionError` — Error base de conexión

Indica un problema general de conexión a la base de datos.

**Causas comunes:**
- Servidor de BD no accesible
- Credenciales incorrectas
- Red desconectada

**Ejemplo:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import ConnectionError

try:
    manager = SyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "invalid-host",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "mydb"
        }
    )
except ConnectionError as e:
    print(f"No se pudo conectar: {e.message}")
    print(f"Detalles: {e.details}")
```

---

### `PoolConnectionError` — Error obteniendo conexión del pool

Indica un problema al obtener o devolver una conexión del pool.

**Causas comunes:**
- Pool no inicializado
- Conexión cerrada inesperadamente
- Error al devolver conexión

**Ejemplo:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import PoolConnectionError

try:
    manager = SyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": ":memory:"}
    )
    # ... operaciones ...
    manager.close()
    # Intentar usar después de cerrar
    manager.get_tables()
except PoolConnectionError as e:
    print(f"Error del pool: {e.message}")
```

---

### `PoolExhaustedError` — Pool de conexiones agotado

El pool alcanzó el máximo de conexiones y no hay más disponibles.

**Causas comunes:**
- Pool muy pequeño para la carga
- Conexiones no liberadas (memory leak)
- Demasiadas operaciones concurrentes

**Solución:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import PoolExhaustedError

try:
    manager = SyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "mydb",
            "pool_size": 10,           # Tamaño del pool
            "max_overflow": 20,        # Conexiones temporales adicionales
        }
    )
except PoolExhaustedError as e:
    print(f"Pool agotado: máx. {e.max_connections} conexiones")
    # Aumentar pool_size o max_overflow
```

---

### `PoolTimeoutError` — Timeout esperando conexión

Se agotó el tiempo esperando una conexión disponible del pool.

**Causas comunes:**
- Todas las conexiones en uso
- Conexión "colgada" (deadlock)
- Pool muy pequeño

**Solución:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import PoolTimeoutError

try:
    manager = SyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "mydb",
            "pool_timeout": 30,  # Aumentar timeout (segundos)
            "pool_size": 20,     # Aumentar tamaño del pool
        }
    )
except PoolTimeoutError as e:
    print(f"Timeout: {e.timeout_seconds}s excedido")
```

---

## Categoría 2: Errores en Ejecución de Queries

Estos errores ocurren al ejecutar consultas SQL.

### `QueryError` — Error base de query

Error genérico al ejecutar una query.

**Ejemplo:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import QueryError

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

try:
    # Query con sintaxis incorrecta
    manager.execute_custom_many("SELECT * FORM users")  # FORM en lugar de FROM
except QueryError as e:
    print(f"Error en query: {e.message}")
    print(f"Operación: {e.operation}")
    print(f"BD: {e.db_type}")

manager.close()
```

---

### `QueryTimeoutError` — Query excedió timeout

La query tardó más del tiempo permitido.

**Causas comunes:**
- Query muy compleja
- Tabla sin índices
- Servidor saturado

**Ejemplo:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import QueryTimeoutError

try:
    manager = SyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "mydb",
            "statement_timeout": 5000,  # 5 segundos
        }
    )
    # Query larga
    result = manager.execute_custom_many(
        "SELECT * FROM huge_table WHERE status = 'pending'"
    )
except QueryTimeoutError as e:
    print(f"Query timeout: {e.message}")
    # Optimizar query, agregar índices, aumentar timeout

manager.close()
```

---

### `QueryExecutionError` — Error durante ejecución

Error específico durante la ejecución de la query (violación de constraint, etc.).

**Ejemplo:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import QueryExecutionError

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

try:
    manager.execute_custom_many(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    # Intentar insert sin valor obligatorio
    manager.execute_custom_many("INSERT INTO users (id) VALUES (1)")
except QueryExecutionError as e:
    print(f"Error en ejecución: {e.message}")
    print(f"Detalles: {e.details}")

manager.close()
```

---

### `QueryNotFoundError` — Query no existe en registry

La query solicitada no está registrada.

**Ejemplo:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import QueryNotFoundError

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

try:
    # Query_name que no existe en el registry
    manager.execute_query_from_registry("nonexistent_query")
except QueryNotFoundError as e:
    print(f"Query no encontrada: {e.message}")

manager.close()
```

---

### `QueryValidationError` — Parámetros inválidos

Los parámetros de la query no cumplen las reglas de validación.

**Ejemplo:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import QueryValidationError

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

try:
    # Parámetro requerido faltante
    manager.execute_query_from_registry(
        "get_user_by_id",
        params={}  # Falta 'user_id'
    )
except QueryValidationError as e:
    print(f"Validación fallida: {e.message}")

manager.close()
```

---

## Categoría 3: Errores de Metadatos

Estos errores ocurren al obtener o procesar metadatos de la base de datos.

### `MetadataError` — Error base de metadatos

Error genérico en operación de metadatos.

**Ejemplo:**
```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import MetadataError

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

try:
    # Obtener columnas de tabla inexistente
    columns = manager.get_columns("nonexistent_table")
except MetadataError as e:
    print(f"Error de metadatos: {e.message}")

manager.close()
```

---

### `MetadataFetchError` — Error obteniendo metadatos

No se pudieron obtener los metadatos de la BD.

**Causas comunes:**
- Tabla no existe
- Insuficientes permisos
- Motor no soporta operación

---

### `MetadataNormalizationError` — Error normalizando

Error al normalizar metadatos para formato interno.

---

### `DDLBuildError` — Error construyendo DDL

Error al generar sentencias DDL desde metadatos.

---

## Categoría 4: Errores de Validación

Estos errores indican datos o configuración inválida.

### `ValidationError` — Error base de validación

Error en validación de datos.

---

### `InvalidDatabaseType` — Motor no soportado

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import InvalidDatabaseType

try:
    manager = SyncDatabaseManager(
        db_type="mongodb",  # No soportado
        conn_params={"host": "localhost"}
    )
except InvalidDatabaseType as e:
    print(f"Motor no soportado: {e.message}")
    print(f"Use uno de: postgresql, mariadb, sqlite, oracle, sqlserver, hsqldb")
```

---

### `InvalidConnectionConfig` — Configuración inválida

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import InvalidConnectionConfig

try:
    manager = SyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            # Faltan parámetros requeridos
            "host": "localhost"
        }
    )
except InvalidConnectionConfig as e:
    print(f"Configuración inválida: {e.message}")
```

---

### `InvalidQueryParameters` — Parámetros inválidos

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import InvalidQueryParameters

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

try:
    manager.execute_custom_many(
        "SELECT * FROM users WHERE id = ?",
        params=("not_a_number", "extra_param")  # Parámetros incorrectos
    )
except InvalidQueryParameters as e:
    print(f"Parámetros inválidos: {e.message}")

manager.close()
```

---

## Categoría 5: Errores de Drivers

Estos errores están relacionados con los drivers de base de datos.

### `DriverError` — Error base de driver

Error relacionado con drivers.

---

### `DriverNotFoundError` — Driver no instalado

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import DriverNotFoundError

try:
    manager = SyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "mydb"
        }
    )
    # Si psycopg2 no está instalado
except DriverNotFoundError as e:
    print(f"Driver no encontrado: {e.driver_name}")
    print(f"Instalar con: {e.install_command}")
```

**Solución:**
```bash
pip install psycopg2-binary
# o
pip install util_bbdd[postgres]
```

---

### `DriverConfigurationError` — Error configurando driver

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import DriverConfigurationError

try:
    manager = SyncDatabaseManager(
        db_type="sqlserver",
        conn_params={
            "host": "localhost",
            "port": 1433,
            "user": "sa",
            "password": "secret",
            "database": "mydb",
            "driver": "ODBC Driver NonExistent"  # Driver no instalado
        }
    )
except DriverConfigurationError as e:
    print(f"Error en driver: {e.message}")
    print(f"Verifica {e.driver_name} está instalado en tu SO")
```

---

## Categoría 6: Errores Específicos de Operaciones

### `DatabaseOperationError` — Error genérico de operación

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import DatabaseOperationError

try:
    manager = SyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": ":memory:"}
    )
    # Cualquier operación no categorizadas
    manager.bulk_insert(None, None)  # Parámetros nulos
except DatabaseOperationError as e:
    print(f"Error en operación: {e.message}")
```

---

### `DatabaseConfigurationError` — Error en configuración del manager

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import DatabaseConfigurationError

try:
    # Configuración inconsistente
    manager = SyncDatabaseManager(
        db_type="postgresql",
        conn_params=None  # Parámetros nulos
    )
except DatabaseConfigurationError as e:
    print(f"Error en configuración: {e.message}")
```

---

## Patrón Recomendado: Captura Estratificada

Captura excepciones de más específico a más genérico:

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import (
    DatabaseException,
    ConnectionError,
    QueryError,
    PoolTimeoutError,
    InvalidDatabaseType,
)

manager = None

try:
    manager = SyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "mydb",
            "pool_timeout": 10,
        }
    )

    # Operaciones
    tables = manager.get_tables()
    columns = manager.get_columns("users")
    result = manager.execute_custom_many("SELECT * FROM users LIMIT 10")

except InvalidDatabaseType as e:
    # Motor no soportado
    print(f"❌ Motor no soportado: {e.message}")

except PoolTimeoutError as e:
    # Problema específico de pool
    print(f"❌ Pool timeout: aumentar pool_size o pool_timeout")

except ConnectionError as e:
    # Problemas de conexión (más genérico)
    print(f"❌ Error de conexión: {e.message}")
    print(f"   Verifica host, puerto, credenciales")

except QueryError as e:
    # Problemas en query
    print(f"❌ Error en query: {e.message}")

except DatabaseException as e:
    # Error base (captura el resto)
    print(f"❌ Error en BD: {e.message}")
    if e.details:
        print(f"   Detalles: {e.details}")

finally:
    # Liberar recursos
    if manager:
        manager.close()
```

---

## Atributos Estándar de Excepciones

Toda excepción `DatabaseException` tiene estos atributos:

```python
try:
    # operación
except DatabaseException as e:
    print(f"message: {e.message}")           # Mensaje principal
    print(f"operation: {e.operation}")       # Tipo de operación
    print(f"db_type: {e.db_type}")           # Tipo de BD
    print(f"details: {e.details}")           # Detalles adicionales
```

---

## Mejores Prácticas

✅ **Captura específico primero:**
```python
try:
    # código
except DriverNotFoundError as e:
    print(f"Driver: {e.driver_name}")
except ConnectionError as e:
    print(f"Conexión: {e.message}")
```

✅ **Usa `e.details` para debugging:**
```python
except DatabaseException as e:
    log.error(f"Error: {e.message} | Detalles: {e.details}")
```

✅ **Siempre cierra recursos en `finally`:**
```python
try:
    # operaciones
finally:
    if manager:
        manager.close()
```

❌ **Evita capturar `Exception` genérica:**
```python
# MALO
try:
    # código
except Exception as e:
    print(f"Error: {e}")
```

---

## Próximos Pasos

- Consulta [INSTALLATION.md](INSTALLATION.md) para resolver problemas de drivers
- Lee [COMPARATOR.md](COMPARATOR.md) para operaciones de esquema
- Explora [Quick Start](../README.md#-quick-start-5-minutos) para ejemplos
