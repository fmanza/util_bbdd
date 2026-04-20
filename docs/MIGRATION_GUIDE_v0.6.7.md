# Migration Guide: v0.6.6 → v0.6.7

Guía rápida para migrar código de util_bbdd **v0.6.6 a v0.6.7**.

**Release:** 2026-04-10 | **Python:** 3.12+ | **Breaking Changes:** ✅ Sí

---

## 🎯 Resumen (2 minutos)

v0.6.7 introduce **3 cambios rotos** (breaking):

1. **Exception renaming** — `DatabaseConnectionError` → `ConnectionError`
2. **Module facades removal** — `util_bbdd.database_exceptions` → directamente desde `util_bbdd`
3. **Protocol renaming** — `SourceAdapter` → `SourceAdapterSync`/`SourceAdapterAsync`

**Si solo usas:**
- `SyncDatabaseManager`/`AsyncDatabaseManager` → **Sin cambios** ✅
- Manager methods (`get_tables()`, etc.) → **Sin cambios** ✅
- Custom exception handling → **REQUIERE ACTUALIZACIÓN** ⚠️

---

## 🔄 Tabla Completa: Exception Renaming

| v0.6.6 | v0.6.7 | Uso típico |
|--------|--------|-----------|
| `DatabaseConnectionError` | `ConnectionError` | Red/credenciales |
| `DatabasePoolError` | `PoolConnectionError` | Pool corrupted |
| `DatabasePoolTimeoutError` | `PoolTimeoutError` | Pool exhausted |
| `DatabaseError` | `DatabaseException` | Catch-all base |
| `UtilBbddError` | `DatabaseException` | Catch-all base |
| `DatabaseValidationError` | `ValidationError` | Parámetros inválidos |
| `DatabaseTypeNotSupportedError` | `InvalidDatabaseType` | BD motor desconocido |
| `DatabaseDriverError` | `DriverError` | Driver issue |
| `InvalidQueryError` | `QueryValidationError` | SQL inválido |
| `QueryExecutionTimeoutError` | `QueryTimeoutError` | Query > timeout |

### Migración automática (copy-paste)

```bash
# En tu proyecto, ejecutar:
find . -name "*.py" -type f -exec sed -i \
  -e 's/DatabaseConnectionError/ConnectionError/g' \
  -e 's/DatabasePoolTimeoutError/PoolTimeoutError/g' \
  -e 's/DatabasePoolError/PoolConnectionError/g' \
  -e 's/DatabaseTypeNotSupportedError/InvalidDatabaseType/g' \
  -e 's/InvalidQueryError/QueryValidationError/g' \
  -e 's/QueryExecutionTimeoutError/QueryTimeoutError/g' \
  {} \;
```

### Antes vs Después

**v0.6.6:**
```python
from util_bbdd import (
    DatabaseConnectionError, DatabasePoolTimeoutError, DatabaseError
)

try:
    await manager.init()
except DatabasePoolTimeoutError:
    print("Pool timeout")
except DatabaseConnectionError:
    print("Connection failed")
except DatabaseError as e:
    print(f"Other error: {e}")
```

**v0.6.7:**
```python
from util_bbdd import (
    PoolTimeoutError, ConnectionError, DatabaseException
)

try:
    await manager.init()
except PoolTimeoutError:
    print("Pool timeout")
except ConnectionError:
    print("Connection failed")
except DatabaseException as e:
    print(f"Other error: {e}")
```

---

## 🗂️ Module Facades Removal

**Módulos eliminados:**

| v0.6.6 | v0.6.7 | Uso |
|--------|--------|-----|
| `from util_bbdd import database_exceptions` | `from util_bbdd import ConnectionError, ...` | Ver tabla arriba |
| `from util_bbdd.database_queries import ...` | `from util_bbdd.query import DatabaseQueries` | Ver ejemplo |
| `from util_bbdd.database_type_validator import ...` | `from util_bbdd._drivers import DatabaseTypeValidator` | Ver ejemplo |
| `from util_bbdd.driver_validator import ...` | `from util_bbdd._drivers import DriverValidator` | Ver ejemplo |

### Ejemplos

**database_exceptions — Cambiar imports:**

```python
# ❌ No funciona en v0.6.7
from util_bbdd.database_exceptions import (
    DatabaseConnectionError,
    DatabasePoolTimeoutError,
)

# ✅ Correcto en v0.6.7
from util_bbdd import (
    ConnectionError,
    PoolTimeoutError,
)
```

**database_queries:**

