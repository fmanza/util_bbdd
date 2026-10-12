"""Ejemplo verificable: generar documentación de base de datos.

El script crea una base SQLite local, inicializa SyncDatabaseManager y usa
DatabaseDocumentation para generar HTML, Word y Excel sin credenciales reales.
"""

import logging
import sqlite3

from pathlib import Path

from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager

# Configurar logging para ver el proceso
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# ============================================================================
# 1. CREAR UNA BASE SQLITE DE DEMOSTRACIÓN
# ============================================================================

db_path = Path("demo_documentation.db")

with sqlite3.connect(db_path) as conn:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            total NUMERIC NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE VIEW IF NOT EXISTS customer_order_totals AS
        SELECT c.id, c.name, SUM(o.total) AS total_amount
        FROM customers c
        JOIN orders o ON o.customer_id = c.id
        GROUP BY c.id, c.name;
        """
    )

print(f"Conectando a SQLite: {db_path}")

db_manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": str(db_path)},
    use_pool=False,
)

# ============================================================================
# 2. CONFIGURAR LA DOCUMENTACIÓN (imprimir config)
# ============================================================================

# Directorio de salida para documentos generados
output_dir = Path("generated_docs")
output_dir.mkdir(exist_ok=True)

# Configuración de qué documentar y cómo presentarlo
imprimir_config = {
    # Plantillas (opcionales)
    # "plantilla_word": "templates/my_template.docx",
    # "plantilla_html": "templates/my_page.html",
    # Configuración de fragmentación y estilo
    "tablas_por_documento": 50,  # Max tablas por documento Word
    "table_style": "Table Grid",  # Estilo para tablas
    "html_items_por_pagina": 15,  # Elementos por página HTML
    # Qué documentar: Tablas
    "tablas": {
        "imprimir_tablas": True,  # Generar seccion de tablas
        "ddl": True,  # Incluir DDL de tabla
        "columnas": True,  # Listar columnas
        "pk": True,  # Mostrar claves primarias
        "fk": True,  # Mostrar claves foráneas
        "indices": True,  # Mostrar índices
        "constraints": True,  # Mostrar constraints
    },
    # Qué documentar: Vistas
    "vistas": {
        "imprimir_vistas": True,  # Generar seccion de vistas
        "ddl": True,  # Incluir DDL de vista
        "columnas": True,  # Listar columnas
    },
    # Qué documentar: Rutinas (Stored Procedures, Functions)
    "rutinas": {
        "imprimir_procedures": False,  # SQLite no tiene stored procedures
        "imprimir_function": False,  # SQLite no tiene functions de catálogo comparables
    },
    # Configuración de gráficos de relaciones
    "grafo": {
        "enabled": True,
        "max_depth": 2,  # Profundidad máxima de relaciones
        "direction": "outgoing",  # incoming, outgoing, both
        "images_paginated": True,  # Paginar gráficos grandes
        "max_subnodes": 10,  # Max tablas por imagen
        "columns": {
            "mode": "compact",  # compact, relations, all
            "max_items": 5,  # Columnas visibles en compact
        },
    },
}

print("Configuración de documentación:")
print(f"   - Directorio: {output_dir}")
print(f"   - Tablas: {imprimir_config['tablas']['imprimir_tablas']}")
print(f"   - Vistas: {imprimir_config['vistas']['imprimir_vistas']}")
print(f"   - Rutinas: {imprimir_config['rutinas']['imprimir_procedures']}")
print(f"   - Grafos: profundidad={imprimir_config['grafo']['max_depth']}")

# ============================================================================
# 3. GENERAR DOCUMENTACIÓN EN MÚLTIPLES FORMATOS
# ============================================================================

print("\nGenerando documentación...")

# Crear instancia de DatabaseDocumentation (solo valida la configuración; no consulta la base de datos)
documentation = DatabaseDocumentation(
    db_manager=db_manager,
    directorio_salida=output_dir,
    fichero_salida=Path("demo-sqlite"),
    imprimir=imprimir_config,
    formatos=["html", "word", "excel"],  # Generar en estos formatos
)

# Ejecutar la generación: lee el catálogo, escribe los ficheros y devuelve un DocumentationResult
try:
    result = documentation.generate()
finally:
    db_manager.close()

print("Documentación generada correctamente.\n")

# ============================================================================
# 4. INFORMACIÓN SOBRE ARCHIVOS GENERADOS
# ============================================================================

print("Archivos generados:")
for formato, ruta in result.outputs.items():
    print(f"   {formato:<5}: {ruta.absolute()}")

print("\nResumen de documentación:")
print(f"   Tablas documentadas:  {result.tables}")
print(f"   Vistas documentadas:  {result.views}")
print(f"   Rutinas documentadas: {result.routines}")

# ============================================================================
# 5. CASOS DE USO ADICIONALES (Comentados)
# ============================================================================

# --- Caso 1: Generar solo HTML sin gráficos ---
# documentation_minimal = DatabaseDocumentation(
#     db_manager=db_manager,
#     directorio_salida=output_dir,
#     imprimir={
#         "tablas": {"imprimir_tablas": True, "ddl": True},
#         "vistas": {"imprimir_vistas": False},
#         "rutinas": {"imprimir_procedures": False, "imprimir_function": False},
#     },
#     formatos=["html"],
# )
# documentation_minimal.generate()

# --- Caso 2: Con plantilla personalizada Word ---
# documentation_custom = DatabaseDocumentation(
#     db_manager=db_manager,
#     directorio_salida=output_dir,
#     imprimir={
#         "plantilla_word": "path/to/custom_template.docx",
#         "tablas": {"imprimir_tablas": True},
#     },
#     formatos=["word"],
# )
# documentation_custom.generate()

# --- Caso 3: Generar documentación en batch con batching automático ---
# Múltiples generaciones dentro de 90 segundos reutilizan la misma carpeta
# for i in range(3):
#     documentation_batch = DatabaseDocumentation(
#         db_manager=db_manager,
#         directorio_salida=output_dir,
#         # fichero_salida=None genera automático; cache agrupa en ventana de 90 s
#         imprimir=imprimir_config,
#         formatos=["html"],
#     )
#     documentation_batch.generate()
#     print(f"Batch {i+1} completado")

# --- Caso 4: Configurar la ventana de batching ---
# Generar múltiples veces rápidamente sin reutilizar carpeta (batch_window_seconds=0)
# documentation_no_batch = DatabaseDocumentation(
#     db_manager=db_manager,
#     directorio_salida=output_dir,
#     imprimir=imprimir_config,
#     formatos=["html"],
#     batch_window_seconds=0,  # Sin cache: cada generación usa nombre nuevo
# )
# documentation_no_batch.generate()

# --- Caso 5: Ventana más larga (5 minutos) ---
# documentation_long_batch = DatabaseDocumentation(
#     db_manager=db_manager,
#     directorio_salida=output_dir,
#     imprimir=imprimir_config,
#     formatos=["html"],
#     batch_window_seconds=300,  # Agrupa durante 5 minutos
# )
# documentation_long_batch.generate()

print("\nEjemplo completado. Abre los archivos generados para explorar la documentación.")
