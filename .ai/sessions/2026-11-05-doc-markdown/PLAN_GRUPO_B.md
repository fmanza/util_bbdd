# PLAN + AUDIT_PLAN — Grupo B (renderer Markdown)

`/new-feature` sobre la sesión `2026-11-05-doc-markdown` (PLAN §7, grupo B). Se apoya en el grupo A (`fa6af78c`,
`efb40252`). Quedan fuera los grupos C (`catalog.json`, `llms*.txt`, `mkdocs.yml`), D (trazabilidad), E
(`CHANGES.md`) y F (documentación, versión).

## Inputs

| Input | Valor |
|---|---|
| Objetivo | `DatabaseDocumentation(formatos=["markdown"])` genera una carpeta de ficheros `.md`, uno por objeto, con las mismas secciones y opciones que Word, diagramas ER Mermaid, front matter, anclas, índices paginados y `manifest.json`, de forma determinista |
| Módulos | `doc/infrastructure/renderers/markdown/` (paquete nuevo); `registry.py`, `output_runtime.py`, `print_config_manager.py`, `database_documentation.py` (registro y docstring) |
| API pública | `formatos` admite `"markdown"` (y el alias `"md"`); bloque opcional `imprimir["markdown"]`; `DocumentationResult.outputs["markdown"]` = carpeta `MARKDOWN`. Sin firmas nuevas → MINOR |
| Contrato de entrada | El mismo de Word: `tables`, `views` y `routines` de la sesión, `data_provider` (`DocumentationManagerPort`) y `print_config` normalizado. Los diagramas usan `data_provider.db_manager` (fuente por lotes, ADR-003) |
| Contrato de salida | Árbol UTF-8/LF idéntico byte a byte para el mismo catálogo y las mismas opciones, salvo `generated_at` de `manifest.json`. Progreso `"markdown"` por tabla y cancelación entre tablas, sin dejar la carpeta a medias |
| Reglas de negocio | Sin datos inventados; misma información y mismas cabeceras que Word; las decisiones D1–D7 aprobadas |
| Restricciones | Sin dependencias nuevas (ni Jinja2: constructores Python); sin Graphviz; solo síncrono |
| Motores | Todos; tests con fuente simulada y SQLite |
| Migraciones | No |

## PLAN

### B1 · Registro y configuración

- `output_runtime.py`:
  - `"markdown"` en `_DEFAULT_SUPPORTED_OUTPUT_FORMATS` y carpeta `MARKDOWN` en el mapa de carpetas;
  - alias `"md"` → `"markdown"` en `normalize_output_formats`;
  - el mensaje de error pasa a listar los cuatro formatos.
- `registry.py`: registro `markdown` con `output_extension=None` (carpeta, como HTML),
  `include_graph_generator=False` y `accepts_graph_generator=False`. El Markdown crea su propio
  `MermaidRelationshipGraph`, que no necesita Graphviz.
- `print_config_manager.py`:
  - `DEFAULT_MARKDOWN = {"max_diagram_depth": 2, "index_page_size": 200, "front_matter": True,
    "column_anchors": True}` (los grupos C a E añaden sus claves);
  - normalización del bloque `markdown` (enteros positivos y booleanos, como el resto);
  - `resolve_for_markdown(config)` con los mismos flags que `resolve_for_word` y las opciones del diagrama
    (`direction`, `max_depth` efectiva = `min(grafo.max_depth, max_diagram_depth)`, la configurada para el aviso,
    `max_subnodes` (10 por defecto, como HTML), `columns.mode`/`max_items`, `cardinality.show_constraint_name` y
    `summary.enabled`).
- `database_documentation.py`: el docstring documenta `"markdown"` y el bloque `markdown`; se pasa la clase a
  `build_default_renderer_registry(markdown_generator_cls=…)`.

### B2 · Paquete `doc/infrastructure/renderers/markdown/`

