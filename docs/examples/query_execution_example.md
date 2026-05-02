# Ejecución de Consultas — Ejemplos

Ejemplos verificables para `SyncQueryExecutor`, `AsyncQueryExecutor` y los tipos de resultado
(`Row`, `Rows`, `RowOrNone`).

## Requisitos

```bash
pip install util_bbdd
```

No se necesitan credenciales reales: los ejemplos usan SQLite en memoria.

---

## Ejemplo 1. Consulta libre síncrona con SQLite en memoria

```python
import sqlite3
from util_bbdd.executors import SyncQueryExecutor
from util_bbdd.results import Row, Rows

# Conexión SQLite en memoria
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT, activo INTEGER)")
conn.execute("INSERT INTO usuarios VALUES (1, 'Ana', 1)")
conn.execute("INSERT INTO usuarios VALUES (2, 'Luis', 1)")
conn.execute("INSERT INTO usuarios VALUES (3, 'Eva', 0)")
conn.commit()

# El ejecutor recibe callables de proveedor y liberador
executor = SyncQueryExecutor(
    connection_provider=lambda: conn,
    connection_releaser=lambda c: None,  # en memoria, no se cierra
)

# Múltiples filas
filas: Rows = executor.execute_custom_many(
    "SELECT id, nombre FROM usuarios WHERE activo = :activo",
    params={"activo": 1},
)
print(filas)
# [(1, 'Ana'), (2, 'Luis')]

# Una sola fila
fila: Row | None = executor.execute_custom_one(
    "SELECT nombre FROM usuarios WHERE id = :id",
    params={"id": 3},
)
print(fila)
# ('Eva',)

# Sin resultado
vacio = executor.execute_custom_one(
    "SELECT nombre FROM usuarios WHERE id = :id",
    params={"id": 99},
)
print(vacio)
# None
```

**Resultado esperado**:

```
[(1, 'Ana'), (2, 'Luis')]
('Eva',)
None
```

---

## Ejemplo 2. Consulta con QueryRegistry (queries nombradas)

```python
import sqlite3
from util_bbdd.executors import SyncQueryExecutor
from util_bbdd.query import QueryRegistry

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE productos (id INTEGER, nombre TEXT, precio REAL)")
conn.execute("INSERT INTO productos VALUES (1, 'Teclado', 29.99)")
conn.execute("INSERT INTO productos VALUES (2, 'Ratón', 14.50)")
conn.commit()

# Registrar queries por motor
registry = QueryRegistry()
registry.register(
    "get_productos",
    {"sqlite": "SELECT id, nombre, precio FROM productos ORDER BY precio"},
)
registry.register(
    "get_producto_por_id",
    {"sqlite": "SELECT id, nombre, precio FROM productos WHERE id = :id"},
)

executor = SyncQueryExecutor(
    connection_provider=lambda: conn,
    connection_releaser=lambda c: None,
    registry=registry,
)

# Todos los productos
productos = executor.execute_query_many("get_productos", "sqlite", {})
for p in productos:
    print(f"[{p[0]}] {p[1]} — {p[2]:.2f} €")

# Un producto por ID
producto = executor.execute_query_one("get_producto_por_id", "sqlite", {"id": 1})
print(producto)
```

**Resultado esperado**:

```
[2] Ratón — 14.50 €
[1] Teclado — 29.99 €
(1, 'Teclado', 29.99)
```

---

## Ejemplo 3. Ejecutor asíncrono con SQLite

```python
import asyncio
import aiosqlite
from util_bbdd.executors import AsyncQueryExecutor

async def main() -> None:
    async with aiosqlite.connect(":memory:") as db:
        await db.execute(
            "CREATE TABLE tareas (id INTEGER, titulo TEXT, completada INTEGER)"
        )
        await db.execute("INSERT INTO tareas VALUES (1, 'Revisar código', 0)")
        await db.execute("INSERT INTO tareas VALUES (2, 'Escribir tests', 1)")
        await db.commit()

        executor = AsyncQueryExecutor(
            connection_provider=lambda: asyncio.coroutine(lambda: db)(),
            connection_releaser=lambda c: asyncio.coroutine(lambda: None)(),
        )

        filas = await executor.execute_custom_many(
            "SELECT id, titulo FROM tareas WHERE completada = :completada",
            params={"completada": 0},
        )
        print(filas)
        # [(1, 'Revisar código')]

asyncio.run(main())
```

**Resultado esperado**:

```
[(1, 'Revisar código')]
```

---

## Ejemplo 4. Uso directo de ResultNormalizer

```python
from util_bbdd.results import ResultNormalizer, Row, Rows

normalizer = ResultNormalizer()

# Resultado de fetchone() — puede ser tuple, Row o None
raw_one = (42, "Ana García")
fila: Row | None = normalizer.normalize_one(raw_one)
print(fila)          # (42, 'Ana García')
print(type(fila))    # <class 'tuple'>

# Sin resultado
vacio = normalizer.normalize_one(None)
print(vacio)         # None

# Resultado de fetchall()
raw_many = [(1, "A"), (2, "B"), (3, "C")]
filas: Rows = normalizer.normalize_many(raw_many)
print(filas)         # [(1, 'A'), (2, 'B'), (3, 'C')]
print(len(filas))    # 3
```

**Resultado esperado**:

```
(42, 'Ana García')
<class 'tuple'>
None
[(1, 'A'), (2, 'B'), (3, 'C')]
3
```

---

## Notas de seguridad

- Usa siempre parámetros nombrados (`:nombre`) en lugar de concatenar SQL con variables.
- No pasar entrada de usuario directamente a `execute_custom_*` sin validación previa.
- El timeout (`float | None`) ayuda a evitar conexiones colgadas en entornos de producción.
