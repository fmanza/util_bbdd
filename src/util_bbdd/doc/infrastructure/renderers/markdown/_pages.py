"""Páginas de objeto de la documentación Markdown: tabla, vista y rutina.

Mismas secciones, flags, cabeceras y mensajes que Word (``word_generator.py``), con las filas de los runtimes
compartidos. Cada función devuelve las líneas de la página; el texto del catálogo pasa siempre por ``_text``. Los textos
fijos salen del catálogo ``doc_md`` en el idioma de ``PageContext.tr`` (5.10.0).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ....._core.exceptions import DatabaseException
from ....._core.i18n import Translator
from .....analysis.mermaid_er import MermaidErResult
from ....application.ports import DocumentationManagerPort
from ..shared.diagram_summary import build_diagram_summary_line, build_diagram_summary_payload_from_document
from ..shared.generator_shared import GeneratorRoutineRuntime, GeneratorTabularRuntime
from ._front_matter import front_matter_data
from ._slugs import unique_slugs
from ._text import admonition, front_matter, md_code_block, md_link, md_table, md_text

# Títulos en español (públicos desde antes de 5.10.0); la salida usa el catálogo ``doc_md`` del idioma de la generación
SECTION_COLUMNS = "Columnas"
SECTION_PK = "Claves Primarias"
SECTION_FK = "Relaciones (Claves Foráneas)"
SECTION_UNIQUE = "Restricciones Únicas"
SECTION_INDICES = "Índices"
SECTION_CHARSET = "Charset/Collation de Columnas"
SECTION_PARAMETERS = "Parámetros"
SECTION_DIAGRAM = "Diagrama de relaciones"
SECTION_DDL = "## DDL"
REFERENCED_BY = "Referenciada por"
#: Marcas de una tabla relacionada que no se documenta por el filtro (5.5.0)
MARK_FRONTIER = "frontera, sin ficha"
MARK_EXCLUDED = "excluida por el filtro"

#: Cabeceras por defecto (si ``headers`` no trae la sección): claves ``doc_md.col.*``; las que empiezan por ``=`` son
#: literales que no se traducen.
_DEFAULT_HEADERS: dict[str, list[str]] = {
    "COLUMNAS": ["field", "type", "null", "default", "generation", "comment"],
    "FK": ["constraint_name", "column", "referenced_table", "referenced_column", "=ON DELETE", "=ON UPDATE"],
    "UNIQUE": ["constraint_name", "field"],
    "INDICES": ["index_name", "column", "unique", "index_type"],
    "PARAMETROS_RUTINA": ["mode", "parameter", "type", "default_value", "position"],
}


@dataclass(frozen=True)
class PageContext:
    """Lo que comparten las páginas de una generación.

    Attributes:
        data_provider: Sesión de la documentación (filas de cada sección).
        headers: Cabeceras de ``headers_config.json``.
        resolved: Configuración de ``PrintConfigManager.resolve_for_markdown``.
        table_slugs: Slug de cada tabla documentada (para enlazar las FK).
        referencing: Tablas que apuntan a una tabla con alguna FK (sección «Referenciada por», 5.5.0).
        filtered: Hay un ``filtro`` de tablas activo (5.5.0): las tablas no documentadas se marcan.
        frontier: Tablas de la frontera del filtro, en minúsculas.
        tr: Idioma de los textos fijos de las páginas (5.10.0).
    """

    data_provider: DocumentationManagerPort
    headers: dict[str, list[str]]
    resolved: dict[str, Any]
    table_slugs: dict[str, str]
    referencing: Callable[[str], list[str]] = lambda _name: []
    filtered: bool = False
    frontier: frozenset[str] = field(default_factory=frozenset)
    tr: Translator = field(default_factory=Translator)

    def header(self, key: str) -> list[str]:
        if self.headers.get(key):
            return list(self.headers[key])
        return [name[1:] if name.startswith("=") else self.t(f"col.{name}") for name in _DEFAULT_HEADERS[key]]

    def t(self, key: str, **params: Any) -> str:
        """Texto ``doc_md.<key>`` en el idioma de la generación."""
        return self.tr.t(f"doc_md.{key}", **params)


def _rows(values: Any) -> list[list[Any]]:
    """Filas de ``data_provider`` como listas (las de una sola columna pueden llegar como escalares)."""
    return [list(row) if isinstance(row, (list, tuple)) else [row] for row in values or []]


def _empty(title: str, message: str) -> list[str]:
    return [f"## {md_text(title)}", "", md_text(message), ""]


def _section(title: str, table: list[str]) -> list[str]:
    return [f"## {md_text(title)}", "", *table, ""]


def _header_block(
    ctx: PageContext, record: dict[str, Any] | None, title: str, comment: str, extra: list[str] | None = None
) -> list[str]:
    """Front matter, título, líneas previas al comentario (``extra``) y comentario."""
    lines = front_matter(front_matter_data(record)) if record is not None else []
    comment_line = f"**{ctx.t('label.comment')}:** {md_text(comment)}".rstrip()
    return [*lines, f"# {md_text(title)}", "", *(extra or []), comment_line, ""]


# --- Tablas -------------------------------------------------------------------


def table_page(
    ctx: PageContext,
    name: str,
    comment: str,
    charset_collation: str | None,
    record: dict[str, Any] | None,
    diagram: MermaidErResult | None,
) -> list[str]:
    """Página de una tabla: comentario, charset, secciones por flags (orden de Word) y diagrama."""
    lines = _header_block(ctx, record, ctx.t("title.table", name=name), comment)
    if charset_collation and str(charset_collation).strip():
        lines += [f"**Charset & Collation:** {md_text(charset_collation)}", ""]
    flags: list[bool] = ctx.resolved["table_section_flags"]
    # Orden y flags de Word: [ddl, columnas, pk, fk, unicas, indices]
    sections = (_table_ddl, _columns, _primary_keys, _foreign_keys, _unique_constraints, _indices)
    for enabled, section in zip(flags, sections, strict=False):
        if enabled:
            lines += section(ctx, name)
    if diagram is not None:
        lines += _diagram(ctx, diagram)
    return lines


def _ddl(ddl: Any) -> list[str]:
    return [SECTION_DDL, "", *md_code_block(ddl, "sql"), ""]


def _table_ddl(ctx: PageContext, name: str) -> list[str]:
    return _ddl(ctx.data_provider.get_ddl(name))


def _primary_keys(ctx: PageContext, name: str) -> list[str]:
    keys = _rows(ctx.data_provider.get_primary_keys(name))
    title = ctx.t("section.pk")
    return _section(title, md_table([ctx.t("col.field")], keys)) if keys else _empty(title, ctx.t("empty.pk"))


def _foreign_keys(ctx: PageContext, name: str) -> list[str]:
    """Claves foráneas (con enlace a la tabla referenciada) y, desde 5.5.0, las tablas que referencian a esta."""
    fks = _rows(ctx.data_provider.get_foreign_keys(name))
    if fks:
        lines = _section(
            ctx.t("section.fk"),
            md_table(ctx.header("FK"), fks, cell_renderers={2: lambda ref: _table_link(ctx, ref)}),
        )
    else:
        lines = _empty(ctx.t("section.fk"), ctx.t("empty.fk"))
    children = ctx.referencing(name)
    if children:
        lines += [
            f"**{ctx.t('label.referenced_by')}:**",
            "",
            *(f"- {_table_link(ctx, child)}" for child in children),
            "",
        ]
    return lines


def _unique_constraints(ctx: PageContext, name: str) -> list[str]:
    uniques = GeneratorTabularRuntime.process_unique_constraints_data(ctx.data_provider.get_unique_constraints(name))
    if not uniques:
        return _empty(ctx.t("section.unique"), ctx.t("empty.unique"))
    return _section(ctx.t("section.unique"), md_table(ctx.header("UNIQUE"), _rows(uniques)))


def _indices(ctx: PageContext, name: str) -> list[str]:
    indices = ctx.data_provider.get_indices(name)
    if not indices:
        return _empty(ctx.t("section.indices"), ctx.t("empty.indices"))
    return _section(
        ctx.t("section.indices"), md_table(ctx.header("INDICES"), GeneratorTabularRuntime.process_indices_data(indices))
    )


def _table_link(ctx: PageContext, ref: Any) -> str:
    """Tabla relacionada: enlace si se documenta; si no, texto y, con un filtro activo, la marca de por qué no está."""
    name = "" if ref is None else str(ref)
    slug = ctx.table_slugs.get(name)
    if slug:
        return md_link(name, f"{slug}.md")
    if not ctx.filtered or not name:
        return md_text(name)
    mark = ctx.t("mark.frontier") if name.casefold() in ctx.frontier else ctx.t("mark.excluded")
    return f"{md_text(name)} *({mark})*"


def _columns(ctx: PageContext, name: str) -> list[str]:
    """Sección «Columnas» (con anclas ``col-…`` por columna) y, si se pide, la de charset/collation."""
    provider = ctx.data_provider
    columns = GeneratorTabularRuntime.process_columns_data(provider.get_columns(name))
    include_charset: bool = ctx.resolved["include_columns_charset"]
    if not columns:
        lines = _empty(ctx.t("section.columns"), ctx.t("empty.columns"))
        if include_charset:
            lines += _empty(ctx.t("section.charset"), ctx.t("empty.charset"))
        return lines
    anchors: list[str] | None = None
    if ctx.resolved["column_anchors"]:
        slugs = unique_slugs(str(row[0]) for row in columns)
        anchors = [f'<a id="col-{slugs[str(row[0])]}"></a>' for row in columns]
    lines = _section(ctx.t("section.columns"), md_table(ctx.header("COLUMNAS"), columns, raw_first_cell=anchors))
    if include_charset:
        lines += _columns_charset(ctx, name)
    return lines


def _columns_charset(ctx: PageContext, name: str) -> list[str]:
    title = ctx.t("section.charset")
    try:
        info = ctx.data_provider.get_columns_charset_collation(name)
    except DatabaseException as error:
        return _empty(title, ctx.t("error.charset", error=error))
    if not info:
        return _empty(title, ctx.t("empty.charset"))
    rows = [[row[0], row[1] or "", row[2] or ""] for row in info]
    return _section(title, md_table([ctx.t("col.column"), "Charset", "Collation"], rows))


def _diagram(ctx: PageContext, diagram: MermaidErResult) -> list[str]:
    """Diagramas ER, avisos de recorte y resumen de niveles bajo cada uno."""
    options: dict[str, Any] = ctx.resolved["diagram_options"]
    lines = [f"## {ctx.t('section.diagram')}", ""]
    if options["configured_max_depth"] > options["max_depth"]:
        lines += admonition(
            "warning",
            ctx.t("diagram.depth_title", max_depth=options["max_depth"], configured=options["configured_max_depth"]),
            ctx.t("diagram.depth_body"),
        )
    for warning in diagram.warnings:
        lines += admonition("note", warning)
    if not diagram.blocks:
        return [*lines, ctx.t("diagram.none"), ""]
    summary = (
        build_diagram_summary_line(build_diagram_summary_payload_from_document(diagram.document, ctx.tr), ctx.tr)
        if options["summary_enabled"]
        else ""
    )
    total = len(diagram.blocks)
    for index, block in enumerate(diagram.blocks, start=1):
        if total > 1:
            lines += [f"**{ctx.t('diagram.part', index=index, total=total)}**", ""]
        lines += [*md_code_block(block, "mermaid"), ""]
        if summary:
            lines += [summary, ""]  # texto de la librería (cifras y etiquetas fijas), sin datos del catálogo
    return lines


# --- Vistas -------------------------------------------------------------------


def view_page(ctx: PageContext, name: str, comment: str, record: dict[str, Any] | None) -> list[str]:
    """Página de una vista: DDL y columnas, según flags (como Word)."""
    lines = _header_block(ctx, record, ctx.t("title.view", name=name), comment)
    flags: list[bool] = ctx.resolved["view_section_flags"]
    if len(flags) > 0 and flags[0]:
        try:
            lines += _ddl(ctx.data_provider.get_view_ddl(name))
        except DatabaseException:
            lines += [ctx.t("error.view_ddl"), ""]
    if len(flags) > 1 and flags[1]:
        try:
            lines += _columns(ctx, name)
        except DatabaseException:
            lines += [ctx.t("error.view_columns"), ""]
    return lines


# --- Rutinas ------------------------------------------------------------------


def routine_page(
    ctx: PageContext, name: str, routine_type: str, comment: str, record: dict[str, Any] | None
) -> list[str]:
    """Página de una rutina: tipo, comentario, DDL y parámetros (como Word)."""
    type_line = f"**{ctx.t('label.type')}:** {md_text(routine_type.title())}"
    lines = _header_block(ctx, record, f"{routine_type.title()}: {name}", comment, extra=[type_line, ""])
    provider = ctx.data_provider
    try:
        lines += _ddl(provider.get_routine_ddl(name, routine_type))
    except DatabaseException:
        lines += [ctx.t("error.routine_ddl"), ""]
    try:
        parameters = provider.get_routine_parameters(name, routine_type)
    except DatabaseException:
        return lines + _empty(ctx.t("section.parameters"), ctx.t("error.routine_parameters"))
    if not parameters:
        return lines + _empty(ctx.t("section.parameters"), ctx.t("empty.parameters"))
    rows = GeneratorRoutineRuntime.parameter_rows(parameters)
    return lines + _section(ctx.t("section.parameters"), md_table(ctx.header("PARAMETROS_RUTINA"), _rows(rows)))


__all__: list[str] = [
    "MARK_EXCLUDED",
    "MARK_FRONTIER",
    "REFERENCED_BY",
    "PageContext",
    "routine_page",
    "table_page",
    "view_page",
]
