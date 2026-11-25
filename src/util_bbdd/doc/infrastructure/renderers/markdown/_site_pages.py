"""Portada, índices paginados y páginas de base de datos de la documentación Markdown.

Índices por letra (``a``–``z``, ``0-9``, ``otros``) con subpáginas de ``index_page_size`` entradas: con 500+ tablas, una
sola página de índice o una ``nav`` explícita serían inmanejables (D4).
"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from typing import Any

from ....._core.exceptions import DatabaseException
from ....._core.i18n import Translator
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


#: Claves ``doc_md.legend.*`` de :data:`ER_LEGEND_ROWS` (5.10.0): la salida usa el idioma de la generación; el
#: elemento vacío es ``nombre tipo``, que también se traduce.
_LEGEND_KEYS: tuple[tuple[str, str], ...] = (
    ("||", "one"),
    ("|o", "zero_or_one"),
    ("o{", "many"),
    ("o|", "one_to_one"),
    ("--", "identifying"),
    ("..", "non_identifying"),
    ("PK, FK, UK", "keys"),
    ("", "column"),
)


def _t(tr: Translator, key: str, **params: object) -> str:
    """Texto ``doc_md.<key>`` en el idioma de ``tr``."""
    return tr.t(f"doc_md.{key}", **params)


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
    translator: Translator | None = None,
) -> list[str]:
    """``index.md``: título, inventario, alcance del filtro, enlaces a las secciones y leyenda de los diagramas."""
    tr = translator or Translator()
    lines = [f"# {_t(tr, 'title.home', database=md_text(database))}", ""]
    inventory_table = md_table([_t(tr, "col.section"), _t(tr, "col.total")], [list(r) for r in inventory])
    lines += [f"## {_t(tr, 'home.inventory')}", "", *inventory_table, ""]
    if scope is not None:
        lines += scope_section(scope, tr)
    if sections:
        lines += [
            f"## {_t(tr, 'home.contents')}",
            "",
            *(f"- {md_link(title, target)}" for title, target in sections),
            "",
        ]
    if include_legend:
        legend = [
            [element or _t(tr, "legend.column_element"), _t(tr, f"legend.{key}")] for element, key in _LEGEND_KEYS
        ]
        lines += [
            f"## {_t(tr, 'home.legend')}",
            "",
            *md_table([_t(tr, "col.element"), _t(tr, "col.meaning")], legend),
            "",
            f"**{_t(tr, 'legend.levels_label')}:** {_t(tr, 'legend.levels_help')}",
        ]
        lines.append("")
    return lines


def scope_section(scope: FilterScope, translator: Translator | None = None) -> list[str]:
    """Sección «Alcance»: patrones del filtro y tablas de la frontera (sin ficha), como texto."""
    tr = translator or Translator()

    def patterns(values: tuple[str, ...]) -> str:
        return ", ".join(code_span(value) for value in values) if values else "—"

    lines = [
        f"## {_t(tr, 'scope.title')}",
        "",
        _t(tr, "scope.intro"),
        "",
        f"- **{_t(tr, 'scope.include')}:** {patterns(scope.include) if scope.include else _t(tr, 'scope.all')}",
        f"- **{_t(tr, 'scope.exclude')}:** {patterns(scope.exclude)}",
        "",
    ]
    if scope.frontier:
        lines += [
            f"### {_t(tr, 'scope.frontier_title')}",
            "",
            _t(tr, "scope.frontier_intro"),
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


def _letter_label(letter: str, tr: Translator) -> str:
    """Letra visible de un índice: la de ``otros`` se traduce (el fichero ``index-otros.md`` no cambia)."""
    return _t(tr, "index.letter_other") if letter == "otros" else letter.upper()


def _letter_pages(
    title: str, entries: list[IndexEntry], page_size: int, tr: Translator
) -> list[tuple[str, int, list[_LetterPage]]]:
    """Paginación por letra (común a :func:`index_pages` e :func:`index_page_titles`): ``(letra, total, páginas)``."""
    by_letter: dict[str, list[IndexEntry]] = {}
    for entry in entries:
        by_letter.setdefault(index_letter(entry.name), []).append(entry)
    letters = sorted(by_letter, key=lambda letter: (letter == "otros", letter == "0-9", letter))
    result: list[tuple[str, int, list[_LetterPage]]] = []
    for letter in letters:
        chunks = [by_letter[letter][i : i + page_size] for i in range(0, len(by_letter[letter]), page_size)]
        label = _letter_label(letter, tr)
        pages = [
            _LetterPage(
                f"index-{letter}.md" if number == 1 else f"index-{letter}-{number}.md",
                _t(tr, "index.letter_heading_paged", title=title, letter=label, number=number, total=len(chunks))
                if len(chunks) > 1
                else _t(tr, "index.letter_heading", title=title, letter=label),
                chunk,
            )
            for number, chunk in enumerate(chunks, start=1)
        ]
        result.append((letter, len(by_letter[letter]), pages))
    return result


def index_page_titles(
    title: str, entries: list[IndexEntry], page_size: int, translator: Translator | None = None
) -> dict[str, tuple[str, str | None]]:
    """Título (sin escapar) y letra de cada página de :func:`index_pages`, para ``manifest.json`` → ``pages`` (5.4.0).

    Returns:
        Nombre de fichero → ``(título, letra)``; el ``index.md`` de la sección lleva letra ``None``. Mismo orden que
        el índice: ``index.md`` y luego las letras con sus subpáginas.
    """
    titles: dict[str, tuple[str, str | None]] = {"index.md": (title, None)}
    for letter, _, letter_pages in _letter_pages(title, entries, page_size, translator or Translator()):
        for page in letter_pages:
            titles[page.file_name] = (page.heading, letter)
    return titles


def index_pages(
    title: str, entries: list[IndexEntry], page_size: int, translator: Translator | None = None
) -> dict[str, list[str]]:
    """Índice de una sección: ``index.md`` con las letras y una página por letra (``index-a.md``, ``index-a-2.md``…).

    Args:
        title: Título de la sección («Tablas», «Vistas»…).
        entries: Entradas ya ordenadas.
        page_size: Entradas por página de letra.
        translator: Idioma de los textos fijos (5.10.0); por defecto, español.

    Returns:
        Nombre de fichero (relativo a la carpeta de la sección) → líneas.
    """
    tr = translator or Translator()
    pages: dict[str, list[str]] = {}
    summary: list[list[Any]] = []
    for letter, total, letter_pages in _letter_pages(title, entries, page_size, tr):
        names = [page.file_name for page in letter_pages]
        summary.append([letter, total, names[0]])
        for page in letter_pages:
            chunk, file_name, heading = page.entries, page.file_name, page.heading
            nav = [
                md_link(_t(tr, "index.page", number=n), other)
                for n, other in enumerate(names, start=1)
                if other != file_name
            ]
            pages[file_name] = [
                f"# {md_text(heading)}",
                "",
                md_link(_t(tr, "index.back", title=title.lower()), "index.md"),
                "",
                *md_table(
                    [_t(tr, "col.name"), _t(tr, "col.comment")],
                    [[(e.name, e.target), e.comment] for e in chunk],
                    cell_renderers={0: _link_cell},
                ),
                "",
                *([" · ".join(nav), ""] if nav else []),
            ]
    pages["index.md"] = [
        f"# {md_text(title)}",
        "",
        md_link(_t(tr, "nav.home"), "../index.md"),
        "",
        *md_table(
            [_t(tr, "col.letter"), _t(tr, "col.total")],
            [[(_letter_label(str(row[0]), tr), row[2]), row[1]] for row in summary],
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


def database_info_page(
    provider: DocumentationManagerPort,
    flags: list[bool],
    logger: logging.Logger,
    translator: Translator | None = None,
) -> list[str]:
    """``database/info.md``: versión y charset/collation (como la sección final del Word)."""
    tr = translator or Translator()
    lines = [f"# {_t(tr, 'title.database_info')}", ""]
    try:
        rows = GeneratorDatabaseInfoRuntime.collect_database_info_rows(
            data_provider=provider, database_info_flags=flags, logger=logger, include_error_rows=True, translator=tr
        )
    except DatabaseException as error:
        return [*lines, md_text(_t(tr, "error.database_info", error=error)), ""]
    if not rows:
        return [*lines, _t(tr, "empty.database_info"), ""]
    table = md_table([_t(tr, "col.property"), _t(tr, "col.value")], [list(r) for r in rows])
    return [*lines, f"## {_t(tr, 'database.properties')}", "", *table, ""]


def storage_page(provider: DocumentationManagerPort, translator: Translator | None = None) -> list[str]:
    """``database/storage.md``: resumen y una tabla por consulta del inventario de almacenamiento."""
    tr = translator or Translator()
    lines = [f"# {_t(tr, 'title.storage')}", ""]
    try:
        report: dict[str, Any] = provider.get_storage_inventory_report()
    except DatabaseException as error:
        return [*lines, md_text(_t(tr, "error.storage", error=error)), ""]
    sections: list[dict[str, Any]] = report.get("sections", [])
    if sections:
        summary = [
            [s.get("title", ""), s.get("status", ""), len(s.get("rows", [])), s.get("message", "")] for s in sections
        ]
        headers_summary = [_t(tr, f"col.{key}") for key in ("query", "status", "rows", "message")]
        lines += [f"## {_t(tr, 'storage.summary')}", "", *md_table(headers_summary, summary), ""]
    for section in sections:
        title = str(section.get("title", _t(tr, "storage.query")))
        rows: list[list[Any]] = [list(r) for r in section.get("rows", [])]
        headers = [str(h) for h in section.get("headers", [])]
        if not headers and rows:
            headers = [_t(tr, "col.storage_column", number=i) for i in range(1, max(len(r) for r in rows) + 1)]
        lines += [f"## {md_text(title)}", ""]
        empty = section.get("message", _t(tr, "empty.storage_section"))
        lines += [*md_table(headers, rows), ""] if rows else [md_text(empty), ""]
    return lines


def engine_conditions_page(provider: DocumentationManagerPort, translator: Translator | None = None) -> list[str]:
    """``database/engine-conditions.md``: «Condiciones del motor» (``EngineReadinessAdvisor``)."""
    tr = translator or Translator()
    section = EngineConditionsSectionBuilder.of(provider)
    lines = [f"# {_t(tr, 'title.engine_conditions')}", ""]
    lines += [line for notice in section.notices for line in (md_text(notice), "")]
    if section.metadata:
        metadata = md_table([_t(tr, "col.property"), _t(tr, "col.value")], [list(i) for i in section.metadata])
        lines += [f"## {_t(tr, 'engine.verification')}", "", *metadata, ""]
    if section.summary:
        rows = [[level, count] for level, count in section.summary]
        summary = md_table([_t(tr, "col.level"), _t(tr, "col.findings")], rows)
        lines += [f"## {_t(tr, 'engine.summary')}", "", *summary, ""]
    if section.rows:
        lines += [
            f"## {_t(tr, 'engine.findings')}",
            "",
            *md_table(list(section.headers), [list(r) for r in section.rows]),
            "",
        ]
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
