# AUDIT_PLAN — Documentación Markdown con ER Mermaid

Audita `PLAN.md` de esta sesión contra el código de `develop` (v5.2.0, `30e47bf1`).

## 1. Riesgos funcionales

| # | Riesgo | Evidencia | Mitigación en el plan | Severidad |
|---|---|---|---|---|
| F1 | Paridad con Word incompleta: secciones condicionadas a flags e `idx == total_chunks` (vistas, rutinas, info BD, almacenamiento y condiciones solo en el último trozo) | `word_generator.py:227-320` | Como el Markdown no tiene trozos, se emite una vez. Test e2e con todas las combinaciones de flags contra la lista de secciones de Word | Media |
| F2 | Las cabeceras de `headers_config.json` son posicionales y varían con `charset_collation` (columnas extra). `catalog.json` no puede depender de las etiquetas | `headers_config.json`, `include_columns_charset` | Claves estables en `catalog.json`; las etiquetas solo en las tablas Markdown. **Verificar en IMPLEMENT** qué posición tiene cada dato en las filas de `get_columns` con y sin charset | Media |
| F3 | Cardinalidad heredada discutible: `M:N` cuando ambas columnas son PK (caso típico 1:1 de tabla de extensión) | `graphviz_ext.py:184-185` | Se traslada sin cambiarla (paridad). Que `M:N` sea en realidad 1:1 se anota como deuda; no se arregla aquí (política sin refactor ajeno) | Baja |
| F4 | Opcionalidad del lado padre (`|o` si la FK admite nulos): Graphviz no la dibuja | `graphviz_ext.py:166` | Decidido (2026-11-06, PLAN §4.4): sí en Mermaid, aunque Word no la tenga. Test con FK nullable y no nullable | Baja |
| F5 | Orden alfabético en lugar del orden del catálogo de Word | PLAN §2.1 | Decisión explícita (determinismo). Documentarlo en la guía | Baja |
| F6 | `CHANGES.md` compara solo dentro del mismo motor y schema; renombrar el schema invalida la comparación | PLAN §4.8 | Error de configuración claro. Permitir `schema` distinto con aviso queda como posible ampliación | Baja |
| F7 | Schemas sin FK: diagramas vacíos en 500 páginas | — | Sin relaciones no hay bloque Mermaid: se escribe «Sin relaciones», como `test_doc_html_isolated_table_diagram.py` | Baja |
| F8 | Tablas con 100+ columnas en `mode=all`: diagrama ilegible | `DEFAULT_GRAPH.columns.max_items=8` | Se respeta `max_items`; guarda de tamaño | Baja |

## 2. Riesgos técnicos

