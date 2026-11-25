# TRACEABILITY

## Session metadata
- id: 2026-11-25-i18n-resultados
- fecha: 2026-11-25
- rama: `feature/i18n-resultados` (PR #27 a `develop`)
- skill: new_feature + version_closure
- fase: análisis de impacto (librería y util_bbdd_web) + PLAN + AUDIT_PLAN (v1 y v2) + IMPLEMENT + VERSION

## Prompt issued
«Necesito saber el impacto que tendría incluir en los resultados incluir i18n, solo información» → «Analiza también el
impacto en util_bbdd_web» → «PLAN y AUDIT_PLAN por fases» → «¿Cuál es el motivo de no incluir formato de fechas y
números por idioma?» → «Hazlo, actualiza PLAN y AUDIT_PLAN» → «IMPLEMENT con tus recomendaciones» → «Haz los commits como
propones» → «Haz push y abre la PR a develop» → «Haz el cierre de versión 5.10.0».

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, `.github/prompts/new_feature.prompt.md`, `.github/agents/plan-architect.agent.md`
- `.github/prompts/version_closure.prompt.md`, `.github/agents/version-closer.agent.md`, `.github/instructions/sync.instructions.md`
- Código de `doc/`, `comparar/reporters/`, `dump/`, `audit/`, `analysis/` y de util_bbdd_web (`backend/app/domain/runs/operations.py`, `integrations/util_bbdd/`, `frontend/src/i18n/`)

## AI output summary
- Análisis de impacto: la librería no tenía i18n (textos en español escritos a mano en unas 14.000 líneas de generadores y plantillas); util_bbdd_web ya usa react-i18next y su tarjeta «Lanzar ejecución» se genera desde los `Params` (`ubw_group`).
- PLAN/AUDIT_PLAN v1 (GO_CONDICIONAL) y v2: separadores numéricos por idioma dentro del alcance (2 puntos con el formato escrito a mano: `audit/exporters.py` y `doc/infrastructure/storage/runtime.py`), fechas en ISO 8601.
- Condiciones aceptadas: `es`/`en` con `es` por defecto, excepciones y logs fuera, cambio visible aceptado en el HTML de auditoría en español.
- Referencia de no regresión: script (fuera del repo) que genera 74 salidas sobre SQLite (doc en 4 formatos con todas las secciones, trazabilidad y `previous`; comparación; volcado; auditoría) y vuelca su texto normalizado; generado en `HEAD` con `git stash`.
- F0: `_core/i18n.py` (`Locale`, `Translator`, `validate_locale`, `CATALOG_ROOT`), `data/i18n/{es,en}/_format.json`, glob de `package-data`, `tests/_core/test_i18n.py`.
- F1 (yo): `audit/readiness.py`, `audit/exporters.py`, `audit/html_template.py`, `bulk/audit.py` (`AuditManager(locale=)`), `dump/_models.py` (`DumpConfig.locale`), `dump/reporters.py`, `dump/orchestrator.py`.
- F3a (yo): `DatabaseDocumentation(locale=)`, `headers_file=None` por defecto con `headers_config.en.json`, `DocumentationSession.translator`, `build_default_renderer_registry(translator=)`, `EngineConditionsSectionBuilder(headers, translator)`, `StorageInventoryReportService.translator`.
- F2/F3b/F3c/F4 en 4 agentes en paralelo, cada uno con un namespace propio (`comparar`+`analysis`, `doc`, `doc_html`, `doc_md`). El de `comparar`/`analysis` se cortó por el límite de uso; terminé su integración (`build_graph_generator_from_options(translator=)`, `partial` en la fachada, `_tr` de clase en `analysis/base.py`).
- Decisión: títulos de `manifest.json` → `pages` en el idioma de la generación (son el H1, contrato 5.4.0, y util_bbdd_web los muestra en la navegación).
- Ajustados 2 dobles de test de `test_database_documentation.py` a la nueva firma de la fábrica de grafos; `version_label` con valor por defecto en `GeneratorDatabaseInfoRuntime._append_version_info`.
- Docs: `docs/guides/output_language.md` (+ `zensical.toml`), `docs/api/database_documentation.md`, `docs/api/dump.md`, `docs/api/bulk_audit.md`, diagrama de capas regenerado.
- Commits `bee762c3` (feat) y `a9560bb6` (fix(audit)); push y PR #27.
- VERSION: `pyproject.toml` 5.10.0, CHANGELOG `[5.10.0] - 2026-11-25`, README, `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md` (376 ficheros), `.ai/CURRENT_STATE.md`, `SESSIONS_DIGEST.md`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN/AUDIT_PLAN v1 y v2 | conversación (no versionados) | emitidos, GO_CONDICIONAL aceptado |
| Traductor y catálogos | `src/util_bbdd/_core/i18n.py`, `src/util_bbdd/data/i18n/{es,en}/*.json` (837 claves por idioma) | completado |
| Cabeceras en inglés | `src/util_bbdd/doc/data/headers_config.en.json` | completado |
| Tests | `tests/_core/test_i18n.py`, `tests/unit/i18n/` (7 ficheros + `_leftovers.py`) | completado |
| Guía | `docs/guides/output_language.md` | completado |
| PR | https://github.com/fmanza/util_bbdd/pull/27 | abierta |

## Directrices para Futuras IAs
- **[i18n]**: el punto canónico es `src/util_bbdd/_core/i18n.py`; los textos viven en `src/util_bbdd/data/i18n/<locale>/<namespace>.json` y la clave completa es `<namespace>.<clave>` (namespaces: `_format`, `audit`, `dump`, `doc`, `doc_html`, `doc_md`, `comparar`, `analysis`). Una clave nueva va en `es` y en `en` con los mismos `{marcadores}`: lo exige `tests/_core/test_i18n.py`.
- **[i18n]**: los catálogos se localizan con `Path(__file__)` (`CATALOG_ROOT`), no con `importlib.resources`: este último falla (`'NoneType' object has no attribute 'name'`) cuando el paquete raíz aún se está importando, y lo detecta `test_each_package_imports_cleanly_as_the_first_import`.
- **[i18n]**: no usar `locale.setlocale` (estado global del proceso, inseguro con hilos); los números de texto van por `Translator.format_int`/`format_decimal`. Las fechas se quedan en ISO 8601.
- **[i18n]**: las constantes públicas en español (`ReadinessRows.NOTICE_*`, `ReadinessSheetWriter.HEADERS`, `EngineConditionsSectionBuilder.DEFAULT_HEADERS`, `WordGenerator.SECTION_*`, constantes de `markdown/_pages.py`) se conservan por compatibilidad; la salida usa el `translator` de la instancia.
- **[i18n]**: no se traducen excepciones, logs, recomendaciones de `EngineReadinessAdvisor` (`connection/`, ~145 textos cacheados por engine sin idioma), columnas de las hojas de auditoría (esquema del CSV) ni datos para máquinas del Markdown (`catalog.json`, `changes.json`, front matter, rutas, anclas).
- **[doc/html]**: `template_engine.header_key` convierte el texto de la cabecera en clase CSS; para que no cambie con el idioma, `TemplateEngine(header_aliases=...)` traduce la cabecera inglesa a la española antes de calcular la clase.
- **[doc/markdown]**: los títulos de `manifest.json` → `pages` son el H1 de la página en el idioma de la generación (contrato 5.4.0; util_bbdd_web los muestra en `markdownNav`); `path`, `section` y `role` no cambian.
- **[doc]**: `DocumentationOrchestrator` recibe la fábrica de grafos como `partial(build_graph_generator_from_options, translator=...)`; los dobles de test de esa fábrica deben aceptar `translator`.
- **[tests]**: `tests/unit/i18n/_leftovers.py` (`spanish_hits`, `visible_text`, `spanish_hits_in`) detecta español en salidas en inglés; los datos de los fixtures deben ir en inglés y sin tildes.
- **[técnica]**: para i18n sin regresiones sirvió una referencia de texto normalizado de todas las salidas generada en `HEAD` (`git stash`) y comparada con `diff -r` tras cada fase; normalizar marcas de tiempo, rutas de trabajo y tiempos pequeños (`0,00x`).
- **[técnica]**: repartir una fase grande entre agentes en paralelo funcionó dando a cada uno ficheros y namespace de catálogo disjuntos; los ficheros compartidos (`renderers/shared/*`) deben tener un único dueño.
- **[bash]**: en este entorno los heredocs con comillas mezcladas fallan (`unexpected EOF`); las sustituciones grandes se hicieron con un script de reglas (`antes` → `después`, cada `antes` exactamente una vez).

## Veredicto final
Veredicto: CLOSED (VERSION 5.10.0 preparada; publicación pendiente del merge de la PR #27)
Pendientes al cierre:
- Merge de la PR #27 en `develop`, tag `v5.10.0`, fast-forward de `main` y wheel en GitHub Releases (`docs/guides/release_guide.md`).
- util_bbdd_web W1 (fijar 5.10.0 y añadir `locale` a `DocumentationParams`, `CompareParams` y parámetros del dump) y W2 (`lang` dinámico en `markdownFrame.ts`), cuando exista el wheel.
- Opcional: traducir las recomendaciones de `EngineReadinessAdvisor` (refactor de `AdvisoryFinding` y de su caché por engine).
- Opcional: el tamaño del inventario de almacenamiento se guarda como texto en Excel (no se puede sumar ni ordenar como número); fuera de alcance por la regla de no refactorizar.
- Las líneas de instalación `@v5.9.1` de `README.md` y `docs/index.md` no son campos de versión de `sync.instructions.md` § 4: se cambian al publicar el tag.
