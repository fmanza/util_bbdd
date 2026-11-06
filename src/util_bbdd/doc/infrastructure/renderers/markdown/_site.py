"""``mkdocs.yml`` mínimo para publicar la documentación Markdown con Zensical o MkDocs Material.

``nav`` corta (portada e índices): con cientos de tablas, la barra lateral automática sería inmanejable. Mermaid
con ``pymdownx.superfences`` (la configuración que documenta Zensical). Con ``mermaid_js``, el sitio carga un Mermaid
local: Zensical 0.0.71 solo va a unpkg si ``window.mermaid`` no existe (verificado en su bundle), así que el sitio
funciona sin Internet.

Con ``mermaid_js_ref`` (5.4.0) no se copia nada: si el fichero referenciado no está al publicar, ``zensical build
--strict`` y ``mkdocs build --strict`` no avisan, y en el navegador Zensical 0.0.71 y Material 9.7 cargan
``mermaid@11`` de unpkg (sin Internet, los diagramas se quedan como código). Verificado en la sesión
``2026-11-06-gaps-g50-g51``.
"""

from __future__ import annotations

import json

#: Ruta del Mermaid local dentro de ``docs/``
MERMAID_JS_PATH = "assets/javascripts/mermaid.min.js"


def mkdocs_yml(
    site_name: str,
    *,
    version: str,
    with_mermaid_js: bool,
    nav: list[tuple[str, str]],
    mermaid_ref: str | None = None,
) -> str:
    """Texto de ``mkdocs.yml``.

    Args:
        site_name: Título del sitio; se escribe como cadena JSON (escalar YAML entre comillas, sin inyección).
        version: Versión de util_bbdd (comentario de cabecera).
        with_mermaid_js: Añade ``extra_javascript`` con el Mermaid local (:data:`MERMAID_JS_PATH`) y ``font: false``
            en el tema: un Mermaid local indica un sitio sin Internet, y así no se pide nada fuera.
        nav: Navegación corta ``(título, página)``: portada e índices. Las páginas de cada objeto quedan fuera de la
            barra lateral (con cientos de tablas sería inmanejable) y se llega a ellas por los índices o el buscador.
        mermaid_ref: Mermaid ya publicado (``markdown.mermaid_js_ref``, 5.4.0): ruta relativa a ``docs/`` o URL
            ``https://``, ya validada. Va a ``extra_javascript`` sin copiar nada; con una ruta relativa añade también
            ``font: false`` (sitio sin Internet), con una URL no.
    """
    local = with_mermaid_js or (mermaid_ref is not None and "://" not in mermaid_ref)
    scripts = [json.dumps(mermaid_ref, ensure_ascii=False)] if mermaid_ref is not None else []
    if with_mermaid_js:
        scripts = [MERMAID_JS_PATH]
    lines = [
        f"# Generado por util_bbdd {version} (formato markdown); se reescribe en cada generación.",
        f"site_name: {json.dumps(site_name, ensure_ascii=False)}",
        "docs_dir: docs",
        "theme:",
        "  name: material",
        *(["  font: false"] if local else []),
        "nav:",
        *(f"  - {json.dumps(title, ensure_ascii=False)}: {path}" for title, path in nav),
        "markdown_extensions:",
        "  - tables",
        "  - admonition",
        "  - attr_list",
        "  - toc:",
        "      permalink: true",
        "  - pymdownx.superfences:",
        "      custom_fences:",
        "        - name: mermaid",
        "          class: mermaid",
        "          format: !!python/name:pymdownx.superfences.fence_code_format",
    ]
    if scripts:
        lines += ["extra_javascript:", *(f"  - {script}" for script in scripts)]
    return "\n".join(lines) + "\n"


__all__: list[str] = ["MERMAID_JS_PATH", "mkdocs_yml"]
