# Troubleshooting Guide

Guía de problemas comunes y soluciones en util_bbdd.

---

## Errores de Conexión y Pool

### 1. `PoolExhaustedError: Pool de conexiones agotado`

**Síntomas:**
```
PoolExhaustedError: Pool de conexiones agotado (Operación: SELECT) (BD: postgresql)
```

**Causas:**
- El `pool_size` es insuficiente para la carga concurrente
- Las conexiones no se están liberando correctamente
- Hay queries lentas bloqueando conexiones

**Soluciones:**

**Opción 1: Aumentar tamaño del pool**
```python
manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={...},
    pool_size=50,        # Aumentar de 10 a 50
    max_overflow=20,     # Permitir 20 conexiones extra
)
```

**Opción 2: Reducir número de queries concurrentes**
```python
# ❌ PROBLEMA: 1000 queries simultáneas con pool_size=10
tasks = [manager.execute_custom_many(q) for q in 1000_queries]
results = await asyncio.gather(*tasks)

# ✅ SOLUCIÓN: Batch por semáforo
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent

async def bounded_query(q):
    async with semaphore:
        return await manager.execute_custom_many(q)

tasks = [bounded_query(q) for q in 1000_queries]
results = await asyncio.gather(*tasks)
```

**Opción 3: Agregar timeout**
```python
try:
    result = await asyncio.wait_for(
        manager.execute_custom_many("SELECT ..."),
        timeout=5.0
    )
except asyncio.TimeoutError:
    print("Query excedió timeout de 5s (conexión disponible después)")
except PoolExhaustedError:
    print("No hay conexión disponible ni después del timeout")
```

**Monitoreo:**
```python
# Verificar pool status antes de operación
if hasattr(manager, '_pool_stats'):
    stats = manager._pool_stats()
    print(f"Conexiones activas: {stats['checked_out']}")
    print(f"Conexiones libres: {stats['available']}")
```

**Checklist:**
- [ ] ¿Cierras todas las conexiones con `await manager.close()`?
- [ ] ¿Usas `async with` para context managers?
- [ ] ¿Monitoreaste queries lentas (> 1 seg)?
- [ ] ¿Aumentaste `pool_size` según concurrencia esperada?

---

### 2. `PoolTimeoutError: Timeout esperando conexión del pool`

**Síntomas:**
```
PoolTimeoutError: Timeout esperando conexión del pool (Operación: INSERT)
Timeout: 30.0s
```

**Causas:**
- Pool agotado + timeout por espera
- Backend de BD no responde
- Red lenta/congestionada

**Soluciones:**

**Aumentar timeout de pool:**
```python
manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={...},
    pool_timeout=60,  # Esperar hasta 60 seg por conexión
)
```

**Mejorar query (es lenta):**
```python
# ❌ Query que toma 30+ segundos
await manager.execute_custom_many(
    "SELECT ... FROM huge_table WHERE id IN (subquery)"
)

# ✅ Optimizar: agregar índice, usar WHERE más específico
await manager.execute_custom_many(
    "SELECT ... FROM huge_table WHERE indexed_col = ? LIMIT 1000"
)
```

**Conectar a replica/staging primero (test):**
```python
# Test con BD de staging
test_manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "staging.example.com",  # Replica rápida
        # ...
    }
)
await test_manager.init()
# Si funciona aquí pero no en prod, es problema de red/BD
```

---

### 3. `ConnectionError: No se pudo conectar a la base de datos`

**Síntomas:**
```
ConnectionError: No se pudo conectar a la base de datos (Operación: CONNECT)
(BD: oracle) - ORA-12514: TNS listener no conoce el servicio
```

**Causas:**
- Credenciales incorrectas
- Host/puerto incorrecto
- Servicio/listener no disponible
- Firewall bloqueando puerto
- BD no iniciada

**Soluciones:**

