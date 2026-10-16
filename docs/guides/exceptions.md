# Guía de Excepciones — util_bbdd

## 1. Objetivo

Importar y usar la jerarquía de excepciones de `util_bbdd` para capturar errores específicos y aplicar patrones de retry robustos.

## 2. Requisitos Previos

- `util_bbdd` instalado
- Familiaridad con el manejo de excepciones de Python (`try/except/finally`)
- Todas las excepciones de `util_bbdd` heredan de `DatabaseException`; capturar `DatabaseException` como fallback garantiza que no escapen errores silenciosos

## 3. Pasos

### Paso 1 — Importar las excepciones necesarias

```python
from util_bbdd.exceptions import (
    DatabaseException,        # Base de todas las excepciones (también en la raíz: from util_bbdd import ...)
    ConnectionError,          # Falla la conexión única al crear el manager
    DatabaseConfigurationError,  # Falla la creación del manager (incluido el pool)
    PoolTimeoutError,         # Pool sync agotado durante pool_timeout
    QueryTimeoutError,        # Query superó el timeout
    QueryNotFoundError,       # Query nombrada no registrada
    ValidationError,          # Parámetros de configuración inválidos
    DriverError,              # Driver Python no disponible
    DatabaseOperationError,   # Error al ejecutar una consulta (SQL inválido, conexión caída…)
)
```

### Paso 2 — Jerarquía de excepciones

Todas heredan de `DatabaseException`. El árbol completo (generado desde `util_bbdd.exceptions`) está en la
[referencia de excepciones](../api/exceptions.md). Las que más se capturan:

| Momento | Excepción |
|---|---|
| Crear el manager | `InvalidDatabaseType`, `ValidationError`, `DriverError`, `DatabaseConfigurationError`, `ConnectionError` |
| Ejecutar una consulta | `DatabaseOperationError` (con el error del driver en `__cause__`), `QueryTimeoutError`, `QueryNotFoundError` |
| Esperar conexión de un pool sync | `PoolTimeoutError` |

### Paso 3 — Patrón de manejo recomendado

```python
from util_bbdd import SyncDatabaseManager, DatabaseException
from util_bbdd.exceptions import DatabaseOperationError, QueryTimeoutError

with SyncDatabaseManager("postgresql", conn_params) as manager:
    try:
        filas = manager.execute_custom_many("SELECT ...", timeout=5.0)
    except QueryTimeoutError as e:
        # Timeout específico: reintentar con timeout mayor o registrar
        print(f"Query superó timeout: {e}")
    except DatabaseOperationError as e:
        # Fallo de la consulta: el error del driver está en e.__cause__
        print(f"Error ejecutando la consulta: {e} ({type(e.__cause__).__name__})")
    except DatabaseException as e:
        # Fallback para cualquier otra excepción de util_bbdd
        print(f"Error inesperado: {e}")
```

### Paso 4 — Patrón de retry para errores transitorios

```python
import time

from util_bbdd.exceptions import DatabaseOperationError, QueryTimeoutError

def ejecutar_con_retry(manager, sql, max_reintentos=3, delay=1.0):
    for intento in range(1, max_reintentos + 1):
        try:
            return manager.execute_custom_many(sql)
        except (DatabaseOperationError, QueryTimeoutError):
            if intento == max_reintentos:
                raise
            time.sleep(delay * intento)
```

`DatabaseOperationError` envuelve también errores permanentes (SQL inválido, permisos): para reintentar solo los
transitorios, decide por el error del driver (`e.__cause__`). Las cargas de `ParallelBulkLoader` ya lo hacen con
`RetryOptions.max_retries` (desconexiones, deadlocks, timeouts).

## 4. Verificación

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.exceptions import InvalidDatabaseType

try:
    SyncDatabaseManager("motor_inexistente", {"database": ":memory:"})
    print("ERROR: debería haber lanzado InvalidDatabaseType")
except InvalidDatabaseType:
    print("OK: InvalidDatabaseType lanzado correctamente para motor no soportado")

try:
    SyncDatabaseManager("sqlite", {})  # falta 'database'
    print("ERROR: debería haber lanzado ValidationError")
except Exception as e:
    print(f"OK: {type(e).__name__} lanzado correctamente al faltar 'database'")
```

## 5. Variantes y Solución de Problemas

| Excepción | Causa típica | Solución |
|---|---|---|
| `InvalidDatabaseType` | `db_type` no reconocido | Usar uno de: `mariadb`, `mysql`, `oracle`, `postgresql`, `sqlite`, `hsqldb`, `sqlserver` |
| `DriverError` | Driver Python del motor no instalado | Instalar el driver correspondiente (ver [Instalación](../installation.md)) |
| `PoolTimeoutError` | Pool sync agotado durante `pool_timeout` | Aumentar `pool_size`/`pool_timeout` o limitar la concurrencia |
| `QueryTimeoutError` | La query supera el timeout configurado | Aumentar el timeout o optimizar la query |
| `QueryNotFoundError` | Query por nombre que no está en el JSON de `queries_file` (la librería no trae ninguna) | Añadirla al fichero o usar `execute_custom_*` |
| `QueryValidationError` | Parámetros que no pasan el validador del motor | Verificar los parámetros requeridos de la query |
| `DatabaseOperationError` | La consulta falla en la base de datos | Ver el error del driver en `e.__cause__` |
