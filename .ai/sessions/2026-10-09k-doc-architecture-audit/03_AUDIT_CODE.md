# AUDIT_CODE — `doc/` + `analysis/`

Logs: `build/logs/doc_audit_20261009_lint.txt`, `build/logs/doc_audit_20261009_coverage.txt`,
`build/logs/doc_audit_20261009_baseline_integration.txt`, `build/logs/doc_perf_baseline_sqlite_*_20261009.json`.

## 1. Tipado y lint

| Herramienta | Resultado |
|---|---|
| `ruff check src/util_bbdd/doc src/util_bbdd/analysis` | All checks passed |
| `mypy src/util_bbdd/doc src/util_bbdd/analysis` (config del repo) | Success: no issues found in 42 source files |
| `mypy --strict` (lo que pide el skill; no es la puerta del repo) | 93 errores en 5 ficheros: 78 `type-arg` (`tuple`/`list`/`dict` sin parámetros en firmas de los renderers: Excel 39, Word 23, HTML 14, matplotlib 2), 14 `no-untyped-call` (python-docx sin tipos) y 1 `attr-defined` (el adaptador importa `StorageInventoryManagerProtocol` a través de `storage.runtime`, que no lo reexporta) |

## 2. Cobertura (unit, sin integración) — total `doc/`+`analysis/` 61 % (4.504 sentencias)

| Fichero | % | Nota |
|---|---|---|
| `renderers/excel_generator.py` | **18** | Sin test de `generate_document` de extremo a extremo |
| `renderers/word_generator.py` | **37** | Diagramas, almacenamiento e información de BD sin cubrir |
| `storage/oracle_strategy.py` | **20** | |
| `analysis/graphviz_ext.py` | 47 | Graphviz 14.1.2 sí está instalado; faltan tests de `pipe_*` |
| `analysis/matplotlib_graph.py` | 27 | |
| `renderers/html_generator.py` | 63 | Más la integración golden |
| `documentation_orchestrator.py` | 86 | |
| `analysis/base.py` | 91 | |

Integración (banco docker, previa al cambio): `test_doc_matches_golden` + `test_analysis_relations` → **17 pasan, 1 saltado**
(Oracle doc: «schema de pruebas no aislado»). El dorado de documentación solo cubre **HTML sin grafo**: Word y Excel no tienen dorado por motor.

## 3. Seguridad

Sin hallazgos críticos ni altos. Se mantienen las remediaciones de 2026-09-22 (DOC-01 autoescape `*.j2`, DOC-03 saneado
de nombres de fichero, `SafeWorkbook` contra fórmulas en Excel; `tests/unit/test_export_safety.py`). Bajos: S-01, S-02 y S-03
(ver `02_AUDIT_ARCH.md`). No hay secretos en la salida: `conn_params` solo aporta `user`/`schema`/`database` para el nombre del contexto.

## 4. Rendimiento (benchmark activado: hay hotspots)

SQLite sintético, 120 tablas (13 columnas, 2 FK, 1 UNIQUE y 1 índice cada una), 12 vistas, todas las secciones activas,
Graphviz 14.1.2, máquina de 32 núcleos. Script: `scratchpad/doc_profile.py` (cProfile + tracemalloc).

| Escenario | Tiempo | Pico de memoria | Dónde se va |
|---|---|---|---|
| HTML con grafos | 75,7 s | 10,0 MB | **67,1 s (89 %)** en 238 llamadas a `dot` en serie (`pipe_level_graphs_ext`) |
| Word con grafos | 68,3 s | 10,6 MB | **40,3 s (59 %)** en 120 llamadas a `dot`; el resto, python-docx |
| Word + HTML con grafos | 127,8 s | 24,1 MB | 66,7 s en `dot` (Word reutiliza la caché SVG de HTML) + 238 conversiones SVG→PNG (cairosvg) |
| Excel | 3,1 s | 11,5 MB | — |
| Word + Excel + HTML sin grafos | 26,4 s | 17,1 MB | python-docx |
| Word sin grafos (perfil aparte) | 8,4 s | — | **`_apply_table_style` 3,66 s (43 %)**: recorre todos los estilos del documento en cada una de las 612 tablas |

| ID | Sev. | Hallazgo | Propuesta |
|---|---|---|---|
| P-01 | Alta | Los subprocesos `dot` se lanzan en serie; el proceso Python espera en `read()` | Precalcular los grafos con un pool de hilos acotado (el subproceso libera el GIL); opción `grafo.workers` |
| P-02 | Media | `_apply_table_style` resuelve el estilo en cada tabla | Resolverlo una vez por documento |
| P-03 | Baja | `CatalogRows.view_ddl` recorre todas las vistas en cada vista (O(V²)) | Índice por nombre (`casefold`) |
| — | OK | Metadatos: una consulta por tipo de objeto y schema, snapshots ensamblados y cacheados en la fuente (ADR-003); `doc/` y `analysis/` comparten la caché del manager | — |

## 5. Casos límite por motor

| Motor | Caso | Estado |
|---|---|---|
| SQL Server | Inventario de almacenamiento con aviso de «fallback» falso | Bug B-01 |
| HSQLDB | Sin consultas de almacenamiento: aviso + 2 secciones «no disponible» | Correcto, pero redundante |
| Oracle | Dorado de documentación saltado (schema compartido) | Hueco de test (fuera de alcance: requiere un schema aislado en el banco) |
| MySQL/MariaDB | Parser de `innodb_temp_data_file_path` | Cubierto (88 %) |
| Todos | FK compuestas, sobrecargas de rutinas, columnas generadas e identidad | Cubiertos por `CatalogRows` + dorados |