**1. Verificar credenciales:**
```python
# Test con sqlalchemy directamente
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg2://user:pass@localhost:5432/mydb"
)

try:
    with engine.connect() as conn:
        print("✅ Conexión exitosa")
except Exception as e:
    print(f"❌ Error: {e}")
```

**2. Verificar conectividad de red:**
```bash
# Desde terminal
telnet localhost 5432        # PostgreSQL
telnet localhost 3306        # MariaDB
telnet localhost 1521        # Oracle
nc -zv localhost 5432        # netcat (alternativa)
```

**3. Usar connection string correcta por motor:**
```python
# PostgreSQL
"postgresql+psycopg2://user:pass@host:5432/db"

# MariaDB
"mysql+pymysql://user:pass@host:3306/db"

# Oracle
"oracle+oracledb://user:pass@host:1521/db"

# SQLite (local)
"sqlite:///path/to/database.db"
"sqlite:///:memory:"
```

**4. Aumentar timeout de conexión:**
```python
manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "slow-host.example.com",
        # ...
    },
    connect_timeout=10,  # Esperar 10 seg para conectar
)
```

---

## Errores de Query

### 4. `QueryValidationError: Validación de query fallida`

**Síntomas:**
```
QueryValidationError: Validación de query fallida (Operación: SELECT)
Column 'user_id' not found in table 'users'
```

**Causas:**
- Columna/tabla no existe
- Typo en nombre
- Tabla no disponible en este schema/contexto
- DDL de tabla cambió

**Soluciones:**

**Verificar esquema primero:**
```python
# Obtener tablas disponibles
tables = await manager.get_tables()
print("Tablas disponibles:", [t['table_name'] for t in tables])

# Obtener columnas de tabla
columns = await manager.get_table_columns(schema="public", table="users")
print("Columnas:", [c['column_name'] for c in columns])

# Verificar la query
# ✅ CORRECTO
await manager.execute_custom_many("SELECT user_id FROM users")

# ❌ INCORRECTO
await manager.execute_custom_many("SELECT user_id FROM usrs")  # Typo
```

**Usar introspección:**
```python
from util_bbdd.comparar import SchemaComparator

# Generar DDL actual
comparator = SchemaComparator(
    source_manager=manager,
    target_manager=None
)

schema_diff = comparator.compare()
for table in schema_diff.source_only_tables:
    print(f"Tabla disponible en source: {table.table_name}")
    print(f"DDL:\n{table.ddl}")
```

---

### 5. `QueryTimeoutError: Query excedió timeout`

**Síntomas:**
```
QueryTimeoutError: Query excedió timeout de 30 segundos (Operación: SELECT)
```

**Causas:**
- Query es lenta (tabla grande, sin índice)
- BD sobrecargada
- Red lenta

**Soluciones:**

**Aumentar timeout global:**
```python
manager = AsyncDatabaseManager(
    db_type="postgresql",
    # ...
    query_timeout=60,  # Aumentar a 60 seg
)
```

**Timeout específico por query:**
```python
try:
    result = await asyncio.wait_for(
        manager.execute_custom_many(
            "SELECT * FROM huge_table"  # Slow query
        ),
        timeout=120.0  # 2 minutos para esta query
    )
except asyncio.TimeoutError:
    print("Query tomó demasiado tiempo")
```

**Optimizar query:**
```python
# ❌ Lenta: full table scan
"SELECT * FROM users WHERE created_at LIKE '%2024%'"

# ✅ Rápida: indexed column + BETWEEN
"SELECT * FROM users WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'"

# Verificar índices
indices = await manager.get_table_indices(schema="public", table="users")
print("Índices:", [i['index_name'] for i in indices])
```

---

### 6. `QueryExecutionError: Error en ejecución de query`

**Síntomas:**
```
QueryExecutionError: Error ejecutando query (Operación: INSERT)
(BD: postgresql) - Duplicate key value violates unique constraint
```

**Causas:**
- Violación de constraint (PK, UNIQUE)
- Tipo de dato incorrecto
- Valor NULL donde no se permite
- FK violada

