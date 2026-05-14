# Ejemplo: Conectar a base de datos y obtener esquema

## Descripción

Este ejemplo muestra cómo usar `SyncDatabaseManager` para conectarse a una base de datos real,
listar tablas, obtener columnas, leer claves primarias y ejecutar una consulta SQL personalizada.

**Objetivo**: Verificar conectividad y explorar el esquema de la BD sin modificar datos.

## Requisitos previos

- Una base de datos accesible (o usar SQLite en memoria para probar sin servidor)
- Driver Python instalado para tu motor (ver [Instalación](../INSTALLATION.md))
- `pip install util_bbdd`

---

## Caso 1: SQLite en memoria (sin servidor externo)

El caso más sencillo para probar la API sin dependencias externas:

```python
from util_bbdd import SyncDatabaseManager

# Crear manager con SQLite en memoria
manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

# Crear tabla de prueba
manager.execute_custom_many(
    "CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT, email TEXT)"
)
manager.execute_custom_many(
    "INSERT INTO usuarios VALUES (1, 'Ana', 'ana@example.com')"
)

# Listar tablas
tablas = manager.get_tables()
print("Tablas:", [t["table_name"] for t in tablas])
# → Tablas: ['usuarios']

# Obtener columnas de una tabla
columnas = manager.get_columns("usuarios")
for col in columnas:
    print(f"  {col['column_name']}: {col['data_type']}")
# → id: INTEGER
# → nombre: TEXT
# → email: TEXT

# Ejecutar consulta personalizada
filas = manager.execute_custom_many("SELECT * FROM usuarios")
for fila in filas:
    print(dict(fila))
# → {'id': 1, 'nombre': 'Ana', 'email': 'ana@example.com'}

manager.close()
```

---

## Caso 2: PostgreSQL

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

# Listar tablas del esquema público
tablas = manager.get_tables()
print(f"Total de tablas: {len(tablas)}")
for t in tablas:
    print(f"  - {t['table_name']}")

# Columnas de una tabla específica
columnas = manager.get_columns("users")
for col in columnas:
    print(f"  {col['column_name']}: {col['data_type']}")

# Clave primaria
pks = manager.get_primary_keys("users")
print("PKs:", [pk["column_name"] for pk in pks])

# Claves foráneas
fks = manager.get_foreign_keys("orders")
for fk in fks:
    print(f"  FK: {fk['constrained_columns']} → {fk['referred_table']}.{fk['referred_columns']}")

manager.close()
```

---

## Caso 3: MariaDB

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "secret",
        "database": "myapp"
    }
)

tablas = manager.get_tables()
print(f"Total de tablas: {len(tablas)}")

# DDL de una tabla
ddl = manager.get_ddl("users")
print(ddl)

manager.close()
```

---

## Caso 4: Consulta SQL personalizada con parámetros

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

manager.execute_custom_many(
    "CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre TEXT, precio REAL, activo INTEGER)"
)
manager.execute_custom_many(
    "INSERT INTO productos VALUES (1, 'Widget', 9.99, 1), (2, 'Gadget', 19.99, 0)"
)

# execute_custom_many → devuelve múltiples filas
activos = manager.execute_custom_many(
    "SELECT * FROM productos WHERE activo = :activo",
    params={"activo": 1}
)
print("Productos activos:", [dict(r) for r in activos])
# → [{'id': 1, 'nombre': 'Widget', 'precio': 9.99, 'activo': 1}]

# execute_custom_one → devuelve una fila o None
producto = manager.execute_custom_one(
    "SELECT * FROM productos WHERE id = :id",
    params={"id": 2}
)
if producto:
    print("Encontrado:", dict(producto))

manager.close()
```

---

## Caso 5: Como context manager (cierre automático)

```python
from util_bbdd import SyncDatabaseManager

with SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
) as manager:
    manager.execute_custom_many(
        "CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)"
    )
    tablas = manager.get_tables()
    print("Tablas:", [t["table_name"] for t in tablas])
# manager.close() se llama automáticamente al salir del bloque
```

---

## Errores comunes y soluciones

### Error: `InvalidDatabaseType`

```
→ Usar exactamente uno de: mariadb, oracle, postgresql, sqlite, hsqldb, sqlserver
→ ❌ db_type="mysql"   ✅ db_type="mariadb"
→ ❌ db_type="postgre" ✅ db_type="postgresql"
```

### Error: `ConnectionError: connection refused`

```
→ Verificar que el servidor de BD está corriendo y accesible
  $ telnet localhost 5432  # Para PostgreSQL
  $ telnet localhost 3306  # Para MariaDB
```

### Error: `DriverError: No module named 'psycopg2'`

```
→ Instalar el driver del motor correspondiente (ver INSTALLATION.md)
  $ pip install psycopg2-binary   # PostgreSQL
  $ pip install pymysql           # MariaDB
  $ pip install pyodbc            # SQL Server
```

## Checklist de validación

- ✅ Conexión establecida sin errores
- ✅ `get_tables()` devuelve lista de dicts con clave `table_name`
- ✅ `get_columns(tabla)` devuelve lista de dicts con `column_name` y `data_type`
- ✅ `execute_custom_many()` acepta parámetros nombrados con `:nombre`
- ✅ Conexión cerrada con `manager.close()` o al salir del context manager

---

*Ejemplo verificado contra la API real de `SyncDatabaseManager` en util_bbdd v0.7.0*
