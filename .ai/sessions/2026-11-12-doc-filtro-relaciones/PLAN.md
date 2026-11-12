# PLAN — 2026-11-12-doc-filtro-relaciones

## Diagnóstico verificado

| Punto | Evidencia |
|---|---|
| «Pido 1 nivel y salen 2» | `MermaidRelationshipGraph.render_er` respeta `max_depth`; con `direction="both"` y 1 nivel, el diagrama de `B` en `A→B→C` muestra las tres tablas (prueba con SQLite). El resumen «Salida visible: 1 de 2» y los dos campos de la web (`graph_depth` y `markdown_diagram_depth`, se usa el menor) lo hacen confuso |
| Enlaces del Markdown | 17 enlaces relativos generados, 0 rotos. La sección FK enlaza la tabla referenciada, pero no hay FK entrantes; el diagrama `erDiagram` no admite clic. El fallo de clic en el visor de la web queda por reproducir allí (W2) |
| Instrucciones en la exportación | No había `README.md`: solo `docs/`, `mkdocs.yml` y `manifest.json` |
| Filtro | Ningún filtro en `doc/` |
| 5.4.0 | Ya publicada (tag, release «Latest» y ZIP de documentación del 2026-11-06); formato en ADR-006 y `docs/api/database_documentation.md` |
| Calidad frente a producción | Ya cubierto: `SchemaComparator` en vivo o `markdown.previous` (mismo motor, schema distinto permitido) |

## Grupos

- **L1 Filtro con frontera**: `doc/domain/table_filter.py` (`TableFilter`, puro). Normaliza `PrintConfigManager`;
  aplica `DocumentationBootstrap.build` (punto único, todos los formatos); frontera con
  `CatalogRows.foreign_key_edges()`. `DocumentationResult.frontier`, sección «Alcance» de la portada Markdown,
  `filter`/`frontier` en `catalog.json` y `manifest.json` solo con filtro; `build_changes` compara la intersección
  de los dos filtros.
- **L2 Referenciada por**: `ObjectRecords.referencing_tables`; `_pages._foreign_keys` añade la lista; `_table_link`
  marca las tablas sin ficha si hay filtro.
- **L3 README**: `markdown/_readme.py`, `markdown.readme` (por defecto `True`), fuera de `manifest.pages`.
- **L5 Niveles**: `build_diagram_summary_line` y `detail.html.j2` dicen «Niveles por sentido»; explicación en la
  portada Markdown. El pie de Graphviz no cambia.
- Aplazados: L4 datos de referencia (5.6.0), L6 especificación + JSON Schema, comparación offline entre catálogos.

## Web (repositorio util_bbdd_web)

W1 ancho de las fichas; W2 reproducir el clic en el visor; W3 descarga con README; W4 un solo campo de niveles para
Markdown o el valor efectivo; W5 campos de filtro con ayuda; W6 ayuda interactiva («probar patrón», ayudas por
campo, panel con la documentación); W7 wheel 5.5.0 y `UTIL_BBDD_GAPS.md`.
