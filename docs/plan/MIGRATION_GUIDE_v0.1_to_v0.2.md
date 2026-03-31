# Guía de Migración: v0.1.x → v0.2.0

**Fecha:** 7 de marzo de 2026
**Versión anterior:** v0.1.0
**Versión nueva:** v0.2.0

> Nota Fase 4 (2026-03-31): esta es una guia historica de la transicion a v0.2.0. Para la documentacion viva actual, los imports publicos canonicos de managers se recomiendan desde `util_bbdd`; las referencias a `database_queries`, `database_exceptions` o rutas internas deben interpretarse como compatibilidad o contexto historico cuando no esten exportadas desde el paquete raiz.

### Referencia viva actual

- Para managers, el import canónico actual es `from util_bbdd import SyncDatabaseManager, AsyncDatabaseManager`.
- Esta guía conserva ejemplos históricos de `DatabaseQueries` y de rutas previas para explicar la transición a v0.2.0, no para marcar la recomendación actual de entrada al paquete.
- Si un ejemplo histórico usa una ruta hoy no preferida, toma README y `docs/MIGRATION_GUIDE.md` como fuente vigente.

---

## 📋 Resumen

v0.2.0 introduce una **refactorización significativa** de la arquitectura interna de `DatabaseQueries` sin romper la mayoría de los casos de uso. La API pública permanece mayormente compatible, pero hay cambios **importantes** en:

1. **Excepciones levantadas** - Nueva jerarquía
2. **Métodos internos** - `_load_queries()` ya no es accesible
3. **Validaciones** - Más estrictas (detección temprana de errores)
4. **AsyncDatabaseManager** - Ahora tiene paridad total con sync

---

## 🔴 Breaking Changes

### 1. Jerarquía de Excepciones

**ANTES (v0.1.x):**
```python
from util_bbdd.database_exceptions import DatabaseQueryError

try:
    query = dq.get_query("nonexistent")
except DatabaseQueryError:
    print("Query error")
except KeyError:
    print("Generic error")
```

**DESPUÉS (v0.2.0):**
```python
from util_bbdd.database_exceptions import (
    QueryNotFoundError,
    QueryValidationError,
    DatabaseError
)

try:
    query = dq.get_query("nonexistent")
except QueryNotFoundError:  # Específica
    print("Query not found")
except QueryValidationError:  # Si hay error de validación
    print("Invalid parameters")
except DatabaseError:  # Fallback genérico
    print("Database error")
```

**Alias para compatibilidad:**
```python
# Esto aún funciona en v0.2.0 (deprecated)
from util_bbdd.database_exceptions import DatabaseQueryError  # ⚠️ Alias de compatibilidad; no usar util_bbdd.database_queries como ruta canónica

# Pero muestra una advertencia en logs
```

---

### 2. Métodos privados eliminados de API pública

**ANTES (v0.1.x):**
```python
# Podía acceder al método privado (mala práctica)
dq = DatabaseQueries('mariadb')
queries = dq._load_queries(Path('custom_queries.json'))
```

**DESPUÉS (v0.2.0):**
```python
# Este método ahora es completamente interno
dq = DatabaseQueries('mariadb', queries_file=Path('custom_queries.json'))
# ✅ Correcto: pasa el archivo en __init__

# ❌ Incorrecto: _load_queries() no está disponible
# queries = dq._load_queries(...)  # AttributeError!
```

**Corrección:**
```python
# Usa el parámetro queries_file en __init__
dq = DatabaseQueries(
    db_type='mariadb',
    queries_file=Path('my_queries.json')
)
```

---

### 3. Validación más estricta de parámetros

**ANTES (v0.1.x):**
```python
# Permitía parámetros faltantes, error en runtime
query = dq.get_query('obtener_tablas')  # ✅ Retorna template
result = dq.execute(query)  # ❌ Falla en ejecución!
```

**DESPUÉS (v0.2.0):**
```python
# Valida parámetros temprano si se proporcionan
query = dq.get_query('obtener_tablas')  # ✅ Template sin parámetros (compatibilidad de la transición v0.2.0)

# Con parámetros, valida inmediatamente
query = dq.get_query('obtener_tablas', database='test')  # ✅ OK, parámetro válido
query = dq.get_query('obtener_tablas', tabla='users')  # ❌ QueryValidationError (param incorrecto)
```

**Impacto:**
- ✅ Errores detectados temprano
- ✅ Mejor debugging
- ❌ Código que antes funcionaba "por suerte" ahora falla

**Corrección:**
```python
from util_bbdd.database_exceptions import QueryValidationError

try:
    query = dq.get_query('obtener_columnas', database='test', table='users')
except QueryValidationError as e:
    print(f"Invalid parameters: {e}")
    # Proporciona parámetros correctos
```