**Soluciones:**

**Verificar constraints:**
```python
# Obtener claves primarias
pks = await manager.get_table_primary_keys(schema="public", table="users")
print("Primary keys:", pks)

# Obtener foreign keys
fks = await manager.get_table_foreign_keys(schema="public", table="orders")
print("Foreign keys:", fks)

# Obtener unique constraints
ucs = await manager.get_table_unique_constraints(schema="public", table="users")
print("Unique constraints:", ucs)
```

**Verificar datos antes de insertar:**
```python
# ❌ PROBLEMA: Insertar PK duplicada
await manager.execute_custom_many(
    "INSERT INTO users (id, name) VALUES (1, 'Alice')"
)
await manager.execute_custom_many(
    "INSERT INTO users (id, name) VALUES (1, 'Bob')"  # Error!
)

# ✅ SOLUCIÓN: Verificar que ID es único
existing = await manager.execute_custom_many(
    "SELECT id FROM users WHERE id = 1"
)
if not existing:
    await manager.execute_custom_many(
        "INSERT INTO users (id, name) VALUES (1, 'Bob')"
    )
```

**Usar bulk insert con error handling:**
```python
from pathlib import Path
import csv

# Preparar datos
csv_path = Path("users_to_insert.csv")

try:
    await manager.bulk_insert_from_csv(
        schema="public",
        table="users",
        csv_path=csv_path,
        on_constraint_error="skip"  # Saltar filas conflictivas
    )
except QueryExecutionError as e:
    print(f"Error en bulk: {e.details}")
```

---

## Errores de Metadatos

### 7. `MetadataError: No se pudo obtener metadatos`

**Síntomas:**
```
MetadataError: No se pudo obtener metadatos (Operación: METADATA_FETCH)
(BD: oracle) - Table or view does not exist
```

**Causas:**
- Tabla no existe
- Permiso denegado
- Schema incorrecto
- Nombre con case-sensitivity

**Soluciones:**

**Verificar tabla existe:**
```python
# Listar todas las tablas
tables = await manager.get_tables()
table_names = [t['table_name'].lower() for t in tables]

if 'users' not in table_names:
    print("❌ Tabla 'users' no existe")
    print(f"Tablas disponibles: {table_names}")
else:
    print("✅ Tabla 'users' existe")
```

**Verificar permisos:**
```python
# En cliente SQL directo (sqlplus, psql, etc.)
GRANT SELECT ON users TO your_user;
GRANT SELECT, INSERT, UPDATE ON schema.* TO your_user;
```

**Case-sensitivity en Oracle/SQL Server:**
```python
# Oracle: nombres en MAYÚS por defecto
await manager.get_table_columns(schema="PUBLIC", table="USERS")

# SQL Server: nombres case-insensitive pero mejor ser consistente
await manager.get_table_columns(schema="dbo", table="Users")

# PostgreSQL: lowercase por defecto
await manager.get_table_columns(schema="public", table="users")
```

**Usar cache para acelerar:**
```python
from util_bbdd.metadata import DatabaseMetadataCache

# Cache evita queries repetidas
cache = DatabaseMetadataCache()

# Primera vez (query a BD)
columns = await manager.get_table_columns(
    schema="public",
    table="users",
    cache=cache  # Guardar en cache
)

# Segunda vez (desde cache, más rápido)
columns = cache.get_columns(("public", "users"))
```

---

## Errores de Importación y Tipado

### 8. `ImportError: No se pudo importar módulo`

**Síntomas:**
```
ImportError: cannot import name 'DatabaseManager' from 'util_bbdd'
ModuleNotFoundError: No module named 'util_bbdd'
```

**Causas:**
- util_bbdd no instalado
- Versión incorrecta
- Nombre incorrecto

**Soluciones:**

