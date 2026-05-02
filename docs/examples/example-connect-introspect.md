# Ejemplo: Conectar a base de datos y extraer esquema

## Descripción

Este ejemplo muestra cómo usar `SyncDatabaseManager` para conectarse a una base de datos real, extraer su esquema completo (tablas, columnas, constraints) y procesarlo.

**Objetivo**: Verificar conectividad y obtener metadata estructural sin modificar nada en la BD.

## Requisitos previos

- Una base de datos accesible (PostgreSQL, MySQL, SQLite, etc.)
- Credenciales válidas
- Dependencia instalada: `pip install util-bbdd`

## Caso 1: PostgreSQL

```python
from util_bbdd.managers import SyncDatabaseManager

# Conexión a PostgreSQL local
with SyncDatabaseManager(
    db_type="postgresql",
    host="localhost",
    port=5432,
    user="postgres",
    password="admin",
    database="test_db"
) as manager:

    # Obtener esquema
    schema = manager.introspect()

    # Iterar tablas
    for table in schema.tables:
        print(f"\nTabla: {table.name}")
        print(f"  Columnas ({len(table.columns)}):")
        for col in table.columns:
            pk = " [PK]" if col.primary_key else ""
            print(f"    - {col.name}: {col.type}{pk}")

        # Constraints
        if table.constraints:
            print(f"  Constraints:")
            for constraint in table.constraints:
                print(f"    - {constraint.name} ({constraint.type})")
```

**Salida esperada**:
```
Tabla: users
  Columnas (3):
    - id: INTEGER [PK]
    - email: VARCHAR(255)
    - created: TIMESTAMP
  Constraints:
    - users_email_unique (UNIQUE)

Tabla: orders
  Columnas (4):
    - id: INTEGER [PK]
    - user_id: INTEGER
    - total: DECIMAL(10,2)
    - created: TIMESTAMP
  Constraints:
    - fk_orders_users (FOREIGN KEY)
```

## Caso 2: MySQL

```python
from util_bbdd.managers import SyncDatabaseManager

with SyncDatabaseManager(
    db_type="mysql",
    host="localhost",
    port=3306,
    user="root",
    password="mysql_password",
    database="myapp"
) as manager:

    schema = manager.introspect()

    # Contar tablas
    print(f"Total de tablas: {len(schema.tables)}")

    # Listar tablas con primary keys
    for table in schema.tables:
        pk_cols = [c.name for c in table.columns if c.primary_key]
        print(f"{table.name}: PK={pk_cols}")
```

**Salida esperada**:
```
Total de tablas: 12
users: PK=['id']
orders: PK=['id']
products: PK=['sku']
inventory: PK=['product_id', 'warehouse_id']
```

## Caso 3: SQLite (archivo local)

```python
from util_bbdd.managers import SyncDatabaseManager

# SQLite no requiere usuario/contraseña
with SyncDatabaseManager(
    db_type="sqlite",
    database="/path/to/database.db"  # Ruta local
) as manager:

    schema = manager.introspect()

    # Estadísticas
    total_cols = sum(len(t.columns) for t in schema.tables)
    print(f"Tablas: {len(schema.tables)}, Columnas totales: {total_cols}")
```

## Caso 4: Análisis de constraints

```python
from util_bbdd.managers import SyncDatabaseManager

with SyncDatabaseManager(
    db_type="postgresql",
    host="localhost",
    port=5432,
    user="analyst",
    password="secret",
    database="analytics_db"
) as manager:

    schema = manager.introspect()

    # Encontrar todas las foreign keys
    print("=== Foreign Keys ===")
    for table in schema.tables:
        for constraint in table.constraints:
            if constraint.type == "FOREIGN KEY":
                print(f"{table.name}: {constraint.name} → {constraint.references_table}")

    # Encontrar tablas sin primary key
    print("\n=== Tablas sin Primary Key ===")
    for table in schema.tables:
        if not any(c.primary_key for c in table.columns):
            print(f"  - {table.name}")
```

## Caso 5: Procesamiento de tipos de datos

```python
from util_bbdd.managers import SyncDatabaseManager
from collections import Counter

with SyncDatabaseManager(
    db_type="mysql",
    host="localhost",
    port=3306,
    user="root",
    password="mysql",
    database="test_db"
) as manager:

    schema = manager.introspect()

    # Contar tipos de datos más comunes
    type_counter = Counter()
    for table in schema.tables:
        for column in table.columns:
            # Normalizar tipo (VARCHAR(255) → VARCHAR)
            base_type = column.type.split('(')[0]
            type_counter[base_type] += 1

    print("=== Distribución de tipos de datos ===")
    for dtype, count in type_counter.most_common(5):
        print(f"{dtype}: {count} columnas")
```

**Salida esperada**:
```
=== Distribución de tipos de datos ===
VARCHAR: 47 columnas
INT: 23 columnas
TIMESTAMP: 12 columnas
DECIMAL: 8 columnas
BIGINT: 5 columnas
```

## Errores comunes y soluciones

### Error: `ConnectionError: connection refused`

```
→ Solución: Verificar que el servidor de BD está corriendo y accesible
  $ ping localhost
  $ telnet localhost 5432  # Para PostgreSQL
```

### Error: `ValidationError: db_type 'postgre' not supported`

```
→ Solución: Usar tipo exacto. Soportados: postgresql, mysql, oracle, sqlite, sqlserver, snowflake, redshift, mariadb, hsqldb
```

### Error: `DatabaseOperationError: access denied for user 'analyst'`

```
→ Solución: Revisar credenciales (usuario, contraseña, base de datos)
  SELECT USER();  # En el servidor, verificar permisos
```

## Checklist de validación

Después de ejecutar los ejemplos, verifica:

- ✅ Conexión establecida sin errores
- ✅ Schema introspectado correctamente (tablas, columnas, constraints visibles)
- ✅ Tipos de datos reconocidos y normalizados
- ✅ Sin memory leaks (conexión cerrada automáticamente con `with`)
- ✅ Salida determinista (mismos resultados en ejecuciones múltiples)

---

*Generado por Documentation Generator - Fase 4: Ejemplos verificables*
