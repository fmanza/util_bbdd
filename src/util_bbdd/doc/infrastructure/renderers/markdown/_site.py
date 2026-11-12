"""Configuración mínima del sitio de la documentación Markdown: ``zensical.toml`` (estándar) o ``mkdocs.yml``.

``zensical.toml`` (5.6.0) es el formato nativo de Zensical y el que se genera por defecto; ``mkdocs.yml`` queda como
opción en desuso (``markdown.mkdocs_yml``), que Zensical también lee. Los dos describen el mismo sitio
(:class:`_SiteSpec`).

``nav`` corta (portada e índices): con cientos de tablas, la barra lateral automática sería inmanejable. Mermaid
con ``pymdownx.superfences`` (la configuración que documenta Zensical). Con ``mermaid_js``, el sitio carga un Mermaid
local: Zensical 0.1.1 solo va a unpkg (``mermaid@12``) si ``window.mermaid`` no existe (verificado en su bundle), así
que el sitio funciona sin Internet.

Con ``mermaid_js_ref`` (5.4.0) no se copia nada: si el fichero referenciado no está al publicar, ``zensical build
--strict`` no avisa, y en el navegador Zensical carga ``mermaid@12`` de unpkg (sin Internet, los diagramas se quedan
como código). Verificado en las sesiones ``2026-11-06-gaps-g50-g51`` (0.0.71) y ``2026-11-13-zensical-only`` (0.1.1).
"""

from __future__ import annotations

import json

from dataclasses import dataclass

#: Ruta del Mermaid local dentro de ``docs/``
MERMAID_JS_PATH = "assets/javascripts/mermaid.min.js"


def _quote(value: str) -> str:
    """Cadena entre comillas, válida a la vez en YAML y en TOML (escapes de JSON): sin inyección."""
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class _SiteSpec:
    """Lo que describen por igual ``zensical.toml`` y ``mkdocs.yml``."""

    header: str
    site_name: str
    nav: list[tuple[str, str]]
    scripts: list[str]
    no_external_fonts: bool


def _spec(
    site_name: str,
    *,
    version: str,
    with_mermaid_js: bool,
    nav: list[tuple[str, str]],
    mermaid_ref: str | None,
) -> _SiteSpec:
    local = with_mermaid_js or (mermaid_ref is not None and "://" not in mermaid_ref)
    scripts = [mermaid_ref] if mermaid_ref is not None else []
    if with_mermaid_js:
        scripts = [MERMAID_JS_PATH]
    return _SiteSpec(
        header=f"# Generado por util_bbdd {version} (formato markdown); se reescribe en cada generación.",
        site_name=site_name,
        nav=nav,
        scripts=scripts,
        no_external_fonts=local,
    )


def zensical_toml(
    site_name: str,
    *,
    version: str,
    with_mermaid_js: bool,
    nav: list[tuple[str, str]],
    mermaid_ref: str | None = None,
) -> str:
    """Texto de ``zensical.toml`` (formato nativo de Zensical, ámbito ``[project]``; 5.6.0).

    Args:
        site_name: Título del sitio; se escribe como cadena TOML entre comillas (sin inyección).
        version: Versión de util_bbdd (comentario de cabecera).
        with_mermaid_js: Añade ``extra_javascript`` con el Mermaid local (:data:`MERMAID_JS_PATH`) y ``font = false``
            en el tema: un Mermaid local indica un sitio sin Internet, y así no se pide nada fuera.
        nav: Navegación corta ``(título, página)``: portada e índices. Las páginas de cada objeto quedan fuera de la
            barra lateral (con cientos de tablas sería inmanejable) y se llega a ellas por los índices o el buscador.
        mermaid_ref: Mermaid ya publicado (``markdown.mermaid_js_ref``, 5.4.0): ruta relativa a ``docs/`` o URL
            ``https://``, ya validada. Va a ``extra_javascript`` sin copiar nada; con una ruta relativa añade también
            ``font = false`` (sitio sin Internet), con una URL no.
    """
    spec = _spec(site_name, version=version, with_mermaid_js=with_mermaid_js, nav=nav, mermaid_ref=mermaid_ref)
    lines = [
        spec.header,
        "[project]",
        f"site_name = {_quote(spec.site_name)}",
        'docs_dir = "docs"',
        "nav = [",
        *(f"  {{ {_quote(title)} = {_quote(path)} }}," for title, path in spec.nav),
        "]",
    ]
    if spec.scripts:
        lines.append(f"extra_javascript = [{', '.join(_quote(script) for script in spec.scripts)}]")
    if spec.no_external_fonts:
        lines += ["", "[project.theme]", "font = false"]
    lines += [
        "",
        "[project.markdown_extensions]",
        "tables = {}",
        "admonition = {}",
        "attr_list = {}",
        "toc.permalink = true",
        "pymdownx.superfences.custom_fences = [",
        '  { name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" },',
        "]",
    ]
    return "\n".join(lines) + "\n"


def mkdocs_yml(
    site_name: str,
    *,
    version: str,
    with_mermaid_js: bool,
    nav: list[tuple[str, str]],
    mermaid_ref: str | None = None,
) -> str:
    """Texto de ``mkdocs.yml`` (en desuso desde 5.6.0: ``markdown.mkdocs_yml``; el estándar es :func:`zensical_toml`).

    Mismos argumentos y mismo sitio que :func:`zensical_toml`, en el formato YAML de MkDocs.
    """
    spec = _spec(site_name, version=version, with_mermaid_js=with_mermaid_js, nav=nav, mermaid_ref=mermaid_ref)
    lines = [
        spec.header,
        f"site_name: {_quote(spec.site_name)}",
        "docs_dir: docs",
        "theme:",
        "  name: material",
        *(["  font: false"] if spec.no_external_fonts else []),
        "nav:",
        *(f"  - {_quote(title)}: {path}" for title, path in spec.nav),
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
    if spec.scripts:
        # La referencia de mermaid_js_ref va entre comillas; la ruta local es una constante.
        scripts = [MERMAID_JS_PATH] if with_mermaid_js else [_quote(script) for script in spec.scripts]
        lines += ["extra_javascript:", *(f"  - {script}" for script in scripts)]
    return "\n".join(lines) + "\n"


__all__: list[str] = ["MERMAID_JS_PATH", "mkdocs_yml", "zensical_toml"]
