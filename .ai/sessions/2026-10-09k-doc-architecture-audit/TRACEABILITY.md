# TRACEABILITY

## Session metadata
- id: 2026-10-09k-doc-architecture-audit
- fecha: 2026-10-09
- rama: develop
- skill: documentation-architecture-audit
- fase: PLAN + AUDIT_ARCH + AUDIT_CODE + IMPROVE_PLAN + IMPLEMENT (WP1–WP5) + VERIFY

## Prompt issued
```text
/documentation-architecture-audit

Objetivo: Auditoría y refactorización de arquitectura doc
Fases: PLAN → AUDIT_ARCH → AUDIT_CODE → IMPROVE_PLAN → IMPLEMENT → VERIFY
Motores: PostgreSQL, MySQL, MariaDB, Oracle, SQL Server, SQLite, Snowflake
Módulos: src/util_bbdd/doc/ + src/util_bbdd/analysis/
Alcance: Consolidación módulos + duplicidades + seguridad + rendimiento
Breakability: Sí (major version)
Validación: docker-compose
Benchmark: Condicional
```

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md`, `.github/skills/documentation-architecture-audit/SKILL.md`,
  `.github/prompts/doc_architecture_audit.prompt.md` (no existe `documentation-architecture-auditor.agent.md`).
- Código de `src/util_bbdd/doc/` y `src/util_bbdd/analysis/`; tests de doc/analysis; dorados de
  `tests/fixtures/metadata_golden/`; contenedores `util_bbdd_bench_*` (5 servidores + HSQLDB).

## AI output summary
- PLAN: el skill suponía paquetes por motor y Snowflake; ninguno existe. Se descarta `doc/motors/<motor>/` y Snowflake
  (N/A). Informes en esta carpeta (no en `docs/audits/`, que se publicaría con `--strict`), JSON en `build/logs/`.
- AUDIT_ARCH/AUDIT_CODE: 26 hallazgos (A-01…A-14, B-01…B-04, P-01…P-04, S-01…S-04). Benchmark activado: el 89 % del
  HTML con diagramas era esperar a `dot` en serie.
- IMPROVE_PLAN aprobado por el usuario: WP1–WP5 con ruptura de API (0.41.0).
- Línea base de salida (texto de Word/Excel/HTML con diagramas, 6 motores) capturada antes de tocar código con
  `doc_output_snapshot.py`; comparada tras cada WP.
- IMPLEMENT: 7 commits (`53ff3c55`, `9d4d3429`, `70f9e6df`, `03783459`, `54ff56d6`, `5a949e82`, `a4652f74`).
- VERIFY: READY_FOR_RELEASE (`06_VERIFY.md`).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN | `.ai/sessions/2026-10-09k-doc-architecture-audit/01_PLAN.md` | emitido |
| AUDIT_ARCH | `.../02_AUDIT_ARCH.md` | emitido |
| AUDIT_CODE | `.../03_AUDIT_CODE.md` | emitido |
| IMPROVE_PLAN | `.../04_IMPROVE_PLAN.md` | aprobado (WP1–WP5) |
| IMPLEMENT | `.../05_IMPLEMENT.md` + commits | completado |
| VERIFY | `.../06_VERIFY.md` | READY_FOR_RELEASE |
| Snapshot de salida | `.../doc_output_snapshot.py` | reutilizable |
| JSON por fase | `build/logs/doc_audit_20261009_{plan,audit_arch,audit_code,improve_plan,implement,verify}.json` | no versionado |
| Benchmarks | `build/logs/doc_perf_{baseline,after_*,final}_*.json` | no versionado |

## Directrices para Futuras IAs
- **[graphviz/rendimiento]**: el coste de `dot` es arrancar el proceso (~0,26 s con un grafo trivial en Windows) y no
  renderizar (~0,01 s). No paralelizar con un proceso por grafo (escala mal: 4,4× con 8 hilos); usar
  `GraphvizRelationshipGraphExt.prefetch`, que agrupa por (motor, formato) en lotes `dot -K<motor> -T<formato> -O f1.gv …`.
- **[graphviz/stdin]**: `dot` 14.1.2 en Windows renderiza solo el **primer** grafo cuando recibe varios por stdin; para
  lotes, varios ficheros con `-O` (un `<fichero>.<formato>` por entrada; el que falla no deja salida y el resto sí).
- **[doc/grafos]**: un único generador por documentación, creado en `DocumentationOrchestrator` con
  `build_graph_generator_from_options` (inyectada por la fachada). No volver a una caché SVG entre Word y HTML: cambiaba
  el contenido del .docx según los demás formatos (B-02).
- **[doc/precarga]**: la clave de la caché de renders es `(formato, motor, dot.source)`. `prefetch(render, tablas)`
  necesita que `render` haga exactamente la misma llamada que el renderer después (HTML: `_level_graph_kwargs`;
  Word: `_diagram_render`).
- **[doc/storage]**: el inventario de almacenamiento por motor está en `doc/infrastructure/storage/engines.py`
  (`ENGINE_SPECS`). Un motor nuevo = una entrada; el SQL sigue en `metadata/storage.py`.
- **[doc/API]**: `util_bbdd.doc` exporta solo `DatabaseDocumentation` y `DocumentationResult`. El constructor no
  consulta la BD (`DocumentationBootstrap.settings()`); `generate()` lee el catálogo (`build()`). Configuración inválida
  → `DocumentationConfigError` (también `ValueError`); fallo de renderer → `DocumentationRenderError`; errores de BD sin
  envolver.
- **[doc/filas]**: desde D1 las filas que ven los renderers son neutras (`catalog_rows.py`); no reintroducir lecturas
  tolerantes por motor ni cabeceras por motor (`headers_config.json` solo tiene `base`).
- **[seguridad/ficheros]**: todo nombre de fichero derivado del catálogo pasa por `_core/filenames.safe_file_stem`
  (S-04: el camino principal de HTML escribía `graphviz_ext_<tabla sin sanear>.svg`).
- **[verificación/doc]**: para refactors de `doc/`, `doc_output_snapshot.py` (en esta carpeta) vuelca el texto de
  Word/Excel/HTML con diagramas por motor del banco; comparar antes/después. MariaDB y MySQL cambian el orden de
  `ficheros_fisicos` entre ejecuciones (sin `ORDER BY`): comparar ordenado.
- **[herramientas]**: no usar `sed` global sobre `src`/`tests` para renombrar; tocó 4 ficheros fuera de alcance
  (restaurados). Las regex con `\b` escritas con heredocs de Bash + Python acaban como retroceso (`^H`): usar Write/Edit.
- **[HSQLDB]**: los tests de HSQLDB necesitan `JAVA_HOME="C:/Program Files/Java/jdk-25"` (JPype no encuentra `jvm.dll`
  desde el `java` del PATH). El DDL de tabla de HSQLDB falla en 2.7.4 (B-04, `metadata/ddl.py`).

## Veredicto final
Veredicto: READY_FOR_RELEASE
Pendientes al cierre:
- Tag `v0.41.0` y push (`/version-closure`); `.ai/CURRENT_STATE.md` refleja 0.41.0 sin tag.
- B-04 (`metadata/ddl.py`, HSQLDB `LISTAGG`) → `/hotfix`.
- S-02 (decodificación múltiple de entidades en el DDL de HTML), `mypy --strict` en renderers (81 errores),
  cobertura de `matplotlib_graph` (27 %), dorado de documentación de Oracle (schema no aislado).
- Fuera de alcance: docstrings con `DatabaseConnectionError` (inexistente) en `managers/` y `factory/`; orden de
  `ficheros_fisicos` en MySQL/MariaDB.
