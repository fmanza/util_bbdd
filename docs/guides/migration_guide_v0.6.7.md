# Guía de Migración — v0.6.6 → v0.6.7

!!! note "Guía histórica"
    Los imports de excepciones desde la raíz que muestra esta guía (`from util_bbdd import ConnectionError`) ya no
    existen desde v1.0.0: usa `util_bbdd.exceptions`. Ver [Migración a la API 1.0](api_1_0_migration.md).

## 1. Objetivo

Migrar código de v0.6.6 a v0.6.7 actualizando los nombres de excepciones y eliminando imports de módulos de fachada obsoletos.

## 2. Requisitos Previos

- util_bbdd v0.6.6 instalado en el proyecto
- Identificar si el proyecto captura excepciones específicas de `util_bbdd` (las más afectadas)
- Si solo se usa `SyncDatabaseManager`/`AsyncDatabaseManager` sin captura de excepciones específicas: **sin cambios necesarios**

| Afectación | Descripción |
|---|---|
| **Sin cambios** | Uso de `SyncDatabaseManager`, `AsyncDatabaseManager` y sus métodos |
| **Requiere actualización** | Captura de excepciones específicas por nombre (`DatabaseConnectionError`, etc.) |
| **Requiere actualización** | Imports desde `util_bbdd.database_exceptions` |

## 3. Pasos

### Paso 1 — Actualizar util_bbdd

```bash
# util_bbdd no está en PyPI: se instala desde el repositorio, con el tag de la versión
pip install --upgrade "util_bbdd @ git+https://github.com/fmanza/util_bbdd.git@v0.6.7"
```

### Paso 2 — Actualizar nombres de excepciones

| v0.6.6 | v0.6.7 |
|---|---|
| `DatabaseConnectionError` | `ConnectionError` |
| `DatabasePoolError` | `PoolConnectionError` |
| `DatabasePoolTimeoutError` | `PoolTimeoutError` |
| `DatabaseError` | `DatabaseException` |
| `UtilBbddError` | `DatabaseException` |
| `DatabaseValidationError` | `ValidationError` |
| `DatabaseTypeNotSupportedError` | `InvalidDatabaseType` |
| `DatabaseDriverError` | `DriverError` |
| `InvalidQueryError` | `QueryValidationError` |
| `QueryExecutionTimeoutError` | `QueryTimeoutError` |

**Migración automática** (Linux/macOS):

```bash
find . -name "*.py" -type f -exec sed -i \
  -e 's/DatabaseConnectionError/ConnectionError/g' \
  -e 's/DatabasePoolTimeoutError/PoolTimeoutError/g' \
  -e 's/DatabasePoolError/PoolConnectionError/g' \
  -e 's/DatabaseTypeNotSupportedError/InvalidDatabaseType/g' \
  -e 's/InvalidQueryError/QueryValidationError/g' \
  -e 's/QueryExecutionTimeoutError/QueryTimeoutError/g' \
  -e 's/DatabaseError\b/DatabaseException/g' \
  -e 's/UtilBbddError/DatabaseException/g' \
  {} \;
```

### Paso 3 — Actualizar imports de excepciones

```python
# v0.6.6 — importar desde módulo específico
from util_bbdd.database_exceptions import DatabaseConnectionError, DatabaseError

# v0.6.7 — importar directamente desde util_bbdd
from util_bbdd import ConnectionError, DatabaseException
```

### Paso 4 — Actualizar código de manejo de excepciones

```python
# v0.6.6
from util_bbdd import DatabaseConnectionError, DatabasePoolTimeoutError, DatabaseError

try:
    await manager.init()
except DatabasePoolTimeoutError:
    print("Pool timeout")
except DatabaseConnectionError:
    print("Connection failed")
except DatabaseError as e:
    print(f"Other error: {e}")

# v0.6.7
from util_bbdd import PoolTimeoutError, ConnectionError, DatabaseException

try:
    await manager.init()
except PoolTimeoutError:
    print("Pool timeout")
except ConnectionError:
    print("Connection failed")
except DatabaseException as e:
    print(f"Other error: {e}")
```

## 4. Verificación

```bash
# Verificar versión instalada
python -c "import util_bbdd; print(util_bbdd.__version__)"
# → 0.6.7

# Verificar que los nuevos nombres de excepción están disponibles
python -c "from util_bbdd import ConnectionError, PoolTimeoutError, DatabaseException; print('OK')"

# Ejecutar tests del proyecto
python -m pytest
```

Si no hay excepciones en los imports y los tests pasan: migración completa.

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `ImportError: cannot import name 'DatabaseConnectionError'` | Nombre de excepción eliminado | Cambiar a `ConnectionError` (ver tabla Paso 2) |
| `ImportError: cannot import name 'DatabaseError'` | Nombre de excepción renombrado | Cambiar a `DatabaseException` |
| `ModuleNotFoundError: util_bbdd.database_exceptions` | Módulo de fachada eliminado | Importar directamente desde `util_bbdd` |
| Los tests de excepciones fallan después de actualizar | No se actualizaron todos los `except` | Ejecutar el script de migración automática del Paso 2 |
