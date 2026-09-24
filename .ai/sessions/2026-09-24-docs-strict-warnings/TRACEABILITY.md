# TRACEABILITY

## Session metadata
- id: 2026-09-24-docs-strict-warnings
- fecha: 2026-09-24
- rama: develop
- skill: plan-architect (PLAN + AUDIT_PLAN) → implementación aprobada ("IMPLMENT tu propuesta")
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + VERIFY

## Prompt issued
```
Correguir mkdocs --strict	13 avisos;. PLAN y AUDIT_PLAN
```
```
IMPLMENT tu propuesta
```

## Context supplied
- Salida de `mkdocs build --strict` y `zensical build --strict` (zensical 0.0.44 local)
- `git ls-files docs`, `mkdocs.yml`, `.github/workflows/docs*.yml`, `.github/instructions/docs.instructions.md`, `.github/DOCUMENTATION_STANDARD.md`, README, CLAUDE.md, prompts

## AI output summary
- **Diagnóstico**:
  - MkDocs: 13 avisos, 2 de la navegación y 11 enlaces en 9 páginas, todos a `installation.md` o `roadmap.md`;
  - Zensical estricto: 12 problemas, 11 de esos enlaces y `guides/benchmarks.md:75` (`[Unreleased]` leído como referencia no definida; además desfasado, P-18 salió en 0.12.0);
  - los ficheros son `docs/INSTALLATION.md` y `docs/ROADMAP.md`. Windows (`core.ignorecase=true`) no distingue mayúsculas; MkDocs, Zensical y Linux sí;
  - `docs-zip-release.yml` ejecuta `zensical build --strict`, así que debía abortar en CI (sin `gh` no se pudo confirmar);
  - anclas enlazadas (`#3-drivers-por-motor`, `#5-solucion-de-problemas`) existentes.
- **Decisión** (opción A): referencias en mayúsculas, por coherencia con la convención normativa:
  - `docs.instructions.md` usa `INSTALLATION.md`/`ROADMAP.md` en la navegación, y README, CLAUDE.md y los prompts también;
  - se descartó B (renombrar a minúsculas): más cambios en instrucciones y un renombrado solo de mayúsculas en Windows.
- **Implementado**:
  1. `mkdocs.yml`: navegación `INSTALLATION.md` y `ROADMAP.md`.
  2. 11 enlaces en `index.md` (3), `architecture.md`, `legacy-versions.md`, `guides/connection_guide.md` (2), `guides/ddl_migration_guide.md`, `guides/dump_guide.md`, `guides/onboarding_dev.md` y `guides/troubleshooting.md`, conservando las anclas.
  3. `guides/benchmarks.md:75`: "Hasta [Unreleased]" → "Antes de la 0.12.0".
  4. `.github/DOCUMENTATION_STANDARD.md:244`: `docs/installation.md` → `docs/INSTALLATION.md` (se contradecía con su línea 553).
  5. `tests/unit/test_docs_links.py` (2 tests):
     - la navegación de `mkdocs.yml` se lee con un cargador YAML que ignora etiquetas `!!python/...`;
     - los enlaces relativos `.md` de `docs/` se revisan ignorando código cercado y en línea, URLs externas y anclas locales;
     - en ambos casos se comprueba el nombre exacto contra `rglob`, que devuelve el nombre real también en Windows;
     - antes del arreglo detectaba exactamente los 13 casos de MkDocs y ningún falso positivo.
- **Verificación**:
  - test de enlaces: falla antes (2 de navegación + 11 enlaces) y pasa después;
  - `mkdocs build --strict`: 0 avisos;
  - `zensical build --strict`: "No issues found";
  - HTML generado: `site/INSTALLATION/` y `site/ROADMAP/` existen; la portada enlaza `INSTALLATION/` (6) e `INSTALLATION/#3-drivers-por-motor`; las guías enlazan `../../INSTALLATION/` y la arquitectura `../INSTALLATION/#5-solucion-de-problemas`; los `id` de las anclas existen;
  - `ruff check` limpio; suite 4738 passed / 139 skipped (+2 tests).

## Observación (fuera de alcance)
- `https://fmanza.github.io/util_bbdd/` devuelve 404 en todas las rutas, incluida la raíz: GitHub Pages sin publicar o `docs.yml` sin desplegar. Hay que revisarlo en Actions.

## Directrices para Futuras IAs
- **[docs]**: en Windows no se ven los errores de mayúsculas en nombres de página. `tests/unit/test_docs_links.py` los detecta; ejecutar además `zensical build --strict`, que es el que usa la CI.
- **[docs]**: no escribir `[texto]` sin enlace en Markdown (Zensical lo trata como referencia); usar código en línea o texto plano.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit (pendiente de petición del usuario).
