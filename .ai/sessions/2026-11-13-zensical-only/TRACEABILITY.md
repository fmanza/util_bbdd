# TRACEABILITY

## Session metadata
- id: 2026-11-13-zensical-only
- fecha: 2026-11-12 / 2026-11-13
- rama: develop
- skill: refactor (documentación y configuración) + feature acotada en `doc/` (salida Markdown)
- fase: PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
«Se quiere actualizar a la última versión de zensical y usarlo como única opción utilizando su estándar. Dime si
existe en el proyecto alguna mejora o implementación pendiente. Dame PLAN» → «IMPLEMENT» (decisiones D1–D3 sin
contestar: se aplicaron las recomendadas, D1-b, D2 renombrar a `ZENSICAL.md`, D3 probar `privacy` y descartarlo si no
funciona).

## Context supplied
- `CLAUDE.md`, `.github/SHARED_INSTRUCTIONS.md`, memoria del usuario.
- Notas de versión de Zensical 0.0.72–0.1.1 y documentación oficial (configuración, plugins compatibles, CLI).

## AI output summary
- Zensical 0.0.71 → 0.1.1 (`pyproject.toml`: `zensical>=0.1.1,<0.2`; fuera `mkdocs-material`).
- `mkdocs.yml` → `zensical.toml` (nav generado desde el YAML con un script, resto según la plantilla de `zensical new`).
  Sitio comparado por página contra el de `mkdocs.yml` con 0.1.1: 140 páginas, 0 diferencias en autodoc, Mermaid,
  código, avisos, anclas y enlaces de `nav`.
- Mermaid: fuera `mermaid@11` de jsDelivr y `docs/assets/js/mermaid.js` (se imponían al Mermaid 12 de Zensical).
  Verificado en Chromium (Playwright): diagramas dibujados con Mermaid 12; botón de la barra lateral y `nav.css` intactos.
- Plugin `documentation_zip` retirado (`src/util_bbdd/docs_build_plugin.py`, entry point, overrides de mypy); su lógica
  y sus tests de regresión (DOC-02) pasan a `scripts/build_docs_zip.py` y `tests/unit/test_build_docs_zip_script.py`;
  `OFFLINE_README.txt` a `scripts/`; `--builder` eliminado.
- Workflows: disparadores `zensical.toml`, `--strict` en la validación, sin doble build en `docs-zip-release.yml`.
- Librería (`doc/`, formato Markdown): `markdown.zensical_toml` (por defecto `True`) genera `zensical.toml`;
  `markdown.mkdocs_yml` por defecto `False` y en desuso (aviso; retirada en 6.0.0); README generado solo con Zensical.
  Salida verificada con `zensical build --strict` y, sin red, con Mermaid local y sin Google Fonts.
- `mermaid_js_ref` a un fichero ausente, verificado con 0.1.1: el build no avisa, 404 y Zensical carga `mermaid@12`.
- Plugin `privacy` probado y descartado (reescribe a `/util_bbdd/assets/external/…`, que el ZIP servido en la raíz no
  sirve; ~8 MB de terceros).
- Instrucciones IA y guías: unas 60 fuentes sin «o `mkdocs build`»; fragmentos YAML de `nav` pasados a TOML;
  `ZENICAL.md` → `ZENSICAL.md` reescrito; `mkdocs_nav_update` → `zensical_nav_update`; eliminados
  `.github/docs-zip-validation-checklist.md` y `.github/docs-download-fragment.md`; `.github/docs-zip-setup-guide.md`
  reescrito; decisión nueva en `.ai/DECISIONS_LOG.md`.
- Tras «Continúa» (decisiones: release 5.6.0, Mermaid local, nota en la web): `mermaid-12.3.0.min.js` de npm (MIT,
  idéntico byte a byte al de unpkg) en `docs/assets/js/vendor/` y en `extra_javascript`; ZIP extraído y servido sin
  red en Chromium: diagramas dibujados. G55 añadido en `util_bbdd_web/docs/plan/UTIL_BBDD_GAPS.md` (sin commit).
