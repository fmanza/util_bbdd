# Prompt: doc_markdown_feature (Python library)

Nueva funcionalidad: generar la documentación de un schema en **Markdown** desde `src/util_bbdd/doc/`, con
diagramas entidad-relación en **Mermaid**, pensada para leerla una persona, publicarla con Zensical/MkDocs y
que una IA la interprete y la trace con el código y la documentación funcional y técnica.

Este prompt aplica las fases y reglas de `new_feature.prompt.md` (política: **prohibido refactorizar** código no
relacionado), pero **solo emite PLAN y AUDIT_PLAN**. No se implementa nada ni se edita ningún fichero de `src/`,
`tests/` ni `docs/`. La salida va a la sesión `.ai/sessions/<fecha>-doc-markdown/` (plantilla
`.ai/sessions/TEMPLATE/`).

Agente: Plan Architect (PLAN + AUDIT_PLAN).

---

## Inputs (prefijados; confirma o corrige antes de emitir PLAN)

- **Objetivo**: nuevo formato `"markdown"` en `DatabaseDocumentation(formatos=[...])`, con las mismas secciones y
  opciones de `imprimir` que Word, diagramas ER en Mermaid, salida paginada para schemas de 500+ tablas,
  integrable en Zensical/MkDocs, descargable y versionable.
- **Módulos**:
  - `src/util_bbdd/doc/infrastructure/renderers/markdown_generator.py` `(nuevo)`
  - `src/util_bbdd/doc/infrastructure/renderers/shared/mermaid_er.py` `(nuevo)` — emisor `erDiagram` desde
    `GraphDocument`
  - `src/util_bbdd/doc/infrastructure/renderers/registry.py` — registro `"markdown"`
  - `src/util_bbdd/doc/infrastructure/runtime/output_runtime.py` — `_DEFAULT_SUPPORTED_OUTPUT_FORMATS` y carpeta
    `MARKDOWN`
  - `src/util_bbdd/doc/infrastructure/renderers/shared/print_config_manager.py` — `resolve_for_markdown()` y bloque
    `imprimir["markdown"]`
  - `src/util_bbdd/doc/database_documentation.py` — docstring y `build_default_renderer_registry(...)`
- **API pública esperada**: sin firmas nuevas; `formatos` admite `"markdown"` (decidir si también el alias `"md"`) y
  `imprimir` admite el bloque `markdown` (ver § Decisiones). `DocumentationResult.outputs["markdown"]` es la carpeta
  raíz generada. Cambio MINOR (SemVer).
- **Contrato de entrada**: el mismo `DocumentationSourcePort` y `print_config` normalizado que usan Word/Excel/HTML;
  catálogo leído por lotes (ADR-003), sin SQL de catálogo nuevo fuera de `metadata/`.
- **Contrato de salida**: árbol de ficheros `.md` UTF-8 (LF) determinista para el mismo snapshot, con manifiesto
  máquina-legible; progreso `on_progress` en fase `"markdown"` por tabla y cancelación entre tablas.
- **Reglas de negocio**: no inventar metadatos; un dato ausente se marca como ausente, nunca se rellena; mismo orden
  y mismas secciones que Word salvo las alternativas aprobadas en § Decisiones.
- **Restricciones técnicas**: sin dependencias nuevas obligatorias (Jinja2 ya es dependencia; sin PyYAML salvo que
  el PLAN lo justifique como extra); **sin Graphviz** para el Markdown (Mermaid se genera como texto desde el modelo
  agnóstico `GraphDocument` de `analysis/base.py`); solo síncrono, como el resto de `doc/`.
- **Motores afectados**: todos (la salida no depende del motor; los nombres sí: mayúsculas de Oracle, nombres
  entrecomillados de PostgreSQL/SQL Server, schemas de MySQL/MariaDB).
