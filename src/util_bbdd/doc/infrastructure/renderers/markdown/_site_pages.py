"""Portada, índices paginados y páginas de base de datos de la documentación Markdown.

Índices por letra (``a``–``z``, ``0-9``, ``otros``) con subpáginas de ``index_page_size`` entradas: con 500+ tablas, una
sola página de índice o una ``nav`` explícita serían inmanejables (D4).
"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from typing import Any

from ....._core.exceptions import DatabaseException
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
)


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
) -> list[str]:
    """``index.md``: título, inventario, enlaces a las secciones y leyenda de los diagramas."""
    lines = [f"# Documentación de la Base de Datos - {md_text(database)}", ""]
    lines += ["## Resumen de inventario", "", *md_table(["Sección", "Total"], [list(r) for r in inventory]), ""]
    if sections:
        lines += ["## Contenido", "", *(f"- {md_link(title, target)}" for title, target in sections), ""]
    if include_legend:
        lines += [
            "## Leyenda de los diagramas",
            "",
            *md_table(["Elemento", "Significado"], [list(r) for r in ER_LEGEND_ROWS]),
        ]
        lines.append("")
    return lines


def index_pages(title: str, entries: list[IndexEntry], page_size: int) -> dict[str, list[str]]:
    """Índice de una sección: ``index.md`` con las letras y una página por letra (``index-a.md``, ``index-a-2.md``…).

    Args:
        title: Título de la sección («Tablas», «Vistas»…).
        entries: Entradas ya ordenadas.
        page_size: Entradas por página de letra.

    Returns:
        Nombre de fichero (relativo a la carpeta de la sección) → líneas.
    """
    by_letter: dict[str, list[IndexEntry]] = {}
    for entry in entries:
        by_letter.setdefault(index_letter(entry.name), []).append(entry)
    letters = sorted(by_letter, key=lambda letter: (letter == "otros", letter == "0-9", letter))

    pages: dict[str, list[str]] = {}
    summary: list[list[Any]] = []
    for letter in letters:
        chunks = [by_letter[letter][i : i + page_size] for i in range(0, len(by_letter[letter]), page_size)]
        names = [f"index-{letter}.md" if n == 1 else f"index-{letter}-{n}.md" for n in range(1, len(chunks) + 1)]
        summary.append([letter, len(by_letter[letter]), names[0]])
        for number, (chunk, file_name) in enumerate(zip(chunks, names, strict=True), start=1):
            heading = f"{title}: {letter.upper()}" + (f" ({number} de {len(chunks)})" if len(chunks) > 1 else "")
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
    "ER_LEGEND_ROWS",
    "IndexEntry",
    "database_info_page",
    "engine_conditions_page",
    "home_page",
    "index_pages",
    "storage_page",
]
