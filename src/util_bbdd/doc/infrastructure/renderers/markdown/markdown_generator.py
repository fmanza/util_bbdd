"""Generador de la documentación en Markdown: un fichero por tabla, vista y rutina, con diagramas ER de Mermaid.

Mismas secciones, opciones de ``imprimir`` y cabeceras que Word; alternativas propias del formato aprobadas en la sesión
``2026-11-05-doc-markdown`` (D1–D7): orden alfabético, DDL en bloques ``sql``, front matter y anclas para que una IA
pueda trazar los objetos, índices por letra para esquemas de cientos de tablas y salida determinista (versionable con
git). Los diagramas no necesitan Graphviz.

Salida en la carpeta del formato (``<directorio_salida>/<nombre>/MARKDOWN``)::

    manifest.json
    mkdocs.yml                                  # markdown.mkdocs_yml
    docs/index.md
    docs/tables/index.md, index-<letra>.md, <slug>.md
    docs/views/…, docs/routines/…
    docs/database/info.md | storage.md | engine-conditions.md
    docs/catalog.json                           # markdown.catalog_json (ADR-006)
    docs/llms.txt, docs/llms-full.txt           # markdown.llms_txt / llms_full_txt
    docs/assets/javascripts/mermaid.min.js      # markdown.mermaid_js
"""

from __future__ import annotations

import logging

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any

from .....analysis.mermaid_er import MermaidRelationshipGraph
from ....application.ports import DocumentationManagerPort
from ..shared.generator_shared import GeneratorInventoryRuntime, GeneratorRoutineRuntime, GeneratorTableRuntime
from ..shared.print_config_manager import PrintConfigManager
from ..shared.table_progress import TableProgress
from ._catalog import CatalogEntry, catalog_json, llms_full_marker, llms_txt
from ._changes import build_changes, changes_json, changes_page, load_previous
from ._front_matter import RECORD_KINDS, ObjectRecords
from ._pages import PageContext, routine_page, table_page, view_page
from ._site import MERMAID_JS_PATH, mkdocs_yml
from ._site_pages import (
    IndexEntry,
    database_info_page,
    engine_conditions_page,
    home_page,
    index_pages,
    storage_page,
)
from ._slugs import sort_key, unique_slugs
from ._trace import TracedObject, TraceEntry, TraceMap, Unmatched, match_columns, trace_section, traceability_page
from ._writer import StagedWriter, TextStream, library_version

_ROUTINE_TYPES: frozenset[str] = frozenset({"PROCEDURE", "FUNCTION"})
_FRONT_MATTER_LINES = 4  # "---", JSON, "---", ""


