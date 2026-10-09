# IMPLEMENT — `doc/` + `analysis/`

Aprobación: plan completo WP1–WP5 (pregunta al usuario tras IMPROVE_PLAN: «Todo WP1–WP5»).

## Commits (rama `develop`)

| Commit | WP | Hallazgos | Resumen |
|---|---|---|---|
| `53ff3c55` | WP1 | P-01, P-04, B-02, A-02, A-03, A-13, A-14, S-04 | `GraphvizRelationshipGraphExt.prefetch` por lotes (`dot -O`), `_build_dot` único, un generador por documentación, fuera la caché SVG cruzada, SVG con una escritura y nombre saneado |
| `9d4d3429` | WP2 | P-02, P-03, A-11 | Estilo de tabla de Word una vez por documento; `view_ddl` indexado; Excel sin aviso por «Table Grid» |
| `70f9e6df` | WP3 | A-01, B-01, B-03 | `storage/engines.py` declarativo; SQL Server con entrada propia; detección de columnas de tamaño por palabra |
| `03783459` | WP4 | A-04, A-05, A-06, A-09, A-10, A-12, S-01 (test) | Helper de parámetros de rutina, UNIQUE neutro, cabeceras sin bloques por motor, código muerto fuera, matplotlib opcional + extra |
| `54ff56d6` | WP5 | A-06 (resto), A-07, A-08 | `util_bbdd.doc` = `DatabaseDocumentation` + `DocumentationResult`; `__init__` sin BD; `DocumentationConfigError`/`DocumentationRenderError`; docs, CHANGELOG, 0.41.0 |
| `5a949e82` | VERIFY | T-01 | Test de extremo a extremo sobre SQLite (Word, Excel, HTML) |

## Descubrimientos durante IMPLEMENT

| ID | Hallazgo | Tratamiento |
|---|---|---|
| P-01b | El coste de `dot` es el **arranque del proceso** (~0,26 s con un grafo trivial) y no el render (~0,01 s). Con un pool de hilos y un proceso por grafo, el HTML solo bajó de 75,7 s a 20,2 s (escalado sublinear: 4,4× con 8 hilos). Además, esta versión de `dot` en Windows solo renderiza el **primer** grafo de stdin, mientras que `dot -O f1.gv f2.gv …` escribe un fichero por entrada (100 SVG en 0,94 s). | `prefetch` agrupa por (motor, formato) y lanza un `dot -O` por lote; un grafo sin salida se renderiza aparte con `dot.pipe` (mismo resultado o excepción que sin precarga) |
| S-04 | **Seguridad (media)**: el camino principal de HTML (`graphs/graphviz_ext_<tabla>_…svg`) y los `generate_*` de `analysis` nombraban los ficheros con el nombre de tabla **sin sanear**. DOC-03 (2026-09-22) solo había saneado los caminos de respaldo. | `_core/filenames.safe_file_stem` (antes `sanitize_table_filename` en `doc/`); HTML usa el slug único de la tabla |
| B-03 | La heurística de «columna de tamaño» buscaba la subcadena `mb`, que aparece en «No**mb**re lógico» (SQL Server) | Coincidencia por palabra (`\b(mb\|size\|tamaño)\b`) |
| B-04 | **Fuera de alcance** (`metadata/ddl.py`): el DDL de tabla de HSQLDB usa `LISTAGG(…)` sin `WITHIN GROUP` y HSQLDB 2.7.4 lo rechaza. Documentar HSQLDB con `tablas.ddl=True` falla con `MetadataError`. Ya fallaba antes de esta sesión. | Diferido (ver VERIFY) |
| — | `DatabaseConnectionError` aparece en 4 docstrings de `managers/`/`factory/`, pero esa excepción no existe (la de conexión es `ConnectionError`) | Diferido: deuda de documentación fuera de alcance |

## Incidencias del proceso

- Un `sed` global (`DatabaseConnectionError` → `DatabaseOperationError` en `src`/`tests`) tocó 4 ficheros ajenos al
  alcance. Se detectó en `git status` antes del commit de WP5 y se restauraron con `git checkout` (el diff solo contenía
  esa sustitución).
- Los heredocs de Bash con Python convirtieron `\b` en un retroceso (`^H`) dentro de una regex; se detectó con
  `cat -A` y se corrigió. Las ediciones con barras invertidas se hicieron después con Write/Edit.
