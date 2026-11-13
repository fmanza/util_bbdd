"""Portada, índices paginados y páginas de base de datos de la documentación Markdown.

Índices por letra (``a``–``z``, ``0-9``, ``otros``) con subpáginas de ``index_page_size`` entradas: con 500+ tablas, una
sola página de índice o una ``nav`` explícita serían inmanejables (D4).
"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from typing import Any

from ....._core.exceptions import DatabaseException
from ....._core.markdown import code_span
from ....application.ports import DocumentationManagerPort
from ....application.use_cases.engine_conditions import EngineConditionsSectionBuilder
from ..shared.generator_shared import GeneratorDatabaseInfoRuntime
from ._slugs import index_letter
from ._text import md_link, md_table, md_text

#: Leyenda de la notación de los diagramas ER de Mermaid (pata de gallo); no la de Graphviz, cuyos colores y
#: direcciones no existen aquí.
ER_LEGEND_ROWS: tuple[tuple[str, str], ...] = (
    ("||", "Exactamente uno (lado de la tabla referenciada)."),
    ("|o", "Cero o uno: la FK admite nulos, la fila puede no tener tabla referenciada."),
    ("o{", "Cero o muchos (lado de la tabla que tiene la FK)."),
    ("o|", "Cero o uno en la tabla que tiene la FK: relación 1:1 (la FK es su PK o una restricción UNIQUE)."),
    ("--", "Línea continua: relación identificante (la FK forma parte de la PK de la tabla hija)."),
    ("..", "Línea discontinua: relación no identificante."),
    ("PK, FK, UK", "Clave primaria, foránea o única en la columna."),
    # 5.8.0: el texto erDiagram lleva el nombre antes que el tipo (Mermaid toma el primero por tipo): se explica aquí
    # para quien lea el Markdown o llms-full.txt sin dibujarlo
    (
        "nombre tipo",
        "Cada columna de una tabla: nombre, tipo, claves y, entre comillas, el nombre real si hubo que normalizarlo.",
    ),
)


#: Qué es un nivel en los diagramas (L5 de la sesión 2026-11-12): con «ambas» direcciones, 1 nivel ya muestra la tabla
#: entre su padre y su hija, y parecía que se habían pedido 2.
DIAGRAM_LEVELS_HELP = (
    "Un nivel son las tablas unidas directamente por una FK. Los niveles se cuentan en cada sentido: con 1 nivel y las "
    "dos direcciones, el diagrama de una tabla muestra las tablas a las que apunta y las que la apuntan (por ejemplo, "
    "A → B → C en el de B). Bajo cada diagrama, «de N» indica cuántos niveles hay en total en ese sentido."
)


@dataclass(frozen=True)
class FilterScope:
    """Alcance de una documentación filtrada (5.5.0): patrones y tablas de la frontera."""

    include: tuple[str, ...]
    exclude: tuple[str, ...]
    frontier: tuple[str, ...]


@dataclass(frozen=True)
class IndexEntry:
    """Una entrada de índice: nombre visible, fichero (relativo a la carpeta del índice) y comentario."""

    name: str
    target: str
    comment: str


def home_page(
    database: str,
    inventory: list[tuple[str, int]],
    sections: list[tuple[str, str]],
    include_legend: bool,
    scope: FilterScope | None = None,
) -> list[str]:
    """``index.md``: título, inventario, alcance del filtro, enlaces a las secciones y leyenda de los diagramas."""
    lines = [f"# Documentación de la Base de Datos - {md_text(database)}", ""]
    lines += ["## Resumen de inventario", "", *md_table(["Sección", "Total"], [list(r) for r in inventory]), ""]
    if scope is not None:
        lines += scope_section(scope)
    if sections:
        lines += ["## Contenido", "", *(f"- {md_link(title, target)}" for title, target in sections), ""]
    if include_legend:
        lines += [
            "## Leyenda de los diagramas",
            "",
            *md_table(["Elemento", "Significado"], [list(r) for r in ER_LEGEND_ROWS]),
            "",
            f"**Niveles de relación:** {DIAGRAM_LEVELS_HELP}",
        ]
        lines.append("")
    return lines


def scope_section(scope: FilterScope) -> list[str]:
    """Sección «Alcance»: patrones del filtro y tablas de la frontera (sin ficha), como texto."""

    def patterns(values: tuple[str, ...]) -> str:
        return ", ".join(code_span(value) for value in values) if values else "—"

    lines = [
        "## Alcance",
        "",
        "Documentación filtrada: solo se incluyen las tablas y vistas que casan con algún patrón de inclusión y con "
        "ninguno de exclusión (patrones *glob*, sin distinguir mayúsculas).",
        "",
        f"- **Incluir:** {patterns(scope.include) if scope.include else 'todas'}",
        f"- **Excluir:** {patterns(scope.exclude)}",
        "",
    ]
    if scope.frontier:
        lines += [
            "### Tablas de frontera",
            "",
            "Unidas por una FK a alguna tabla documentada, pero fuera del filtro: aparecen en los diagramas y en las "
            "relaciones, sin ficha propia.",
            "",
            *(f"- {md_text(name)}" for name in scope.frontier),
            "",
        ]
    return lines


@dataclass(frozen=True)
class _LetterPage:
    """Una página de letra de un índice: fichero, título sin escapar y entradas."""

    file_name: str
    heading: str
    entries: list[IndexEntry]


def _letter_pages(title: str, entries: list[IndexEntry], page_size: int) -> list[tuple[str, int, list[_LetterPage]]]:
    """Paginación por letra (común a :func:`index_pages` e :func:`index_page_titles`): ``(letra, total, páginas)``."""
    by_letter: dict[str, list[IndexEntry]] = {}
    for entry in entries:
        by_letter.setdefault(index_letter(entry.name), []).append(entry)
    letters = sorted(by_letter, key=lambda letter: (letter == "otros", letter == "0-9", letter))
    result: list[tuple[str, int, list[_LetterPage]]] = []
    for letter in letters:
        chunks = [by_letter[letter][i : i + page_size] for i in range(0, len(by_letter[letter]), page_size)]
        pages = [
            _LetterPage(
                f"index-{letter}.md" if number == 1 else f"index-{letter}-{number}.md",
                f"{title}: {letter.upper()}" + (f" ({number} de {len(chunks)})" if len(chunks) > 1 else ""),
                chunk,
            )
            for number, chunk in enumerate(chunks, start=1)
        ]
        result.append((letter, len(by_letter[letter]), pages))
    return result


def index_page_titles(title: str, entries: list[IndexEntry], page_size: int) -> dict[str, tuple[str, str | None]]:
    """Título (sin escapar) y letra de cada página de :func:`index_pages`, para ``manifest.json`` → ``pages`` (5.4.0).

    Returns:
        Nombre de fichero → ``(título, letra)``; el ``index.md`` de la sección lleva letra ``None``. Mismo orden que
        el índice: ``index.md`` y luego las letras con sus subpáginas.
    """
    titles: dict[str, tuple[str, str | None]] = {"index.md": (title, None)}
    for letter, _, letter_pages in _letter_pages(title, entries, page_size):
        for page in letter_pages:
            titles[page.file_name] = (page.heading, letter)
    return titles


def index_pages(title: str, entries: list[IndexEntry], page_size: int) -> dict[str, list[str]]:
    """Índice de una sección: ``index.md`` con las letras y una página por letra (``index-a.md``, ``index-a-2.md``…).

    Args:
        title: Título de la sección («Tablas», «Vistas»…).
        entries: Entradas ya ordenadas.
        page_size: Entradas por página de letra.

    Returns:
        Nombre de fichero (relativo a la carpeta de la sección) → líneas.
    """
    pages: dict[str, list[str]] = {}
    summary: list[list[Any]] = []
    for letter, total, letter_pages in _letter_pages(title, entries, page_size):
        names = [page.file_name for page in letter_pages]
        summary.append([letter, total, names[0]])
        for page in letter_pages:
            chunk, file_name, heading = page.entries, page.file_name, page.heading
            nav = [md_link(f"Página {n}", other) for n, other in enumerate(names, start=1) if other != file_name]
            pages[file_name] = [
                f"# {md_text(heading)}",
                "",
                md_link(f"Índice de {title.lower()}", "index.md"),
                "",
                *md_table(
                    ["Nombre", "Comentario"],
                    [[(e.name, e.target), e.comment] for e in chunk],
                    cell_renderers={0: _link_cell},
                ),
                "",
                *([" · ".join(nav), ""] if nav else []),
            ]
    pages["index.md"] = [
        f"# {md_text(title)}",
        "",
        md_link("Inicio", "../index.md"),
        "",
        *md_table(
            ["Letra", "Total"],
            [[(str(row[0]).upper(), row[2]), row[1]] for row in summary],
            cell_renderers={0: _link_cell},
        ),
        "",
    ]
    return pages


def _link_cell(value: tuple[str, str]) -> str:
    """Celda ``(texto, destino)`` → enlace relativo (el texto se escapa; el destino lo genera la librería)."""
    label, target = value
    return md_link(label, target)


# --- Base de datos ------------------------------------------------------------


def database_info_page(provider: DocumentationManagerPort, flags: list[bool], logger: logging.Logger) -> list[str]:
    """``database/info.md``: versión y charset/collation (como la sección final del Word)."""
    lines = ["# Información de la Base de Datos", ""]
    try:
        rows = GeneratorDatabaseInfoRuntime.collect_database_info_rows(
            data_provider=provider, database_info_flags=flags, logger=logger, include_error_rows=True
        )
    except DatabaseException as error:
        return [*lines, md_text(f"Error al obtener información: {error}"), ""]
    if not rows:
        return [*lines, "No se configuró información de base de datos para mostrar.", ""]
    return [*lines, "## Propiedades", "", *md_table(["Propiedad", "Valor"], [list(r) for r in rows]), ""]


def storage_page(provider: DocumentationManagerPort) -> list[str]:
    """``database/storage.md``: resumen y una tabla por consulta del inventario de almacenamiento."""
    lines = ["# Almacenamiento", ""]
    try:
        report: dict[str, Any] = provider.get_storage_inventory_report()
    except DatabaseException as error:
        return [*lines, md_text(f"No se pudo obtener la información de almacenamiento: {error}"), ""]
    sections: list[dict[str, Any]] = report.get("sections", [])
    if sections:
        summary = [
            [s.get("title", ""), s.get("status", ""), len(s.get("rows", [])), s.get("message", "")] for s in sections
        ]
        lines += ["## Resumen", "", *md_table(["Consulta", "Estado", "Filas", "Mensaje"], summary), ""]
    for section in sections:
        title = str(section.get("title", "Consulta"))
        rows: list[list[Any]] = [list(r) for r in section.get("rows", [])]
        headers = [str(h) for h in section.get("headers", [])]
        if not headers and rows:
            headers = [f"Columna {i}" for i in range(1, max(len(r) for r in rows) + 1)]
        lines += [f"## {md_text(title)}", ""]
        lines += [*md_table(headers, rows), ""] if rows else [md_text(section.get("message", "Sin datos")), ""]
    return lines


def engine_conditions_page(provider: DocumentationManagerPort) -> list[str]:
    """``database/engine-conditions.md``: «Condiciones del motor» (``EngineReadinessAdvisor``)."""
    section = EngineConditionsSectionBuilder.of(provider)
    lines = ["# Condiciones del motor", ""]
    lines += [line for notice in section.notices for line in (md_text(notice), "")]
    if section.metadata:
        lines += ["## Verificación", "", *md_table(["Propiedad", "Valor"], [list(i) for i in section.metadata]), ""]
    if section.summary:
        rows = [[level, count] for level, count in section.summary]
        lines += ["## Resumen por severidad", "", *md_table(["Nivel", "Hallazgos"], rows), ""]
    if section.rows:
        lines += ["## Hallazgos", "", *md_table(list(section.headers), [list(r) for r in section.rows]), ""]
    return lines


__all__: list[str] = [
    "DIAGRAM_LEVELS_HELP",
    "ER_LEGEND_ROWS",
    "FilterScope",
    "IndexEntry",
    "database_info_page",
    "engine_conditions_page",
    "home_page",
    "index_page_titles",
    "index_pages",
    "scope_section",
    "storage_page",
]