---

## 🟡 Deprecations (Funcionales pero no recomendadas)

### 1. `DatabaseQueryError`

**Estado:** ⚠️ Deprecated (pero funcional gracias a alias)

**Cambiar de:**
```python
from util_bbdd.database_exceptions import DatabaseQueryError

except DatabaseQueryError:
    pass
```

**Cambiar a:**
```python
from util_bbdd.database_exceptions import QueryNotFoundError

except QueryNotFoundError:
    pass
```

---

### 2. `validate_query_parameters()`

**Estado:** ⚠️ Deprecated (pero funcional)

**Antes:**
```python
is_valid = dq.validate_query_parameters('obtener_tablas', database='test')
if not is_valid:
    print("Invalid!")
```

**Mejor ahora:**
```python
from util_bbdd.database_exceptions import QueryValidationError

try:
    query = dq.get_query('obtener_tablas', database='test')
    print("✅ Valid")
except QueryValidationError as e:
    print(f"❌ Invalid: {e}")
```

---

### 3. `analyze_query_parameters()`

**Estado:** ⚠️ Deprecated

**Cambiar de:**
```python
analysis = dq.analyze_query_parameters('obtener_tablas')
print(analysis)
```

**Cambiar a:**
```python
from util_bbdd.query.resolver import QueryResolver

resolver = QueryResolver(dq.registry)
resolved = resolver.resolve('obtener_tablas', 'mariadb', {})
print(f"Template: {resolved.query_definition.sql_template}")
print(f"Params: {resolved.query_definition.required_params}")
```

---

## 🟢 Cambios Compatibles

### 1. API Pública sin Cambios

Estos métodos funcionan **exactamente igual** en v0.2.0:

```python
dq = DatabaseQueries('mariadb')

# ✅ Todos funcionan sin cambios
dq.get_query(query_name)
dq.get_tables_query(database)
dq.get_columns_query(database, table)
dq.get_views_query(database)
dq.get_routines_query(database)
dq.get_available_query_names()
dq.get_all_queries()
```

### 2. DatabaseManager sin cambios de API

```python
dm = DatabaseManager('mariadb', conn_params)

# ✅ Métodos existentes sin cambios
dm.get_tables(database)
dm.get_columns(database, table)
dm.execute_custom_query(sql)

# ✨ Nuevo método en v0.2.0
dm.execute_query('query_name', **params)  # Ejecutar por nombre
```

### 3. AsyncDatabaseManager - Nueva Paridad

```python
adm = AsyncDatabaseManager('postgresql', conn_params)
await adm.ainit()

# ✨ Nuevo en v0.2.0: Métodos que faltaban
await adm.get_tables(database)      # ✨ Nuevo!
await adm.get_columns(database, table)  # ✨ Nuevo!
await adm.get_views(database)       # ✨ Nuevo!
await adm.execute_query('query_name', **params)  # ✨ Nuevo!
```

---

## 📝 Checklist de Migración

Use este checklist para migrar su código a v0.2.0:

### Paso 1: Actualizar Excepciones
- [ ] Cambiar `DatabaseQueryError` → `QueryNotFoundError`
- [ ] Actualizar importaciones desde `database_exceptions`
- [ ] Confirmar con tests

### Paso 2: Validaciones Mejoradas
- [ ] Buscar calls a `validate_query_parameters()`
- [ ] Cambiar a try/except con `QueryValidationError`
- [ ] Probar con parámetros inválidos (debe fallar temprano)

### Paso 3: Métodos Internos
- [ ] Buscar calls a `_load_queries()` (privado)
- [ ] Cambiar a parámetro `queries_file` en `__init__`
- [ ] Confirmar que queries se cargan

### Paso 4: Async Compatibility
- [ ] Si usas `AsyncDatabaseManager`, verifica nuevos métodos
- [ ] Prueba `get_tables()`, `get_columns()`, etc. en async
- [ ] Proporciona parámetros correctos (ahora validados)

### Paso 5: Tests
- [ ] Ejecutar suite de tests: `pytest tests/`
- [ ] Confirmar nuevas excepciones levantadas correctamente
- [ ] Validar que métodos deprecated muestran warnings

---

## 🧪 Ejemplos de Migración

### Ejemplo 1: Manejo de Query No Encontrada

**Antes (v0.1.x):**
```python
from util_bbdd.database_queries import DatabaseQueries
from util_bbdd.database_exceptions import DatabaseQueryError

dq = DatabaseQueries('mariadb')

try:
    query = dq.get_query('nonexistent_query')
except (DatabaseQueryError, KeyError) as e:
    logger.error(f"Query error: {e}")
```

