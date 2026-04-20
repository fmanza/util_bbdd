# Generación de Documentación de Base de Datos

Ejemplo que demuestra cómo generar documentación completa de una base de datos en múltiples formatos (HTML, Word, Excel) usando `DatabaseDocumentation`.

**Cubre:**

- Conectar a la base de datos
- Configurar la documentación (`imprimir_config`)
- Generar HTML interactivo con gráficos
- Exportar a Word con tablas formateadas
- Exportar a Excel para análisis

**Formatos soportados:**

| Formato | Extensión | Caso de uso |
|---------|-----------|------------|
| **HTML** | `.html` | Exploración interactiva, gráficos Mermaid, índices navegables |
| **Word** | `.docx` | Reportes profesionales, compartir con stakeholders |
| **Excel** | `.xlsx` | Análisis en hojas de cálculo, datos tabulares |

---

## Configuración (`imprimir_config`)

La configuración controla qué documentar y cómo presentarlo:

```python
imprimir_config = {
    # Qué documentar
    "tablas": {
        "imprimir_tablas": True,  # Generar sección de tablas
        "ddl": True,              # Incluir DDL
        "columnas": True,         # Listar columnas
        "pk": True,               # Claves primarias
        "fk": True,               # Claves foraneas
    },
    "vistas": {
        "imprimir_vistas": True,  # Generar sección de vistas
        "ddl": True,
    },
    "rutinas": {
        "imprimir_rutinas": True,  # Stored procedures, functions
        "ddl": True,
    },

    # Configuración de gráficos
    "grafo": {
        "max_depth": 2,         # Profundidad de relaciones
        "direction": "outgoing", # incoming, outgoing, both
        "images_paginated": True,
        "max_subnodes": 10,
    },
}
```

---

## Ejemplo Completo

```python
--8<-- "examples/database_documentation_generation.py"
```

---

## Casos de Uso Comunes

### Generar solo HTML sin gráficos

```python
documentation = DatabaseDocumentation(
    db_manager=db_manager,
    directorio_salida=Path("output"),
    imprimir={
        "tablas": {"imprimir_tablas": True, "ddl": True},
        "vistas": {"imprimir_vistas": False},
        "rutinas": {"imprimir_rutinas": False},
    },
    formatos=["html"],
)
```

### Con plantilla Word personalizada

```python
documentation = DatabaseDocumentation(
    db_manager=db_manager,
    imprimir={
        "plantilla_word": "templates/my_template.docx",
        "tablas": {"imprimir_tablas": True},
        "tablas_por_documento": 30,  # Fragmentar en docs
    },
    formatos=["word"],
)
```

### Generar desde conexión existente

```python
# Si ya tienes SyncDatabaseManager
from util_bbdd.managers import SyncDatabaseManager

db_manager = SyncDatabaseManager.create(
    connection_string="postgresql://user:pass@localhost/mydb"
)

documentation = DatabaseDocumentation(
    db_manager=db_manager,
    directorio_salida=Path("docs"),
    imprimir=imprimir_config,
    formatos=["html", "word", "excel"],
)

# Acceder a metadatos documentados
print(f"Tablas: {len(documentation.tablas)}")
print(f"Vistas: {len(documentation.vistas)}")
print(f"Rutinas: {len(documentation.rutinas)}")
```

---

## Estructura de Salida

```
generated_docs/
├── documentacion_20260420_120530.html      # Reportes interactivos
├── documentacion_20260420_120530.docx      # Reporte Word profesional
└── documentacion_20260420_120530.xlsx      # Hojas de cálculo Excel
```

Cada formato incluye:

- **HTML:** Índices navegables, gráficos Mermaid, búsqueda
- **Word:** Portadas, tablas formateadas, encabezados, Heading 1 por sección
- **Excel:** Hojas separadas por tipo (tablas, vistas, rutinas)

---

## Configuración Avanzada

### Personalizar profundidad de gráficos

```python
imprimir_config = {
    "grafo": {
        "max_depth": 3,          # Mostrar 3 niveles de relaciones
        "direction": "both",     # Relaciones entrantes y salientes
        "images_paginated": True,
        "max_subnodes": 15,      # 15 tablas por imagen paginada
        "columns": {
            "mode": "all",       # Mostrar todas las columnas
        },
    },
}
```

### Controlar fragmentación en Word

```python
imprimir_config = {
    "tablas_por_documento": 25,  # Crear nuevo doc cada 25 tablas
    "table_style": "Light Grid", # Estilo alternativo
}
```

### Excluir secciones

```python
imprimir_config = {
    "tablas": {"imprimir_tablas": True},
    "vistas": {"imprimir_vistas": False},      # ← No generar
    "rutinas": {"imprimir_rutinas": False},    # ← No generar
}
```

---

!!! tip "Ver también"
    - [API Reference](../API_REFERENCE.md) — Referencia rápida de clases y módulos
    - [Guía de Instalación](../INSTALLATION.md) — Instalar extras necesarios (word, excel)
    - [Excepciones](../EXCEPTIONS.md) — Manejo de errores en generación
    - [Ejemplo: Comparación de Esquemas](schema_comparison.md) — Generar comparativas antes de documentar

---

## Notas

- La documentación se genera **automáticamente en `__init__`** — no necesitas llamar métodos adicionales
- Los archivos se guardan en `directorio_salida` con nombres auto-generados (timestamp)
- Para generar múltiples formatos, pasar lista: `formatos=["html", "word", "excel"]`
- Requiere dependencias opcionales: `pip install util-bbdd[doc]`
