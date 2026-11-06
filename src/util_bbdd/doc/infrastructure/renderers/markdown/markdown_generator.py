"""Generador de la documentación en Markdown: un fichero por tabla, vista y rutina, con diagramas ER de Mermaid.

Mismas secciones, opciones de ``imprimir`` y cabeceras que Word; alternativas propias del formato aprobadas en la sesión
``2026-11-05-doc-markdown`` (D1–D7): orden alfabético, DDL en bloques ``sql``, front matter y anclas para que una IA
pueda trazar los objetos, índices por letra para esquemas de cientos de tablas y salida determinista (versionable con
git). Los diagramas no necesitan Graphviz.

Salida en la carpeta del formato (``<directorio_salida>/<nombre>/MARKDOWN``)::

    manifest.json
    docs/index.md
    docs/tables/index.md, index-<letra>.md, <slug>.md
    docs/views/…, docs/routines/…
    docs/database/info.md | storage.md | engine-conditions.md
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any

from .....analysis.mermaid_er import MermaidRelationshipGraph
from ....application.ports import DocumentationManagerPort
from ..shared.generator_shared import GeneratorInventoryRuntime, GeneratorRoutineRuntime, GeneratorTableRuntime
from ..shared.print_config_manager import PrintConfigManager
from ..shared.table_progress import TableProgress
from ._front_matter import RECORD_KINDS, ObjectRecords
from ._pages import PageContext, routine_page, table_page, view_page
from ._site_pages import (
    IndexEntry,
    database_info_page,
    engine_conditions_page,
    home_page,
    index_pages,
    storage_page,
)
from ._slugs import sort_key, unique_slugs
from ._writer import StagedWriter

_ROUTINE_TYPES: frozenset[str] = frozenset({"PROCEDURE", "FUNCTION"})


class MarkdownGenerator:
    """Genera la documentación Markdown de un schema (``DocumentRendererPort``).

    Args:
        database: Nombre de la base de datos que se muestra en la portada.
        headers: Cabeceras de cada sección (``headers_config.json``).

    Example:
        >>> result = DatabaseDocumentation(manager, Path("out"), formatos=["markdown"]).generate()
        >>> result.outputs["markdown"]  # …/MARKDOWN con docs/ y manifest.json
    """

    def __init__(self, database: str, headers: dict[str, list[str]]) -> None:
        self.database: str = database
        self.headers: dict[str, list[str]] = headers
        self.logger: logging.Logger = logging.getLogger(__name__)

    def generate_document(
        self,
        tables: list[tuple[Any, ...]],
        views: list[tuple[Any, ...]],
        routines: list[tuple[Any, ...]],
        data_provider: DocumentationManagerPort,
        output_target: Path,
        print_config: dict[str, Any] | None = None,
        graph_generator: Any | None = None,
    ) -> None:
        """Escribe la documentación en ``output_target`` (la carpeta ``MARKDOWN``).

        Args:
            tables: Tablas de la sesión (``[nombre, comentario, charset…]``).
            views: Vistas (``[nombre, comentario]``).
            routines: Rutinas (``[nombre, tipo, comentario]``).
            data_provider: Sesión de la documentación (filas por sección y lectura por lotes).
            output_target: Carpeta de salida del formato.
            print_config: Configuración ``imprimir``; si es None, la de ``data_provider``.
            graph_generator: No se usa: los diagramas ER se generan sin Graphviz.

        Raises:
            OperationCancelledError: Se canceló la generación; la carpeta queda como estaba.
        """
        _ = graph_generator
        config = PrintConfigManager.normalize(print_config or getattr(data_provider, "imprimir_config", {}))
        resolved = PrintConfigManager.resolve_for_markdown(config)
        self.logger.info(f"🟢 Iniciando documentación Markdown de {self.database}")

        table_rows = sorted(
            (GeneratorTableRuntime.extract_table_row_data(r) for r in tables) if resolved["include_tables"] else [],
            key=lambda row: sort_key(row[0]),
        )
        view_rows = sorted(
            ((str(v[0]), "" if len(v) < 2 or v[1] is None else str(v[1])) for v in views)
            if resolved["include_views"]
            else [],
            key=lambda row: sort_key(row[0]),
        )
        routine_rows = sorted(self._routines(routines, resolved), key=lambda row: (sort_key(row[0]), row[1]))

        records = ObjectRecords(data_provider.get_schema_metadata(kinds=RECORD_KINDS))
        table_slugs = unique_slugs(row[0] for row in table_rows)
        ctx = PageContext(data_provider, self.headers, resolved, table_slugs)
        writer = StagedWriter(output_target, self.logger)
        try:
            self._write_tables(writer, ctx, table_rows, records, data_provider)
            self._write_views(writer, ctx, view_rows, records)
            self._write_routines(writer, ctx, routine_rows, records)
            self._write_home(writer, ctx, tables=table_rows, views=view_rows, routines=routine_rows)
            writer.publish({"engine": records.engine, "schema": records.schema, "database": self.database})
        finally:
            writer.discard()
        self.logger.info(f"✅ Documentación Markdown generada en {output_target}")

    # --- Selección ---

    @staticmethod
    def _routines(routines: list[tuple[Any, ...]], resolved: dict[str, Any]) -> list[tuple[str, str, str]]:
        """Rutinas documentadas, como Word: procedures y funciones según sus flags; las de otro tipo si hay alguno."""
        include_procedures: bool = resolved["include_procedures"]
        include_functions: bool = resolved["include_functions"]
        selected: list[tuple[str, str, str]] = []
        for routine in routines:
            name, routine_type, comment = GeneratorRoutineRuntime.normalize_entry(routine)
            wanted = (
                (routine_type == "PROCEDURE" and include_procedures)
                or (routine_type == "FUNCTION" and include_functions)
                or (routine_type not in _ROUTINE_TYPES and (include_procedures or include_functions))
            )
            if wanted:
                selected.append((name, routine_type, comment))
        return selected

    # --- Objetos ---

    def _write_tables(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        rows: list[tuple[str, str, str | None]],
        records: ObjectRecords,
        data_provider: DocumentationManagerPort,
    ) -> None:
        options: dict[str, Any] = ctx.resolved["diagram_options"]
        graph = (
            MermaidRelationshipGraph(
                data_provider,
                column_mode=options["column_mode"],
                max_columns=options["max_columns"],
                show_constraint_name=options["show_constraint_name"],
            )
            if ctx.resolved["include_diagrams"] and rows
            else None
        )
        progress = TableProgress.of(data_provider, "markdown", len(rows))
        entries: list[IndexEntry] = []
        for name, comment, charset in rows:
            progress.before(name)
            slug = ctx.table_slugs[name]
            diagram = (
                graph.render_er(
                    name,
                    max_depth=options["max_depth"],
                    direction=options["direction"],
                    max_subnodes=options["max_subnodes"],
                )
                if graph is not None
                else None
            )
            record = records.table(name, comment) if ctx.resolved["front_matter"] else None
            writer.write(f"docs/tables/{slug}.md", _join(table_page(ctx, name, comment, charset, record, diagram)))
            entries.append(IndexEntry(name, f"{slug}.md", comment))
            progress.done(name)
        self._write_index(writer, "tables", "Tablas", entries, ctx)

    def _write_views(
        self, writer: StagedWriter, ctx: PageContext, rows: list[tuple[str, str]], records: ObjectRecords
    ) -> None:
        slugs = unique_slugs(name for name, _ in rows)
        entries: list[IndexEntry] = []
        for name, comment in rows:
            record = records.view(name, comment) if ctx.resolved["front_matter"] else None
            writer.write(f"docs/views/{slugs[name]}.md", _join(view_page(ctx, name, comment, record)))
            entries.append(IndexEntry(name, f"{slugs[name]}.md", comment))
        self._write_index(writer, "views", "Vistas", entries, ctx)

    def _write_routines(
        self, writer: StagedWriter, ctx: PageContext, rows: list[tuple[str, str, str]], records: ObjectRecords
    ) -> None:
        # Clave TIPO:nombre como en el HTML: un procedure y una función homónimos tienen ficheros distintos
        slugs = unique_slugs(f"{routine_type}:{name}" for name, routine_type, _ in rows)
        entries: list[IndexEntry] = []
        for name, routine_type, comment in rows:
            slug = slugs[f"{routine_type}:{name}"]
            record = records.routine(name, routine_type, comment) if ctx.resolved["front_matter"] else None
            writer.write(f"docs/routines/{slug}.md", _join(routine_page(ctx, name, routine_type, comment, record)))
            entries.append(IndexEntry(f"{name} ({routine_type.title()})", f"{slug}.md", comment))
        self._write_index(writer, "routines", "Rutinas", entries, ctx)

    @staticmethod
    def _write_index(
        writer: StagedWriter, folder: str, title: str, entries: list[IndexEntry], ctx: PageContext
    ) -> None:
        if not entries:
            return
        for file_name, lines in index_pages(title, entries, ctx.resolved["index_page_size"]).items():
            writer.write(f"docs/{folder}/{file_name}", _join(lines))

    # --- Portada y base de datos ---

    def _write_home(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        *,
        tables: list[tuple[str, str, str | None]],
        views: list[tuple[str, str]],
        routines: list[tuple[str, str, str]],
    ) -> None:
        resolved = ctx.resolved
        provider = ctx.data_provider
        sections: list[tuple[str, str]] = [
            (title, f"{folder}/index.md")
            for title, folder, items in (
                ("Tablas", "tables", tables),
                ("Vistas", "views", views),
                ("Rutinas", "routines", routines),
            )
            if items
        ]
        extra_pages = (
            ("include_database_info", "Información de la Base de Datos", "database/info.md"),
            ("include_storage", "Almacenamiento", "database/storage.md"),
            ("include_engine_conditions", "Condiciones del motor", "database/engine-conditions.md"),
        )
        for flag, title, path in extra_pages:
            if resolved[flag]:
                sections.append((title, path))
                writer.write(f"docs/{path}", _join(self._database_page(path, ctx)))
        inventory = GeneratorInventoryRuntime.build_summary_rows_from_entities(
            tables=list(tables),
            views=list(views),
            routines=list(routines),
            include_storage=resolved["include_storage"],
            data_provider=provider,
            include_routines=True,
        )
        include_legend = bool(resolved["include_diagrams"] and tables)
        writer.write("docs/index.md", _join(home_page(self.database, inventory, sections, include_legend)))

    def _database_page(self, path: str, ctx: PageContext) -> list[str]:
        provider = ctx.data_provider
        if path == "database/info.md":
            return database_info_page(provider, ctx.resolved["database_info_flags"], self.logger)
        if path == "database/storage.md":
            return storage_page(provider)
        return engine_conditions_page(provider)


def _join(lines: list[str]) -> str:
    """Líneas → texto con un único salto de línea final."""
    return "\n".join(lines).rstrip("\n") + "\n"


__all__: list[str] = ["MarkdownGenerator"]
