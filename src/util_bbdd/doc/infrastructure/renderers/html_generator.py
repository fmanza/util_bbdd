"""Módulo para generación de documentación en formato HTML."""

import html
import logging
import re
import shutil
import xml.etree.ElementTree as ET

from datetime import datetime
from pathlib import Path
from typing import Any, LiteralString

from jinja2 import Template

from ...._core.exceptions import DatabaseException
from ...._core.filenames import safe_file_stem
from ....analysis.graphviz_ext import GraphvizRelationshipGraphExt
from ...application.ports import DocumentationManagerPort, HeadersConfig
from .shared.diagram_legend import (
    build_diagram_direction_help,
    build_diagram_legend_payload,
    build_diagram_navigation_tips,
    build_hidden_levels_help,
)
from .shared.diagram_summary import build_diagram_summary_payload
from .shared.generator_shared import (
    GeneratorDatabaseInfoRuntime,
    GeneratorInventoryRuntime,
    GeneratorRoutineRuntime,
    GeneratorTableRuntime,
    GeneratorTabularRuntime,
    build_graph_generator_from_options,
)
from .shared.print_config_manager import PrintConfigManager
from .shared.template_engine import TemplateEngine


class HtmlGenerator:
    """Clase para generar documentación en formato HTML."""

    DEFAULT_STORAGE_TITLE: str = "Inventario de almacenamiento"

    def __init__(self, database: str, headers: HeadersConfig, template_file: Path | None = None):
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.database: str = database
        self.headers: HeadersConfig = dict(headers)  # copia: la sesión comparte el suyo entre formatos (A-12)
        self.headers.setdefault("UNIQUE", ["Nombre Restricción", "Campo"])
        self._doc_root: Path = Path(__file__).resolve().parents[2]
        self.templates_root: Path = self._doc_root / "templates"
        self.default_template_file: Path = self.templates_root / "pages" / "detail.html.j2"
        self.default_index_template_file: Path = self.templates_root / "pages" / "index.html.j2"
        self.default_collection_template_file: Path = self.templates_root / "pages" / "collection.html.j2"
        self.template_file: Path = template_file if template_file is not None else self.default_template_file

    def generate_document(
        self,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: DocumentationManagerPort,
        output_target: Path,
        print_config: dict[str, Any] | None = None,
        graph_generator: GraphvizRelationshipGraphExt | None = None,
    ) -> None:
        """Genera la documentación HTML completa.

        Args:
            tables: lista de tablas.
            views: lista de vistas.
            routines: lista de rutinas.
            output_target: Carpeta de salida del sitio HTML.
            print_config: Configuración unificada de secciones y gráficos.
        """
        self.logger.info(f"🟢 Iniciando generación de documentación HTML para base de datos: {self.database}")

        resolved: dict[str, Any] = self._resolve_print_config(print_config, data_provider, output_target)
        include_database_info: bool = resolved.get("include_database_info", False)

        self.logger.debug(
            f"⚙️  Configuración HTML resuelta: "
            f"tables={resolved.get('include_tables', False)}, views={resolved.get('include_views', False)}, "
            f"storage={resolved.get('include_storage', False)}, database_info={include_database_info}, "
            f"database_info_flags={resolved.get('database_info_flags', [False, False])}"
        )

        # Diagnóstico: verificar si la información de BD está deshabilitada
        if not include_database_info:
            self.logger.info(
                "ℹ️  La información de la base de datos NO se incluirá en la documentación. "
                "Si desea incluirla, configure [imprimir.info_database] en el archivo TOML con imprimir_info_database = true"
            )

        generated_at: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._prepare_output_directories(output_target, resolved)

        storage_report: dict[str, Any] = (
            self._get_storage_report(data_provider=data_provider)
            if resolved["include_storage"]
            else {"sections": [], "total_rows": 0}
        )

        detail_template, index_template, collection_template = self._setup_templates(resolved["template_path"])

        database_info_entries: list[dict[str, str]] = (
            self._process_database_info(
                data_provider=data_provider,
                database_info_flags=resolved.get("database_info_flags", [False, False]),
                output_dir=output_target,
                generated_at=generated_at,
                detail_template=detail_template,
            )
            if resolved.get("include_database_info", False)
            else []
        )

        table_slug_map, view_slug_map, selected_routines, routine_slug_map, svg_navigation_links = (
            self._build_slug_maps_and_filters(tables, views, routines, resolved)
        )

        resolved_graph_generator: GraphvizRelationshipGraphExt | None = (
            graph_generator if resolved["include_diagrams"] else None
        )
        if resolved["include_diagrams"] and resolved_graph_generator is None:
            self.logger.debug("🟢 Inicializando generador de grafos para diagramas HTML")
            resolved_graph_generator = self._build_graph_generator(data_provider, resolved["diagram_options"])
        elif resolved_graph_generator is not None:
            self.logger.debug("♻️ Reutilizando generador de grafos compartido para diagramas HTML")

        tables_index: list[dict[str, str]] = self._process_tables(
            tables,
            detail_template,
            table_slug_map,
            resolved,
            data_provider,
            output_target,
            svg_navigation_links,
            generated_at,
            resolved_graph_generator,
        )

        views_index: list[dict[str, str]] = self._process_views(
            views, detail_template, view_slug_map, resolved, data_provider, output_target, generated_at
        )

        routines_index: list[dict[str, str]] = self._process_routines(
            selected_routines,
            detail_template,
            routine_slug_map,
            data_provider,
            output_target,
            generated_at,
        )

        storage_entries: list[dict[str, str]] = self._process_storage(
            storage_report, detail_template, output_target, generated_at
        )

        collection_links: dict[str, str] = self._render_collection_pages(
            collection_template=collection_template,
            output_dir=output_target,
            generated_at=generated_at,
            tables_index=tables_index,
            views_index=views_index,
            routines_index=routines_index,
            storage_entries=storage_entries,
            storage_report=storage_report,
            data_provider=data_provider,
        )

        self._render_index_page(
            index_template,
            generated_at,
            tables_index,
            views_index,
            routines_index,
            storage_entries,
            storage_report,
            resolved,
            output_target,
            database_info_entries,
            collection_links,
        )

    def _resolve_print_config(
        self, print_config: dict[str, Any] | None, data_provider: DocumentationManagerPort, output_target: Path
    ) -> dict[str, Any]:
        """Resuelve la configuración de impresión normalizada."""
        normalized_config: dict[str, Any] = PrintConfigManager.normalize(print_config or data_provider.imprimir_config)
        return PrintConfigManager.resolve_for_html(
            config=normalized_config,
            output_dir=output_target,
            default_template_file=self.default_template_file,
        )

    def _prepare_output_directories(self, output_dir: Path, resolved: dict[str, Any]) -> None:
        """Prepara los directorios de salida necesarios."""
        output_dir.mkdir(parents=True, exist_ok=True)
        self._copy_offline_assets(output_dir)

        if resolved["include_tables"]:
            (output_dir / "tables").mkdir(parents=True, exist_ok=True)
        if resolved["include_views"]:
            (output_dir / "views").mkdir(parents=True, exist_ok=True)
        if resolved["include_procedures"] or resolved["include_functions"]:
            (output_dir / "routines").mkdir(parents=True, exist_ok=True)

    def _setup_templates(self, template_path: Path) -> tuple[Template, Template, Template]:
        """Configura el entorno de plantillas y devuelve las plantillas necesarias."""
        custom_detail_template: bool = template_path != self.default_template_file
        extra_search_paths: list[Path] = [template_path.parent] if custom_detail_template else []
        template_engine = TemplateEngine(templates_root=self.templates_root, extra_search_paths=extra_search_paths)

        detail_template_name: str = template_path.name if custom_detail_template else "pages/detail.html.j2"
        detail_template: Template = template_engine.get_template(detail_template_name)
        index_template: Template = template_engine.get_template("pages/index.html.j2")
        collection_template: Template = template_engine.get_template("pages/collection.html.j2")
        return detail_template, index_template, collection_template

    def _build_slug_maps_and_filters(
        self,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        resolved: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, str], list[tuple], dict[str, str], dict[str, str]]:
        """Construye mapas de slugs y filtra rutinas."""
        table_slug_map: dict[str, str] = (
            self._build_slug_map([row[0] for row in tables]) if resolved["include_tables"] else {}
        )
        view_slug_map: dict[str, str] = (
            self._build_slug_map([row[0] for row in views]) if resolved["include_views"] else {}
        )
        selected_routines: list[tuple] = GeneratorRoutineRuntime.filter_by_flags(
            routines,
            include_procedures=resolved["include_procedures"],
            include_functions=resolved["include_functions"],
            include_non_procedure_as_function=True,
        )
        routine_slug_map: dict[str, str] = self._build_slug_map(
            [self._build_routine_key(routine) for routine in selected_routines]
        )
        svg_navigation_links: dict[str, str] = {
            table_name: f"../tables/{slug}.html" for table_name, slug in table_slug_map.items()
        }
        return (
            table_slug_map,
            view_slug_map,
            selected_routines,
            routine_slug_map,
            svg_navigation_links,
        )

    def _process_tables(
        self,
        tables: list[tuple],
        detail_template: Template,
        table_slug_map: dict[str, str],
        resolved: dict[str, Any],
        data_provider: DocumentationManagerPort,
        output_dir: Path,
        svg_navigation_links: dict[str, str],
        generated_at: str,
        graph_generator: GraphvizRelationshipGraphExt | None = None,
    ) -> list[dict[str, str]]:
        """Procesa todas las tablas y genera sus páginas HTML."""
        tables_index: list[dict[str, str]] = []
        if not resolved["include_tables"]:
            return tables_index

        if resolved["include_diagrams"] and graph_generator is not None:
            level_kwargs: dict[str, Any] = self._level_graph_kwargs(resolved["diagram_options"])
            graph_generator.prefetch(
                lambda table_name: graph_generator.pipe_level_graphs_ext(table_name=table_name, **level_kwargs),
                [row[0] for row in tables],
            )

        for row in tables:
            tabla, comentario, charset_collation = GeneratorTableRuntime.extract_table_row_data(row)
            table_slug: str = table_slug_map[tabla]

            table_payload: dict[str, Any] = self._build_table_payload(
                table_name=tabla,
                file_stem=table_slug,
                comentario=comentario,
                charset_collation=charset_collation,
                data_provider=data_provider,
                section_flags=resolved["table_section_flags"],
                include_diagrams=resolved["include_diagrams"],
                graph_generator=graph_generator,
                diagram_options=resolved["diagram_options"],
                output_dir=output_dir,
                svg_navigation_links=svg_navigation_links,
                include_columns_charset=resolved.get("include_columns_charset", False),
            )
            table_rel_path: Path = Path("tables") / f"{table_slug}.html"
            table_output_file: Path = output_dir / table_rel_path

            self._render_detail_page(
                template=detail_template,
                output_file=table_output_file,
                entity_kind="tabla",
                entity=table_payload,
                generated_at=generated_at,
                storage_report=None,
            )

            tables_index.append(
                {
                    "name": tabla,
                    "comment": comentario or "",
                    "path": str(table_rel_path).replace("\\", "/"),
                }
            )
        return tables_index

    def _process_views(
        self,
        views: list[tuple],
        detail_template: Template,
        view_slug_map: dict[str, str],
        resolved: dict[str, Any],
        data_provider: DocumentationManagerPort,
        output_dir: Path,
        generated_at: str,
    ) -> list[dict[str, str]]:
        """Procesa todas las vistas y genera sus páginas HTML."""
        views_index: list[dict[str, str]] = []
        if not resolved["include_views"]:
            return views_index

        for vista, comentario in views:
            view_payload: dict[str, Any] = self._build_view_payload(
                view_name=vista,
                comentario=comentario,
                data_provider=data_provider,
                section_flags=resolved["view_section_flags"],
                include_diagrams=resolved.get("include_diagrams", False),
                diagram_options=resolved.get("diagram_options", {}),
                include_columns_charset=resolved.get("include_columns_charset", False),
            )
            view_slug: str = view_slug_map[vista]
            view_rel_path: Path = Path("views") / f"{view_slug}.html"
            view_output_file: Path = output_dir / view_rel_path

            self._render_detail_page(
                template=detail_template,
                output_file=view_output_file,
                entity_kind="vista",
                entity=view_payload,
                generated_at=generated_at,
                storage_report=None,
            )

            views_index.append(
                {
                    "name": vista,
                    "comment": comentario or "",
                    "path": str(view_rel_path).replace("\\", "/"),
                }
            )
        return views_index

    def _process_routines(
        self,
        routines: list[tuple],
        detail_template: Template,
        routine_slug_map: dict[str, str],
        data_provider: DocumentationManagerPort,
        output_dir: Path,
        generated_at: str,
    ) -> list[dict[str, str]]:
        """Procesa todas las rutinas y genera sus páginas HTML."""
        routines_index: list[dict[str, str]] = []

        for routine in routines:
            routine_name, routine_type, routine_comment = GeneratorRoutineRuntime.normalize_entry(routine)
            routine_key: str = self._build_routine_key(routine)
            routine_payload: dict[str, Any] = self._build_routine_payload(
                routine_name=routine_name,
                routine_type=routine_type,
                comentario=routine_comment,
                data_provider=data_provider,
            )
            routine_slug: str = routine_slug_map[routine_key]
            routine_rel_path: Path = Path("routines") / f"{routine_slug}.html"
            routine_output_file: Path = output_dir / routine_rel_path

            self._render_detail_page(
                template=detail_template,
                output_file=routine_output_file,
                entity_kind="rutina",
                entity=routine_payload,
                generated_at=generated_at,
                storage_report=None,
            )

            routines_index.append(
                {
                    "name": routine_name,
                    "comment": routine_comment or "",
                    "path": str(routine_rel_path).replace("\\", "/"),
                    "routine_type": routine_type,
                }
            )
        return routines_index

    def _process_storage(
        self,
        storage_report: dict[str, Any],
        detail_template: Template,
        output_dir: Path,
        generated_at: str,
    ) -> list[dict[str, str]]:
        """Procesa secciones de almacenamiento y genera sus páginas HTML."""
        storage_entries: list[dict[str, str]] = []
        if not storage_report.get("sections"):
            return storage_entries

        storage_dir: Path = output_dir / "storage"
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_used_slugs: set[str] = set()

        for section in storage_report.get("sections", []):
            section_slug: str = self._build_unique_slug(str(section.get("query", "storage")), storage_used_slugs)
            storage_rel_path: Path = Path("storage") / f"{section_slug}.html"
            storage_output_file: Path = output_dir / storage_rel_path
            storage_payload: dict[str, Any] = {
                "name": str(section.get("title", self.DEFAULT_STORAGE_TITLE)),
                "ddl": str(section.get("sql", "") or ""),
            }
            single_section_report: dict[str, Any] = {
                "total_rows": len(section.get("rows", [])),
                "sections": [section],
            }
            self._render_detail_page(
                template=detail_template,
                output_file=storage_output_file,
                entity_kind="almacenamiento",
                entity=storage_payload,
                generated_at=generated_at,
                storage_report=single_section_report,
            )
            storage_entries.append(
                {
                    "name": str(section.get("title", self.DEFAULT_STORAGE_TITLE)),
                    "comment": str(section.get("message", "")),
                    "path": str(storage_rel_path).replace("\\", "/"),
                    "total_rows": str(len(section.get("rows", []))),
                }
            )
        return storage_entries

    def _process_database_info(
        self,
        data_provider: DocumentationManagerPort,
        database_info_flags: list[bool],
        output_dir: Path,
        generated_at: str,
        detail_template: Template | None,
    ) -> list[dict[str, str]]:
        """Procesa información de la base de datos (versión, charset, collation) y genera página HTML."""
        database_info_entries: list[dict[str, str]] = []

        self.logger.debug(
            f"🔍 _process_database_info() llamado con flags={database_info_flags}, template={'sí' if detail_template else 'no'}"
        )

        if not any(database_info_flags):
            self.logger.debug("⏭️  Sin flags activados, retornando vacío")
            return database_info_entries

        if detail_template is None:
            self.logger.debug("⏭️  Sin template de detalle, retornando vacío")
            return database_info_entries

        try:
            self.logger.info(f"📚 Procesando información de BD con flags: {database_info_flags}")
            info_dir: Path = output_dir / "info"
            info_dir.mkdir(parents=True, exist_ok=True)

            properties_list: list[list[str]] = GeneratorDatabaseInfoRuntime.collect_database_info_rows(
                data_provider=data_provider,
                database_info_flags=database_info_flags,
                logger=self.logger,
                include_error_rows=False,
            )
            self.logger.debug(f"📊 Propiedades recolectadas: {len(properties_list)} items")

            if properties_list:
                database_info_entries = self._render_database_info_page(
                    data_provider,
                    database_info_flags,
                    output_dir,
                    generated_at,
                    detail_template,
                    properties_list,
                )
            else:
                self.logger.warning("⚠️  No se recolectaron propiedades de BD")

        except DatabaseException as error:
            self.logger.error(f"❌ Error procesando información de BD: {error}", exc_info=True)

        return database_info_entries

    def _render_database_info_page(
        self,
        data_provider: DocumentationManagerPort,
        database_info_flags: list[bool],
        output_dir: Path,
        generated_at: str,
        detail_template: Template,
        properties_list: list[list[str]],
    ) -> list[dict[str, str]]:
        """Renderiza la página de información de BD."""
        info_rel_path: Path = Path("info") / "database-info.html"
        info_output_file: Path = output_dir / info_rel_path

        sql_queries: list[str] = GeneratorDatabaseInfoRuntime.collect_database_info_query_templates(
            data_provider=data_provider,
            database_info_flags=database_info_flags,
            logger=self.logger,
        )
        combined_sql: str = "\n\n".join(sql_queries) if sql_queries else ""
        self.logger.debug(f"📋 SQL combinado: {len(combined_sql)} caracteres")

        database_info_payload: dict[str, Any] = {
            "name": "Información de la Base de Datos",
            "ddl": combined_sql,
        }

        database_info_section: dict[str, Any] = {
            "title": "Propiedades de Base de Datos",
            "rows": properties_list,
            "sql": combined_sql,
        }

        database_info_report: dict[str, Any] = {
            "total_rows": len(properties_list),
            "sections": [database_info_section],
        }

        self.logger.debug(f"📄 Renderizando página de detalle: {info_output_file}")
        self._render_detail_page(
            template=detail_template,
            output_file=info_output_file,
            entity_kind="información",
            entity=database_info_payload,
            generated_at=generated_at,
            storage_report=database_info_report,
        )

        self.logger.info(f"✅ Información de BD generada: {info_output_file}")
        return [
            {
                "name": "Información de la Base de Datos",
                "comment": f"{len(properties_list)} propiedades",
                "path": str(info_rel_path).replace("\\", "/"),
            }
        ]

    def _render_index_page(
        self,
        index_template: Template,
        generated_at: str,
        tables_index: list[dict[str, str]],
        views_index: list[dict[str, str]],
        routines_index: list[dict[str, str]],
        storage_entries: list[dict[str, str]],
        storage_report: dict[str, Any],
        resolved: dict[str, Any],
        output_dir: Path,
        database_info_entries: list[dict[str, str]] | None = None,
        collection_links: dict[str, str] | None = None,
    ) -> None:
        """Renderiza y escribe la página de índice."""
        if database_info_entries is None:
            database_info_entries = []
        if collection_links is None:
            collection_links = {}
        tables_index.sort(key=lambda item: str(item.get("name", "")).lower())
        views_index.sort(key=lambda item: str(item.get("name", "")).lower())
        routines_index.sort(
            key=lambda item: (
                str(item.get("routine_type", "")).lower(),
                str(item.get("name", "")).lower(),
            )
        )

        procedures_index: list[dict[str, str]] = [
            item for item in routines_index if str(item.get("routine_type", "")).upper() == "PROCEDURE"
        ]
        functions_index: list[dict[str, str]] = [
            item for item in routines_index if str(item.get("routine_type", "")).upper() == "FUNCTION"
        ]
        inventory_summary: list[dict[str, Any]] = self._build_inventory_summary(
            tables_index=tables_index,
            views_index=views_index,
            procedures_index=procedures_index,
            functions_index=functions_index,
            storage_report=storage_report,
        )

        default_content_path: str = self._get_default_content_path(
            tables_index,
            views_index,
            procedures_index,
            functions_index,
            routines_index,
            storage_entries,
        )

        rendered_index: str = index_template.render(
            database=self.database,
            generated_at=generated_at,
            tables=tables_index,
            views=views_index,
            procedures=procedures_index,
            functions=functions_index,
            storage=storage_entries,
            storage_total_rows=int(storage_report.get("total_rows", 0) or 0),
            database_info=database_info_entries,
            routines=routines_index,
            inventory_summary=inventory_summary,
            collection_links=collection_links,
            default_content_path=default_content_path,
            page_size=resolved["html_items_per_page"],
        )

        index_file: Path = Path(output_dir) / "index.html"
        index_file.write_text(rendered_index, encoding="utf-8")
        self.logger.info(f"✅ Índice HTML generado: {index_file}")

    def _build_inventory_summary(
        self,
        *,
        tables_index: list[dict[str, str]],
        views_index: list[dict[str, str]],
        procedures_index: list[dict[str, str]],
        functions_index: list[dict[str, str]],
        storage_report: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Construye el resumen visual de inventario para el índice HTML."""
        summary_rows: list[tuple[str, int]] = GeneratorInventoryRuntime.build_summary_rows(
            tables_count=len(tables_index),
            views_count=len(views_index),
            routines_count=0,
            procedures_count=len(procedures_index),
            functions_count=len(functions_index),
            storage_count=int(storage_report.get("total_rows", 0)),
            include_routines=False,
        )
        style_by_label: dict[str, dict[str, str]] = {
            "Tablas": {"accent": "tables", "collection_key": "tables"},
            "Vistas": {"accent": "views", "collection_key": "views"},
            "Procedures": {"accent": "procedures", "collection_key": "procedures"},
            "Funciones": {"accent": "functions", "collection_key": "functions"},
            "Almacenamiento": {"accent": "storage", "collection_key": "storage"},
        }
        return [
            {
                "label": label,
                "count": count,
                "accent": style_by_label[label]["accent"],
                "collection_key": style_by_label[label]["collection_key"],
            }
            for label, count in summary_rows
        ]

    def _summarize_storage_entries(self, storage_entries: list[dict[str, str]]) -> dict[str, int]:
        """Resume el inventario de almacenamiento a partir de las entradas renderizadas."""
        total_rows: int = 0
        for entry in storage_entries:
            try:
                total_rows += int(str(entry.get("total_rows", "0") or "0"))
            except ValueError:
                continue
        return {"total_rows": total_rows}

    def _render_collection_pages(
        self,
        *,
        collection_template: Template,
        output_dir: Path,
        generated_at: str,
        tables_index: list[dict[str, str]],
        views_index: list[dict[str, str]],
        routines_index: list[dict[str, str]],
        storage_entries: list[dict[str, str]],
        storage_report: dict[str, Any],
        data_provider: DocumentationManagerPort,
    ) -> dict[str, str]:
        """Genera páginas HTML globales por categoría con búsqueda, orden y exportación."""
        collections_dir: Path = output_dir / "collections"
        collections_dir.mkdir(parents=True, exist_ok=True)

        procedures_index: list[dict[str, str]] = [
            item for item in routines_index if str(item.get("routine_type", "")).upper() == "PROCEDURE"
        ]
        functions_index: list[dict[str, str]] = [
            item for item in routines_index if str(item.get("routine_type", "")).upper() == "FUNCTION"
        ]

        tables_headers, tables_rows = self._build_table_collection_dataset(
            tables_index=tables_index,
            data_provider=data_provider,
        )
        views_headers, views_rows = self._build_view_collection_dataset(
            views_index=views_index,
            data_provider=data_provider,
        )
        procedures_headers, procedures_rows = self._build_routine_collection_dataset(
            routines_index=procedures_index,
            data_provider=data_provider,
        )
        functions_headers, functions_rows = self._build_routine_collection_dataset(
            routines_index=functions_index,
            data_provider=data_provider,
        )

        storage_headers, storage_rows = self._build_storage_collection_dataset(
            storage_entries=storage_entries,
            storage_report=storage_report,
        )

        pages: list[tuple[str, str, list[str], list[list[str]], str]] = [
            (
                "tables",
                "Todas las tablas y columnas",
                tables_headers,
                tables_rows,
                "tables_all.html",
            ),
            (
                "views",
                "Todas las vistas y columnas",
                views_headers,
                views_rows,
                "views_all.html",
            ),
            (
                "procedures",
                "Todos los procedures",
                procedures_headers,
                procedures_rows,
                "procedures_all.html",
            ),
            (
                "functions",
                "Todas las funciones",
                functions_headers,
                functions_rows,
                "functions_all.html",
            ),
            (
                "storage",
                "Todo el almacenamiento",
                storage_headers,
                storage_rows,
                "storage_all.html",
            ),
        ]

        collection_links: dict[str, str] = {}
        for key, title, headers, rows, filename in pages:
            rel_path: Path = Path("collections") / filename
            output_file: Path = output_dir / rel_path
            rendered: str = collection_template.render(
                database=self.database,
                generated_at=generated_at,
                collection_key=key,
                title=title,
                headers=headers,
                rows=rows,
            )
            output_file.write_text(rendered, encoding="utf-8")
            collection_links[key] = str(rel_path).replace("\\", "/")
        return collection_links

    def _build_storage_collection_dataset(
        self, storage_entries: list[dict[str, str]], storage_report: dict[str, Any]
    ) -> tuple[list[str], list[list[str]]]:
        """Construye el dataset detallado de almacenamiento para la página global HTML."""
        sections: list[dict[str, Any]] = list(storage_report.get("sections", []))
        data_headers: list[str] = self._collect_storage_data_headers(sections)
        headers: list[str] = ["Sección", "Estado"] + data_headers + ["Mensaje", "Detalle"]
        rows: list[list[str]] = self._build_storage_collection_rows(
            storage_entries=storage_entries,
            sections=sections,
            data_headers=data_headers,
        )
        return headers, rows

    def _collect_storage_data_headers(self, sections: list[dict[str, Any]]) -> list[str]:
        """Recolecta encabezados únicos de todas las secciones de almacenamiento."""
        data_headers: list[str] = []
        seen_headers: set[str] = set()

        for section in sections:
            for header in self._normalize_storage_section_headers(section):
                if header in seen_headers:
                    continue
                seen_headers.add(header)
                data_headers.append(header)

        return data_headers

    def _build_storage_collection_rows(
        self,
        *,
        storage_entries: list[dict[str, str]],
        sections: list[dict[str, Any]],
        data_headers: list[str],
    ) -> list[list[str]]:
        """Construye las filas detalladas para la colección HTML de almacenamiento."""
        rows: list[list[str]] = []

        for index, entry in enumerate(storage_entries):
            section: dict[str, Any] = self._get_storage_section_by_index(sections, index)
            section_name: str = str(entry.get("name", ""))
            status: str = str(section.get("status", ""))
            message: str = str(entry.get("comment", ""))
            detail_path: str = str(entry.get("path", ""))
            rows.extend(
                self._build_storage_collection_entry_rows(
                    section=section,
                    section_name=section_name,
                    status=status,
                    message=message,
                    detail_path=detail_path,
                    data_headers=data_headers,
                )
            )

        return rows

    def _get_storage_section_by_index(self, sections: list[dict[str, Any]], index: int) -> dict[str, Any]:
        """Devuelve la sección de almacenamiento correspondiente al índice o un dict vacío."""
        return sections[index] if index < len(sections) else {}

    def _build_storage_collection_entry_rows(
        self,
        *,
        section: dict[str, Any],
        section_name: str,
        status: str,
        message: str,
        detail_path: str,
        data_headers: list[str],
    ) -> list[list[str]]:
        """Construye las filas asociadas a una entrada de almacenamiento."""
        section_rows: list[list[Any]] = list(section.get("rows", []))
        if not section_rows:
            return [[section_name, status] + [""] * len(data_headers) + [message, detail_path]]

        section_headers: list[str] = self._normalize_storage_section_headers(section)
        return [
            [section_name, status]
            + self._build_storage_collection_data_cells(raw_row, section_headers, data_headers)
            + [message, detail_path]
            for raw_row in section_rows
        ]

    def _normalize_storage_section_headers(self, section: dict[str, Any]) -> list[str]:
        """Normaliza los encabezados declarados en una sección de almacenamiento."""
        return [str(value) for value in section.get("headers", [])]

    def _build_storage_collection_data_cells(
        self,
        raw_row: list[Any],
        section_headers: list[str],
        data_headers: list[str],
    ) -> list[str]:
        """Alinea una fila de almacenamiento con el conjunto global de encabezados."""
        row_map: dict[str, str] = {
            header: self._stringify_storage_row_value(raw_row[column_index] if len(raw_row) > column_index else "")
            for column_index, header in enumerate(section_headers)
        }
        return [row_map.get(header, "") for header in data_headers]

    def _stringify_storage_row_value(self, value: Any) -> str:
        """Convierte valores de filas de almacenamiento a string preservando vacíos."""
        return "" if value is None else str(value)

    def _build_table_collection_dataset(
        self,
        *,
        tables_index: list[dict[str, str]],
        data_provider: DocumentationManagerPort,
    ) -> tuple[list[str], list[list[str]]]:
        """Construye el dataset plano de tablas/columnas alineado con la hoja Columnas de Excel."""
        flat_headers: list[str] = [str(header) for header in self.headers.get("FLAT", [])]
        headers: list[str] = flat_headers + ["Detalle"] if flat_headers else ["Tabla", "Comentario", "Detalle"]
        rows: list[list[str]] = []

        for item in tables_index:
            table_name: str = str(item.get("name", ""))
            table_comment: str = str(item.get("comment", ""))
            detail_path: str = str(item.get("path", ""))
            try:
                rows.extend(
                    self._build_table_collection_rows_for_table(
                        table_name=table_name,
                        table_comment=table_comment,
                        detail_path=detail_path,
                        data_provider=data_provider,
                    )
                )
            except DatabaseException as error:
                self.logger.warning(f"⚠️ No se pudo construir dataset HTML global para tabla {table_name}: {error}")

        return headers, rows

    def _build_view_collection_dataset(
        self,
        *,
        views_index: list[dict[str, str]],
        data_provider: DocumentationManagerPort,
    ) -> tuple[list[str], list[list[str]]]:
        """Construye el dataset plano de vistas/columnas alineado con el detalle HTML de vistas."""
        base_headers: list[str] = [str(header) for header in self.headers.get("COLUMNAS", [])]
        headers: list[str] = ["Vista", "Comentario"] + base_headers + ["Detalle"]
        rows: list[list[str]] = []

        for item in views_index:
            view_name: str = str(item.get("name", ""))
            view_comment: str = str(item.get("comment", ""))
            detail_path: str = str(item.get("path", ""))
            try:
                columns = data_provider.get_columns(view_name)
                processed_columns = GeneratorTabularRuntime.process_columns_data(columns)
                for column in processed_columns:
                    rows.append([view_name, view_comment] + [str(value) for value in column] + [detail_path])
            except DatabaseException as error:
                self.logger.warning(f"⚠️ No se pudo construir dataset HTML global para vista {view_name}: {error}")

        return headers, rows

    def _build_routine_collection_dataset(
        self,
        *,
        routines_index: list[dict[str, str]],
        data_provider: DocumentationManagerPort,
    ) -> tuple[list[str], list[list[str]]]:
        """Construye el dataset plano de rutinas/parámetros para la página global HTML."""
        parameter_headers: list[str] = [
            str(header)
            for header in self.headers.get(
                "PARAMETROS_RUTINA",
                ["Modo", "Parámetro", "Tipo", "Valor por defecto", "Posición"],
            )
        ]
        headers: list[str] = ["Rutina", "Tipo rutina", "Comentario"] + parameter_headers + ["Detalle"]
        rows: list[list[str]] = []

        for item in routines_index:
            routine_name: str = str(item.get("name", ""))
            routine_type: str = str(item.get("routine_type", ""))
            routine_comment: str = str(item.get("comment", ""))
            detail_path: str = str(item.get("path", ""))
            try:
                parameters = data_provider.get_routine_parameters(routine_name, routine_type)
                normalized_parameters = GeneratorRoutineRuntime.parameter_rows(parameters)
            except DatabaseException as error:
                self.logger.warning(
                    f"⚠️ No se pudo construir dataset HTML global para rutina {routine_type}:{routine_name}: {error}"
                )
                normalized_parameters = []

            if not normalized_parameters:
                normalized_parameters = [["", "", "", "", ""]]

            for parameter_row in normalized_parameters:
                rows.append(
                    [routine_name, routine_type, routine_comment]
                    + [str(value) for value in parameter_row]
                    + [detail_path]
                )

        return headers, rows

    def _build_table_collection_rows_for_table(
        self,
        *,
        table_name: str,
        table_comment: str,
        detail_path: str,
        data_provider: DocumentationManagerPort,
    ) -> list[list[str]]:
        """Construye filas planas de una tabla para la página global HTML."""
        # D1: PK, FK e índices por columna en todos los motores (antes solo Oracle, PostgreSQL y HSQLDB; H-15)
        return GeneratorTabularRuntime.build_enriched_flat_rows_for_table(
            table_name=table_name,
            table_comment=table_comment,
            columns=list(data_provider.get_columns(table_name)),
            data_provider=data_provider,
            detail_path=detail_path,
            fk_arrow="->",
        )

    def _get_default_content_path(
        self,
        tables_index: list[dict[str, str]],
        views_index: list[dict[str, str]],
        procedures_index: list[dict[str, str]],
        functions_index: list[dict[str, str]],
        routines_index: list[dict[str, str]],
        storage_entries: list[dict[str, str]],
    ) -> str:
        """Determina la ruta de contenido por defecto para el índice."""
        candidates = [
            tables_index,
            views_index,
            procedures_index,
            functions_index,
            routines_index,
            storage_entries,
        ]
        for candidate_list in candidates:
            if candidate_list:
                return candidate_list[0]["path"]
        return ""

    def _build_unique_slug(self, raw_name: str, used_slugs: set[str]) -> str:
        """Construye un slug único para nombres de tablas/vistas."""
        normalized: str = "".join(char.lower() if char.isalnum() else "-" for char in raw_name)
        normalized = "-".join(part for part in normalized.split("-") if part)
        base_slug: str = normalized or "item"

        candidate: str = base_slug
        suffix = 2
        while candidate in used_slugs:
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        used_slugs.add(candidate)
        return candidate

    def _build_slug_map(self, names: list[str]) -> dict[str, str]:
        """Genera un mapa nombre->slug único preservando orden de entrada."""
        used_slugs: set[str] = set()
        slug_map: dict[str, str] = {}
        for name in names:
            slug_map[name] = self._build_unique_slug(name, used_slugs)
        return slug_map

    def _build_routine_key(self, routine: tuple) -> str:
        """Construye clave estable para slugs de rutina."""
        routine_name, routine_type, _ = GeneratorRoutineRuntime.normalize_entry(routine)
        return f"{routine_type}:{routine_name}"

    def _render_detail_page(
        self,
        template: Any,
        output_file: Path,
        entity_kind: str,
        entity: dict[str, Any],
        generated_at: str,
        storage_report: dict[str, Any] | None,
    ) -> None:
        """Renderiza una página de detalle (tabla o vista)."""
        rendered = template.render(
            database=self.database,
            generated_at=generated_at,
            entity_kind=entity_kind,
            entity=entity,
            headers=self.headers,
            storage=storage_report or {},
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(rendered, encoding="utf-8")

    def _get_storage_report(self, data_provider: DocumentationManagerPort) -> dict[str, Any]:
        """Obtiene reporte de almacenamiento para incluirlo en páginas HTML."""
        try:
            report: dict[str, Any] = data_provider.get_storage_inventory_report()
        except DatabaseException as error:
            report = {
                "sections": [
                    {
                        "title": self.DEFAULT_STORAGE_TITLE,
                        "status": "error",
                        "message": f"No se pudo obtener la información de almacenamiento: {error}",
                        "headers": [],
                        "rows": [],
                    }
                ],
                "total_rows": 0,
            }

        sections: list[dict[str, Any]] = list(report.get("sections", []))
        for section in sections:
            rows: list[list[Any]] = list(section.get("rows", []))
            headers: list[str] = [str(h) for h in section.get("headers", [])]
            numeric_columns: list[int] = [int(idx) for idx in section.get("numeric_columns", [])]
            if not headers and rows:
                max_cols: int = max(len(row) for row in rows)
                headers = [f"Columna {idx}" for idx in range(1, max_cols + 1)]
            section["headers"] = headers
            section["numeric_columns"] = numeric_columns
            section["rows"] = [[str(value) if value is not None else "" for value in row] for row in rows]
        report["sections"] = sections
        return report

    def _copy_offline_assets(self, output_dir: Path) -> None:
        """Copia assets estáticos (incluyendo subcarpetas) para funcionamiento offline del HTML."""
        source_assets_dir: Path = self._doc_root / "data" / "html_assets"
        target_assets_dir: Path = output_dir / "assets"

        if not source_assets_dir.exists() or not source_assets_dir.is_dir():
            self.logger.warning(f"⚠️ No se encontraron assets HTML offline en {source_assets_dir}")
            return

        target_assets_dir.mkdir(parents=True, exist_ok=True)
        for source_item in source_assets_dir.iterdir():
            target_item: Path = target_assets_dir / source_item.name
            if source_item.is_file():
                shutil.copy2(source_item, target_item)
            elif source_item.is_dir():
                # Copiar carpeta recursivamente (ej. icons/)
                if target_item.exists():
                    shutil.rmtree(target_item)
                shutil.copytree(source_item, target_item)

    def _build_graph_generator(self, data_provider: Any, options: dict[str, Any]) -> GraphvizRelationshipGraphExt:
        """Crea el generador de grafos cuando el orquestador no ha pasado uno."""
        return build_graph_generator_from_options(data_provider.db_manager, options)

    def _build_table_payload(
        self,
        table_name: str,
        comentario: str,
        data_provider: DocumentationManagerPort,
        section_flags: list[bool],
        include_diagrams: bool,
        graph_generator: GraphvizRelationshipGraphExt | None,
        diagram_options: dict[str, Any],
        output_dir: Path,
        svg_navigation_links: dict[str, str],
        charset_collation: str | None = None,
        include_columns_charset: bool = False,
        file_stem: str | None = None,
    ) -> dict[str, Any]:
        """Construye el payload HTML de una tabla (``file_stem``: nombre de fichero de sus SVG, por defecto el saneado)."""
        payload: dict[str, Any] = self._initialize_table_payload(
            table_name, comentario, charset_collation, section_flags, include_columns_charset
        )

        self._populate_table_payload_sections(
            payload, data_provider, table_name, section_flags, include_columns_charset
        )

        if include_diagrams and graph_generator is not None:
            diagram_tabs, diagram_paths, raw_diagram_summary = self._generate_svg_for_table(
                table_name=table_name,
                graph_generator=graph_generator,
                diagram_options=diagram_options,
                output_dir=output_dir,
                navigation_links=svg_navigation_links,
                file_stem=file_stem or safe_file_stem(table_name),
            )
            summary_enabled = bool(diagram_options.get("summary", {}).get("enabled", True))
            diagram_summary = raw_diagram_summary if summary_enabled else {}
            payload["diagram_tabs"] = diagram_tabs
            payload["diagram_paths"] = diagram_paths
            payload["diagram_summary"] = diagram_summary
            payload["diagram_legend"] = self._build_diagram_legend_payload()
            payload["diagram_viewer"] = self._build_diagram_viewer_payload(
                diagram_summary=raw_diagram_summary,
                diagram_tabs=diagram_tabs,
            )

        return payload

    def _initialize_table_payload(
        self,
        table_name: str,
        comentario: str,
        charset_collation: str | None,
        section_flags: list[bool],
        include_columns_charset: bool,
    ) -> dict[str, Any]:
        """Inicializa la estructura base del payload de tabla."""
        return {
            "name": table_name,
            "comment": comentario or "",
            "charset_collation": charset_collation or "",
            "ddl": None,
            "show_columnas": bool(section_flags[1]),
            "columnas": {"headers": self.headers.get("COLUMNAS", []), "rows": []},
            "show_columns_charset": include_columns_charset,
            "columns_charset": {"headers": ["Columna", "Charset", "Collation"], "rows": []},
            "show_pk": bool(section_flags[2]),
            "pk": None,
            "show_fk": bool(section_flags[3]),
            "fk": None,
            "show_unicas": bool(section_flags[4]),
            "unicas": None,
            "show_indices": bool(section_flags[5]),
            "indices": None,
            "diagram_tabs": [],
            "diagram_summary": {},
            "diagram_legend": {},
            "diagram_viewer": {},
            "diagram_paths": [],
        }

    def _build_diagram_viewer_payload(
        self,
        *,
        diagram_summary: dict[str, Any] | None = None,
        diagram_tabs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Expone la configuración del visor HTML para pan y zoom controlado desde la página."""
        summary: dict[str, Any] = diagram_summary or {}
        tabs: list[dict[str, Any]] = diagram_tabs or []
        has_hidden_levels: bool = bool(summary.get("has_any_hidden_levels"))
        has_both_directions: bool = len(tabs) > 1
        viewer_tips: list[str] = [
            "Usa las pestañas por nivel para aislar relaciones cuando el diagrama tenga mucha densidad.",
            "Empieza con Ajustar y luego aplica zoom solo sobre la zona que estés revisando.",
        ]
        if has_hidden_levels:
            viewer_tips.append(
                "Existen niveles no visibles por profundidad: revisa el resumen superior antes de asumir que el grafo está completo."
            )
        if has_both_directions:
            viewer_tips.append(
                "Alterna entre salida y entrada para separar dependencias hijas de tablas referenciadoras."
            )

        return {
            "title": "Controles del visor",
            "help": "Usa los botones, Ctrl + rueda para zoom y arrastra el diagrama para desplazarte.",
            "status_ready": "Listo para navegar",
            "status_dragging": "Moviendo diagrama",
            "status_zoom_prefix": "Zoom",
            "min_zoom": 0.5,
            "max_zoom": 3.0,
            "zoom_step": 0.25,
            "pan_step": 140,
            "initial_zoom": 1.0,
            "wheel_zoom_requires_ctrl": True,
            "drag_pan_enabled": True,
            "tips": viewer_tips,
        }

    def _populate_table_payload_sections(
        self,
        payload: dict[str, Any],
        data_provider: DocumentationManagerPort,
        table_name: str,
        section_flags: list[bool],
        include_columns_charset: bool,
    ) -> None:
        """Rellena las secciones del payload según los flags activados."""
        self._populate_ddl_section(payload, data_provider, table_name, section_flags)
        self._populate_columns_section(payload, data_provider, table_name, section_flags, include_columns_charset)
        self._populate_constraints_and_indices(payload, data_provider, table_name, section_flags)

    def _populate_ddl_section(
        self,
        payload: dict[str, Any],
        data_provider: DocumentationManagerPort,
        table_name: str,
        section_flags: list[bool],
    ) -> None:
        """Rellena la sección DDL del payload."""
        if section_flags[0]:
            try:
                ddl: str = data_provider.get_ddl(table_name)
                payload["ddl"] = self._decode_html_entities(ddl) if ddl is not None else ""
            except DatabaseException as error:
                payload["ddl"] = f"⚠️ Error obteniendo DDL: {error}"

    def _populate_columns_section(
        self,
        payload: dict[str, Any],
        data_provider: DocumentationManagerPort,
        table_name: str,
        section_flags: list[bool],
        include_columns_charset: bool,
    ) -> None:
        """Rellena la sección de columnas del payload."""
        if not section_flags[1]:
            return

        try:
            columnas = data_provider.get_columns(table_name)
            payload["columnas"]["rows"] = GeneratorTabularRuntime.process_columns_data(columnas)
            self._populate_columns_charset(payload, data_provider, table_name, include_columns_charset)
        except DatabaseException:
            payload["columnas"]["rows"] = []

    def _populate_columns_charset(
        self,
        payload: dict[str, Any],
        data_provider: DocumentationManagerPort,
        table_name: str,
        include_columns_charset: bool,
    ) -> None:
        """Rellena información de charset/collation de columnas."""
        if not include_columns_charset:
            return

        try:
            charset_info = data_provider.get_columns_charset_collation(table_name)
            payload["columns_charset"]["rows"] = [[row[0], row[1] or "", row[2] or ""] for row in charset_info]
        except DatabaseException as e:
            self.logger.debug(f"⚠️  No se pudo obtener charset/collation de columnas para {table_name}: {e}")
            payload["columns_charset"]["rows"] = []

    def _populate_constraints_and_indices(
        self,
        payload: dict[str, Any],
        data_provider: DocumentationManagerPort,
        table_name: str,
        section_flags: list[bool],
    ) -> None:
        """Rellena las secciones de restricciones e índices del payload."""
        if section_flags[2]:
            payload["pk"] = data_provider.get_primary_keys(table_name)

        if section_flags[3]:
            payload["fk"] = data_provider.get_foreign_keys(table_name)

        if section_flags[4]:
            unique_constraints = data_provider.get_unique_constraints(table_name)
            payload["unicas"] = GeneratorTabularRuntime.process_unique_constraints_data(unique_constraints)

        if section_flags[5]:
            indices = data_provider.get_indices(table_name)
            payload["indices"] = GeneratorTabularRuntime.process_indices_data(indices)

    def _build_view_payload(
        self,
        view_name: str,
        comentario: str,
        data_provider: DocumentationManagerPort,
        section_flags: list[bool],
        include_diagrams: bool = False,
        diagram_options: dict[str, Any] | None = None,
        include_columns_charset: bool = False,
    ) -> dict[str, Any]:
        """Construye el payload HTML de una vista."""
        payload: dict[str, Any] = {
            "name": view_name,
            "comment": comentario or "",
            "ddl": None,
            "show_columnas": bool(section_flags[1]),
            "columnas": {"headers": self.headers.get("COLUMNAS", []), "rows": []},
            "show_columns_charset": include_columns_charset,
            "columns_charset": {"headers": ["Columna", "Charset", "Collation"], "rows": []},
            "diagram_policy": self._build_view_diagram_policy_payload(
                view_name=view_name,
                include_diagrams=include_diagrams,
                diagram_options=diagram_options or {},
            ),
        }

        self._populate_view_ddl_section(payload, data_provider, view_name, section_flags)
        self._populate_view_columns_section(payload, data_provider, view_name, section_flags, include_columns_charset)

        return payload

    def _build_view_diagram_policy_payload(
        self,
        *,
        view_name: str,
        include_diagrams: bool,
        diagram_options: dict[str, Any],
    ) -> dict[str, Any]:
        """Expone la política actual de diagramado de vistas para el detalle HTML."""
        if not include_diagrams:
            return {}

        policy: str = str(diagram_options.get("view_policy", "exclude")).strip().lower() or "exclude"
        if policy != "exclude":
            policy = "exclude"

        return {
            "state": policy,
            "title": "Política de diagramado de vistas",
            "label": "Las vistas no se incluyen en el diagrama relacional enriquecido.",
            "description": (
                f"La vista {view_name} se documenta con su DDL y columnas, pero no participa en el grafo "
                "de relaciones generado para tablas."
            ),
            "reasons": [
                "El renderer actual de relaciones trabaja sobre claves foráneas entre tablas y no modela vistas como nodos del grafo.",
                "Excluir vistas evita diagramas con ruido visual cuando una vista referencia muchas tablas base.",
            ],
            "notes": [
                "Si en una versión futura analysis incorpora soporte real para vistas, esta política podrá ampliarse.",
            ],
        }

    def _populate_view_ddl_section(
        self,
        payload: dict[str, Any],
        data_provider: DocumentationManagerPort,
        view_name: str,
        section_flags: list[bool],
    ) -> None:
        """Rellena la sección DDL del payload de vista."""
        if section_flags[0]:
            try:
                ddl: str = data_provider.get_view_ddl(view_name)
                payload["ddl"] = self._decode_html_entities(ddl) if ddl is not None else ""
            except DatabaseException as error:
                payload["ddl"] = f"⚠️ Error obteniendo DDL: {error}"

    def _populate_view_columns_section(
        self,
        payload: dict[str, Any],
        data_provider: DocumentationManagerPort,
        view_name: str,
        section_flags: list[bool],
        include_columns_charset: bool,
    ) -> None:
        """Rellena la sección de columnas del payload de vista."""
        if not section_flags[1]:
            return

        try:
            columnas = data_provider.get_columns(view_name)
            payload["columnas"]["rows"] = GeneratorTabularRuntime.process_columns_data(columnas)
            self._populate_view_columns_charset(payload, data_provider, view_name, include_columns_charset)
        except DatabaseException:
            payload["columnas"]["rows"] = []

    def _populate_view_columns_charset(
        self,
        payload: dict[str, Any],
        data_provider: DocumentationManagerPort,
        view_name: str,
        include_columns_charset: bool,
    ) -> None:
        """Rellena información de charset/collation de columnas de vista."""
        if not include_columns_charset:
            return

        try:
            charset_info = data_provider.get_columns_charset_collation(view_name)
            payload["columns_charset"]["rows"] = [[row[0], row[1] or "", row[2] or ""] for row in charset_info]
        except DatabaseException as e:
            self.logger.debug(f"⚠️  No se pudo obtener charset/collation de columnas para {view_name}: {e}")
            payload["columns_charset"]["rows"] = []

    def _build_routine_payload(
        self,
        routine_name: str,
        routine_type: str,
        comentario: str,
        data_provider: DocumentationManagerPort,
    ) -> dict[str, Any]:
        """Construye el payload HTML de una rutina (procedure/función)."""
        payload: dict[str, Any] = {
            "name": routine_name,
            "routine_type": routine_type,
            "comment": comentario or "",
            "ddl": None,
            "parametros": {"headers": self.headers.get("PARAMETROS_RUTINA", []), "rows": []},
        }

        try:
            ddl: str = data_provider.get_routine_ddl(routine_name, routine_type)
            payload["ddl"] = self._decode_html_entities(ddl) if ddl is not None else ""
        except DatabaseException as error:
            payload["ddl"] = f"⚠️ Error obteniendo DDL: {error}"

        try:
            parametros = data_provider.get_routine_parameters(routine_name, routine_type)
            payload["parametros"]["rows"] = GeneratorRoutineRuntime.parameter_rows(parametros)
        except DatabaseException:
            payload["parametros"]["rows"] = []

        return payload

    def _build_diagram_tab_payload(
        self,
        table_name: str,
        piped: dict[str, Any],
        graph_output_dir: Path,
        output_dir: Path,
        navigation_links: dict[str, str],
        file_stem: str,
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
        """Construye las pestañas HTML a partir de ``pipe_level_graphs_ext`` y escribe cada SVG con sus enlaces."""
        summary = dict(piped.get("summary", {}))
        tabs: list[dict[str, Any]] = []
        flat_paths: list[str] = []

        for direction_key, direction_label in (("outgoing", "Salida"), ("incoming", "Entrada")):
            items = sorted(piped.get(direction_key, []), key=lambda item: int(item.get("depth", 0)))
            tab_items: list[dict[str, Any]] = []
            for item in items:
                depth = int(item["depth"])
                svg_markup: str = self._inject_links_into_svg_markup(item["bytes"], navigation_links)
                path: Path = graph_output_dir / f"graphviz_ext_{file_stem}_{direction_key}_level{depth}.svg"
                path.write_text(svg_markup, encoding="utf-8")
                relative_path = html.escape(str(path.relative_to(output_dir)).replace("\\", "/"))
                flat_paths.append(relative_path)
                title = f"Nivel {depth}"
                tab_items.append(
                    {
                        "tab_id": f"{table_name}-{direction_key}-level-{depth}",
                        "title": title,
                        "short_title": title,
                        "depth": depth,
                        "path": relative_path,
                        "inline_svg": svg_markup,
                        "direction": direction_key,
                        "aria_label": f"{direction_label} {title} de {table_name}",
                    }
                )

            if not tab_items:
                continue

            hidden_levels = int(summary.get(f"hidden_{direction_key}_levels", 0))
            total_levels = int(summary.get(f"total_{direction_key}_levels", len(tab_items)))

            tabs.append(
                {
                    "group_id": f"{table_name}-{direction_key}",
                    "direction": direction_key,
                    "direction_label": direction_label,
                    "tablist_label": f"Pestañas {direction_label} {table_name}",
                    "direction_help": self._get_diagram_direction_help(direction_key),
                    "group_hint": self._build_diagram_group_hint(
                        direction_key=direction_key,
                        visible_levels=len(tab_items),
                        total_levels=total_levels,
                        hidden_levels=hidden_levels,
                    ),
                    "density_badge": self._build_diagram_density_badge(
                        visible_levels=len(tab_items),
                        total_levels=total_levels,
                        hidden_levels=hidden_levels,
                    ),
                    "items": tab_items,
                    "total_levels": total_levels,
                    "visible_levels": len(tab_items),
                    "hidden_levels": hidden_levels,
                    "has_hidden_levels": hidden_levels > 0,
                }
            )

        return tabs, flat_paths, self._build_diagram_summary_payload(table_name=table_name, summary=summary, tabs=tabs)

    def _build_diagram_summary_payload(
        self,
        table_name: str,
        summary: dict[str, Any],
        tabs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Normaliza el resumen de diagramas a un contrato estable para HTML."""
        visible_outgoing_levels = next(
            (int(group.get("visible_levels", 0)) for group in tabs if group.get("direction") == "outgoing"),
            0,
        )
        visible_incoming_levels = next(
            (int(group.get("visible_levels", 0)) for group in tabs if group.get("direction") == "incoming"),
            0,
        )
        hidden_outgoing_levels = int(summary.get("hidden_outgoing_levels", 0))
        hidden_incoming_levels = int(summary.get("hidden_incoming_levels", 0))

        payload = build_diagram_summary_payload(
            max_depth=int(summary.get("max_depth", 0)),
            total_outgoing_levels=int(summary.get("total_outgoing_levels", visible_outgoing_levels)),
            total_incoming_levels=int(summary.get("total_incoming_levels", visible_incoming_levels)),
            visible_outgoing_levels=visible_outgoing_levels,
            visible_incoming_levels=visible_incoming_levels,
            hidden_outgoing_levels=hidden_outgoing_levels,
            hidden_incoming_levels=hidden_incoming_levels,
        )
        payload["root_table"] = str(summary.get("root_table", table_name))
        return payload

    def _build_diagram_group_hint(
        self,
        *,
        direction_key: str,
        visible_levels: int,
        total_levels: int,
        hidden_levels: int,
    ) -> str:
        """Devuelve una ayuda corta para orientar la lectura de un grupo de tabs."""
        if hidden_levels > 0:
            return (
                f"Esta vista muestra {visible_levels} nivel(es) visibles de {total_levels}. "
                "Usa las pestañas para aislar relaciones y reduce el ruido visual por profundidad."
            )
        if total_levels > 1:
            return f"Esta vista reparte {total_levels} niveles en pestañas separadas para revisar la dirección {direction_key} sin mezclar recorridos."
        return "Esta vista muestra un único nivel, útil para inspección rápida sin cambiar de contexto."

    def _build_diagram_density_badge(self, *, visible_levels: int, total_levels: int, hidden_levels: int) -> str:
        """Resume el nivel de densidad visual del grupo actual."""
        if hidden_levels > 0:
            return "Vista densa"
        if total_levels > 1 or visible_levels > 1:
            return "Vista multinivel"
        return "Vista directa"

    def _build_diagram_navigation_tips(
        self,
        *,
        visible_outgoing_levels: int,
        visible_incoming_levels: int,
        hidden_outgoing_levels: int,
        hidden_incoming_levels: int,
    ) -> list[str]:
        """Construye consejos de lectura para diagramas con varias pestañas o profundidad oculta."""
        return build_diagram_navigation_tips(
            visible_outgoing_levels=visible_outgoing_levels,
            visible_incoming_levels=visible_incoming_levels,
            hidden_outgoing_levels=hidden_outgoing_levels,
            hidden_incoming_levels=hidden_incoming_levels,
        )

    def _build_diagram_legend_payload(self) -> dict[str, Any]:
        """Devuelve la leyenda HTML del diagrama basada en el contrato real actual."""
        return build_diagram_legend_payload()

    def _get_diagram_direction_help(self, direction_key: str) -> str:
        """Devuelve ayuda contextual por sentido del diagrama."""
        return build_diagram_direction_help(direction_key)

    def _build_hidden_levels_help(self, direction_key: str) -> str:
        """Explica qué significa que existan niveles ocultos por dirección."""
        return build_hidden_levels_help(direction_key)

    @staticmethod
    def _level_graph_kwargs(diagram_options: dict[str, Any]) -> dict[str, Any]:
        """Argumentos de ``pipe_level_graphs_ext`` (los mismos en la precarga y en la llamada real)."""
        return {
            "format": "svg",
            "max_depth": int(diagram_options.get("max_depth", 1)),
            "direction": str(diagram_options.get("direction", "both")),
        }

    def _generate_svg_for_table(
        self,
        table_name: str,
        graph_generator: GraphvizRelationshipGraphExt,
        diagram_options: dict[str, Any],
        output_dir: Path,
        navigation_links: dict[str, str],
        file_stem: str,
    ) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
        """Diagramas por nivel de una tabla: pestañas con el SVG incrustado y rutas relativas de los ficheros.

        Los SVG se generan en memoria (precargados en paralelo por ``_process_tables``), se les inyectan los enlaces
        a las páginas de detalle y se escriben una sola vez en ``grafo.output_dir`` (por defecto ``graphs/``).

        Returns:
            ``(pestañas, rutas relativas, resumen de niveles)``; vacío si Graphviz falla para esta tabla.
        """
        graph_output_dir: Path = Path(diagram_options.get("output_dir", output_dir / "graphs"))
        try:
            piped: dict[str, Any] = graph_generator.pipe_level_graphs_ext(
                table_name=table_name, **self._level_graph_kwargs(diagram_options)
            )
            graph_output_dir.mkdir(parents=True, exist_ok=True)
            return self._build_diagram_tab_payload(
                table_name=table_name,
                piped=piped,
                graph_output_dir=graph_output_dir,
                output_dir=output_dir,
                navigation_links=navigation_links,
                file_stem=file_stem,
            )
        except (OSError, RuntimeError) as error:
            self.logger.warning(f"⚠️ No se pudo generar SVG para tabla {table_name}: {error}")
            return [], [], {}

    def _inject_links_into_svg_markup(self, svg_bytes: bytes, navigation_links: dict[str, str]) -> str:
        """Inyecta enlaces clicables en bytes SVG en memoria y devuelve el markup resultante.

        Cada nodo cuyo ``<title>`` está en ``navigation_links`` queda envuelto en un ``<a>`` a su página de detalle.
        Devuelve el SVG sin declaración XML, listo para incrustar inline en HTML y para escribirlo a disco.

        Args:
            svg_bytes: Contenido SVG como bytes (salida de dot.pipe o caché)
            navigation_links: Mapa de nombre de tabla → URL de destino

        Returns:
            str: Markup SVG con enlaces inyectados, sin declaración XML

        Example:
            >>> markup = generator._inject_links_into_svg_markup(svg_bytes, {"orders": "orders.html"})
            >>> markup.startswith("<svg")
            True
        """
        svg_ns = "http://www.w3.org/2000/svg"
        xlink_ns = "http://www.w3.org/1999/xlink"
        ET.register_namespace("", svg_ns)
        ET.register_namespace("xlink", xlink_ns)

        def _decode_markup(raw: bytes) -> str:
            text = raw.decode("utf-8")
            return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", text, count=1).strip()

        if not navigation_links:
            return _decode_markup(svg_bytes)

        try:
            root: ET.Element = ET.fromstring(svg_bytes)
            node_selector: LiteralString = f".//{{{svg_ns}}}g[@class='node']"
            for node_group in root.findall(node_selector):
                title_element: ET.Element | None = node_group.find(f"{{{svg_ns}}}title")
                if title_element is None or not title_element.text:
                    continue
                target_href: str | None = navigation_links.get(title_element.text)
                if not target_href:
                    continue
                existing_anchor: ET.Element | None = node_group.find(f"{{{svg_ns}}}a")
                if existing_anchor is not None:
                    existing_anchor.set(f"{{{xlink_ns}}}href", target_href)
                    existing_anchor.set("target", "_blank")
                    existing_anchor.set("rel", "noopener noreferrer")  # S-03
                    continue
                anchor: ET.Element = ET.Element(f"{{{svg_ns}}}a")
                anchor.set(f"{{{xlink_ns}}}href", target_href)
                anchor.set("target", "_blank")
                anchor.set("rel", "noopener noreferrer")  # S-03
                children: list[ET.Element] = list(node_group)
                for child in children:
                    node_group.remove(child)
                    anchor.append(child)
                node_group.append(anchor)
            return ET.tostring(root, encoding="unicode").strip()
        except ET.ParseError as error:
            self.logger.warning(f"⚠️ No se pudieron inyectar enlaces SVG en memoria: {error}")
            return _decode_markup(svg_bytes)

    def _decode_html_entities(self, value: str, max_rounds: int = 3) -> str:
        """Decodifica entidades HTML (incluyendo casos doblemente escapados)."""
        decoded: str = value
        for _ in range(max_rounds):
            unescaped = html.unescape(decoded)
            if unescaped == decoded:
                break
            decoded = unescaped
        return decoded