| Módulo | Responsabilidad | Tamaño orientativo |
|---|---|---|
| `markdown_generator.py` | `MarkdownGenerator` (`DocumentRendererPort`): resuelve la configuración, recorre objetos con `TableProgress("markdown")`, coordina páginas, diagramas y escritura | ~200 |
| `_text.py` | Escape en línea (ver B5), celdas GFM, *fence* segura, enlace relativo y front matter (`json.dumps` en una línea entre `---`) | ~120 |
| `_slugs.py` | `SlugPolicy`: nombres de fichero estables (B4) y anclas de columna | ~100 |
| `_pages.py` | Constructores de página de tabla, vista y rutina, que devuelven `list[str]` de líneas | ~300 |
| `_site_pages.py` | `index.md`, índices por letra, `database/info.md`, `storage.md` y `engine-conditions.md` | ~250 |
| `_front_matter.py` | Registro estructurado por objeto desde el snapshot: `id`, `kind`, `engine`, `schema`, `name`, `pk`, `fk_out`, `fk_in`, `hash`. Lo reutilizará `catalog.json` (grupo C) | ~120 |
| `_writer.py` | `StagedWriter`: escribe en una carpeta temporal, calcula hashes, publica (B6) y escribe `manifest.json` | ~150 |

Reutilización sin duplicar (todo en `renderers/shared/` o `application/use_cases/`):

- filas de las secciones: `GeneratorTableRuntime.extract_table_row_data`, `GeneratorTabularRuntime.process_columns_data`,
  `process_unique_constraints_data` y `process_indices_data`;
- rutinas: `GeneratorRoutineRuntime.normalize_entry`, `split_by_type`, `filter_by_flags` y `parameter_rows`;
- portada: `GeneratorInventoryRuntime.build_summary_rows_from_entities`,
  `GeneratorDatabaseInfoRuntime.collect_database_info_rows`, `EngineConditionsSectionBuilder.of`,
  `build_diagram_legend_payload` / `build_diagram_legend_rows` y `build_diagram_summary_payload` / `line`.

### B3 · Estructura de salida

```text
<directorio_salida>/<nombre>/MARKDOWN/        # outputs["markdown"]
  manifest.json
  docs/
    index.md                                  # título, avisos, leyenda (si hay diagramas), inventario, enlaces
    tables/index.md                           # letras con recuento → tables/index-a.md (+ index-a-2.md si > index_page_size)
    tables/<slug>.md
    views/index.md, views/index-<letra>.md, views/<slug>.md
    routines/index.md, routines/index-<letra>.md, routines/<tipo>-<slug>.md
    database/info.md | storage.md | engine-conditions.md   # según flags, como al final del Word
```

- Letra del índice: primer carácter sin tildes (NFKD) en minúscula: `a`–`z`, `0-9` o `otros`.
- Orden de los objetos: `casefold` y, a igualdad, el nombre exacto (D1).
- Columnas, índices y parámetros mantienen el orden del catálogo (ordinal), como Word.
- Secciones de cada página: las de Word con sus flags, cabeceras de `headers_config.json` y mismos mensajes
  vacíos («No se encontraron …»). DDL en *fence* `sql`. Diagramas al final de la página de tabla, con el resumen de
  niveles y los avisos de `MermaidErResult`. Si el tope recorta la profundidad, aviso
  `!!! warning "Profundidad limitada a N (configurada M)"`.
- Enlaces internos relativos: FK → página de la tabla referenciada si se documenta (si no, texto); índice ↔ objeto.

### B4 · Nombres de fichero y anclas

- `safe_file_stem(nombre)` (`_core/filenames.py`), truncado a 80 caracteres.
- Colisión en el mismo tipo de objeto (`Foo`/`FOO`, sobrecargas): **todos** los del grupo llevan
  `-<8 hex sha256(nombre exacto)>`. Así el slug no depende del orden.
- Reservados de Windows (`con`, `prn`, `aux`, `nul`, `com1-9`, `lpt1-9`) e `index` / `index-*`: sufijo hash.
- Rutinas: `<tipo>-<slug>`, con la clave `TIPO:nombre` como en el HTML.
- Anclas de columna: `col-<slug>`, únicas dentro de la tabla con la misma regla. Van como `<a id="…"></a>` en la
  primera celda (validado en SPIKE_C3).
