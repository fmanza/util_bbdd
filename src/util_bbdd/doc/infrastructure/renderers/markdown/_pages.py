"""Páginas de objeto de la documentación Markdown: tabla, vista y rutina.

Mismas secciones, flags, cabeceras y mensajes que Word (``word_generator.py``), con las filas de los runtimes
compartidos. Cada función devuelve las líneas de la página; el texto del catálogo pasa siempre por ``_text``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ....._core.exceptions import DatabaseException
from .....analysis.mermaid_er import MermaidErResult
from ....application.ports import DocumentationManagerPort
from ..shared.diagram_summary import build_diagram_summary_line, build_diagram_summary_payload_from_document
from ..shared.generator_shared import GeneratorRoutineRuntime, GeneratorTabularRuntime
from ._front_matter import front_matter_data
from ._slugs import unique_slugs
from ._text import admonition, front_matter, md_code_block, md_link, md_table, md_text

SECTION_COLUMNS = "Columnas"
SECTION_PK = "Claves Primarias"
SECTION_FK = "Relaciones (Claves Foráneas)"
SECTION_UNIQUE = "Restricciones Únicas"
SECTION_INDICES = "Índices"
SECTION_CHARSET = "Charset/Collation de Columnas"
SECTION_PARAMETERS = "Parámetros"
SECTION_DIAGRAM = "Diagrama de relaciones"
SECTION_DDL = "## DDL"

_DEFAULT_HEADERS: dict[str, list[str]] = {
    "COLUMNAS": ["Campo", "Tipo", "Nulo", "Por defecto", "Generación", "Comentario"],
    "FK": ["Nombre Restricción", "Columna", "Tabla Referenciada", "Columna Referenciada", "ON DELETE", "ON UPDATE"],
    "UNIQUE": ["Nombre Restricción", "Campo"],
    "INDICES": ["Nombre Índice", "Columna", "Único", "Tipo de Índice"],
    "PARAMETROS_RUTINA": ["Modo", "Parámetro", "Tipo", "Valor por defecto", "Posición"],
}


@dataclass(frozen=True)
class PageContext:
    """Lo que comparten las páginas de una generación.

    Attributes:
        data_provider: Sesión de la documentación (filas de cada sección).
        headers: Cabeceras de ``headers_config.json``.
        resolved: Configuración de ``PrintConfigManager.resolve_for_markdown``.
        table_slugs: Slug de cada tabla documentada (para enlazar las FK).
    """

    data_provider: DocumentationManagerPort
    headers: dict[str, list[str]]
    resolved: dict[str, Any]
    table_slugs: dict[str, str]

    def header(self, key: str) -> list[str]:
        return list(self.headers.get(key) or _DEFAULT_HEADERS[key])


def _rows(values: Any) -> list[list[Any]]:
    """Filas de ``data_provider`` como listas (las de una sola columna pueden llegar como escalares)."""
    return [list(row) if isinstance(row, (list, tuple)) else [row] for row in values or []]


def _empty(title: str, message: str) -> list[str]:
    return [f"## {md_text(title)}", "", md_text(message), ""]


def _section(title: str, table: list[str]) -> list[str]:
    return [f"## {md_text(title)}", "", *table, ""]


def _header_block(record: dict[str, Any] | None, title: str, comment: str, extra: list[str] | None = None) -> list[str]:
    """Front matter, título, líneas previas al comentario (``extra``) y comentario."""
    lines = front_matter(front_matter_data(record)) if record is not None else []
    comment_line = f"**Comentario:** {md_text(comment)}".rstrip()
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
    lines = _header_block(record, f"Tabla: {name}", comment)
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
    return _section(SECTION_PK, md_table(["Campo"], keys)) if keys else _empty(SECTION_PK, _NO_PK)


def _foreign_keys(ctx: PageContext, name: str) -> list[str]:
    fks = _rows(ctx.data_provider.get_foreign_keys(name))
    if not fks:
        return _empty(SECTION_FK, "No se encontraron claves foráneas.")
    return _section(SECTION_FK, md_table(ctx.header("FK"), fks, cell_renderers={2: lambda ref: _table_link(ctx, ref)}))


def _unique_constraints(ctx: PageContext, name: str) -> list[str]:
    uniques = GeneratorTabularRuntime.process_unique_constraints_data(ctx.data_provider.get_unique_constraints(name))
    if not uniques:
        return _empty(SECTION_UNIQUE, "No se encontraron claves únicas.")
    return _section(SECTION_UNIQUE, md_table(ctx.header("UNIQUE"), _rows(uniques)))


def _indices(ctx: PageContext, name: str) -> list[str]:
    indices = ctx.data_provider.get_indices(name)
    if not indices:
        return _empty(SECTION_INDICES, "No se encontraron índices.")
    return _section(
        SECTION_INDICES, md_table(ctx.header("INDICES"), GeneratorTabularRuntime.process_indices_data(indices))
    )


_NO_PK = "No se encontraron claves primarias."


def _table_link(ctx: PageContext, ref: Any) -> str:
    """Tabla referenciada de una FK: enlace si se documenta; si no, texto."""
    name = "" if ref is None else str(ref)
    slug = ctx.table_slugs.get(name)
    return md_link(name, f"{slug}.md") if slug else md_text(name)


def _columns(ctx: PageContext, name: str) -> list[str]:
    """Sección «Columnas» (con anclas ``col-…`` por columna) y, si se pide, la de charset/collation."""
    provider = ctx.data_provider
    columns = GeneratorTabularRuntime.process_columns_data(provider.get_columns(name))
    include_charset: bool = ctx.resolved["include_columns_charset"]
    if not columns:
        lines = _empty(SECTION_COLUMNS, "No se encontraron columnas.")
        if include_charset:
            lines += _empty(SECTION_CHARSET, "No hay información de charset/collation disponible.")
        return lines
    anchors: list[str] | None = None
    if ctx.resolved["column_anchors"]:
        slugs = unique_slugs(str(row[0]) for row in columns)
        anchors = [f'<a id="col-{slugs[str(row[0])]}"></a>' for row in columns]
    lines = _section(SECTION_COLUMNS, md_table(ctx.header("COLUMNAS"), columns, raw_first_cell=anchors))
    if include_charset:
        lines += _columns_charset(provider, name)
    return lines


def _columns_charset(provider: DocumentationManagerPort, name: str) -> list[str]:
    try:
        info = provider.get_columns_charset_collation(name)
    except DatabaseException as error:
        return _empty(SECTION_CHARSET, f"Error obteniendo información: {error}")
    if not info:
        return _empty(SECTION_CHARSET, "No hay información de charset/collation disponible.")
    rows = [[row[0], row[1] or "", row[2] or ""] for row in info]
    return _section(SECTION_CHARSET, md_table(["Columna", "Charset", "Collation"], rows))


def _diagram(ctx: PageContext, diagram: MermaidErResult) -> list[str]:
    """Diagramas ER, avisos de recorte y resumen de niveles bajo cada uno."""
    options: dict[str, Any] = ctx.resolved["diagram_options"]
    lines = [f"## {SECTION_DIAGRAM}", ""]
    if options["configured_max_depth"] > options["max_depth"]:
        lines += admonition(
            "warning",
            f"Profundidad limitada a {options['max_depth']} (configurada {options['configured_max_depth']})",
            "Los diagramas del Markdown se limitan con markdown.max_diagram_depth; las relaciones completas están en "
            "la sección de claves foráneas y en el front matter.",
        )
    for warning in diagram.warnings:
        lines += admonition("note", warning)
    if not diagram.blocks:
        return [*lines, "Sin relaciones con otras tablas.", ""]
    summary = (
        build_diagram_summary_line(build_diagram_summary_payload_from_document(diagram.document))
        if options["summary_enabled"]
        else ""
    )
    total = len(diagram.blocks)
    for index, block in enumerate(diagram.blocks, start=1):
        if total > 1:
            lines += [f"**Parte {index} de {total}**", ""]
        lines += [*md_code_block(block, "mermaid"), ""]
        if summary:
            lines += [summary, ""]  # texto de la librería (cifras y etiquetas fijas), sin datos del catálogo
    return lines


# --- Vistas -------------------------------------------------------------------


def view_page(ctx: PageContext, name: str, comment: str, record: dict[str, Any] | None) -> list[str]:
    """Página de una vista: DDL y columnas, según flags (como Word)."""
    lines = _header_block(record, f"Vista: {name}", comment)
    flags: list[bool] = ctx.resolved["view_section_flags"]
    if len(flags) > 0 and flags[0]:
        try:
            lines += _ddl(ctx.data_provider.get_view_ddl(name))
        except DatabaseException:
            lines += ["No se pudo obtener el DDL de la vista.", ""]
    if len(flags) > 1 and flags[1]:
        try:
            lines += _columns(ctx, name)
        except DatabaseException:
            lines += ["No se pudieron obtener las columnas de la vista.", ""]
    return lines


# --- Rutinas ------------------------------------------------------------------


def routine_page(
    ctx: PageContext, name: str, routine_type: str, comment: str, record: dict[str, Any] | None
) -> list[str]:
    """Página de una rutina: tipo, comentario, DDL y parámetros (como Word)."""
    lines = _header_block(
        record, f"{routine_type.title()}: {name}", comment, extra=[f"**Tipo:** {md_text(routine_type.title())}", ""]
    )
    provider = ctx.data_provider
    try:
        lines += _ddl(provider.get_routine_ddl(name, routine_type))
    except DatabaseException:
        lines += ["No se pudo obtener el DDL de la rutina.", ""]
    try:
        parameters = provider.get_routine_parameters(name, routine_type)
    except DatabaseException:
        return lines + _empty(SECTION_PARAMETERS, "No se pudieron obtener los parámetros de la rutina.")
    if not parameters:
        return lines + _empty(SECTION_PARAMETERS, "No se encontraron parámetros.")
    rows = GeneratorRoutineRuntime.parameter_rows(parameters)
    return lines + _section(SECTION_PARAMETERS, md_table(ctx.header("PARAMETROS_RUTINA"), _rows(rows)))


__all__: list[str] = ["PageContext", "routine_page", "table_page", "view_page"]