```python
# ❌ v0.6.6
from util_bbdd.database_queries import DatabaseQueries
queries = DatabaseQueries()

# ✅ v0.6.7
from util_bbdd.query import DatabaseQueries
queries = DatabaseQueries()
```

---

## 🔌 Protocol Renaming (Adapters)

Si defines **custom adapters**, cambiar:

```python
# ❌ v0.6.6 (ambiguo)
from util_bbdd.metadata.adapters import SourceAdapter, RoutineAdapter

class MySourceAdapter(SourceAdapter):
    def fetch(...): pass

# ✅ v0.6.7 (explícito)
from util_bbdd.metadata.adapters import SourceAdapterSync, SourceAdapterAsync

class MySourceAdapterSync(SourceAdapterSync):
    def fetch(...): pass

async def MySourceAdapterAsync(SourceAdapterAsync):
    async def fetch(...): pass
```

---

## ✅ Sin Cambios (Compatibilidad)

```python
# ✅ TODO esto funciona igual en v0.6.7

from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager

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

# Métodos sin cambios
tables = manager.get_tables()
columns = manager.get_table_columns(schema="public", table="users")
ddl = manager.get_table_ddl(schema="public", table="users")

# Async también igual
await manager.init()
await manager.execute_custom_many("SELECT ...")
await manager.close()
```

---

## ✋ Checklist Rápida

```
🔄 Exception handling:
  □ DatabaseConnectionError → ConnectionError
  □ DatabasePoolTimeoutError → PoolTimeoutError
  □ DatabaseTypeNotSupportedError → InvalidDatabaseType
  □ DatabaseError/UtilBbddError → DatabaseException

🗂️ Imports de módulos:
  □ Remover: util_bbdd.database_exceptions
  □ Actualizar: util_bbdd.database_queries → util_bbdd.query
  □ Actualizar: util_bbdd.database_type_validator
  □ Actualizar: util_bbdd.driver_validator

🔌 Adapters (si aplica):
  □ SourceAdapter → SourceAdapterSync/Async
  □ RoutineAdapter → RoutineAdapterSync/Async

✅ Testing:
  □ pytest sin cambios de API
  □ Except blocks actualizados
  □ Imports verificados
```

---

## 🆘 Troubleshooting

**"ImportError: cannot import name 'DatabaseConnectionError'"**

```python
# ❌ Culpable
from util_bbdd import DatabaseConnectionError

# ✅ Solución
from util_bbdd import ConnectionError
```

**"ModuleNotFoundError: No module named 'util_bbdd.database_exceptions'"**

```python
# ❌ Culpable
import util_bbdd.database_exceptions

# ✅ Solución
# Las excepciones están en util_bbdd root
from util_bbdd import ConnectionError, PoolTimeoutError, ...
```

**"TypeError: 'SourceAdapter' is not subscriptable"**

```python
# ❌ Culpable (no existe en v0.6.7)
from util_bbdd.metadata.adapters import SourceAdapter

# ✅ Solución (ser específico sync/async)
from util_bbdd.metadata.adapters import SourceAdapterSync, SourceAdapterAsync
```

---

## 🚀 Validación

Después de migrar:

```bash
# 1. Instalar
pip install --upgrade util-bbdd

# 2. Ejecutar tests
python -m pytest

# 3. Verificar imports
python -c "from util_bbdd import ConnectionError, PoolTimeoutError; print('✅ OK')"

# 4. Check managers (sin cambios)
python -c "from util_bbdd import SyncDatabaseManager; print('✅ Managers OK')"
```

---

## 📚 Referencias

- [CHANGELOG v0.6.7 (GitHub)](https://github.com/fmanza/util_bbdd/blob/main/CHANGELOG.md) — Lista completa v0.6.7
- [Excepciones](EXCEPTIONS.md) — Jerarquía de excepciones
- [API Reference](API_REFERENCE.md) — Documentación completa
- [Guía anterior: v0.6.3](MIGRATION_GUIDE.md) — Si vienes de versión más antigua

---

## ❓ Preguntas frecuentes

**¿Es breaking change?**
Sí, pero solo si usas excepciones o módulos legacy. Las APIs principales (`SyncDatabaseManager`, `AsyncDatabaseManager`) no cambian.

**¿Dónde están las nuevas excepciones?**
En `util_bbdd._core.exceptions`, pero también re-exportadas desde raíz `util_bbdd`.

**¿Puedo tener v0.6.6 y v0.6.7 en diferentes venvs?**
Sí, pero no en el mismo venv.
