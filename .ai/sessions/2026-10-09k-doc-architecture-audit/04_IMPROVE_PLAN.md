# IMPROVE_PLAN — `doc/` + `analysis/`

Hallazgos añadidos al leer los flujos de diagramas (completan `02_AUDIT_ARCH.md`/`03_AUDIT_CODE.md`):

| ID | Sev. | Hallazgo | Evidencia |
|---|---|---|---|
| P-04 | Media | Con `grafo.images_paginated=False`, HTML lanza un `dot` extra por tabla (`_cache_single_svg_for_word`) para una caché de Word que, en una ejecución solo HTML, nadie lee: una llamada más por tabla además de las de cada nivel. *(Corregido en VERIFY: la primera versión decía «siempre» y estimaba 120 de 238 llamadas; con el valor por defecto `images_paginated=True` no ocurre)* | `html_generator.py:1715-1722, 1914-1962` |
| B-02 | Media (bug) | El .docx cambia según qué otros formatos se pidan. Con Word+HTML, Word paginado inserta las páginas por nivel de la caché HTML («Salida - Nivel 1») en vez de paginar por `max_subnodes` («Página N»), y Word sin paginar convierte el SVG de HTML con cairosvg en vez de usar el render raster de Graphviz (`_get_table_label_styles(is_raster=True)`) | `word_generator.py:743-752, 651-662, 793-856` |
| A-13 | Alta | `graphviz_ext.py` repite el montaje del `dot` en 3 métodos y mantiene 3 pares disco/memoria casi idénticos (`generate_graphviz_level_graphs_ext`/`pipe_level_graphs_ext`, `generate_graphviz_graph_paginated_ext`/`pipe_paginated_graph_ext`, `_generate_graphviz_graph_internal_ext`/`_pipe_graph_internal_ext`/`pipe_single_table_graph_ext`): ≈ 250 LOC | `graphviz_ext.py:465-1255` |
| A-14 | Media | HTML escribe cada SVG en disco, lo vuelve a leer para inyectar enlaces, lo reescribe y lo lee otra vez para incrustarlo: 4 E/S por SVG (4,3 s en `open` con 120 tablas). Las ramas `hasattr(graph_generator, …)` de respaldo están muertas: el generador siempre tiene `pipe_*` | `html_generator.py:1696-1760, 1499-1525` |

## Estrategia

Sin paquetes por motor (ver `01_PLAN.md` §1). Cinco paquetes de trabajo independientes, cada uno con commits y validación propios:

### WP1 — Grafos: un solo camino, en paralelo y determinista (P-01, P-04, B-02, A-02, A-03, A-13, A-14)

1. `GraphvizRelationshipGraphExt`:
   - `_build_dot(document, *, table_name, format, show_columns)`: el único montaje del `dot`.
   - `_pipe(dot, format)`: caché por `(format, dot.source)`, con un `Future` por entrada.
   - `prefetch(render, table_names)`: ejecuta `render(tabla)` en modo captura (construye los `dot` sin lanzarlos), envía los subprocesos a un `ThreadPoolExecutor` y las llamadas reales recogen el resultado. `render_workers` (por defecto `min(8, os.cpu_count())`; `grafo.workers` en `imprimir`; con `1` no hay paralelismo). `clear_cache()` vacía la caché.
   - Las variantes en disco (`generate_*`) pasan a ser `pipe_*` + `write_bytes`: se elimina la duplicación.
2. Una sola fábrica del generador (`build_graph_generator_from_options`), usada por el orquestador, que respeta `show_columns`, `dpi` y `workers`. Si `grafo.enabled`, el orquestador crea **un** generador y se lo pasa a Word y HTML. Desaparecen los `_build_graph_generator` de los renderers.
3. Se elimina la caché SVG cruzada entre renderers: `DocumentationSession._svg_*`, `get/cache_svg_bytes`, `get/cache_level_groups`, `_write_level_groups_cache`, `_cache_single_svg_for_word`, `_try_insert_from_level_cache`, `_try_get_cached_svg_bytes` y la reordenación HTML→Word del orquestador. Cada renderer produce lo mismo con independencia de los demás formatos (corrige B-02); la caché del generador evita repetir un mismo `dot` entre renderers.
4. HTML: precarga de los grafos por nivel, inyección de enlaces en memoria (una sola función) y una única escritura por SVG.
5. Word: precarga de los grafos únicos o paginados según `images_paginated`.

### WP2 — Rendimiento menor y defaults (P-02, P-03, A-11)

- Word: resolver el estilo de tabla una vez por documento.
- `CatalogRows.view_ddl`: índice por nombre.
- Excel: estilo por defecto propio cuando no se configura `table_style` (sin aviso).

### WP3 — Inventario de almacenamiento declarativo (A-01, B-01)

