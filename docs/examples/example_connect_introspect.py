"""Ejemplo: Conectar a SQLite en memoria e introspeccionar esquema con SyncDatabaseManager."""

from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"},
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

# Obtener columnas
columnas = manager.get_columns("usuarios")
for col in columnas:
    print(f"  {col['column_name']}: {col['data_type']}")
# → id: INTEGER
# → nombre: TEXT
# → email: TEXT

# Ejecutar consulta personalizada con parámetros
filas = manager.execute_custom_many(
    "SELECT * FROM usuarios WHERE id = :id",
    params={"id": 1},
)
print("Fila:", dict(filas[0]) if filas else "sin resultado")
# → Fila: {'id': 1, 'nombre': 'Ana', 'email': 'ana@example.com'}

manager.close()