**Después (v0.2.0):**
```python
from util_bbdd.database_queries import DatabaseQueries
from util_bbdd.database_exceptions import QueryNotFoundError

dq = DatabaseQueries('mariadb')

try:
    query = dq.get_query('nonexistent_query')
except QueryNotFoundError as e:
    logger.error(f"Query not found: {e}")
```

---

### Ejemplo 2: Validación de Parámetros

**Antes (v0.1.x):**
```python
dq = DatabaseQueries('oracle')

# Validación manual (incompleta)
is_valid = dq.validate_query_parameters(
    'columnas_tabla',
    database='mydb',
    tabla='users'
)

if is_valid:
    query = dq.get_query('columnas_tabla', database='mydb', tabla='users')
else:
    print("Invalid parameters")
```

**Después (v0.2.0):**
```python
from util_bbdd.database_queries import DatabaseQueries
from util_bbdd.database_exceptions import QueryValidationError

dq = DatabaseQueries('oracle')

try:
    # Validación automática durante get_query
    query = dq.get_query(
        'columnas_tabla',
        database='mydb',
        tabla='users'
    )
    print("✅ Query is valid and ready")
except QueryValidationError as e:
    print(f"❌ Validation error: {e}")
```

---

### Ejemplo 3: AsyncDatabaseManager

**Antes (v0.1.x):**
```python
from util_bbdd.async_database_manager import AsyncDatabaseManager

adm = AsyncDatabaseManager('postgresql', conn_params)
await adm.ainit()

# Métodos faltantes en v0.1.x
# ❌ await adm.get_tables() no existía!
await adm.execute_custom_query('SELECT table_name FROM information_schema.tables')
```

**Después (v0.2.0):**
```python
from util_bbdd import AsyncDatabaseManager

adm = AsyncDatabaseManager('postgresql', conn_params)
await adm.ainit()

# ✨ Ahora tiene los métodos!
tables = await adm.get_tables(database='public')  # ✨ Nuevo!
columns = await adm.get_columns(database='public', table='users')  # ✨ Nuevo!

# O usando nombres de queries
result = await adm.execute_query('obtener_tablas', database='public')  # ✨ Nuevo!
```

---

## 🐛 Troubleshooting

### Error: `QueryNotFoundError: Query 'X' not found for db_type 'Y'`

**Causa:** Query no existe en `sql_queries.json` para el motor especificado.

**Solución:**
```python
from util_bbdd.database_queries import DatabaseQueries

dq = DatabaseQueries('oracle')

# Verificar qué queries están disponibles
available = dq.get_available_query_names()
print(f"Available queries: {available}")

# Usar un nombre válido
if 'obtener_tablas' in available:
    query = dq.get_query('obtener_tablas', database='test')
```

---

### Error: `QueryValidationError: Validation failed for query 'X'`

**Causa:** Parámetros inválidos o faltantes.

**Solución:**
```python
from util_bbdd.database_queries import DatabaseQueries
from util_bbdd.database_exceptions import QueryValidationError

dq = DatabaseQueries('mariadb')

try:
    # ❌ Falta el parámetro 'database'
    query = dq.get_query('obtener_tablas')
except QueryValidationError as e:
    print(f"Error: {e}")

    # ✅ Proporciona parámetro requerido
    query = dq.get_query('obtener_tablas', database='mydb')
```

---

### Error: `AttributeError: DatabaseQueries object has no attribute '_load_queries'`

**Causa:** Intenta acceder a método privado que ahora es completamente interno.

**Solución:**
```python
# ❌ No funciona
queries_dict = dq._load_queries(Path('queries.json'))

# ✅ Usar parámetro en init
dq = DatabaseQueries('mariadb', queries_file=Path('queries.json'))
```

---

## 📞 Soporte

Si encuentras problemas durante la migración:

1. **Documentación:** Ver [README.md](README.md) sección "API Unificada"
2. **Tests:** Revisar `tests/unit/test_database_queries_refactor_pr5.py` para ejemplos
3. **Issues:** Reportar en GitHub con traceback completo

---

## 📈 Beneficios de Migrar

| Beneficio | v0.1.x | v0.2.0 |
|-----------|--------|--------|
| Validación temprana | ❌ | ✅ |
| Excepciones claras | ⚠️ Genéricas | ✅ Específicas |
| AsyncDatabaseManager completo | ❌ Incompleto | ✅ Paridad! |
| Código mantenible | ⚠️ Complicado | ✅ Simple |
| Motor-specific validation | ❌ Básico | ✅ Avanzado |
| Error context preservation | ❌ | ✅ |

---

**Versión:** 0.2.0
**Fecha:** 7 de marzo de 2026
**Estado:** ✅ MIGRATION GUIDE COMPLETE
