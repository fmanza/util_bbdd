"""
Graph Generation — Visualizar relaciones entre tablas

Este ejemplo muestra cómo:
1. Introspeccionar metadatos
2. Generar grafo de relaciones
3. Exportar a SVG/PNG
4. Configurar profundidad y dirección
"""

from util_bbdd import SyncDatabaseManager
from util_bbdd.analysis import GraphvizRelationshipGraphExt


def demonstrate_graph_generation():
    """Generar grafo de relaciones."""

    # 1. Conectar a BD
    manager = SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"})

    # Crear esquema de ejemplo
    manager.execute_custom_many(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """
    )

    manager.execute_custom_many(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """
    )

    manager.execute_custom_many(
        """
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER,
            product_name TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
    """
    )

    print("Esquema creado: users -> orders -> items\n")

    # 2. Obtener metadatos
    tables = manager.get_tables()
    table_names = [t.name for t in tables]
    print(f"Tablas encontradas: {table_names}\n")

    # 3. Generar grafo paginado por tabla
    from pathlib import Path

    graph = GraphvizRelationshipGraphExt(
        db_manager=manager,
        show_columns=True,
        show_data_types=True,
        max_depth=2,
    )

    print("Generando grafos paginados...\n")

    # 4. Generar archivos SVG
    print("Exportando a formatos:")

    output_dir = Path("./graphviz_output")
    output_dir.mkdir(exist_ok=True)

    graph_files = graph.generate_graphviz_graph_paginated_ext(
        table_name="users",  # Tabla raíz
        output_dir=output_dir,
        format="svg",  # O "png", "pdf"
        max_subnodes=10,
        show_columns=True,
    )

    for file in graph_files:
        print(f"   {file}")
    print()

    # 5. Visualizacion ASCII
    print("Visualizacion ASCII:")
    print(
        """
        users
          |
          | (1:N)
          v
        orders
          |
          | (1:N)
          v
        items
    """
    )

    # 6. Información del grafo
    print("Informacion del grafo:")
    print("   - Tabla raíz: users")
    print("   - Profundidad máxima: 2 niveles")
    print("   - Tablas: 3 (users, orders, items)")
    print("   - Relaciones: 2 (users -> orders, orders -> items)")

    manager.close()


if __name__ == "__main__":
    demonstrate_graph_generation()