- `storage/engines.py`: una tabla por motor (`StorageQuery(name, title, headers, process=None, on_error=None)`) más `default_tablespace`. Las consultas existentes se toman de `metadata.storage`: SQL Server usa la tabla estándar (corrige B-01) y el aviso de «fallback» queda solo para los motores sin ninguna consulta (HSQLDB).
- Las estrategias de MariaDB/MySQL (una sola, compartida) y Oracle pasan a ser funciones puras sobre filas, más un ejecutor (`StorageQueryRunner`) que reciben como argumento; desaparecen el Protocol de métodos privados y los 15 delegadores.
- Salida idéntica (secciones, cabeceras, formato decimal, mensajes) salvo el aviso falso de SQL Server.

### WP4 — Limpieza (A-04, A-05, A-06, A-09, A-10, A-12)

- Un helper `routine_parameter_rows()` compartido; fuera los envoltorios de una línea.
- Fuera la tolerancia pre-D1: UNIQUE se lee como `(restricción, columna)`; cabeceras sin bloque por motor ni `labels`.
- Fuera el código muerto enumerado en A-06; la sesión deja de duplicar `print_config`/`imprimir_config`.
- `_call_optional_metadata` usa sus mensajes (DEBUG en éxito).
- `matplotlib_graph.py`: `Axes` solo bajo `TYPE_CHECKING`; extra `analysis-matplotlib = ["matplotlib", "networkx"]` en `pyproject.toml`; import duplicado de `graphviz_ext.py:12` fuera.
- Los renderers copian `headers` en lugar de mutarlo.

### WP5 — API pública y errores (A-07, A-08) — **rompe API**

| Antes | Después | Migración |
|---|---|---|
| `from util_bbdd.doc import WordGenerator, ExcelGenerator, HtmlGenerator` | Solo `DatabaseDocumentation` (los generadores siguen en `util_bbdd.doc.infrastructure.renderers`, como internos) | Usar `DatabaseDocumentation(formatos=[...])` |
| `DatabaseDocumentation(...)` lee el catálogo en `__init__` | `__init__` solo valida la configuración (formatos, cabeceras); la lectura se hace en `generate()` | Ninguna, salvo que se leyeran atributos internos |
| Atributos `tablas`, `vistas`, `rutinas`, `catalog`, `headers`, `headers_config`, `imprimir_config`, `table_style`, `db_manager` | Privados | No usarlos |
| `ValueError`/`TypeError` por formatos o config inválidos; `FileNotFoundError`/`ValueError` por el JSON de cabeceras | `DocumentationConfigError` (hereda también de `ValueError`, como `AuditConfigError`) | `except ValueError` sigue funcionando |
| Excepción cruda del renderer, registrada 2 veces | `DocumentationRenderError` (con `__cause__`), registrada una sola vez | `except DocumentationError` |
| Caché de nombres automáticos en un `ClassVar` | Se mantiene (es la que agrupa Word/Excel/HTML de lanzamientos consecutivos en una carpeta) pero protegida con un `Lock` | Ninguna |
| `headers_config.json` con bloques por motor y `labels` | Solo `base` por sección | Quitar las claves por motor de los JSON propios |

Versión: **0.41.0** (en 0.x el minor es la versión de ruptura, igual que en 0.40.0).

## Tests

- Línea base previa a cualquier cambio, guardada en `build/logs/doc_baseline/`: texto de Word, Excel y HTML **con grafos** de los 5 motores del banco + SQLite. Tras cada WP se compara; las únicas diferencias admitidas son las de B-01 y B-02.
- Unit nuevos: caché y precarga del generador (sin Graphviz real, con un `dot` falso), tabla de almacenamiento (SQL Server sin aviso), estilo de Word resuelto una vez, excepciones de la fachada, `__init__` sin E/S, un nombre de tabla hostil en el SVG incrustado (S-01).
- Integración: `test_doc_matches_golden` + `test_analysis_relations` contra el banco tras cada WP.

## Riesgo y rollback

| Riesgo | Mitigación |
|---|---|
| Hilos + subprocesos `dot` en Windows | Solo se paraleliza `dot.pipe` (no se toca el estado de Python desde los hilos); `grafo.workers=1` vuelve al modo serie |
| Cambio visual del .docx en Word+HTML (B-02) | Es la corrección; se documenta en el CHANGELOG |
| Ruptura de imports | Tabla de migración en el CHANGELOG y en `docs/api/database_documentation.md` |
| Rollback | Un commit por WP en `develop`; cada uno es revertible por separado |

## Esfuerzo estimado (secuencial)

WP1 ≈ 3 h · WP2 ≈ 0,5 h · WP3 ≈ 1,5 h · WP4 ≈ 1 h · WP5 ≈ 1 h · VERIFY ≈ 1 h.
