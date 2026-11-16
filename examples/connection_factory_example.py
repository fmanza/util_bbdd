"""Ejemplo: conexiones nativas sin pool con ConnectionFactory (sync y async) sobre SQLite en memoria.

Los managers usan la factoría internamente; llamarla directamente solo tiene sentido para obtener una conexión nativa
del driver sin pool. La conexión async necesita aiosqlite.
"""

import asyncio

from util_bbdd.exceptions import InvalidDatabaseType
from util_bbdd.factory import ConnectionFactory

# 1. Conexión síncrona: sqlite3 nativo
conn = ConnectionFactory.create_connection("sqlite", {"database": ":memory:"})
try:
    print("sync:", conn.execute("SELECT 1").fetchone())
finally:
    conn.close()


# 2. Conexión asíncrona: aiosqlite nativo
async def main() -> None:
    aconn = await ConnectionFactory.create_async_connection("sqlite", {"database": ":memory:"})
    try:
        cursor = await aconn.execute("SELECT 2")
        print("async:", await cursor.fetchone())
    finally:
        await aconn.close()


asyncio.run(main())

# 3. Un motor no soportado se rechaza antes de intentar conectar
try:
    ConnectionFactory.create_connection("postgres", {"database": "x"})
except InvalidDatabaseType as exc:
    print("rechazado:", type(exc).__name__)
