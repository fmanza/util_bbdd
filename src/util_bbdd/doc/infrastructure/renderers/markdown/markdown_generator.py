"""Generador de la documentación en Markdown: un fichero por tabla, vista y rutina, con diagramas ER de Mermaid.

Mismas secciones, opciones de ``imprimir`` y cabeceras que Word; alternativas propias del formato aprobadas en la sesión
``2026-11-05-doc-markdown`` (D1–D7): orden alfabético, DDL en bloques ``sql``, front matter y anclas para que una IA
pueda trazar los objetos, índices por letra para esquemas de cientos de tablas y salida determinista (versionable con
git). Los diagramas no necesitan Graphviz.

Salida en la carpeta del formato (``<directorio_salida>/<nombre>/MARKDOWN``)::

    manifest.json
    README.md                                   # markdown.readme (5.5.0): cómo verla y qué contiene
    zensical.toml                               # markdown.zensical_toml (5.6.0, por defecto)
    mkdocs.yml                                  # markdown.mkdocs_yml (en desuso desde 5.6.0, desactivado)
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

from ....._core.i18n import Translator
from .....analysis.mermaid_er import MermaidRelationshipGraph
from ....application.ports import DocumentationManagerPort
from ....domain.table_filter import TableFilter
from ..shared.generator_shared import GeneratorInventoryRuntime, GeneratorRoutineRuntime, GeneratorTableRuntime
from ..shared.print_config_manager import PrintConfigManager
from ..shared.table_progress import TableProgress
from ._catalog import CatalogEntry, catalog_json, llms_full_marker, llms_txt
from ._changes import build_changes, changes_json, changes_page, load_previous
from ._front_matter import RECORD_KINDS, ObjectRecords
from ._pages import PageContext, routine_page, table_page, view_page
from ._readme import ReadmeContents, readme_md
from ._site import MERMAID_JS_PATH, mkdocs_yml, zensical_toml
from ._site_pages import (
    FilterScope,
    IndexEntry,
    database_info_page,
    engine_conditions_page,
    home_page,
    index_page_titles,
    index_pages,
    storage_page,
)
from ._slugs import sort_key, unique_slugs
from ._text import plain_text
from ._trace import TracedObject, TraceEntry, TraceMap, Unmatched, match_columns, trace_section, traceability_page
from ._writer import PageEntry, StagedWriter, TextStream, library_version

_ROUTINE_TYPES: frozenset[str] = frozenset({"PROCEDURE", "FUNCTION"})
_FRONT_MATTER_LINES = 4  # "---", JSON, "---", ""


class MarkdownGenerator:
    """Genera la documentación Markdown de un schema (``DocumentRendererPort``).

    Los textos fijos de las páginas, ``README.md``, ``llms.txt`` y la ``nav`` del sitio salen en el idioma de
    ``translator`` (5.10.0). ``catalog.json``, ``changes.json``, el front matter y ``manifest.json`` (también los
    títulos de ``pages``) no dependen del idioma: la comparación con ``markdown.previous`` funciona entre idiomas.

    Args:
        database: Nombre de la base de datos que se muestra en la portada.
        headers: Cabeceras de cada sección (``headers_config.json``).
        translator: Idioma de la documentación; por defecto, español.

    Example:
        >>> result = DatabaseDocumentation(manager, Path("out"), formatos=["markdown"]).generate()
        >>> result.outputs["markdown"]  # …/MARKDOWN con docs/, manifest.json y zensical.toml
    """

    def __init__(self, database: str, headers: dict[str, list[str]], translator: Translator | None = None) -> None:
        self._tr: Translator = translator or Translator()
        self.database: str = database
        self.headers: dict[str, list[str]] = headers
        self.logger: logging.Logger = logging.getLogger(__name__)

    def _manifest_title(self, key: str, **params: Any) -> str:
        """Título de una página en ``manifest.json`` → ``pages``: su H1 (``doc_md.title.<key>``), en el idioma de salida."""
        return self._tr.t(f"doc_md.title.{key}", **params)

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
        table_filter: TableFilter | None = resolved["filter"]
        # La sesión calcula la frontera al leer el catálogo (5.5.0); otro data_provider puede no tenerla
        frontier: list[str] = list(getattr(data_provider, "frontera", None) or []) if table_filter is not None else []
        ctx = PageContext(
            data_provider,
            self.headers,
            resolved,
            unique_slugs(row[0] for row in table_rows),
            referencing=records.referencing_tables,
            filtered=table_filter is not None,
            frontier=frozenset(name.casefold() for name in frontier),
            tr=self._tr,
        )
        tracer = _Tracer(
            TraceMap.load(resolved["trace_map"]) if resolved["trace_map"] is not None else None,
            tables=[row[0] for row in table_rows],
            views=[row[0] for row in view_rows],
            routines=[f"{routine_type}:{name}" for name, routine_type, _ in routine_rows],
            translator=self._tr,
        )
        writer = StagedWriter(output_target, self.logger)
        # manifest.json → pages (5.4.0): cada página .md se anota donde se escribe, con su título sin escapar
        pages: list[PageEntry] = []
        try:
            entries: list[CatalogEntry] = []
            with self._llms_full(writer, resolved) as full:
                home, sections = self._write_home(
                    writer, ctx, pages, tables=table_rows, views=view_rows, routines=routine_rows, frontier=frontier
                )
                if full is not None:
                    full.write(_join(home))
                entries += self._write_tables(writer, ctx, table_rows, records, full, tracer, pages)
                entries += self._write_views(writer, ctx, view_rows, records, full, tracer, pages)
                entries += self._write_routines(writer, ctx, routine_rows, records, full, tracer, pages)
            nav = [(self._t("nav.home"), "index.md"), *sections]
            if tracer.enabled:
                trace_page = traceability_page(tracer.objects, tracer.unmatched, self._tr)
                writer.write("docs/traceability.md", _join(trace_page))
                pages.append(PageEntry("traceability.md", self._manifest_title("traceability"), "traceability", "page"))
                nav.append((self._t("nav.traceability"), "traceability.md"))
            previous = self._write_changes(writer, resolved, records, entries)
            if previous is not None:
                pages.append(PageEntry("changes.md", self._manifest_title("changes"), "changes", "page"))
                nav.append((self._t("nav.changes"), "changes.md"))
            self._write_machine_files(
                writer,
                resolved,
                records,
                entries,
                nav,
                with_traceability=tracer.enabled,
                with_changes=previous is not None,
                frontier=frontier,
            )
            if resolved["readme"]:
                readme = readme_md(self._readme_contents(resolved, tracer.enabled, previous), self._tr)
                writer.write("README.md", readme)
            metadata: dict[str, Any] = {"engine": records.engine, "schema": records.schema, "database": self.database}
            if previous is not None:
                metadata["previous"] = previous
            if table_filter is not None:
                metadata["filter"] = {**table_filter.to_catalog(), "frontier": frontier}
            writer.publish(metadata, keep=self._kept_paths(resolved), pages=pages)
        finally:
            writer.discard()
        self.logger.info(f"✅ Documentación Markdown generada en {output_target}")

    def _t(self, key: str, **params: Any) -> str:
        """Texto ``doc_md.<key>`` en el idioma de la generación."""
        return self._tr.t(f"doc_md.{key}", **params)

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
        page: tuple[str, str, list[PageEntry]],
    ) -> CatalogEntry:
        """Escribe la página ``docs/<path>`` y la añade a ``llms-full.txt`` (sin front matter, con su marcador).

        ``page`` es ``(título sin escapar, sección, páginas)``: la entrada del objeto en ``manifest.json`` → ``pages``.
        """
        writer.write(f"docs/{path}", _join(lines))
        title, section, pages = page
        pages.append(
            PageEntry(path, plain_text(title), section, "object", object_id=str(record["id"]), kind=str(record["kind"]))
        )
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
        pages: list[PageEntry],
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
                translator=self._tr,
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
                "tables", name, self._t("nav.tables"), name, f"tables/{slug}.md", record, column_names, anchors
            )
            front = record if ctx.resolved["front_matter"] else None
            lines = table_page(ctx, name, comment, charset, front, diagram) + trace_lines
            page = (self._manifest_title("table", name=name), "tables", pages)
            entries.append(self._emit(writer, ctx, f"tables/{slug}.md", lines, record, full, page))
            index.append(IndexEntry(name, f"{slug}.md", comment))
            progress.done(name)
        self._write_index(writer, "tables", index, ctx, pages)
        return entries

    def _write_views(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        rows: list[tuple[str, str]],
        records: ObjectRecords,
        full: TextStream | None,
        tracer: _Tracer,
        pages: list[PageEntry],
    ) -> list[CatalogEntry]:
        slugs = unique_slugs(name for name, _ in rows)
        entries: list[CatalogEntry] = []
        index: list[IndexEntry] = []
        for name, comment in rows:
            path = f"views/{slugs[name]}.md"
            view_record = records.view(name, comment)
            record, trace_lines = tracer.apply("views", name, self._t("nav.views"), name, path, view_record)
            lines = view_page(ctx, name, comment, record if ctx.resolved["front_matter"] else None) + trace_lines
            entries.append(
                self._emit(
                    writer, ctx, path, lines, record, full, (self._manifest_title("view", name=name), "views", pages)
                )
            )
            index.append(IndexEntry(name, f"{slugs[name]}.md", comment))
        self._write_index(writer, "views", index, ctx, pages)
        return entries

    def _write_routines(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        rows: list[tuple[str, str, str]],
        records: ObjectRecords,
        full: TextStream | None,
        tracer: _Tracer,
        pages: list[PageEntry],
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
                "routines", key, self._t("nav.routines"), display, path, records.routine(name, routine_type, comment)
            )
            front = record if ctx.resolved["front_matter"] else None
            lines = routine_page(ctx, name, routine_type, comment, front) + trace_lines
            page = (f"{routine_type.title()}: {name}", "routines", pages)
            entries.append(self._emit(writer, ctx, path, lines, record, full, page))
            index.append(IndexEntry(display, f"{slugs[key]}.md", comment))
        self._write_index(writer, "routines", index, ctx, pages)
        return entries

    @staticmethod
    def _write_index(
        writer: StagedWriter,
        folder: str,
        entries: list[IndexEntry],
        ctx: PageContext,
        pages: list[PageEntry],
    ) -> None:
        """Índice de ``folder`` (``tables``, ``views`` o ``routines``); el título de cada página en ``manifest.json`` es su
        H1, en el idioma de la generación (contrato de 5.4.0)."""
        if not entries:
            return
        page_size: int = ctx.resolved["index_page_size"]
        for file_name, lines in index_pages(ctx.t(f"nav.{folder}"), entries, page_size, ctx.tr).items():
            writer.write(f"docs/{folder}/{file_name}", _join(lines))
        manifest_titles = index_page_titles(ctx.t(f"nav.{folder}"), entries, page_size, ctx.tr)
        for file_name, (page_title, letter) in manifest_titles.items():
            role = "index" if letter is None else "letter"
            pages.append(PageEntry(f"{folder}/{file_name}", plain_text(page_title), folder, role, letter=letter))

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
            table_filter=resolved["filter"],
            translator=self._tr,
        )
        links = {(str(e.record["kind"]), str(e.record["name"])): e.path for e in entries}
        writer.write("docs/changes.md", _join(changes_page(changes, links, self._tr)))
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
        frontier: list[str],
    ) -> None:
        """``catalog.json``, ``llms.txt``, ``zensical.toml``/``mkdocs.yml`` (con ``nav``) y el Mermaid local, según
        ``imprimir["markdown"]``."""
        if resolved["catalog_json"]:
            text = catalog_json(
                entries,
                engine=records.engine,
                schema=records.schema,
                database=self.database,
                selection=self._selection(resolved),
                table_filter=resolved["filter"],
                frontier=frontier,
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
                translator=self._tr,
            )
            writer.write("docs/llms.txt", text)
        mermaid_js: Path | None = resolved["mermaid_js"]
        if mermaid_js is not None:
            writer.copy(f"docs/{MERMAID_JS_PATH}", Path(mermaid_js).expanduser())
        mermaid_ref: str | None = resolved["mermaid_js_ref"]
        site_name = resolved["site_name"] or self._t("site.default_name", database=self.database)
        site_args: dict[str, Any] = {
            "version": library_version(),
            "with_mermaid_js": mermaid_js is not None,
            "nav": nav,
            "mermaid_ref": mermaid_ref,
            "translator": self._tr,
        }
        if resolved["zensical_toml"]:
            writer.write("zensical.toml", zensical_toml(site_name, **site_args))
        if resolved["mkdocs_yml"]:
            self.logger.warning(
                "⚠️ markdown.mkdocs_yml está en desuso desde 5.6.0: zensical.toml (markdown.zensical_toml) es el "
                "formato estándar del sitio y mkdocs.yml se retirará en 6.0.0"
            )
            writer.write("mkdocs.yml", mkdocs_yml(site_name, **site_args))
        if mermaid_ref is not None and not (resolved["zensical_toml"] or resolved["mkdocs_yml"]):
            self.logger.warning(
                "⚠️ markdown.mermaid_js_ref no tiene efecto sin configuración del sitio "
                "(markdown.zensical_toml=False y markdown.mkdocs_yml=False)"
            )

    @staticmethod
    def _readme_contents(
        resolved: dict[str, Any], with_traceability: bool, previous: dict[str, Any] | None
    ) -> ReadmeContents:
        """Qué ficheros se han generado, para que el ``README.md`` describa solo esos."""
        return ReadmeContents(
            version=library_version(),
            zensical_toml=bool(resolved["zensical_toml"]),
            mkdocs_yml=bool(resolved["mkdocs_yml"]),
            catalog_json=bool(resolved["catalog_json"]),
            llms_txt=bool(resolved["llms_txt"]),
            llms_full_txt=bool(resolved["llms_full_txt"]),
            traceability=with_traceability,
            changes=previous is not None,
            local_mermaid=resolved["mermaid_js"] is not None,
            mermaid_ref=resolved["mermaid_js_ref"],
            filtered=resolved["filter"] is not None,
        )

    @staticmethod
    def _kept_paths(resolved: dict[str, Any]) -> frozenset[str]:
        """Rutas que no se borran como huérfanas: el Mermaid referenciado (``mermaid_js_ref`` relativo), que una
        generación anterior con ``mermaid_js`` pudo copiar en esa misma ruta."""
        ref: str | None = resolved["mermaid_js_ref"]
        return frozenset() if ref is None or "://" in ref else frozenset({f"docs/{ref}"})

    # --- Portada y base de datos ---

    def _write_home(
        self,
        writer: StagedWriter,
        ctx: PageContext,
        pages: list[PageEntry],
        *,
        tables: list[tuple[str, str, str | None]],
        views: list[tuple[str, str]],
        routines: list[tuple[str, str, str]],
        frontier: list[str],
    ) -> tuple[list[str], list[tuple[str, str]]]:
        """Escribe ``index.md`` y las páginas de base de datos; devuelve las líneas de la portada y sus secciones."""
        resolved = ctx.resolved
        sections: list[tuple[str, str]] = [
            (self._t(f"nav.{folder}"), f"{folder}/index.md")
            for folder, items in (("tables", tables), ("views", views), ("routines", routines))
            if items
        ]
        # Título visible en el idioma de la generación; el de manifest.json → pages, en español
        extra_pages = (
            ("include_database_info", "database_info", "database/info.md"),
            ("include_storage", "storage", "database/storage.md"),
            ("include_engine_conditions", "engine_conditions", "database/engine-conditions.md"),
        )
        for flag, title_key, path in extra_pages:
            if resolved[flag]:
                sections.append((self._t(f"title.{title_key}"), path))
                writer.write(f"docs/{path}", _join(self._database_page(path, ctx)))
                pages.append(PageEntry(path, self._manifest_title(title_key), "database", "page"))
        inventory = GeneratorInventoryRuntime.build_summary_rows_from_entities(
            tables=list(tables),
            views=list(views),
            routines=list(routines),
            include_storage=resolved["include_storage"],
            data_provider=ctx.data_provider,
            include_routines=True,
            translator=self._tr,
        )
        include_legend = bool(resolved["include_diagrams"] and tables)
        scope = (
            FilterScope(resolved["filter"].include, resolved["filter"].exclude, tuple(frontier))
            if resolved["filter"] is not None
            else None
        )
        lines = home_page(self.database, inventory, sections, include_legend, scope, self._tr)
        writer.write("docs/index.md", _join(lines))
        home_title = plain_text(self._manifest_title("home", database=self.database))
        pages.append(PageEntry("index.md", home_title, "home", "home"))
        return lines, sections

    def _database_page(self, path: str, ctx: PageContext) -> list[str]:
        provider = ctx.data_provider
        if path == "database/info.md":
            return database_info_page(provider, ctx.resolved["database_info_flags"], self.logger, self._tr)
        if path == "database/storage.md":
            return storage_page(provider, self._tr)
        return engine_conditions_page(provider, self._tr)


class _Tracer:
    """Aplica el mapa de trazabilidad (si lo hay) a cada objeto y reúne lo necesario para ``traceability.md``."""

    def __init__(
        self,
        trace_map: TraceMap | None,
        *,
        tables: list[str],
        views: list[str],
        routines: list[str],
        translator: Translator | None = None,
    ) -> None:
        self._tr: Translator = translator or Translator()
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
        return {**record, "trace": entry.to_dict(columns)}, trace_section(entry, columns, anchors or {}, self._tr)


def _join(lines: list[str]) -> str:
    """Líneas → texto con un único salto de línea final."""
    return "\n".join(lines).rstrip("\n") + "\n"


__all__: list[str] = ["MarkdownGenerator"]