- Toda ruta final se comprueba dentro de `docs/` (`resolve()` + `is_relative_to`).

### B5 · Escape (S1–S3 del AUDIT_PLAN)

- Texto en línea (comentarios, nombres, valores): `&` → `&amp;`, `<` → `&lt;` y `>` → `&gt;` primero; después
  barra invertida delante de `` \ ` * _ ~ [ ] | # ``. Saltos de línea → espacio.
- Celdas: lo anterior más `|` (ya incluido).
- Bloques de código: sin escape; *fence* de longitud máxima de racha de backticks + 1 (mínimo 3).
- Front matter: `json.dumps(..., ensure_ascii=False, sort_keys=True)` en una línea. Un salto de línea queda
  escapado como `\n` dentro de la cadena JSON.
- Diagramas: lo ya escapado por `MermaidRelationshipGraph`, dentro de una *fence* `mermaid`.

### B6 · Escritura, determinismo y limpieza

- `StagedWriter` escribe en `<raíz>/.MARKDOWN.tmp-<uuid>/` (mismo volumen), con `newline="\n"` y UTF-8.
- Al terminar, si `MARKDOWN/manifest.json` existe y es nuestro (`format == "util_bbdd.doc.markdown"`), borra de
  `MARKDOWN/` solo los ficheros que ese manifiesto lista y la nueva generación no produce. Cada ruta se valida dentro
  de la carpeta. Después mueve cada fichero nuevo con `os.replace` y elimina el staging.
- Sin manifiesto previo no se borra nada; los ficheros ajenos se conservan siempre.
- Cancelación o error: se elimina el staging (`finally`) y la versión anterior queda intacta.
- `manifest.json`:

  ```json
  {"format": "util_bbdd.doc.markdown", "format_version": 1, "util_bbdd_version": "5.3.0", "engine": "…",
   "schema": "…", "database": "…", "generated_at": "…", "files": {"docs/index.md": "sha256:…", …}}
  ```

  Es el único fichero con fecha. Ordenado, con `indent=2`.

### Tests (`tests/unit/`, SQLite y fuente simulada)

| Fichero | Casos |
|---|---|
| `test_doc_markdown_text.py` | `<script>`, `<img onerror>`, `&`, `*y*`, `_x_`, `` ` ``, `[a](javascript:…)`, `\|`, `#`, saltos de línea, *fences* con ```` ``` ```` y ```` ```` ```` dentro, front matter con `"`, `:`, `---` y saltos |
| `test_doc_markdown_slugs.py` | `Foo`/`FOO` estables al reordenar; `CON`, `index`, nombre de 200 caracteres, unicode, sobrecargas de rutinas; anclas de columna con colisión |
| `test_doc_markdown_config.py` | `imprimir["markdown"]` por defecto y valores inválidos; alias `md`; profundidad efectiva y aviso |
| `test_doc_markdown_e2e.py` | SQLite con 3 tablas y FK + vista: árbol esperado; secciones por flags (todas activas e inactivas, igual que Word); cabeceras de `headers_file` propio; diagrama con `\|o`; índices; **determinismo byte a byte** entre dos generaciones (sin `manifest.json`); progreso `"markdown"` por tabla; cancelación → sin staging y versión anterior intacta; regeneración con tabla eliminada → su `.md` desaparece y un fichero ajeno sobrevive; sin `graphviz` (subproceso) |
| `test_doc_markdown_pagination.py` | 450 tablas sintéticas (fuente simulada): índices por letra con subpáginas de 200; `0-9` y `otros` |
| `test_documentation_contract.py` (existente) | Ajuste si enumera formatos soportados |

Puertas: `ruff format`/`check`, `mypy` completo, `pytest` y `gen_arquitectura_capas.py`. `doc → analysis` ya
existe: no hay aristas nuevas.

## AUDIT_PLAN