- AUDIT_CODE: sin hallazgos bloqueantes (aviso de desuso por logger, como el resto del proyecto; `mkdocs_yml()`
  produce lo mismo que antes; `ReadmeContents` es privado). Un fallo propio corregido: el pie de figura de
  `docs/architecture.md` debe decir «en vX.Y.Z» (`test_docs_version.py`).
- VERSION 5.6.0: campos de `sync.instructions.md` § 4, 19 pines `@v5.6.0`, CHANGELOG fechado. Puerta: pytest
  7115 passed / 618 skipped / 0 failed; ruff, `ruff format --check` y mypy (373) limpios; `zensical build --strict`
  sin incidencias; `python -m build` (sdist + wheel 5.6.0) sin `docs_build_plugin`.
- Gate en venv limpio `.[dev-full]` antes de publicar: 1 fallo (`test_mariadb_tls.py` importa `certifi`, que llegaba
  con mkdocs-material → requests). `certifi` declarado en `dev`; repetido: 7113 passed, 619 skipped (+1 salto:
  `jaydebeapi`, fuera de `dev-full`, ya antes).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Configuración del sitio | `zensical.toml` | creado |
| ZIP offline | `scripts/build_docs_zip.py` | reescrito (sin plugin) |
| Salida Markdown | `src/util_bbdd/doc/infrastructure/renderers/markdown/_site.py` | `zensical_toml()` + `mkdocs_yml()` en desuso |
| Guía | `ZENSICAL.md` | reescrita |

## Directrices para Futuras IAs
- **[docs]**: `zensical.toml` es la única configuración del sitio; no reintroducir `mkdocs.yml` ni plugins de MkDocs
  (Zensical los ignora en silencio salvo sus reimplementaciones nativas, como `mkdocstrings`).
- **[docs]**: Zensical 0.1.1 carga `https://unpkg.com/mermaid@12/dist/mermaid.min.js` solo si `window.mermaid` no existe
  (bundle `zensical_ui/templates/assets/javascripts/bundle.*.min.js`); un Mermaid en `extra_javascript` lo sustituye.
- **[docs]**: el Mermaid nativo dibuja en un shadow root cerrado: para verificarlo en Playwright usa capturas o la altura
  de `div.mermaid`, no `querySelector('svg')`.
- **[docs]**: con el plugin `privacy` las URL locales llevan el prefijo de la ruta de `site_url`; el ZIP offline servido
  en la raíz no las encuentra.
- **[build]**: `python -m build --wheel` reutiliza `build/lib` y puede meter módulos ya borrados; el build por defecto
  (sdist → wheel) es limpio.
- **[docs]**: el Mermaid local del sitio (`docs/assets/js/vendor/mermaid-<versión>.min.js`) debe ser la misma versión
  que la URL de unpkg del bundle de Zensical; al subir Zensical, igualarla (`ZENSICAL.md` §6).
- **[versión]**: `tests/unit/test_docs_version.py` exige el pie de figura de `docs/architecture.md` con «en vX.Y.Z»;
  los pines `git+…@vX.Y.Z` de la documentación (19 en 14 ficheros) también cambian en cada release.
- **[deps]**: quitar una dependencia de un extra puede retirar transitivas que los tests usaban sin declarar (aquí
  `certifi` vía mkdocs-material → requests): el venv limpio `.[dev-full]` es obligatorio antes de publicar.
- **[herramientas]**: para cambios de texto masivos con tildes o barras, scripts escritos con Write y ejecutados con
  `python -I` (sustituciones exactas con recuento); los heredocs de Bash corrompen `\` y caracteres no ASCII.

## Veredicto final
Veredicto: CLOSED — v5.6.0 (commits y tag anotado `v5.6.0` en local; push y release a mano por el usuario).
Pendientes al cierre:
- Push de `develop` y del tag, ff de `main` y release de GitHub (wheel + `.sha256`), `release_guide` §5–7.
- util_bbdd_web: al subir a 5.6.0, su salida Markdown traerá `zensical.toml` en lugar de `mkdocs.yml` (textos de la UI y
  un test del frontend lo nombran); su propio `backend/pyproject.toml` pide `zensical>=0.0.67`.
