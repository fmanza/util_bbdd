# AUDIT_ARCH — `doc/` + `analysis/`

Lectura completa de `doc/` (fachada, aplicación, infraestructura) y `analysis/`; recuento de usos con `grep` sobre `src/` y `tests/`.

## Hallazgos de arquitectura y duplicidad

| ID | Sev. | Hallazgo | Evidencia |
|---|---|---|---|
| A-01 | Alta | El inventario de almacenamiento acopla las estrategias al runtime en los dos sentidos: `MariadbStorageInventoryStrategy` y `OracleStorageInventoryStrategy` reciben el runtime y llaman a sus métodos privados (`runtime._run_storage_query`, `_build_storage_headers`…; Protocol `MariadbStorageRuntimeProtocol`). El runtime mantiene **15 delegadores de una línea sin uso en `src/`** (`_parse_mariadb_size_to_mb`, `_extract_initial_size_and_idx`, `_collect_oracle_*`, `_build_oracle_section`…; solo 2 se usan en tests). La configuración por motor está en 3 sitios del mismo fichero (`_DB_STORAGE_QUERY_SPECS`, `__post_init__` con lambdas y `_get_storage_headers_by_query`), y la entrada de MySQL es una copia literal de la de MariaDB | `storage/runtime.py:47-127, 243-278, 325-405`; `mariadb_strategy.py:14-37` |
| B-01 | Media (bug) | SQL Server tiene consultas (`ficheros_fisicos`, `temp_tablespaces`) y cabeceras, pero no tiene entrada en el registro, así que cada documento suyo incluye «Aviso: estrategia de almacenamiento genérica… puede ser impreciso» y registra un WARNING, aunque la estrategia genérica es justo la suya | `storage/runtime.py:77-127, 288-296`; `metadata.storage` |
| A-02 | Media (bug) | El generador de grafos se construye en 3 sitios con opciones distintas. El compartido (Word+HTML, `DocumentationOrchestrator._build_shared_graph_generator`) **ignora `grafo.show_columns`**; HTML suelto usa el DPI por defecto de la clase (300) y Word usa 150 | `documentation_orchestrator.py:553-575`; `generator_shared.py:533-564`; `word_generator.py:550`; `html_generator.py:1122` |
| A-03 | Media | Inyección de enlaces en SVG duplicada: una versión en disco y otra en memoria (≈45 LOC idénticas) | `html_generator.py:1964-2081` |
| A-04 | Baja | La normalización de filas de parámetros de rutina está triplicada (Word, Excel y HTML), y hay envoltorios de una línea (`_normalize_routine_entry` ×2, `_extract_table_row_data`, `_build_graph_generator` ×2) | `word_generator.py:1302`; `excel_generator.py:677`; `html_generator.py:1476` |
| A-05 | Media | Tolerancia heredada de antes de D1. Las filas ya son neutras (`CatalogRows`), pero `GeneratorTabularRuntime` sigue leyendo los UNIQUE con mapping, búsqueda sin distinguir mayúsculas y heurística de «parece columna» (≈100 LOC). `headers_config.json` conserva claves por motor vacías y `labels: {}`; `DocumentationHeadersRuntime.build_headers` combina cabeceras por `db_type` | `generator_shared.py:196-330`; `data/headers_config.json`; `headers_runtime.py:31-43` |
| A-06 | Media | Código muerto o caminos redundantes: `DocumentationSession._list_cache`/`_get_cached_list`; `DocumentationOrchestrator.from_documentation`; `SyncDatabaseManagerAdapter.get_storage_inventory_report` (la sesión usa `StorageInventoryReportService`, nunca este método); `DocumentationDataProviderPort`; `DOC_KINDS`; `build_storage_inventory_runtime`; `DocumentationOutputRuntime.supported_output_formats`/`format_folder_map`; `print_config` e `imprimir_config` duplicados en la sesión | recuento con `grep` (solo la definición) |
| A-07 | Media (contrato) | `DatabaseDocumentation.__init__` hace E/S (contexto de consulta + 3 lecturas del catálogo) aunque `generate()` documenta «separado de `__init__` para permitir instanciar sin E/S». La fachada expone ~12 atributos mutables de estado interno. La caché de nombres automáticos es un `ClassVar` mutable compartido entre instancias e hilos (contra «evita estado global mutable») | `database_documentation.py:79-147` |
| A-08 | Media | La jerarquía `DocumentationError`/`DocumentationConfigError`/`DocumentationRenderError` se exporta en `util_bbdd`, pero **`doc/` nunca la lanza**: lanza `ValueError`, `TypeError`, `FileNotFoundError` o la excepción cruda. Word registra la traza dos veces (fragmento y documento) antes de relanzar | `_core/exceptions.py:317-347`; `word_generator.py:215, 309`; `output_runtime.py:147-166` |
| A-09 | Baja | `_call_optional_metadata` recibe `success_message`/`error_message` y no los usa: registra `Success: {result}` en INFO | `metadata_runtime.py:24-40` |
| A-10 | Media | `analysis/matplotlib_graph.py` importa `matplotlib.axes.Axes` en el módulo, fuera del `try`: sin matplotlib el import falla y `MATPLOTLIB_AVAILABLE` no sirve. `matplotlib` y `networkx` no están declarados en ningún extra de `pyproject.toml`. `graphviz_ext.py:12` repite con import absoluto (`from util_bbdd.analysis.base import GraphEdge`) lo que ya importa en relativo | `matplotlib_graph.py:12`; `pyproject.toml` |
| A-11 | Baja (bug) | Con la configuración por defecto, Excel recibe `table_style="Table Grid"` (un estilo de Word) y avisa en cada ejecución: «Estilo de tabla Excel 'Table Grid' no reconocido» | `orchestrator.build()` → `ExcelGenerator._normalize_table_style` |
| A-12 | Baja | Los constructores de Word y HTML mutan el dict `headers` compartido de la sesión (`self.headers["UNIQUE"] = …`) | `word_generator.py:112`; `html_generator.py:47` |

