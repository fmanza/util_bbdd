"""Ejemplo: Consultas libres y registradas con SyncQueryExecutor sobre SQLite en memoria."""

import json
import sqlite3
import tempfile

from pathlib import Path

from util_bbdd.executors import SyncQueryExecutor
from util_bbdd.query import QueryRegistry

# Conexión SQLite en memoria
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT, activo INTEGER)")
conn.execute("INSERT INTO usuarios VALUES (1, 'Ana', 1)")
conn.execute("INSERT INTO usuarios VALUES (2, 'Luis', 1)")
conn.execute("INSERT INTO usuarios VALUES (3, 'Eva', 0)")
conn.commit()

# --- Consulta libre (sin QueryRegistry) ---
executor = SyncQueryExecutor(
    connection_provider=lambda: conn,
    connection_releaser=lambda c: None,
)

filas = executor.execute_custom_many(
    "SELECT id, nombre FROM usuarios WHERE activo = :activo",
    params={"activo": 1},
)
print("Activos:", filas)
# → [(1, 'Ana'), (2, 'Luis')]

fila = executor.execute_custom_one(
    "SELECT nombre FROM usuarios WHERE id = :id",
    params={"id": 3},
)
print("Usuario 3:", fila)
# → ('Eva',)

# --- Consulta registrada (con QueryRegistry) ---
# Las queries con nombre se leen de un JSON {motor: {nombre: SQL}}; la librería no trae ninguna.
queries_file = Path(tempfile.mkdtemp()) / "queries.json"
queries_file.write_text(
    json.dumps({"sqlite": {"get_usuario": "SELECT id, nombre FROM usuarios WHERE id = :id"}}),
    encoding="utf-8",
)
registry = QueryRegistry(queries_file)

executor_named = SyncQueryExecutor(
    connection_provider=lambda: conn,
    connection_releaser=lambda c: None,
    registry=registry,
)

resultado = executor_named.execute_query_one("get_usuario", "sqlite", {"id": 1})
print("Query registrada:", resultado)
# → (1, 'Ana')