**Verificar instalación:**
```bash
pip list | grep util-bbdd
# Debe mostrar: util-bbdd              0.6.7

# Si no está:
pip install util-bbdd

# Para development:
pip install -e .
```

**Nombres correctos de importación:**
```python
# ✅ CORRECTO
from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd import DatabaseException, PoolExhaustedError
from util_bbdd.metadata import DatabaseMetadataCache
from util_bbdd.comparar import SchemaComparator

# ❌ INCORRECTO
from util_bbdd import DatabaseManager  # No existe
from util_bbdd.managers import AsyncDatabaseManager  # Importar del root
from util_bbdd.core import anything  # core no está en __init__
```

**Verificar __init__.py:**
```python
# Check what's exported
import util_bbdd
print(dir(util_bbdd))
```

---

### 9. `TypeError: Unsupported type for annotation`

**Síntomas:**
```
TypeError: Cannot handle type: <class 'util_bbdd.metadata.cache.DatabaseMetadataCache'>
```

**Causas:**
- Parámetro con tipo no soportado
- mypy strict mode detecta problema
- Versión de Python antigua

**Soluciones:**

**Agregar Type Hints correctamente:**
```python
# ❌ INCORRECTO
def process_rows(rows):
    return rows

# ✅ CORRECTO
from typing import Any
from util_bbdd.metadata import DatabaseMetadataCache

def process_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows

def cache_metadata(cache: DatabaseMetadataCache) -> None:
    # Usar cache
    pass
```

**Para mypy strict:**
```bash
# Check errors
python -m mypy src/your_file.py --strict

# Fix by adding types
def get_manager() -> AsyncDatabaseManager:
    return AsyncDatabaseManager(...)
```

---

## Mejores Prácticas para Debugging

### Habilitar Logging Detallado

```python
import logging

# Mostrar todos los logs
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Específicamente para util_bbdd
util_bbdd_logger = logging.getLogger('util_bbdd')
util_bbdd_logger.setLevel(logging.DEBUG)

manager = AsyncDatabaseManager(...)
await manager.init()

# Ahora verás logs detallados de cada operación
```

### Usar Context Managers

```python
# ✅ CORRECTO: Cierra automáticamente
manager = AsyncDatabaseManager(...)

async with manager:
    result = await manager.execute_custom_many("SELECT ...")

# ✅ ALTERNATIVA: init + close explícito
await manager.init()
try:
    result = await manager.execute_custom_many("SELECT ...")
finally:
    await manager.close()

# ❌ INCORRECTO: No cierra
manager = AsyncDatabaseManager(...)
result = await manager.execute_custom_many("SELECT ...")
# Manager no cerrado → leak
```

### Probar con SQLite primero

```python
# SQLite es rápido para testing localmente
test_manager = AsyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}  # En memoria, sin archivo
)

await test_manager.init()
# Probar lógica aquí sin depender de BD remota
```

---

## Checklist de Debugging

```markdown
- [ ] ¿Habilitaste logging DEBUG?
- [ ] ¿Probaste con SQLite local primero?
- [ ] ¿Verificaste credenciales con SQL client directo (psql, mysql, etc.)?
- [ ] ¿Probaste telnet/nc a host:puerto?
- [ ] ¿Aumentaste timeouts y pool_size?
- [ ] ¿Cerraste manager con await close()?
- [ ] ¿Usaste context managers (async with)?
- [ ] ¿Revisaste los logs de BD (error logs)?
- [ ] ¿Ejecutaste queries simples primero (SELECT 1)?
- [ ] ¿Comparaste con versión funcional anterior?
```

---

## Recursos Adicionales

- [Excepciones](EXCEPTIONS.md) — Jerarquía completa de excepciones
- [Guía Async](ASYNC_GUIDE.md) — Patrones async/await
- [API Reference](API_REFERENCE.md) — Todas las clases y métodos
- [Instalación](INSTALLATION.md) — Requisitos y configuración inicial
- [Ejemplos](examples/) — Código ejecutable de casos de uso