class MarkdownGenerator:
    """Genera la documentación Markdown de un schema (``DocumentRendererPort``).

    Args:
        database: Nombre de la base de datos que se muestra en la portada.
        headers: Cabeceras de cada sección (``headers_config.json``).

    Example:
        >>> result = DatabaseDocumentation(manager, Path("out"), formatos=["markdown"]).generate()
        >>> result.outputs["markdown"]  # …/MARKDOWN con docs/, manifest.json y mkdocs.yml
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
        ctx = PageContext(data_provider, self.headers, resolved, unique_slugs(row[0] for row in table_rows))
        tracer = _Tracer(
            TraceMap.load(resolved["trace_map"]) if resolved["trace_map"] is not None else None,
            tables=[row[0] for row in table_rows],
            views=[row[0] for row in view_rows],
            routines=[f"{routine_type}:{name}" for name, routine_type, _ in routine_rows],
        )
        writer = StagedWriter(output_target, self.logger)
        try:
            entries: list[CatalogEntry] = []
            with self._llms_full(writer, resolved) as full:
                home, sections = self._write_home(
                    writer, ctx, tables=table_rows, views=view_rows, routines=routine_rows
                )
                if full is not None:
                    full.write(_join(home))
                entries += self._write_tables(writer, ctx, table_rows, records, full, tracer)
                entries += self._write_views(writer, ctx, view_rows, records, full, tracer)
                entries += self._write_routines(writer, ctx, routine_rows, records, full, tracer)
            nav = [("Inicio", "index.md"), *sections]
            if tracer.enabled:
                writer.write("docs/traceability.md", _join(traceability_page(tracer.objects, tracer.unmatched)))
                nav.append(("Trazabilidad", "traceability.md"))
            previous = self._write_changes(writer, resolved, records, entries)
            if previous is not None:
                nav.append(("Cambios", "changes.md"))
            self._write_machine_files(
                writer,
                resolved,
                records,
                entries,
                nav,
                with_traceability=tracer.enabled,
                with_changes=previous is not None,
            )
            metadata: dict[str, Any] = {"engine": records.engine, "schema": records.schema, "database": self.database}
            if previous is not None:
                metadata["previous"] = previous
            writer.publish(metadata)
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

    @staticmethod
    def _llms_full(writer: StagedWriter, resolved: dict[str, Any]) -> AbstractContextManager[TextStream | None]:
        """``llms-full.txt`` en streaming, o nada si está desactivado."""
        if not resolved["llms_full_txt"]:
            return nullcontext(None)
        return writer.open_stream("docs/llms-full.txt")

    @staticmethod
    def _emit(
        writer: StagedWriter,
        ctx: PageContext,
        path: str,
        lines: list[str],
        record: dict[str, Any],
        full: TextStream | None,
    ) -> CatalogEntry:
        """Escribe la página ``docs/<path>`` y la añade a ``llms-full.txt`` (sin front matter, con su marcador)."""
        writer.write(f"docs/{path}", _join(lines))
        if full is not None:
            body = lines[_FRONT_MATTER_LINES:] if ctx.resolved["front_matter"] else lines
            full.write(f"\n{llms_full_marker(record, path)}\n\n{_join(body)}")
        return CatalogEntry(record, path)

    def _write_tables(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        rows: list[tuple[str, str, str | None]],
        records: ObjectRecords,
        full: TextStream | None,
        tracer: _Tracer,
    ) -> list[CatalogEntry]:
        options: dict[str, Any] = ctx.resolved["diagram_options"]
        # Anclas de columna (las mismas que pone la sección «Columnas»), para enlazar las trazas por columna
        with_anchors = bool(ctx.resolved["column_anchors"] and ctx.resolved["table_section_flags"][1])
        graph = (
            MermaidRelationshipGraph(
                ctx.data_provider,
                show_columns=options["show_columns"],
                column_mode=options["column_mode"],
                max_columns=options["max_columns"],
                show_constraint_name=options["show_constraint_name"],
            )
            if ctx.resolved["include_diagrams"] and rows
            else None
        )
        progress = TableProgress.of(ctx.data_provider, "markdown", len(rows))
        entries: list[CatalogEntry] = []
        index: list[IndexEntry] = []
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
            record = records.table(name, comment)
            column_names = [str(column["name"]) for column in record["columns"]]
            anchors = (
                {column: f"col-{anchor}" for column, anchor in unique_slugs(column_names).items()}
                if with_anchors
                else {}
            )
            record, trace_lines = tracer.apply(
                "tables", name, "Tablas", name, f"tables/{slug}.md", record, column_names, anchors
            )
            front = record if ctx.resolved["front_matter"] else None
            lines = table_page(ctx, name, comment, charset, front, diagram) + trace_lines
            entries.append(self._emit(writer, ctx, f"tables/{slug}.md", lines, record, full))
            index.append(IndexEntry(name, f"{slug}.md", comment))
            progress.done(name)
        self._write_index(writer, "tables", "Tablas", index, ctx)
        return entries

    def _write_views(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        rows: list[tuple[str, str]],
        records: ObjectRecords,
        full: TextStream | None,
        tracer: _Tracer,
    ) -> list[CatalogEntry]:
        slugs = unique_slugs(name for name, _ in rows)
        entries: list[CatalogEntry] = []
        index: list[IndexEntry] = []
        for name, comment in rows:
            path = f"views/{slugs[name]}.md"
            record, trace_lines = tracer.apply("views", name, "Vistas", name, path, records.view(name, comment))
            lines = view_page(ctx, name, comment, record if ctx.resolved["front_matter"] else None) + trace_lines
            entries.append(self._emit(writer, ctx, path, lines, record, full))
            index.append(IndexEntry(name, f"{slugs[name]}.md", comment))
        self._write_index(writer, "views", "Vistas", index, ctx)
        return entries

    def _write_routines(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        rows: list[tuple[str, str, str]],
        records: ObjectRecords,
        full: TextStream | None,
        tracer: _Tracer,
    ) -> list[CatalogEntry]:
        # Clave TIPO:nombre como en el HTML: un procedure y una función homónimos tienen ficheros distintos
        slugs = unique_slugs(f"{routine_type}:{name}" for name, routine_type, _ in rows)
        entries: list[CatalogEntry] = []
        index: list[IndexEntry] = []
        for name, routine_type, comment in rows:
            key = f"{routine_type}:{name}"
            path = f"routines/{slugs[key]}.md"
            display = f"{name} ({routine_type.title()})"
            record, trace_lines = tracer.apply(
                "routines", key, "Rutinas", display, path, records.routine(name, routine_type, comment)
            )
            front = record if ctx.resolved["front_matter"] else None
            lines = routine_page(ctx, name, routine_type, comment, front) + trace_lines
            entries.append(self._emit(writer, ctx, path, lines, record, full))
            index.append(IndexEntry(display, f"{slugs[key]}.md", comment))
        self._write_index(writer, "routines", "Rutinas", index, ctx)
        return entries

    @staticmethod
    def _write_index(
        writer: StagedWriter, folder: str, title: str, entries: list[IndexEntry], ctx: PageContext
    ) -> None:
        if not entries:
            return
        for file_name, lines in index_pages(title, entries, ctx.resolved["index_page_size"]).items():
            writer.write(f"docs/{folder}/{file_name}", _join(lines))

    # --- Ficheros para máquinas y publicación ---

    @staticmethod
    def _selection(resolved: dict[str, Any]) -> dict[str, bool]:
        """Tipos de objeto pedidos (``selection`` de ``catalog.json``)."""
        return {
            "tables": bool(resolved["include_tables"]),
            "views": bool(resolved["include_views"]),
            "procedures": bool(resolved["include_procedures"]),
            "functions": bool(resolved["include_functions"]),
        }

    def _write_changes(
        self, writer: StagedWriter, resolved: dict[str, Any], records: ObjectRecords, entries: list[CatalogEntry]
    ) -> dict[str, Any] | None:
        """``changes.md`` y ``changes.json`` respecto de ``markdown.previous``; devuelve sus datos para el manifiesto."""
        if resolved["previous"] is None:
            return None
        previous = load_previous(resolved["previous"])
        changes = build_changes(
            previous,
            entries,
            engine=records.engine,
            schema=records.schema,
            database=self.database,
            selection=self._selection(resolved),
        )
        links = {(str(e.record["kind"]), str(e.record["name"])): e.path for e in entries}
        writer.write("docs/changes.md", _join(changes_page(changes, links)))
        writer.write("docs/changes.json", changes_json(changes))
        return previous.manifest_entry()

    def _write_machine_files(
        self,
        writer: StagedWriter,
        resolved: dict[str, Any],
        records: ObjectRecords,
        entries: list[CatalogEntry],
        nav: list[tuple[str, str]],
        *,
        with_traceability: bool,
        with_changes: bool,
    ) -> None:
        """``catalog.json``, ``llms.txt``, ``mkdocs.yml`` (con ``nav``) y el Mermaid local, según ``imprimir["markdown"]``."""
        if resolved["catalog_json"]:
            text = catalog_json(
                entries,
                engine=records.engine,
                schema=records.schema,
                database=self.database,
                selection=self._selection(resolved),
            )
            writer.write("docs/catalog.json", text)
        if resolved["llms_txt"]:
            text = llms_txt(
                entries,
                database=self.database,
                engine=records.engine,
                schema=records.schema,
                with_catalog=resolved["catalog_json"],
                with_full=resolved["llms_full_txt"],
                with_traceability=with_traceability,
                with_changes=with_changes,
            )
            writer.write("docs/llms.txt", text)
        mermaid_js: Path | None = resolved["mermaid_js"]
        if mermaid_js is not None:
            writer.copy(f"docs/{MERMAID_JS_PATH}", Path(mermaid_js).expanduser())
        if resolved["mkdocs_yml"]:
            site_name = resolved["site_name"] or f"Documentación de {self.database}"
            text = mkdocs_yml(site_name, version=library_version(), with_mermaid_js=mermaid_js is not None, nav=nav)
            writer.write("mkdocs.yml", text)

    # --- Portada y base de datos ---

    def _write_home(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        *,
        tables: list[tuple[str, str, str | None]],
        views: list[tuple[str, str]],
        routines: list[tuple[str, str, str]],
    ) -> tuple[list[str], list[tuple[str, str]]]:
        """Escribe ``index.md`` y las páginas de base de datos; devuelve las líneas de la portada y sus secciones."""
        resolved = ctx.resolved
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
            data_provider=ctx.data_provider,
            include_routines=True,
        )
        include_legend = bool(resolved["include_diagrams"] and tables)
        lines = home_page(self.database, inventory, sections, include_legend)
        writer.write("docs/index.md", _join(lines))
        return lines, sections

    def _database_page(self, path: str, ctx: PageContext) -> list[str]:
        provider = ctx.data_provider
        if path == "database/info.md":
            return database_info_page(provider, ctx.resolved["database_info_flags"], self.logger)
        if path == "database/storage.md":
            return storage_page(provider)
        return engine_conditions_page(provider)


class _Tracer:
    """Aplica el mapa de trazabilidad (si lo hay) a cada objeto y reúne lo necesario para ``traceability.md``."""

    def __init__(self, trace_map: TraceMap | None, *, tables: list[str], views: list[str], routines: list[str]) -> None:
        self.enabled: bool = trace_map is not None
        self.objects: list[TracedObject] = []
        self.unmatched: list[Unmatched] = []
        self._matched: dict[str, dict[str, TraceEntry]] = {}
        if trace_map is not None:
            for section, names in (("tables", tables), ("views", views), ("routines", routines)):
                self._matched[section], unmatched = trace_map.match(section, names)
                self.unmatched += unmatched

    def apply(
        self,
        section: str,
        key: str,
        kind_title: str,
        display: str,
        path: str,
        record: dict[str, Any],
        column_names: list[str] | None = None,
        anchors: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], list[str]]:
        """Registro con ``trace`` (fuera de ``hash``) y sección «Trazabilidad» de la página; sin mapa, sin cambios."""
        if not self.enabled:
            return record, []
        entry = self._matched[section].get(key)
        columns: dict[str, TraceEntry] = {}
        if entry is not None and column_names is not None:
            columns, unmatched = match_columns(entry, key, column_names)
            self.unmatched += unmatched
        self.objects.append(TracedObject(kind_title, display, path, entry, columns))
        if entry is None:
            return record, []
        # ``hash`` ya está calculado sobre la estructura: la traza se añade después y no lo cambia
        return {**record, "trace": entry.to_dict(columns)}, trace_section(entry, columns, anchors or {})


def _join(lines: list[str]) -> str:
    """Líneas → texto con un único salto de línea final."""
    return "\n".join(lines).rstrip("\n") + "\n"


__all__: list[str] = ["MarkdownGenerator"]
