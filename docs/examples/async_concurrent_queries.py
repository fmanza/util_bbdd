"""
Async Concurrent Queries — Ejecutar múltiples queries en paralelo

Este ejemplo muestra cómo:
1. Configurar AsyncDatabaseManager
2. Lanzar queries independientes a la vez con asyncio.gather()
3. Recolectar resultados y medir el tiempo frente a la ejecución secuencial

Se ejecuta con SQLite (sin servidor). En SQLite el pool async es una sola conexión: las queries se
serializan y gather() no gana tiempo. En los motores con pool real (PostgreSQL, MariaDB, MySQL,
Oracle, SQL Server) cada corrutina toma su propia conexión, hasta pool_size a la vez.
"""

import asyncio
import time

from util_bbdd import AsyncDatabaseManager, DatabaseException


async def demonstrate_concurrent_queries():
    """Ejecutar queries concurrentes de forma segura."""

    # 1. Crear manager. En los motores servidor, el tamaño del pool va en conn_params
    # (p. ej. {"pool_size": 5, ...}); no es argumento del constructor.
    manager = AsyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": "async_queries_demo.db"},
    )

    await manager.init()

    # 2. Crear tabla de prueba con datos
    await manager.execute_custom_many("DROP TABLE IF EXISTS products")
    await manager.execute_custom_many(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            price REAL
        )
    """
    )

    # Insertar datos
    for i in range(1, 11):
        await manager.execute_custom_many(
            f"INSERT INTO products (id, name, price) VALUES ({i}, 'Product {i}', {i * 10.0})"
        )

    print("BD inicializada con 10 productos\n")

    # 3. Definir queries concurrentes
    async def get_cheap_products():
        """Obtener productos < $50."""
        result = await manager.execute_custom_many("SELECT * FROM products WHERE price < 50")
        return f"Productos baratos: {len(result)} encontrados"

    async def get_expensive_products():
        """Obtener productos >= $50."""
        result = await manager.execute_custom_many("SELECT * FROM products WHERE price >= 50")
        return f"Productos caros: {len(result)} encontrados"

    async def get_average_price():
        """Obtener precio promedio."""
        result = await manager.execute_custom_one("SELECT AVG(price) FROM products")
        return f"Precio promedio: ${result[0]:.2f}"

    async def get_product_count():
        """Contar productos."""
        result = await manager.execute_custom_one("SELECT COUNT(*) FROM products")
        return f"Total de productos: {result[0]}"

    queries = (get_cheap_products, get_expensive_products, get_average_price, get_product_count)

    # 4. Ejecutar todas a la vez
    print("Ejecutando 4 queries con asyncio.gather()...\n")

    try:
        start = time.perf_counter()
        results = await asyncio.gather(*(query() for query in queries))
        concurrent_ms = (time.perf_counter() - start) * 1000

        for i, result in enumerate(results, 1):
            print(f"   {i}. {result}")

        # 5. Mismas queries una tras otra, para comparar
        start = time.perf_counter()
        for query in queries:
            await query()
        sequential_ms = (time.perf_counter() - start) * 1000

        print(f"\n   gather():   {concurrent_ms:.1f} ms")
        print(f"   secuencial: {sequential_ms:.1f} ms (en SQLite, similares: una sola conexión)")
    except DatabaseException as e:
        print(f"Database error: {e}")

    await manager.close()


if __name__ == "__main__":
    asyncio.run(demonstrate_concurrent_queries())