| # | Riesgo | Evidencia | Mitigación | Severidad |
|---|---|---|---|---|
| T1 | **No determinismo**: `_traverse_levels`/`_build_level_data` recorren `frontier: set[str]`, así que el orden de aristas y niveles depende de `PYTHONHASHSEED`, como pasó en G47 | `analysis/base.py:293,331,406,438` | Ordenar la frontera en `base.py`: también estabiliza Graphviz y HTML. El emisor además ordena entidades y relaciones. Test en subproceso con dos semillas | **Alta** (rompe D7) |
| T2 | **Dependencia de Graphviz**: `GraphvizRelationshipGraphExt.__init__` lanza `ImportError` sin el paquete `graphviz` (extra `analysis`), y la cardinalidad vive en esa clase | `graphviz_ext.py:16-22,100-101,166-203`; `pyproject.toml:75` | `MermaidRelationshipGraph` sobre `DatabaseRelationshipGraphBase` y cardinalidad movida a `base.py`. Registro con `include_graph_generator=False`. Test sin `graphviz` | **Alta** |
| T3 | Capas: `analysis` (6) no puede importar `comparar` (6, misma capa), y el escape Mermaid está en `comparar` | `gen_arquitectura_capas.py:43-50`; `comparar/reporters/_base.py:111` | Mover el escape a `_core/mermaid.py` (capa 1) y reimportarlo desde `comparar`. `doc → comparar` (7 → 6) está permitido, pero hay que dibujarlo en `DRAWN` y regenerar; `test_architecture_import_rules.py` lo vigila | Media |
| T4 | LSP/ISP: `DocumentRendererPort` se cumple. `output_extension=None` sigue el camino del HTML (carpeta). Riesgo de que `MarkdownGenerator` crezca como `HtmlGenerator` (1 816 líneas) | `ports.py:207`; `html_generator.py` | Paquete con 8 módulos de una responsabilidad. Límite orientativo de 400 líneas por módulo | Media |
| T5 | Gramática de `erDiagram`: los tipos no admiten comas ni espacios; los comentarios no admiten `"`; los alias siguen las reglas de los nombres | Docs Mermaid 12.3 (CONTEXT_SNAPSHOT) | Normalizador de tipos y nombres con tests. **Spike obligatorio** antes de cerrar el grupo A: renderizar con Mermaid 12 (y con lo que cargue Zensical) un catálogo con nombres Oracle, PostgreSQL entrecomillado, unicode y tipos compuestos | **Alta** |
| T6 | Límites de Mermaid (`maxTextSize`, `maxEdges`) no verificados en la versión 12 | — | Guarda de tamaño con umbral configurable interno. Verificar los valores por defecto en el spike de T5 | Media |
| T7 | Versión de Mermaid de Zensical desconocida; el sitio del repo usa `mermaid@11` de CDN (`mkdocs.yml:292`). La v12 cambia el ER (ELK, `neo`) | CONTEXT_SNAPSHOT | No se emiten directivas de versión. La salida se valida con 11 y 12 en el spike | Media |
| T8 | `docs_dir` dentro del directorio de `mkdocs.yml`: MkDocs lo rechaza si coincide; en Zensical está sin verificar | PLAN §4.1 | Estructura `mkdocs.yml` + `docs/`. Test `integration` con `zensical build --strict` | Baja |
| T9 | Huérfanos y borrado indebido al regenerar en una ruta fija | PLAN §4.5 | Staging + borrado limitado a lo que lista el `manifest.json` previo. Test con un fichero ajeno que debe sobrevivir | **Alta** |
| T10 | Escritura en Windows: CRLF por defecto, `MAX_PATH` 260, nombres reservados, mayúsculas | — | `newline="\n"`, slugs de 80 caracteres + hash, sufijo para reservados. Los tests corren en Windows (entorno del usuario) | Media |
| T11 | Memoria y tiempo con 500+ tablas: `catalog.json` en memoria, `llms-full.txt` grande, `build_graph_document` por tabla | `base.py:168` (caché por tabla) | `llms-full` en *streaming*; `catalog.json` en memoria es aceptable hasta unos miles de tablas (anotar el límite). El snapshot ya está cargado (ADR-003): no hay SQL nuevo. Test `slow` de 600 tablas | Media |
| T12 | `CHANGES.md` repite parte de la semántica de `SchemaComparator` (tipos, defaults, comentarios) | `comparator.py:95` | Alcance limitado al mismo motor, con comparación literal. Se documenta la diferencia. Deuda registrada: unificar con la comparación por snapshots en la fase posterior | Media |
| T13 | `catalog.json` es un contrato nuevo: cambiarlo después rompe `CHANGES.md` entre versiones | — | `format_version` desde la v1, ADR-006 y compatibilidad hacia atrás para leer v1 en `previous` | Media |
| T15 | **Mermaid con Internet** (SPIKE_C3): Zensical 0.0.71 carga `mermaid@11` de unpkg. Sin Internet (ZIP offline de documentación, util_bbdd_web, ADR-007) los diagramas no se dibujan y queda el código fuente | `zensical/templates/assets/javascripts/bundle.*.min.js` | `mermaid_js` local opcional en el `mkdocs.yml` generado. Verificar que Zensical no recarga unpkg con `window.mermaid` presente. Documentarlo en la guía. La vista previa de la web usa su Mermaid 12 incrustado | Media |
| T14 | Mover la cardinalidad y el escape toca `analysis/graphviz_ext.py` y `comparar/` (fuera del módulo `doc`) | Política `new_feature`: sin refactor no relacionado | Es un movimiento **necesario** para la feature (T2, T3), sin cambio de comportamiento y con tests de regresión. Se declara en el commit. Sin más limpieza | Baja |

## 3. Riesgos de seguridad