### Riesgos funcionales

| # | Riesgo | Mitigación |
|---|---|---|
| BF1 | Paridad de secciones con Word (flags, mensajes vacíos, rutinas «otras», info BD al final) | Constructores que reciben los mismos flags resueltos; test e2e con todas las combinaciones relevantes |
| BF2 | Las filas de `data_provider` (tablas Markdown) y el snapshot (front matter y diagramas) son dos lecturas | Las dos salen del mismo snapshot por lotes (el adaptador construye las filas desde él, ADR-003). Test de coherencia PK/FK entre el front matter y la tabla |
| BF3 | El orden de columnas, índices y FK depende del orden que devuelve el catálogo del motor | Se conserva el de Word (ordinal). Las FK de `fk_in` y los objetos se ordenan. Riesgo residual en motores sin `ORDER BY`: se anota para verificar con el banco antes del cierre de versión |
| BF4 | FK hacia tablas no documentadas (otro schema, o `imprimir_tablas` desactivado) | Texto sin enlace; en el front matter, id con su schema |

### Riesgos técnicos

| # | Riesgo | Mitigación |
|---|---|---|
| BT1 | `os.replace` en Windows con ficheros abiertos (el antivirus, o el visor del usuario) | Reintento corto y error claro (`DocumentationRenderError` con la ruta); el staging se limpia |
| BT2 | Rutas largas en Windows | Slug ≤ 80 + hash; la ruta total depende de `directorio_salida`, se documenta |
| BT3 | LSP con `DocumentRendererPort` | Misma firma; `graph_generator` se acepta y se ignora (`accepts_graph_generator=False` hace que no llegue) |
| BT4 | Tamaño de `_pages.py` | Separación en `_pages.py` (objetos) y `_site_pages.py` (índices y portada) |
| BT5 | `DocumentationGraphDomainService.GRAPH_FORMATS` no incluye `markdown` | Correcto: el orquestador no crea Graphviz solo para el Markdown. El renderer lee `grafo.enabled` |
| BT6 | Rendimiento con 500+ tablas: un `render_er` por tabla | Snapshot cacheado y `GraphDocument` cacheado por tabla. Test de paginación con 450 tablas como humo de tiempo |

### Riesgos de seguridad

| # | Riesgo | Mitigación |
|---|---|---|
| BS1 | XSS por HTML del catálogo en el sitio publicado | Escape de B5; test con entradas hostiles; SPIKE_C3 ya comprobó el comportamiento en Zensical |
| BS2 | Travesía de rutas por nombres o por el `manifest.json` previo | Slugs saneados; toda ruta validada dentro de la carpeta; un manifiesto ajeno o malformado no borra nada |
| BS3 | Enlaces `javascript:` desde el catálogo | El texto del catálogo nunca se convierte en enlace (`[` y `]` escapados); los únicos enlaces son relativos y generados |

### Simplificaciones

- Sin Jinja2 ni plantillas personalizables: se puede añadir más adelante si se pide.
- Las vistas y rutinas no llevan progreso (igual que Word, que solo informa de tablas).
- `hash` del front matter: sha256 del registro estructurado del objeto en JSON canónico. No cubre el DDL; el
  `catalog.json` del grupo C lo amplía.

### Veredicto: `GO_CONDICIONAL`

Condiciones:

1. **BC1**: el test de determinismo byte a byte y el de limpieza con fichero ajeno pasan antes de cerrar el grupo.
2. **BC2**: un `zensical build --strict` sobre la salida e2e (local; en CI, solo si `zensical` está instalado, con
   `pytest.mark.integration`) sin incidencias. Requiere un `mkdocs.yml` de prueba en el test, porque el generado
   llega en el grupo C.
3. **BC3**: confirmación del usuario sobre la estructura `MARKDOWN/{manifest.json, docs/}`. Cambia lo escrito en
   PLAN §4.1 (`MARKDOWN/<nombre>/`): la carpeta `<nombre>` ya la crea la ejecución por encima de `MARKDOWN`.
