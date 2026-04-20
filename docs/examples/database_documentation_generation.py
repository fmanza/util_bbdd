"""
Ejemplo: Generar documentación de base de datos (HTML, Word, Excel).

Este ejemplo demuestra cómo usar DatabaseDocumentation para generar
documentación completa de una base de datos en múltiples formatos.

Incluye:
- Instanciar DatabaseDocumentation
- Configurar bloques (imprimir config)
- Generar HTML, Word, y Excel
"""

import logging

from pathlib import Path

from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager

# Configurar logging para ver el proceso
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# ============================================================================
# 1. CONECTAR A LA BASE DE DATOS
# ============================================================================

# Usar SQLite como ejemplo (portable, sin requerimientos externos)
db_url = "sqlite:///example.db"

# Alternativamente, para PostgreSQL:
# db_url = "postgresql+psycopg2://user:password@localhost/mydb"

# Alternativamente, para Oracle:
# db_url = "oracle+cx_oracle://user:password@localhost:1521/mydb"

print(f"📌 Conectando a: {db_url}")

# Crear manager de base de datos
db_manager = SyncDatabaseManager.create(
    connection_string=db_url,
    log_queries=False,  # No loguear cada query
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
        "imprimir_tablas": True,  # ✅ Generar sección de tablas
        "ddl": True,  # Incluir DDL de tabla
        "columnas": True,  # Listar columnas
        "pk": True,  # Mostrar claves primarias
        "fk": True,  # Mostrar claves foraneas
        "indices": True,  # Mostrar índices
        "constraints": True,  # Mostrar constraints
    },
    # Qué documentar: Vistas
    "vistas": {
        "imprimir_vistas": True,  # ✅ Generar sección de vistas
        "ddl": True,  # Incluir DDL de vista
        "columnas": True,  # Listar columnas
    },
    # Qué documentar: Rutinas (Stored Procedures, Functions)
    "rutinas": {
        "imprimir_rutinas": True,  # ✅ Generar sección de rutinas
        "ddl": True,  # Incluir DDL de rutina
    },
    # Configuración de gráficos (Mermaid)
    "grafo": {
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

print("⚙️  Configuración de documentación:")
print(f"   - Directorio: {output_dir}")
print(f"   - Tablas: {imprimir_config['tablas']['imprimir_tablas']}")
print(f"   - Vistas: {imprimir_config['vistas']['imprimir_vistas']}")
print(f"   - Rutinas: {imprimir_config['rutinas']['imprimir_rutinas']}")
print(f"   - Gráfos: profundidad={imprimir_config['grafo']['max_depth']}")

# ============================================================================
# 3. GENERAR DOCUMENTACIÓN EN MÚLTIPLES FORMATOS
# ============================================================================

print("\n📄 Generando documentación...")

# Crear instancia de DatabaseDocumentation
# Nota: La documentación se genera automáticamente en __init__
documentation = DatabaseDocumentation(
    db_manager=db_manager,
    directorio_salida=output_dir,
    fichero_salida=None,  # Auto-generar nombre basado en fecha/hora
    imprimir=imprimir_config,
    formatos=["html", "word", "excel"],  # Generar en estos formatos
)

print("✅ Documentación generada exitosamente!\n")

# ============================================================================
# 4. INFORMACIÓN SOBRE ARCHIVOS GENERADOS
# ============================================================================

print(f"📁 Archivos generados en: {output_dir.absolute()}")
print(f"   📊 HTML:   {documentation.fichero_salida}.html")
print(f"   📘 Word:   {documentation.fichero_salida}.docx")
print(f"   📊 Excel:  {documentation.fichero_salida}.xlsx")

print("\n📊 Resumen de documentación:")
print(f"   Tablas documentadas:  {len(documentation.tablas)}")
print(f"   Vistas documentadas:  {len(documentation.vistas)}")
print(f"   Rutinas documentadas: {len(documentation.rutinas)}")

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
#         "rutinas": {"imprimir_rutinas": False},
#     },
#     formatos=["html"],
# )

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

# --- Caso 3: Generar documentación cada 90 segundos (batch mode) ---
# # Útil para generar reportes automáticos
# for i in range(3):
#     documentation_batch = DatabaseDocumentation(
#         db_manager=db_manager,
#         directorio_salida=output_dir,
#         imprimir=imprimir_config,
#         formatos=["html"],
#     )
#     print(f"Batch {i+1} completado")
#     # El archivo se genera automáticamente cada 90s en batch mode

print("\n✨ Ejemplo completado. Abre los archivos generados para explorar la documentación.")
