## Responsabilidad del módulo

Fachada pública que orquesta la generación de documentación de bases de datos en múltiples formatos (Word, Excel, HTML) mediante arquitectura hexagonal. El constructor configura el estado sin ejecutar I/O; `generate()` dispara la generación. Internamente delega en `DocumentationOrchestrator`, `DocumentationOutputPlanner` y el registro de renderers (`DocumentationRendererRegistry`).

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
    H -->|word| I[WordGenerator]
    H -->|excel| J[ExcelGenerator]
    H -->|html| K[HtmlGenerator]
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

## Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `db_manager` | `SyncDatabaseManager` | Manager con conexión activa | No puede ser `None`; no soporta `AsyncDatabaseManager` |
| `directorio_salida` | `Path` | Directorio donde escribir ficheros | Debe existir y tener permisos de escritura |
| `fichero_salida` | `Path \| None` | Nombre base del fichero (sin extensión) | Si `None`, se genera automáticamente con timestamp y clave de BD |
| `formatos` | `list[str] \| None` | `["word"]`, `["excel"]`, `["html"]` o combinaciones | Si `None`, puede variar entre versiones; especificar siempre |
| `headers_file` | `Path` | JSON con configuración de cabeceras de secciones | Default: fichero interno del paquete |

## Contrato de salida

- `generate()` retorna `None`; los ficheros se escriben en `directorio_salida`.
- **Word**: uno o más ficheros `.docx` numerados si hay más tablas que `tablas_por_documento`.
- **Excel**: un único fichero `.xlsx` con una hoja por tabla.
- **HTML**: directorio con `index.html` + páginas de detalle por tabla.
- Los grafos se insertan como imágenes SVG o PNG en los documentos Word y HTML (requiere `graphviz` y opcionalmente `cairosvg`).

## Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| Error del `SyncDatabaseManager` | Conexión caída o permisos insuficientes durante la consulta de metadatos |
| `FileNotFoundError` | `directorio_salida` no existe o `plantilla_word` no encontrada |
| `ImportError` | `graphviz` o `cairosvg` no instalados cuando se solicitan grafos |

**Casos especiales:**
- `generate()` está separado del constructor para permitir instanciar sin ejecutar I/O — útil para tests o configuración previa.
- El auto-naming de ficheros usa una ventana de 90 segundos (`_AUTO_OUTPUT_BATCH_WINDOW_SECONDS`): ejecuciones del mismo manager sobre la misma BD dentro de esa ventana reutilizan el mismo nombre de fichero para evitar duplicados en pipelines con retry.
- `tablas_por_documento > 50` puede generar ficheros Word que superen el límite de memoria de Word en esquemas grandes.
- Si `formatos=["word"]` y no hay `plantilla_word`, se genera con la plantilla por defecto de `python-docx`.
