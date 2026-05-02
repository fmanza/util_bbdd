# DatabaseDocumentation

## Responsabilidad del módulo

Fachada pública que orquesta la generación de documentación de bases de datos en múltiples formatos (`word`, `excel`, `html`) mediante una arquitectura interna de bootstrap, sesión, planner y renderers. El constructor prepara configuración y metadatos iniciales; `generate()` dispara la escritura de ficheros.

## Diagrama

```mermaid
flowchart TD
    A[DatabaseDocumentation.__init__] --> B[DocumentationBootstrap.build]
    B --> C[SyncDatabaseManagerAdapter]
    B --> D[DocumentationSession]
    A --> E[generate()]
    E --> F[DocumentationOrchestrator]
    F --> G[DocumentationOutputPlanner]
    G --> H{Formatos solicitados}
    H -->|html| K[HtmlGenerator]
    H -->|excel| J[ExcelGenerator]
    H -->|word| I[WordGenerator]
    I & J & K --> L[SyncDatabaseManager vía Adapter]
    L --> M[Base de datos]
    I --> N[Fichero .docx]
    J --> O[Fichero .xlsx]
    K --> P[Ficheros .html]
    E --> Q{¿Grafos solicitados?}
    Q -->|Sí| R[GraphvizRelationshipGraphExt]
    R --> N
```

## API pública

| Método | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `DatabaseDocumentation` | `(db_manager, directorio_salida?, fichero_salida?, imprimir?, formatos?, headers_file?)` | Configura estado sin ejecutar I/O | `DatabaseDocumentation` |
| `generate` | `()` | Genera documentación para todos los formatos configurados | `None` |

### Parámetros de `imprimir` (dict de configuración)

| Clave | Tipo | Descripción | Default |
|---|---|---|---|
| `plantilla_word` | `str \| Path` | Ruta a plantilla `.docx` | Sin plantilla |
| `tablas_por_documento` | `int` | Tablas por fichero Word | `50` |
| `table_style` | `str` | Estilo de tabla Word/Excel | `"Table Grid"` |
| `html_items_por_pagina` | `int` | Elementos por página en índice HTML | `15` |
| `grafo.max_depth` | `int` | Profundidad de relaciones en grafos | `1` |
| `grafo.direction` | `str` | `incoming`, `outgoing` o `both` | `both` |
| `grafo.images_paginated` | `bool` | Genera imágenes paginadas por tabla | `False` |
| `grafo.max_subnodes` | `int` | Máx. tablas por imagen paginada | `10` |
| `grafo.columns.mode` | `str` | `compact`, `relations` o `all` | `compact` |
| `grafo.columns.max_items` | `int` | Máx. columnas visibles en modo compacto | Según configuración normalizada |
| `grafo.cardinality.show_constraint_name` | `bool` | Muestra nombre de constraint en relaciones | `False` |

## Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `db_manager` | `SyncDatabaseManager` | Manager con conexión activa | No puede ser `None`; no soporta `AsyncDatabaseManager` |
| `directorio_salida` | `Path` | Directorio base donde escribir ficheros | Se crean subdirectorios por ejecución y formato |
| `fichero_salida` | `Path \| None` | Nombre base del fichero (sin extensión) | Si `None`, se genera automáticamente con timestamp y clave de BD |
| `imprimir` | `dict[str, Any] \| None` | Configuración de secciones, tablas, vistas, rutinas, estilos y grafos | Se normaliza con `PrintConfigManager` |
| `formatos` | `list[str] \| None` | `["word"]`, `["excel"]`, `["html"]` o combinaciones | Si `None`, usa `["word"]`; valores inválidos lanzan `ValueError` |
| `headers_file` | `Path` | JSON con configuración de cabeceras de secciones | Default: fichero interno del paquete |

## Contrato de salida

- `generate()` retorna `None`; los ficheros se escriben en `directorio_salida`.
- Cada ejecución crea una carpeta raíz bajo `directorio_salida`, derivada de `fichero_salida` o del nombre automático.
- **Word**: fichero `.docx` bajo `WORD/`.
- **Excel**: fichero `.xlsx` bajo `EXCEL/`.
- **HTML**: sitio HTML bajo `HTML/`.
- Cuando se solicitan HTML y Word con grafos, el orquestador ejecuta HTML antes que Word para poblar caché SVG reutilizable.
- Los grafos se insertan como imágenes generadas por Graphviz en los renderers que los soportan.

## Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| Error del `SyncDatabaseManager` | Conexión caída o permisos insuficientes durante la consulta de metadatos |
| `TypeError` | `formatos` no es una lista |
| `ValueError` | `formatos` contiene valores distintos de `word`, `excel` o `html`, o queda vacío tras normalizar |
| `FileNotFoundError` | Plantilla Word o fichero de headers inexistente cuando se configure explícitamente |
| Error de dependencia opcional | Graphviz/Cairo no disponibles cuando una configuración de grafos los requiera |

**Casos especiales:**
- `generate()` está separado del constructor para permitir instanciar sin ejecutar I/O — útil para tests o configuración previa.
- El constructor sí carga metadatos iniciales (`tablas`, `vistas`, `rutinas`) a través del manager adaptado.
- `formatos` se normaliza: espacios y mayúsculas se corrigen, duplicados se eliminan preservando orden.
- El auto-naming de ficheros usa una ventana de 90 segundos (`_AUTO_OUTPUT_BATCH_WINDOW_SECONDS`): ejecuciones del mismo destino dentro de esa ventana reutilizan el mismo nombre para evitar duplicados en pipelines con retry.
- `tablas_por_documento > 50` puede generar ficheros Word que superen el límite de memoria de Word en esquemas grandes.
- Si `formatos=["word"]` y no hay `plantilla_word`, se genera con la plantilla por defecto de `python-docx`.

## Ejemplo técnico mínimo

```python
from pathlib import Path

from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": "demo_documentation.db"},
    use_pool=False,
)

documentation = DatabaseDocumentation(
    db_manager=manager,
    directorio_salida=Path("generated_docs"),
    fichero_salida=Path("demo-sqlite"),
    imprimir={
        "tablas": {"imprimir_tablas": True, "ddl": True, "columnas": True},
        "vistas": {"imprimir_vistas": True, "ddl": True},
        "rutinas": {"imprimir_procedures": False, "imprimir_function": False},
    },
    formatos=["html"],
)
documentation.generate()
manager.close()
```

Para un ejemplo ejecutable que crea una base SQLite de demostración antes de generar la salida, consulta [Generación de Documentación](../examples/database_documentation_generation.md).
