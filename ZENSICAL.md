# Zensical en util_bbdd — guía para personas e IAs

**Ámbito**: Copilot Chat, Claude Code, Gemini, Codex y Cursor
**Versión de Zensical**: `>=0.1.1,<0.2` (extra `docs` de `pyproject.toml`; 0.1.x es beta)

---

## 1. Qué es y cómo se usa aquí

[Zensical](https://zensical.org) es el generador del sitio de documentación de util_bbdd, de los autores de Material
for MkDocs. Es el **único generador**: no hay `mkdocs.yml`, ni MkDocs Material, ni plugins de MkDocs.

| Aspecto | En util_bbdd |
|---|---|
| Configuración | `zensical.toml` en la raíz (formato nativo; todo bajo el ámbito `[project]`) |
| Contenido | `docs/` (Markdown) |
| Salida | `site/` (ignorado por git) |
| API de referencia | Plugin `mkdocstrings` (Zensical lo implementa de forma nativa), páginas `docs/api/*_autodoc.md` |
| Diagramas | Mermaid nativo, con el `mermaid.min.js` local `docs/assets/js/vendor/mermaid-12.3.0.min.js` en `extra_javascript` (Zensical no va a unpkg si `window.mermaid` existe): funciona sin Internet |
| ZIP offline | `scripts/build_docs_zip.py` después del build (Zensical no ejecuta plugins de MkDocs) |
| CI | `.github/workflows/docs.yml`, `docs-zip-release.yml`, `docs-release.yml`: `zensical build --strict` |

---

## 2. Comandos

```bash
pip install -e ".[docs]"   # zensical + mkdocstrings[python]
zensical serve             # servidor local en http://localhost:8000 (vista previa, no para producción)
zensical build --strict    # sitio en site/; los avisos son error (el mismo comando que el CI)
python scripts/build_docs_zip.py --no-build --in-site   # ZIP offline dentro de site/
```

`zensical build` no vacía `site/` entre builds; para empezar de cero, `zensical build --clean`.

---

## 3. `zensical.toml`

Estructura (las claves reales están en el fichero; la referencia oficial es
[Basics](https://zensical.org/docs/setup/basics/)):

```toml
[project]                         # metadatos, docs_dir, site_dir, nav, extra_css, extra_javascript
nav = [
  { "Inicio" = "index.md" },
  { "Guías" = [
    { "Incorporación para Desarrolladores" = "guides/onboarding_dev.md" },
  ] },
]

[project.theme]                   # language = "es", features, icon
[[project.theme.palette]]         # una tabla por esquema (claro / oscuro)
[[project.extra.social]]          # enlaces del pie
[project.markdown_extensions]     # admonition, pymdownx.* (Mermaid en pymdownx.superfences.custom_fences)
[project.plugins.mkdocstrings.handlers.python]          # paths = ["src"]
[project.plugins.mkdocstrings.handlers.python.options]  # docstring_style = "google", ...
```

Diferencias con el antiguo `mkdocs.yml`:

- Sin etiquetas `!!python/name:`: las funciones se escriben como cadenas
  (`format = "pymdownx.superfences.fence_code_format"`, `zensical.extensions.emoji.twemoji`).
- Sin plugin `search`: la búsqueda es nativa y usa `project.theme.language`.
- Sin `documentation_zip`: el ZIP es un script.
- Sin inicialización propia de Mermaid: el sitio usaba `mermaid@11` de jsDelivr y un `mermaid.js` a mano, que se
  imponían al Mermaid 12 de Zensical. Ahora Zensical inicializa el Mermaid local (misma versión que la de unpkg).

**Al añadir, mover o retirar una página**: actualiza el `nav` (prompt `.github/prompts/zensical_nav_update.prompt.md`).
`tests/unit/test_docs_links.py` comprueba que cada entrada del `nav` existe con el nombre exacto.

---

## 4. La documentación Markdown que genera la librería

Aparte del sitio del proyecto, `DatabaseDocumentation(formatos=["markdown"])` genera una carpeta publicable con
Zensical. Desde 5.6.0 escribe **`zensical.toml`** (`markdown.zensical_toml`, por defecto `True`); `mkdocs.yml`
(`markdown.mkdocs_yml`) está en desuso, desactivado por defecto y se retirará en 6.0.0. Detalle:
`docs/guides/markdown_documentation_guide.md`.

---

## 5. Problemas conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| Plugin configurado que no hace nada | Zensical ignora en silencio los plugins de MkDocs que no reimplementa | Comprobar la lista de [plugins compatibles](https://zensical.org/docs/compatibility/mkdocs/plugins/) |
| Un `.md` con mayúsculas distintas funciona en Windows y falla en el CI | El CI (Linux) distingue mayúsculas | `python -m pytest tests/unit/test_docs_links.py` |
| `--8<--` literal en el HTML | Falta `pymdownx.snippets.base_path = ["docs"]` | Ver `[project.markdown_extensions]` |

---

## 6. Actualizar Zensical

1. Lee las notas de la versión: <https://github.com/zensical/zensical/releases>.
2. Sube el rango en `pyproject.toml` (`docs`) y ejecuta `pip install -e ".[docs]"`.
3. Ejecuta `zensical build --strict` y compara el sitio. En la migración a 0.1.1 (sesión `2026-11-13-zensical-only`)
   se compararon por página los bloques autodoc, Mermaid, código, avisos y enlaces de `nav`, sin diferencias.
4. Revisa a mano una página con diagramas y otra con autodoc (`zensical serve`).
5. Si cambia la versión de Mermaid o su URL (búscala en `zensical_ui/templates/assets/javascripts/bundle.*.min.js`):
   sustituye `docs/assets/js/vendor/mermaid-<versión>.min.js` por la misma versión de npm y actualiza
   `extra_javascript`; revisa también `src/util_bbdd/doc/infrastructure/renderers/markdown/_site.py` (docstring) y la
   guía de la documentación Markdown.

---

*Actualizado: 2026-11-13*
