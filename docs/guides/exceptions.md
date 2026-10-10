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
    ConnectionError,          # Errores de conexión y pool
    PoolExhaustedError,       # Pool agotado
    PoolTimeoutError,         # Timeout esperando conexión
    QueryError,               # Errores en ejecución de queries
    QueryTimeoutError,        # Query superó el timeout
    QueryNotFoundError,       # Query nombrada no registrada
    ValidationError,          # Parámetros de configuración inválidos
    DriverError,              # Driver Python no disponible
    DatabaseOperationError,   # Error genérico de operación
)
```

### Paso 2 — Jerarquía de excepciones

```
DatabaseException (base)
├── ConnectionError
│   ├── PoolExhaustedError
│   └── PoolTimeoutError
├── QueryError
│   ├── QueryTimeoutError
│   ├── QueryNotFoundError
│   ├── QueryValidationError
│   └── QueryParameterError
├── ValidationError
│   ├── InvalidDatabaseType
│   └── InvalidConnectionConfig
├── DriverError
│   └── DriverNotFoundError
├── DatabaseOperationError
├── ComparerError
│   └── DiffReportGenerationError
└── DocumentationError
    └── DocumentationRenderError
```

### Paso 3 — Patrón de manejo recomendado

```python
from util_bbdd import SyncDatabaseManager, DatabaseException
from util_bbdd.exceptions import QueryTimeoutError, ConnectionError

with SyncDatabaseManager("postgresql", conn_params) as manager:
    try:
        filas = manager.execute_custom_many("SELECT ...", timeout=5.0)
    except QueryTimeoutError as e:
        # Timeout específico: reintentar con timeout mayor o registrar
        print(f"Query superó timeout: {e}")
    except ConnectionError as e:
        # Error de red o pool: reintentar o escalar
        print(f"Error de conexión: {e}")
    except DatabaseException as e:
        # Fallback para cualquier otra excepción de util_bbdd
        print(f"Error inesperado: {e}")
```

### Paso 4 — Patrón de retry para errores transitorios

```python
import time
from util_bbdd import DatabaseException
from util_bbdd.exceptions import ConnectionError

def ejecutar_con_retry(manager, sql, max_reintentos=3, delay=1.0):
    for intento in range(1, max_reintentos + 1):
        try:
            return manager.execute_custom_many(sql)
        except ConnectionError:
            if intento == max_reintentos:
                raise
            time.sleep(delay * intento)
```

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
| `InvalidDatabaseType` | `db_type` no reconocido | Usar exactamente: `mariadb`, `oracle`, `postgresql`, `sqlite`, `hsqldb`, `sqlserver` |
| `DriverNotFoundError` | Driver Python del motor no instalado | Instalar el driver correspondiente (ver installation.md) |
| `PoolExhaustedError` | Más conexiones concurrentes que `pool_size` | Aumentar `pool_size` o usar semáforo para limitar concurrencia |
| `QueryTimeoutError` | La query supera el timeout configurado | Aumentar el timeout o optimizar la query |
| `QueryNotFoundError` | Query por nombre no registrada en `QueryRegistry` | Registrar la query antes de usarla o usar `execute_custom_*` |
| `QueryValidationError` | Parámetros no coinciden con los placeholders del SQL | Verificar que los nombres de parámetros coincidan con los `:nombre` en el SQL |
| `DiffReportGenerationError` | Fallo al generar un formato de reporte | Verificar que las dependencias opcionales están instaladas (`openpyxl`, `python-docx`, `Jinja2`) |
