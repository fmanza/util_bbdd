"""``README.md`` de la documentación Markdown (5.5.0): cómo verla y qué contiene cada fichero.

Va en la raíz de la carpeta ``MARKDOWN`` (junto a ``mkdocs.yml``), fuera de ``docs/``: no es una página del sitio. Es
determinista (sin fecha ni rutas locales) para que la carpeta siga siendo versionable con git; solo describe los
ficheros que se han generado.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._site import MERMAID_JS_PATH


@dataclass(frozen=True)
class ReadmeContents:
    """Qué se ha generado: el ``README.md`` describe solo eso."""

    version: str
    mkdocs_yml: bool
    catalog_json: bool
    llms_txt: bool
    llms_full_txt: bool
    traceability: bool
    changes: bool
    local_mermaid: bool
    mermaid_ref: str | None
    filtered: bool


def readme_md(contents: ReadmeContents) -> str:
    """Texto del ``README.md``."""
    lines = [
        "# Documentación de la base de datos",
        "",
        f"Generada por util_bbdd {contents.version}: un fichero Markdown por tabla, vista y rutina, con diagramas de "
        "relaciones en Mermaid. Empieza por `docs/index.md`.",
        "",
        "## Cómo verla",
        "",
        "### Opción 1: en el editor (sin instalar nada más)",
        "",
        "1. Abre esta carpeta en Visual Studio Code.",
        "2. Abre `docs/index.md` y pulsa `Ctrl+Shift+V` (vista previa). Los enlaces llevan de una página a otra.",
        "3. Para ver los diagramas, instala la extensión *Markdown Preview Mermaid Support* "
        "(`bierner.markdown-mermaid`).",
        "",
        "GitHub y GitLab muestran también las páginas y los diagramas si subes la carpeta a un repositorio.",
        "",
    ]
    if contents.mkdocs_yml:
        lines += _site_section(contents)
    lines += ["## Qué contiene", "", "| Fichero | Contenido |", "|---|---|"]
    lines += [f"| {path} | {text} |" for path, text in _files(contents)]
    lines += [
        "",
        "Las páginas de cada objeto empiezan con un *front matter* JSON (id estable, PK, FK y hash) para "
        "herramientas e IA. No edites estos ficheros: se reescriben en cada generación.",
        "",
    ]
    return "\n".join(lines)


def _site_section(contents: ReadmeContents) -> list[str]:
    lines = [
        "### Opción 2: como sitio web (buscador y menú lateral)",
        "",
        "Necesitas Python. En esta carpeta (la que tiene `mkdocs.yml`):",
        "",
        "```bash",
        "pip install zensical",
        "zensical serve        # sitio en http://localhost:8000",
        "zensical build        # genera el sitio estático en site/",
        "```",
        "",
        "También funciona con MkDocs Material, con el mismo `mkdocs.yml`:",
        "",
        "```bash",
        "pip install mkdocs-material",
        "mkdocs serve",
        "```",
        "",
    ]
    if contents.local_mermaid:
        lines += [
            f"Los diagramas usan el Mermaid incluido (`docs/{MERMAID_JS_PATH}`): el sitio no necesita Internet.",
            "",
        ]
    elif contents.mermaid_ref is not None:
        lines += [f"Los diagramas cargan Mermaid desde `{contents.mermaid_ref}`.", ""]
    else:
        lines += [
            "Los diagramas descargan Mermaid de Internet al abrir el sitio. Para un sitio sin Internet, genera la "
            "documentación con `markdown.mermaid_js` (copia un `mermaid.min.js` local).",
            "",
        ]
    return lines


def _files(contents: ReadmeContents) -> list[tuple[str, str]]:
    files = [
        (
            "`docs/index.md`",
            "Portada: inventario, " + ("alcance del filtro, " if contents.filtered else "") + "secciones",
        ),
        ("`docs/tables/`, `docs/views/`, `docs/routines/`", "Una página por objeto e índices por letra"),
        ("`docs/database/`", "Información de la base de datos, almacenamiento y condiciones del motor (si se piden)"),
    ]
    if contents.traceability:
        files.append(("`docs/traceability.md`", "Trazabilidad: objetos ↔ código, documentos y requisitos"))
    if contents.changes:
        files.append(("`docs/changes.md`, `docs/changes.json`", "Cambios respecto de la generación anterior"))
    if contents.catalog_json:
        files.append(("`docs/catalog.json`", "Catálogo máquina-legible: columnas, claves, índices y hashes"))
    if contents.llms_txt:
        files.append(("`docs/llms.txt`", "Índice para asistentes de IA (formato llmstxt.org)"))
    if contents.llms_full_txt:
        files.append(("`docs/llms-full.txt`", "Todas las páginas en un solo fichero"))
    if contents.mkdocs_yml:
        files.append(("`mkdocs.yml`", "Configuración del sitio (Zensical o MkDocs Material)"))
    files.append(("`manifest.json`", "Ficheros generados con su hash, índice de páginas y versión del formato"))
    return files


__all__: list[str] = ["ReadmeContents", "readme_md"]