| # | Riesgo | Mitigación | Severidad |
|---|---|---|---|
| S1 | **XSS en el sitio publicado**: comentarios, nombres y defaults del catálogo son datos no fiables, y Zensical/MkDocs pasan HTML en línea tal cual | Escape de `<`, `>`, `&` en todo texto del catálogo fuera de bloques de código. Las únicas etiquetas HTML las genera la librería (`<a id>`, `<br>`) con valores saneados. Test con `<script>`, `<img onerror>`, `javascript:`. SPIKE_C3 confirma que el escape por entidades evita la ejecución en Zensical, pero `escape_markdown_table_cell` deja pasar el énfasis (`*y*` → `<em>`): el escape de texto debe cubrir `*`, `_`, `~`, `[`, `]` y `` ` `` | **Alta** |
| S2 | Salida de bloque de código: un DDL o comentario con ```` ``` ```` cierra la *fence* | *Fence* más larga que la racha máxima de backticks del contenido | Media |
| S3 | Inyección en el front matter (`---`, `:`, saltos de línea) | Front matter en una línea JSON (`json.dumps`). Test con `---` y saltos | Media |
| S4 | Inyección en Mermaid (`%%{init}`, saltos de línea, `"` en comentarios; G46) | `escape_mermaid_er_text` por entidades (SPIKE_C3: `%%{init}` codificado se muestra como texto y no se aplica; sin HTML ejecutable en el SVG con `securityLevel: "strict"`) + saneado de tipos, nombres y comentarios | Media |
| S5 | Travesía de rutas o nombres reservados en ficheros | `safe_file_stem` + reservados + hash. Ruta final verificada dentro de la carpeta de salida (`resolve()` + `is_relative_to`) | Media |
| S6 | Mapa de trazabilidad: rutas a ficheros o enlaces `javascript:` | Referencias como texto; solo `http(s)` se convierten en enlace; no se lee ningún fichero referenciado | Baja |
| S7 | `previous` apunta a un `catalog.json` manipulado (tamaño o estructura) | Validación de `format`, `format_version` y tipos; límite de tamaño razonable; `json.load` sin `object_hook` | Baja |
| S8 | Limpieza de huérfanos que borra fuera de la carpeta usando rutas del `manifest.json` previo | Cada ruta del manifiesto se resuelve y se exige que quede dentro de la carpeta; si no, se ignora y se avisa | Media |

## 4. Simplificaciones posibles

1. **ZIP en la librería**: fuera del MVP (la web ya lo da) para no cambiar `DocumentationResult`. *A confirmar por el
   usuario.*
2. **Índices por letra sin subpaginación** mientras ninguna letra pase de `index_page_size`. La subpaginación solo
   se activa por encima de ese umbral.
3. **`llms-full.txt`** podría ir desactivado por defecto en esquemas grandes; se mantiene activado porque el usuario
   lo pidió en el MVP.
4. **Constructores Python en lugar de Jinja2**: Jinja escapa HTML, no Markdown, y añadiría filtros propios. Se
   pierde personalización por plantilla (la tienen Word y Excel); si se pide, irá en una fase posterior.
5. **`CHANGES.md`**: reutilizar `MarkdownDiffReporter` tal cual, con su diagrama `graph LR`, en lugar de un formato
   propio.

## 5. Condiciones

1. **C1 (T1)**: recorrido de grafos determinista en `base.py`, con test de dos semillas, antes del grupo B.
2. **C2 (T2)**: el Markdown genera diagramas sin el paquete `graphviz`, con test explícito.
3. **C3 (T5–T8)** — ✅ **cumplida (2026-11-06, `SPIKE_C3.md`)**: sintaxis válida en Mermaid 11.17.2 y 12.2.0 y
   dibujada en Zensical 0.0.71. Cambios incorporados al PLAN: escape ER por entidades, reservados `PK`/`FK`/`UK`,
   guarda de 40 entidades por bloque y riesgo T15 (Mermaid desde unpkg).
4. **C4 (S1–S4)**: batería de escape con entradas hostiles en verde antes de cerrar el grupo B.
5. **C5 (T9, S8)**: limpieza de huérfanos acotada al manifiesto y a la carpeta, con test de fichero ajeno.
6. **C6 (T13)**: ADR-006 de `catalog.json` aprobado antes del grupo E.
7. **C7** — ✅ **cumplida (2026-11-06)**: el usuario acepta D1 (alternativas de formato y orden alfabético), D6
   (sin ZIP en la librería), F4 (lado padre `|o` si la FK admite nulos) y el tope de profundidad 2. El formato del
   mapa de trazabilidad: TOML recomendado y JSON aceptado, elegido por extensión (PLAN §4.7).

## Veredicto

**GO_CONDICIONAL**. El diseño encaja en los puertos y el registro de `doc/` sin romper la API (MINOR 5.3.0) ni
añadir dependencias obligatorias. Las condiciones C1–C7 cubren los tres riesgos altos encontrados al leer el código:

- el recorrido no determinista de `base.py`;
- la dependencia implícita de Graphviz;
- el XSS por HTML del catálogo.

También cubren la incertidumbre de Mermaid 12 y Zensical con `erDiagram`.
