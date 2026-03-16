# 📋 PR #16: Cleanup Sistemático - Plan Detallado

**Status:** En Ejecución
**Objetivo:** Eliminar wrappers legacy SIN breaking changes innecesarios
**Enfoque:** Gradual, validado en cada paso

---

## 🎯 Fase 1: Análisis de Wrappers

### Wrappers Identificados (SOLO re-exportan):
1. ✅ `bulk_crud.py` (raíz) - Re-exporta `from .bulk import bulk_crud`
2. ✅ `grafos.py` (raíz) - Re-exporta `from .analysis import *`
3. ✅ `database_manager.py` (raíz) - Re-exporta DatabaseManager
4. ✅ `async_database_manager.py` (raíz) - Re-exporta AsyncDatabaseManager
5. ✅ `managers.py` (raíz) - Re-exporta `from .managers import *`
6. ✅ `bulk_crud/` (directorio) - Todos son wrappers que re-exportan de `bulk/`
7. ✅ `grafos/` (directorio) - Todos son wrappers que re-exportan de `analysis/`
8. ✅ `connection/` - Archivos wrapper (conn_params_builder, connect_factory, etc.)

### Archivos Reales (CON código):
- `bulk/crud.py`, `bulk/audit.py`, `bulk/normalize.py` - Lógica real
- `analysis/base.py`, `analysis/graphviz.py`, etc. - Lógica real
- `managers/sync_mgr.py`, `managers/async_mgr.py` - Lógica real
- `connection/factory.py`, `connection/config.py`, etc. - Lógica real

---

## 📋 Fase 2: Actualizar Imports en Archivos Reales

> Este paso es CRÍTICO - primero cambiamos los imports internos que apuntan a wrappers

### Paso 2.1: `managers/async_mgr.py`
Detectado: Imports desde wrappers legacy
```python
# ACTUAL (WRAPPER):
from ..connection.async_close_utils import AsyncCloseMode
from ..connection.connect_factory import ConnectFactory
from ..database_exceptions import DatabaseOperationError
...

# CORRECTO (NUEVOS PATHS):
from ..connection.close import AsyncCloseMode
from ..connection.factory import ConnectionFactory
from .._core.exceptions import DatabaseOperationError
...
```

### Paso 2.2: `managers/sync_mgr.py`
Mismo patrón de imports a actualizar

### Paso 2.3: Otros archivos en módulos nuevos
Revisar `bulk/`, `analysis/`, etc.

---

## 🗑️ Fase 3: Eliminación de Wrappers

### Paso 3.1: Eliminar directorios wrapper
- ❌ `bulk_crud/` (completo)
- ❌ `grafos/` (completo)

### Paso 3.2: Eliminar archivos wrapper en raíz
- ❌ `bulk_crud.py`
- ❌ `grafos.py`
- ❌ `database_manager.py`
- ❌ `async_database_manager.py`
- ❌ `managers.py`

### Paso 3.3: Eliminar archivos wrapper en `connection/`
- ❌ `conn_params_builder.py` (wrapper de `builder.py`)
- ❌ `connect_factory.py` (wrapper de `factory.py`)
- ❌ `connection_configs.py` (wrapper de `config.py`)
- ❌ `connection_params_manager.py` (wrapper de `params.py`)
- ❌ `pool_protocol.py` (wrapper de `protocols.py`)
- ❌ `async_close_utils.py` (wrapper de `close.py`)
- ❌ `sync_close_utils.py` (wrapper de `close.py`)
- ❌ `async_protocols.py` (wrapper de `protocols.py`)

---

## 🔧 Fase 4: Actualizar Imports Públicos

### Paso 4.1: `__init__.py` (raíz)
Cambiar de:
```python
from .async_database_manager import AsyncDatabaseManager
from .database_manager import DatabaseManager
from .connection.conn_params_builder import build_conn_params
from .factory import ConnectFactory, PoolFactory
```

A:
```python
from .managers.async_mgr import AsyncDatabaseManager
from .managers.sync import DatabaseManager
from .connection.builder import build_conn_params
from .connection.factory import ConnectionFactory
```

### Paso 4.2: `connection/__init__.py`
Remover imports de wrappers legacy, mantener solo los reales

---

## ✅ Validación en Cada Fase

- ✅ Tests: 443/443 después de cada fase
- ✅ Imports: Verificar sin ciclos
- ✅ Cobertura: Mantener funcionalidad

---

## 📊 Progreso

- [ ] Fase 1: Análisis completado ✓
- [ ] Fase 2: Actualizar imports en archivos reales
- [ ] Fase 3: Eliminar wrappers
- [ ] Fase 4: Actualizar imports públicos
- [ ] Validación final: 443/443 tests

---

**Próximo:** Paso 2.1 - Actualizar imports en `managers/async_mgr.py`
