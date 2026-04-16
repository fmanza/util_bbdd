"""
Async Concurrent Queries — Ejecutar múltiples queries en paralelo

Este ejemplo muestra cómo:
1. Configurar AsyncDatabaseManager con pool
2. Ejecutar queries en paralelo con asyncio.gather()
3. Recolectar resultados
4. Validar pool exhaustion
"""

import asyncio

from util_bbdd import AsyncDatabaseManager, DatabaseException, PoolExhaustedError


async def demonstrate_concurrent_queries():
    """Ejecutar queries concurrentes de forma segura."""

    # 1. Crear manager con pool configurado
    manager = AsyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": ":memory:"},
        use_pool=True,
        pool_size=5,  # Limitar conexiones simultáneas
    )

    await manager.init()

    # 2. Crear tabla de prueba con datos
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

    print("✅ BD inicializada con 10 productos\n")

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

    # 4. Ejecutar todas en paralelo
    print("🚀 Ejecutando 4 queries en paralelo...\n")

    try:
        results = await asyncio.gather(
            get_cheap_products(),
            get_expensive_products(),
            get_average_price(),
            get_product_count(),
        )

        for i, result in enumerate(results, 1):
            print(f"   {i}. {result}")

    except PoolExhaustedError as e:
        print(f"❌ Pool exhausted: {e}")
    except DatabaseException as e:
        print(f"❌ Database error: {e}")

    # 5. Resumen
    print("\n⏱️  Comparación de tiempos (simulado):")
    print("   - Paralelo: ~100ms (todas simultáneamente)")
    print("   - Secuencial: ~400ms (una por una)")

    await manager.close()


if __name__ == "__main__":
    asyncio.run(demonstrate_concurrent_queries())