## Seguridad (arquitectura)

| ID | Sev. | Hallazgo |
|---|---|---|
| S-01 | Baja | `detail.html.j2:416` inserta `inline_svg` con `|safe`. Es seguro porque las etiquetas pasan por `html.escape` (`graphviz_ext.py:329, 388-433`) y Graphviz escapa `<title>`, pero no hay test que fije ese invariante con un nombre de tabla hostil |
| S-02 | Baja | `HtmlGenerator._decode_html_entities` decodifica el DDL hasta 3 veces y `sql-highlight.js` otras 3. Un literal legítimo como `'&amp;lt;'` en un `CHECK` o en una vista se muestra como `<`: es un problema de fidelidad, no una inyección (el JS reescapa antes de `innerHTML`) |
| S-03 | Info | Los anclajes del SVG usan `target="_blank"` sin `rel="noopener"`; los enlaces son relativos y locales |
| — | OK | Sin SQL dinámico en `doc/`/`analysis/` (el almacenamiento usa consultas con nombre y binds de `metadata.storage`); `conn_params` no se vuelca en ningún documento; autoescape activo para `*.j2` (DOC-01); rutas saneadas (DOC-03); Excel con `SafeWorkbook` |

## Puntuación (0–10)

| Eje | Nota | Motivo |
|---|---|---|
| Cohesión | 6 | Capas claras; los renderers son monolitos (Word 1.608 LOC, HTML 2.091) y el almacenamiento mezcla configuración y ejecución |
| Acoplamiento | 7 | Puertos por Protocol y sin ciclos; acoplamiento circular estrategia ↔ runtime en `storage/` |
| Extensibilidad por motor | 6 | Un motor nuevo toca 3 estructuras en `storage/runtime.py` (más el dialecto en `metadata/`); tras A-01 sería 1 entrada |
| Testabilidad | 6 | Golden HTML por motor real, pero Excel al 18 % y Word al 37 % |

## Dependencias (Mermaid)

Ver `01_PLAN.md` §2. Sin ciclos; única dependencia hacia fuera de capa: `doc/application/use_cases/documentation_orchestrator.py`
importa `analysis.graphviz_ext` solo bajo `TYPE_CHECKING` (la clase llega inyectada desde la fachada).
