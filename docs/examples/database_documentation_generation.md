# Generación de documentación de base de datos

Ejemplo verificable para generar documentación de una base de datos con `DatabaseDocumentation`.

El caso principal usa SQLite para evitar credenciales reales y servicios externos. El script crea una base local de demostración, inicializa `SyncDatabaseManager`, configura `DatabaseDocumentation` y escribe la salida en `generated_docs/`.

**Cubre:**

- Crear una base SQLite mínima para pruebas locales
- Conectar con `SyncDatabaseManager`
- Configurar la documentación (`imprimir_config`)
- Generar HTML, Word y Excel
- Cerrar el manager al finalizar

**Formatos soportados:**

| Formato | Extensión | Caso de uso |
|---------|-----------|------------|
| **HTML** | `.html` | Exploración navegable e índices por entidad |
| **Word** | `.docx` | Reportes profesionales, compartir con stakeholders |
| **Excel** | `.xlsx` | Análisis en hojas de cálculo, datos tabulares |

---

## Requisitos

```bash
pip install "util-bbdd[doc]"
```

Para grafos avanzados o reutilización SVG en Word, instala también las dependencias opcionales documentadas en la guía de instalación.

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
        "imprimir_procedures": True,  # Stored procedures
        "imprimir_function": True,    # Functions
    },

    # Configuración de gráficos de relaciones
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
    fichero_salida=Path("demo-html"),
    imprimir={
        "tablas": {"imprimir_tablas": True, "ddl": True},
        "vistas": {"imprimir_vistas": False},
        "rutinas": {"imprimir_procedures": False, "imprimir_function": False},
        "grafo": {"enabled": False},
    },
    formatos=["html"],
)
documentation.generate()
```

### Con plantilla Word personalizada

```python
documentation = DatabaseDocumentation(
    db_manager=db_manager,
    directorio_salida=Path("output"),
    fichero_salida=Path("demo-word"),
    imprimir={
        "plantilla_word": "templates/my_template.docx",
        "tablas": {"imprimir_tablas": True},
        "tablas_por_documento": 30,  # Fragmentar en docs
    },
    formatos=["word"],
)
documentation.generate()
```

### Generar desde conexión existente

```python
from pathlib import Path

from util_bbdd.managers import SyncDatabaseManager

db_manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": "demo_documentation.db"},
    use_pool=False,
)

documentation = DatabaseDocumentation(
    db_manager=db_manager,
    directorio_salida=Path("generated_docs"),
    fichero_salida=Path("demo-sqlite"),
    imprimir=imprimir_config,
    formatos=["html", "word", "excel"],
)

# Los metadatos iniciales se cargan al construir la fachada.
print(f"Tablas: {len(documentation.tablas)}")
print(f"Vistas: {len(documentation.vistas)}")
print(f"Rutinas: {len(documentation.rutinas)}")

# Generar los ficheros de salida
documentation.generate()
db_manager.close()
```

---

## Estructura de Salida

Los ficheros se generan en subdirectorios por formato dentro de una carpeta raíz con timestamp:

```
generated_docs/
└── documentacion_20260420_120530/
    ├── HTML/                                      # Sitio HTML navegable
    │   ├── index.html
    │   └── ...
    ├── WORD/
    │   └── documentacion_20260420_120530.docx     # Reporte Word profesional
    └── EXCEL/
        └── documentacion_20260420_120530.xlsx     # Hojas de cálculo Excel
```

Cada formato incluye:

- **HTML:** Índices navegables y páginas por entidad
- **Word:** Tablas formateadas, encabezados y secciones
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
    "vistas": {"imprimir_vistas": False},             # ← No generar
    "rutinas": {"imprimir_procedures": False,         # ← No generar
                "imprimir_function": False},
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

- El constructor `__init__` configura la instancia y carga metadatos iniciales — **no genera ficheros**
- Llama a `.generate()` explícitamente para producir los ficheros de salida
- Los archivos se guardan en `directorio_salida/<nombre>/WORD|EXCEL|HTML/` con nombre auto-generado (timestamp)
- Para generar múltiples formatos, pasa una lista: `formatos=["html", "word", "excel"]`
- Si `formatos=None`, el formato por defecto es `["word"]`
- `formatos` rechaza valores no soportados; usa solo `word`, `excel` o `html`
- Requiere dependencias opcionales: `pip install util-bbdd[doc]`
