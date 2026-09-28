# TRACEABILITY

## Session metadata
- id: 2026-09-29-docs-review-hotfixes
- fecha: 2026-09-28 / 2026-09-29
- rama: develop
- skill: documentation + refactor (nombres de docs/) + hotfix ×2 + version_closure
- fase: AUDIT (Documentation Reviewer) + PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
1. «Documentation Reviewer» (modo proyecto completo, supuesto) → pasos 1 y 2 aprobados («si»).
2. «normalizar los existentes con guiones o en mayúsculas… y el motivo por el cual se ha quitado "Casos de Uso"» — PLAN y AUDIT_PLAN; decisiones: D1 verificar redirecciones en Zensical y consultar (no las admite; sitio sin publicar → opción (a) renombrar sin redirecciones), D2 excepciones `docs/adr/` y `docs/v0.8.0/`, D3 Arquetipo 1 con 8 secciones.
3. `/hotfix` publicación del sitio rota (job `deploy` de `docs.yml`).
4. «Se puede incluir: Zensical no ejecuta el plugin documentation_zip» → PLAN y AUDIT_PLAN; D1 (a) función compartida, D2 (a) mantener `util_bbdd-docs-<versión>.zip`.
5. `/version-closure` sin inputs (supuestos declarados en el cierre).

## Context supplied
- `.github/agents/documentation-reviewer.agent.md`, `.github/prompts/documentation_review.prompt.md`, `hotfix.prompt.md`
- `mkdocs.yml`, `docs/`, `README.md`, `src/util_bbdd/docs_build_plugin.py`, `scripts/build_docs_zip.py`, `.github/workflows/{docs,docs-release,docs-zip-release}.yml`
- `venv/Lib/site-packages/zensical/config.py` (plugins admitidos) y el sitio `https://fmanza.github.io/util_bbdd/` (404)

## AI output summary
- Documentation Reviewer: NEAR_READY; 3 N1 (README versión/`bulk_insert_from_csv`, anclas que rompían `zensical --strict`), 7 N2, 3 N3; 2 regresiones propias de la sesión config-review (agentes que llamaban canónico a `docs.instructions.md`, Arquetipo 1).
- `8c62b97` README (versión, motores, API real, 13 enlaces) + anclas de `constraints_quick_reference.md`.
- `50b48f0` Generator/Reviewer/config_review leen `DOCUMENTATION_STANDARD.md`; `landing_doc`/bootstrap con `architecture.md` y 8 arquetipos.
- `b3ab306` Arquetipo 1 = 8 secciones del prompt; «Casos de Uso» se retiró en `37d6b58` (2026-06-08) al adoptar el núcleo compartido con dpss, sin justificación documentada; su contenido está en §3 Flujo Principal y §6 Límites/Flujos alternativos.
- `c733847` 65 ficheros de `docs/` a minúsculas con guion bajo (`git mv`, dos pasos para cambios solo de mayúsculas) y 70 ficheros de referencias; `b577831` regla sin excepciones provisionales + `config-reviewer` sin `settings.json.example`.
- `e9fca81` hotfix: `deploy` ejecuta `zensical build` antes de `peaceiris/actions-gh-pages` (RCA `11fb9f8`).
- `9a3c0a2` hotfix: `build_offline_zip` compartido por plugin y script (extras + sin ZIP previo), `--in-site` en `deploy`, `docs-zip-release.yml` con YAML válido, `downloads.md` con nombres reales.
- Validación final: `pytest` 5295 passed / 199 skipped; `zensical build --strict` limpio (worktree limpio y árbol principal tras el último cambio de `docs/`); `mkdocs build --strict` sin avisos; ruff y mypy (plugin) limpios; simulación de ZIP en `site/` y `dist/` (190 entradas, extras, `testzip` OK).
- VERSION: `CHANGELOG.md` § `[Unreleased]` completado (sin subida de versión).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Commits | `8c62b97`, `50b48f0`, `b3ab306`, `c733847`, `b577831`, `e9fca81`, `9a3c0a2` (develop, sin push) | completado |
| Tests nuevos | `tests/unit/test_docs_workflow.py`, `tests/unit/test_build_docs_zip_script.py`, 2 en `test_docs_build_plugin.py` | completado |
| CHANGELOG | `CHANGELOG.md` § `[Unreleased]` | completado |

## Directrices para Futuras IAs
- **[docs/zensical]**: Zensical 0.0.44 solo admite los plugins `search`, `offline`, `mike`, `mkdocstrings`/`autorefs`, `glightbox` y `macros` (`zensical/config.py::_convert_plugins`); ignora en silencio los demás, incluidos `redirects` y el `documentation_zip` propio. No hay redirecciones al renombrar páginas.
- **[docs/zip]**: el ZIP offline se empaqueta solo con `util_bbdd.docs_build_plugin.build_offline_zip` (plugin MkDocs y `scripts/build_docs_zip.py`); con Zensical hay que llamar al script (`--in-site` para el sitio, sin opción para `dist/`). Zensical no vacía `site/` entre builds.
- **[ci]**: cada job de GitHub Actions corre en una máquina nueva: un job que publica `./site` tiene que construirlo él mismo. GitHub no avisa en el push si un workflow tiene YAML inválido; `tests/unit/test_docs_workflow.py` valida todos.
- **[docs/nombres]**: todo `docs/` usa minúsculas con guion bajo salvo `docs/adr/` y `docs/v0.8.0/`. En Windows (`core.ignorecase=true`) un cambio solo de mayúsculas se hace en dos `git mv`; `git apply` de un parche así falla en un worktree de Windows, así que para validar hay que hacer commit y construir el commit en un worktree limpio.
- **[docs/validación]**: el árbol principal puede dar incidencias falsas en `zensical build --strict` por estado local; la referencia es un build en worktree limpio del commit.
- **[docs/arquetipos]**: el Arquetipo 1 vigente son las 8 secciones de `functional_doc.prompt.md` (núcleo compartido por bootstrap; editar el prompt afecta a otros proyectos). Los 19 documentos de `docs/functional/` siguen con 4 secciones hasta migrarse.
- **[publicación]**: `https://fmanza.github.io/util_bbdd/` daba 404 el 2026-09-29 (deploy roto desde `11fb9f8`); `docs.yml` solo publica en push a `main`.
- **[herramientas]**: `scripts/build_docs_zip.py` imprime emojis: en Windows con la salida redirigida falla con `UnicodeEncodeError` después de escribir el ZIP; usar `PYTHONIOENCODING=utf-8`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Push de `develop` y paso a `main` para que se ejecuten por primera vez `deploy` (Pages) y `docs-zip-release.yml`; revisar *Settings › Pages* si el sitio sigue en 404.
- Pasos 3 y 4 de la revisión de documentación: 6 páginas fuera del `nav` (`constraints_*`, `performance_audit_*`, `guides/code_reusability_analysis_guide.md`) y 33 docstrings de la API pública (15 de `AsyncDatabaseManager`, 9+9 de los `*MetadataProvider`).
- Migración de los 19 documentos funcionales a 8 secciones.
- `UnicodeEncodeError` de `build_docs_zip.py` en Windows con salida redirigida.
- Registrar esta sesión y `2026-09-28-config-review` en `.ai/sessions/INDEX.md` (fuera del permiso de Version Closer); `INDEX.md:227` enlaza al TRACEABILITY equivocado.
