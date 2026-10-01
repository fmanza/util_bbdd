# TRACEABILITY

## Session metadata
- id: 2026-10-01e-hotfix-docs-plugin-signature
- fecha: 2026-10-01
- rama: develop
- skill: hotfix (diagnóstico de Pylance pasado por el usuario)
- fase: PLAN → AUDIT_PLAN → IMPLEMENT (RCA + fix, test-first) → AUDIT_CODE → VERSION (commit sin push)

## Prompt issued
- `/hotfix` con el diagnóstico de Pylance `reportIncompatibleMethodOverride` en
  `src/util_bbdd/docs_build_plugin.py:88`: «El método "on_post_build" sobrescribe la clase "BasePlugin" de forma
  incompatible … Falta el parámetro "config"».

## AI output summary
- **RCA**: mkdocs 1.6 declara `BasePlugin.on_post_build(self, *, config: MkDocsConfig)` (solo por nombre); el plugin
  lo declaraba `on_post_build(self, config: Config)` (posicional, tipo genérico).
- **Severidad**: no es P1/P2. mkdocs invoca los eventos con `method(**kwargs)` (`PluginCollection.run_event`), así que
  la firma antigua funcionaba (el test del despachador pasaba antes del fix). Se siguió `/hotfix` porque lo pidió el
  usuario.
- **Por qué no lo veían las herramientas**: mypy excluye el módulo (`pyproject.toml`, `exclude`) y trata `mkdocs.*`
  como sin tipos (`ignore_missing_imports` → `BasePlugin` es `Any`): ni pasándole el fichero lo marca. Además
  `BasePlugin.on_post_build` solo existe bajo `TYPE_CHECKING` en mkdocs: en ejecución no hay atributo que comparar.
- **Fix**: `on_post_build(self, *, config: MkDocsConfig)` (`mkdocs.config.defaults`, desde mkdocs 1.5; instalado
  1.6.1; `mkdocs-material>=9.5` ya exige 1.6). Cuerpo sin cambios (`MkDocsConfig` hereda `get` de `Config`).
- **Tests**: `test_on_post_build_matches_the_mkdocs_signature` (falla con el código anterior) y
  `test_on_post_build_runs_through_the_mkdocs_dispatcher`; los 6 tests antiguos pasan a `config=` (llamaban en
  posicional, que mkdocs nunca hace). `mkdocs build --strict` real: ZIP y SHA256 generados.

## Verificación
- ruff, mypy (386 ficheros): sin errores. `pytest`: verde (ver commit). `mkdocs build --strict`: ZIP creado.

## Directrices para Futuras IAs
- **[docs/plugin]**: los métodos `on_*` de un plugin de MkDocs reciben sus argumentos solo por nombre; copiar la firma
  de `mkdocs/plugins.py` (bajo `TYPE_CHECKING`). mypy no lo comprueba aquí (módulo excluido y mkdocs sin tipos);
  `test_docs_build_plugin.py` lo vigila.

## Veredicto final
Veredicto: CLOSED — hotfix aplicado y verificado (commit sin push).
