# TRACEABILITY

## Session metadata
- id: 2026-10-02e-config-review
- fecha: 2026-10-02
- rama: develop
- skill: config_review (+ un cambio de test, aprobado como C2)
- fase: ANÁLISIS + PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE (commit propuesto)

## Prompt issued
`/config-review` sin inputs → supuestos `repo` · `todo` · `todos` · `análisis`. Tras el AUDIT_PLAN
(GO_CONDICIONAL): «C1: aplica A, C2: si incluye».

## Context supplied
- `.github/agents/config-reviewer.agent.md`, `.github/prompts/config_review.prompt.md`
- Inventario: entry points, `SHARED_INSTRUCTIONS.md`, `.github/AGENTS.md`, `DOCUMENTATION_STANDARD.md`, 13 agentes,
  27 prompts, 12 commands, 7 instrucciones, `.ai/*.md`, `TEMPLATE/`, `.claude/*.md` (85 ficheros, ≈ 8.965 líneas)
- Comprobaciones mecánicas con un script de solo lectura (paridad, frontmatter, enlaces, rutas, fechas, conteos)

## AI output summary
- ANÁLISIS: paridad, frontmatter y conteos correctos; 7 hallazgos: H1 (Alta) contrato de Version Closer contra el
  checklist de `sync.instructions.md` § 4; M1 § 4 incompleto y sin test del CHANGELOG; M2 `audit_module` e inventario
  obsoletos tras ejecutarse; M3 glosario con `audit/` en Level 3 y lista de módulos duplicada; M4 `introspect/`
  huérfano; B1 «user context» falso en `.ai/product.md`; B2 `.github/AGENTS.md` sin fecha.
- AUDIT_PLAN: GO_CONDICIONAL; usuario: C1 = A (ampliar Version Closer a los campos de versión), C2 = incluir el test.
- IMPLEMENT: los 7 hallazgos corregidos; `tests/unit/test_docs_version.py` comprueba también la segunda línea del
  README, el pie de figura de `docs/architecture.md` y la última versión del CHANGELOG (6 marcas).
- AUDIT_CODE: script de comprobaciones sin huérfanos nuevos; ruff limpio; 5830 passed; `mkdocs build --strict` OK.
  Veredicto APROBADO.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Contrato Version Closer | `.github/agents/version-closer.agent.md`, `.github/prompts/version_closure.prompt.md`, `.claude/commands/version-closure.md`, `.github/AGENTS.md` | completado |
| Campos de versión | `.github/instructions/sync.instructions.md` § 4 | completado |
| Test | `tests/unit/test_docs_version.py` | completado |
| Limpieza | `.github/prompts/audit_module.prompt.md`, `.ai/audit/audit_module_baseline_inventory.md`, `.ai/glossary.md`, `.ai/product.md`, `.github/prompts/performance_audit_constraints.prompt.md` | completado |

## Directrices para Futuras IAs
- **[release]**: La lista cerrada de campos de versión vive en `.github/instructions/sync.instructions.md` § 4 y es lo
  único, además de `CHANGELOG.md` y el `TRACEABILITY.md`, que puede editar Version Closer; los demás ficheros del método
  la referencian en una línea (no la copies). Un sitio nuevo con la versión → añadirlo a § 4 y a `VERSION_MARKERS` de
  `tests/unit/test_docs_version.py`.
- **[release]**: `test_docs_version.py` compara con `pyproject.toml` el CHANGELOG (primera sección `## [X.Y.Z]`, salta
  `[Unreleased]`), las dos líneas del README, `docs/index.md`, `docs/roadmap.md` y el pie de figura de
  `docs/architecture.md`. Los campos de `.ai/` se revisan a mano.
- **[config]**: Las rutas `docs/normativa`, `docs/security`, `docs/glossary.md`… de `DOCUMENTATION_STANDARD.md` son
  plantillas condicionales, no huérfanos: no las «corrijas».
- **[config]**: `.ai/glossary.md` ya no lista paquetes ni niveles: la fuente es `.ai/architecture.md` § Capas (y `LAYER`
  en `scripts/gen_arquitectura_capas.py`).
- **[config]**: Un prompt de diseño acotado ya ejecutado (`audit_module`) se conserva con cabecera «Ejecutado en vX» en
  lugar de borrarlo.

## Veredicto final
Veredicto: CLOSED (AUDIT_CODE APROBADO)
Pendientes al cierre:
- Commit propuesto (no ejecutado): `docs(config): Version Closer edita los campos de versión de sync § 4 y test de versión del CHANGELOG`