- **Migraciones**: ninguna.
- **Archivos relevantes existentes**:
  - `doc/infrastructure/renderers/word_generator.py` — orden de secciones de referencia (`_generate_single_document_chunk`,
    `_add_table_section`, `_add_columns_section`…, `_add_table_diagram_page`, `_build_diagram_summary_payload`).
  - `doc/infrastructure/renderers/html_generator.py` — salida multi-fichero, `_build_unique_slug` / `_build_slug_map`.
  - `doc/data/headers_config.json` — cabeceras de cada sección (las del Markdown deben ser las mismas).
  - `doc/application/ports.py` — `DocumentRendererPort`.
  - `doc/infrastructure/renderers/shared/diagram_summary.py` y `diagram_legend.py` — resumen de niveles y leyenda.
  - `analysis/base.py` — `build_graph_document`, `GraphDocument`, `HiddenLevelsSummary`, `CardinalityEndMarker`,
    `_split_relations_for_visualization`.
  - `comparar/reporters/_base.py` — `escape_mermaid_label` (G46) y `comparar/reporters/markdown_reporter.py`
    (`_mermaid_node_id`): reutilizar o mover a un punto común, no duplicar.
  - Proyecto web `C:\Desarrollo\python\libs\util_bbdd_web` (solo lectura desde aquí):
    `backend/app/integrations/util_bbdd/documentation.py` (`_FORMAT_DIRS`, recolocación en `outputs/{word,excel,html}`),
    `backend/app/api/v1/runs.py` (descarga de artefactos y ZIP de la ejecución `/{run_id}/archive`),
    `docs/plan/UTIL_BBDD_GAPS.md` (huecos de API; siguiente id libre tras G48).

Si algún input no se sostiene al leer el código, detente y aclara antes de emitir PLAN.

---

## Decisiones a resolver en el PLAN

Para cada una, el PLAN presenta las opciones con ventajas e inconvenientes, **recomienda una** y deja explícito qué
queda a confirmar por el usuario. Las recomendaciones de abajo son el punto de partida, no un hecho cerrado.

### D1. Reglas de formato: paridad con Word y alternativas

Paridad por defecto con Word: mismas secciones y flags de `imprimir` (`tablas.ddl|columnas|pk|fk|unicas|indices|
charset_collation`, `vistas`, `rutinas`, `info_database`, `almacenamiento`, `condiciones_motor`, `grafo`), mismas
cabeceras de `headers_config.json`, mismo orden (leyenda de diagramas → inventario → tablas → vistas → rutinas →
info BD → almacenamiento → condiciones del motor). Alternativas propias de Markdown que el PLAN debe valorar:

- DDL en bloque ```` ```sql ```` (no tabla); tablas GFM con `|`, saltos de línea y backticks escapados.
- Front matter YAML por fichero (ver D2), anclas estables por columna y por restricción.
- `tablas_por_documento` y `table_style` no aplican: los sustituye la paginación de D4; `plantilla_word` tampoco.
- Leyenda de diagramas una vez en el índice, no repetida.
- Sin emojis ni marcas temporales en el cuerpo (determinismo; la fecha va al manifiesto).

### D2. Markdown legible por IA y trazable con código y documentación

| Opción | Qué añade | Coste |
|---|---|---|
| A. Front matter YAML | `id` estable (`table:<schema>.<tabla>`), `kind`, `schema`, `engine`, `pk`, `fk_to`, `fk_from`, `tags`, `snapshot_hash` | Bajo |
| B. Manifiesto máquina-legible | `catalog.json` (o JSONL): objetos, columnas, FK, ruta de su `.md`, hash por fichero | Bajo |
| C. `llms.txt` / `llms-full.txt` | Índice y concatenado para ingestión por LLM | Bajo |
| D. Anclas y ids estables | `{#col-<tabla>-<columna>}` por columna, para enlazar desde código, requisitos o ADR | Bajo (verificar `attr_list` en Zensical) |
| E. Mapa de trazabilidad de entrada | Fichero opcional (`trace_map`: tabla → módulos de código, documentos funcionales/técnicos, requisitos) que el generador vuelca en una sección «Trazabilidad» y en el front matter | Medio: contrato nuevo de entrada |
| F. Mapa inverso | `traceability.md` con la matriz tabla ↔ artefacto, a partir de E | Medio |

Recomendación de partida: **A + B + D** en la primera versión; **C** si su coste es trivial; **E + F** como fase 2
(nuevo contrato de entrada que conviene validar con un caso real). Relacionar con `normative_traceability.prompt.md`
si aplica.

### D3. Profundidad de las relaciones en los diagramas Mermaid

Opciones:

1. Profundidad fija 1 siempre, avisando en el propio documento.
2. Usar `grafo.max_depth` / `grafo.direction` como Word y HTML.
3. Usar la variable con un tope propio del Markdown y aviso cuando se recorte.

Recomendación de partida: **3**. Respeta la configuración que ya expone la web y mantiene la coherencia entre
formatos, pero acota lo que Mermaid dibuja de forma legible y fiable (límites de aristas y de tamaño de texto del
renderer, que el PLAN debe verificar para Mermaid 12). Por defecto `max_depth=1`; tope configurable
(`imprimir["markdown"]["max_diagram_depth"]`, p. ej. 2) y reparto por `grafo.max_subnodes` reutilizando
`_split_relations_for_visualization`. Cada diagrama lleva siempre debajo el resumen de niveles
(`diagram_summary.py`: niveles visibles y ocultos por dirección) y, si hubo recorte, un aviso explícito. Las
relaciones completas quedan en texto (tablas FK) y en `catalog.json`, que es lo que una IA debe usar para trazar;
el diagrama es apoyo visual.

### D4. Paginación para schemas de 500+ tablas

| Opción | Ventajas | Inconvenientes |
|---|---|---|
| Un fichero por objeto | Granularidad ideal para RAG e IA, diffs en git por tabla, enlaces estables, navegación Zensical | Miles de ficheros; nav larga |
| Paquetes de N tablas | Pocos ficheros, parecido a Word (`tablas_por_documento`) | Enlaces inestables si cambia el reparto; diffs ruidosos; trozos grandes para IA |
| Paquetes por dominio (prefijo, schema o componente conexo de FK) | Agrupa por significado | Heurística frágil; nombres sin convención |

Recomendación de partida: **un fichero por objeto** (tabla, vista, rutina) como modo por defecto, con índices
paginados (`tables/index.md` por letra o por bloques de `html_items_por_pagina`) y diagrama global solo por
paquetes (nunca un ERD de 500 tablas). Modo alternativo `imprimir["markdown"]["layout"] = "bundled"` con
`tables_per_file` si el PLAN lo justifica. Estructura de partida (a validar):

```text
MARKDOWN/<nombre>/
  index.md                 # portada: info BD, inventario, leyenda, enlaces
  tables/index.md          # índice paginado
  tables/<slug>.md         # una tabla: front matter, columnas, PK, FK, únicas, índices, DDL, diagrama
  views/<slug>.md
  routines/<slug>.md
  database/storage.md | engine_conditions.md
  catalog.json             # D2-B
  manifest.json            # versión de util_bbdd, fecha, hash del snapshot y por fichero (D7)
  mkdocs.yml               # opcional (D5)
```

Slugs: deterministas, sin colisiones en sistemas de ficheros que ignoran mayúsculas (Windows), sin nombres
reservados (`CON`, `NUL`…) ni travesías de ruta; reutilizar `_build_unique_slug` del HTML si encaja.

### D5. Integración con Zensical / MkDocs

- Mermaid con `pymdownx.superfences` (`custom_fences` `mermaid`), que es la configuración de este repo
  (`mkdocs.yml`); verificar que Zensical la soporta igual y con qué versión de Mermaid.
- Opciones: (a) carpeta autocontenida con su `mkdocs.yml` mínimo (`zensical build` directo); (b) solo fragmento
  `nav` para incrustarla en un sitio existente; (c) sin `nav` (navegación automática por carpetas). Recomendación de
  partida: **(a) opcional + (c)**: con 500+ tablas, una `nav` explícita es ingobernable.
- Validar con `zensical build --strict` sobre un SQLite de prueba con FK.

### D6. Descarga

- Librería: `outputs["markdown"]` es la carpeta; opción `imprimir["markdown"]["zip"]` que añade
  `<nombre>-markdown.zip` (+ SHA256), coherente con `scripts/build_docs_zip.py` si procede.
- Web (`util_bbdd_web`, proyecto aparte; aquí solo se planifica): añadir `"markdown": "MARKDOWN"` a `_FORMAT_DIRS`,
  registrar los artefactos, descarga individual y ZIP de la ejecución que ya existe (`/{run_id}/archive`); valorar
  vista previa del Markdown (la web ya sanea Mermaid con `stripMermaidConfig`, G46) o del sitio Zensical construido
  (ADR-007). Registrar el hueco en `docs/plan/UTIL_BBDD_GAPS.md` de la web con el siguiente id libre.

### D7. Versionado de la documentación

| Opción | Cómo | Encaje |
|---|---|---|
| a. Carpeta por generación | Comportamiento actual (`<bd>-<fecha_hora>`) | Ya existe; historial sin diff |
| b. Salida estable + git | Ruta fija y salida determinista; el control de versiones es git | Diffs por tabla legibles; requiere determinismo estricto |
| c. Manifiesto con hashes | `manifest.json`: versión de util_bbdd, motor, schema, hash del snapshot y por fichero | Detecta cambios sin comparar contenido; base de a, b y d |
| d. Changelog de esquema | `SchemaComparator` entre el snapshot anterior y el actual → `CHANGES.md` | Reutiliza `comparar/`; necesita el snapshot anterior |
| e. Sitio versionado | `mike` (MkDocs Material) o carpetas `v<N>/` | Verificar soporte en Zensical |

Recomendación de partida: **c siempre + b como uso recomendado**; **d** como fase 2; **e** solo si Zensical lo
soporta. En la web, el historial de ejecuciones ya cubre a.

---

## Devuelve en este orden

### PLAN
- objetivo
- decisiones D1–D7: opciones, recomendación y qué confirma el usuario
- rutas afectadas (librería) y, aparte, cambios propuestos para `util_bbdd_web` (no se ejecutan aquí)
- componentes implicados y su encaje en las capas de `doc/` (domain / application / infrastructure) y en el
  diagrama de capas (`scripts/gen_arquitectura_capas.py` si cambian imports entre paquetes, p. ej. `doc` → `comparar`
  para `escape_mermaid_label`: preferible mover el escape a un punto común)
- tipos necesarios (opciones de `imprimir["markdown"]`, estructura de `catalog.json` y `manifest.json`)
- ejemplo de salida: un `tables/<slug>.md` completo (front matter, secciones, Mermaid `erDiagram`) para un SQLite de
  prueba de 3 tablas con FK
- plan de tests (SQLite en memoria; determinismo byte a byte; escape; slugs; paginación; cancelación) y de
  documentación (`docs/api/database_documentation.md`, guía funcional, `mkdocs.yml`, CHANGELOG)
- fases de entrega (MVP y fase 2)
- riesgos

### AUDIT_PLAN
- riesgos funcionales (paridad con Word, rutinas y vistas sin relaciones, schemas sin FK, tablas con 100+ columnas)
- riesgos técnicos: LSP/ISP con `DocumentRendererPort` y `RendererRegistration` (`include_graph_generator` sin
  Graphviz), memoria y tiempo con 500+ tablas (un solo `build_graph_document` por tabla, sin releer el catálogo),
  límites de Mermaid 12 (`erDiagram`: nombres de entidad y tipos de atributo con paréntesis, espacios o comillas),
  compatibilidad Zensical/MkDocs
- riesgos de seguridad: comentarios y nombres del catálogo son **datos no confiables** → escape de HTML en línea
  (Zensical/MkDocs renderizan HTML crudo), de Markdown, de YAML del front matter y de Mermaid (directivas `%%{init}`,
  saltos de línea; G46); nombres de fichero (travesía, reservados, colisiones)
- simplificaciones posibles (qué recortar del MVP)
- **Veredicto:** `GO | NO_GO | GO_CONDICIONAL` (con condiciones si aplica)

---

## Reglas

- No implementar: ni código, ni tests, ni docs. Solo los artefactos de sesión (`00_REQUEST.md`,
  `00_CONTEXT_SNAPSHOT.md`, `PLAN.md`, `AUDIT_PLAN.md`).
- No inventar capacidades de Zensical, MkDocs ni Mermaid: lo no verificado se marca «pendiente de verificación» con
  la comprobación concreta que lo cerraría.
- Citar `archivo:línea` para cada afirmación sobre el código existente.
- Respetar ADR-003 (metadatos por lotes en `metadata/`) y las reglas de `SHARED_INSTRUCTIONS.md`.
- El proyecto `util_bbdd_web` se lee, no se edita.
