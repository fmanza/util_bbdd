"""
Módulo para generación de documentación en formato Word
"""

import inspect
import logging

from pathlib import Path
from typing import Any

# Word imports
from docx import Document as load_document
from docx.document import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.image.image import Image as DocxImage
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.section import Section
from docx.shared import Emu, Pt
from docx.table import Table, _Row
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from ..analysis.graphviz_ext import GraphvizRelationshipGraphExt
from .print_config_manager import PrintConfigManager


class DocumentChunkConfig:
    """Contenedor de configuración para generar un chunk de documento.

    Agrupa los parámetros booleanos y de configuración para reducir
    la complejidad de las firmas de método.
    """

    def __init__(
        self,
        include_tables: bool,
        include_views: bool,
        include_procedures: bool,
        include_functions: bool,
        include_storage: bool,
        table_section_flags: list[bool],
        view_section_flags: list[bool],
        include_diagrams: bool,
        template_path: Path | None = None,
        diagram_options: dict[str, Any] | None = None,
        include_database_info: bool = False,
        database_info_flags: list[bool] | None = None,
        include_columns_charset: bool = False,
    ) -> None:
        """Inicializa la configuración del documento.

        Args:
            include_tables: Si incluir tablas en el documento
            include_views: Si incluir vistas en el documento
            include_procedures: Si incluir procedures en el documento
            include_functions: Si incluir funciones en el documento
            include_storage: Si incluir sección de almacenamiento
            table_section_flags: Flags para secciones de tablas
            view_section_flags: Flags para secciones de vistas
            include_diagrams: Si incluir diagramas de relaciones
            template_path: Ruta opcional a plantilla Word
            diagram_options: Opciones de generación de diagramas
            include_database_info: Si incluir información de BD (versión, charset)
            database_info_flags: [version_flag, charset_collation_flag]
            include_columns_charset: Si incluir charset/collation de columnas
        """
        self.include_tables: bool = include_tables
        self.include_views: bool = include_views
        self.include_procedures: bool = include_procedures
        self.include_functions: bool = include_functions
        self.include_storage: bool = include_storage
        self.table_section_flags: list[bool] = table_section_flags
        self.view_section_flags: list[bool] = view_section_flags
        self.include_diagrams: bool = include_diagrams
        self.template_path: Path | None = template_path
        self.diagram_options: dict[str, Any] = diagram_options or {}
        self.include_database_info: bool = include_database_info
        self.database_info_flags: list[bool] = database_info_flags or [False, False]
        self.include_columns_charset: bool = include_columns_charset


class WordGenerator:
    """Clase para generar documentación en formato Word"""

    SECTION_PARAMETROS: str = "Parámetros"
    SECTION_CHARSET_COLLATION: str = "Charset/Collation de Columnas"

    def __init__(self, database: str, headers: dict, table_style: str = "Table Grid"):
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.database: str = database
        self.headers = headers
        self.table_style: str = table_style

    def generate_document(
        self,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: Any,
        output_file: Path,
        print_config: dict[str, Any] | None = None,
    ) -> None:
        """Genera el documento Word completo con tablas y vistas.

        Args:
            tables: lista de tablas.
            views: lista de vistas.
            data_provider: Proveedor de metadatos de base de datos.
            output_file: Ruta de salida del .docx.
            print_config: Configuración unificada de secciones y gráficos.
        """
        self.logger.info(f"🟢 Iniciando generación de documentación Word para base de datos: {self.database}")
        try:
            normalized_config: dict[str, Any] = PrintConfigManager.normalize(
                print_config or data_provider.imprimir_config
            )
            resolved: dict[str, Any] = PrintConfigManager.resolve_for_word(normalized_config)
            include_tables: bool = bool(resolved["include_tables"])
            include_views: bool = bool(resolved["include_views"])
            include_procedures: bool = bool(resolved["include_procedures"])
            include_functions: bool = bool(resolved["include_functions"])
            include_storage: bool = bool(resolved["include_storage"])
            include_database_info: bool = bool(resolved.get("include_database_info", False))
            table_section_flags: list[bool] = resolved["table_section_flags"]
            view_section_flags: list[bool] = resolved["view_section_flags"]
            template_path: Path | None = resolved["template_path"]
            tables_per_document: int = int(resolved["tables_per_document"])
            include_diagrams: bool = bool(resolved["include_diagrams"])
            graph_options: dict[str, Any] = resolved["graph_options"]
            database_info_flags: list[bool] = resolved.get("database_info_flags", [False, False])

            self.logger.debug(
                f"⚙️  Configuración Word resuelta: include_diagrams={include_diagrams}, "
                f"template={template_path}, tables_per_document={tables_per_document}, "
                f"include_database_info={include_database_info}, database_info_flags={database_info_flags}"
            )

            # Diagnóstico: verificar si la información de BD está deshabilitada
            if not include_database_info:
                self.logger.info(
                    "ℹ️  La información de la base de datos NO se incluirá en el documento. "
                    "Si desea incluirla, configure [imprimir.info_database] en el archivo TOML con imprimir_info_database = true"
                )

            tables_for_chunks: list[tuple] = tables if include_tables else []
            table_chunks: list[list[tuple]] = self._chunk_tables(tables_for_chunks, tables_per_document)
            if not table_chunks:
                table_chunks = [[]]

            graph_generator: Any = None
            if include_diagrams:
                self.logger.debug("🟢 Inicializando generador de grafos para diagramas")
                graph_generator = self._build_graph_generator(data_provider, graph_options)

            # Configuración de documentos
            doc_config: DocumentChunkConfig = DocumentChunkConfig(
                include_tables=include_tables,
                include_views=include_views,
                include_procedures=include_procedures,
                include_functions=include_functions,
                include_storage=include_storage,
                table_section_flags=table_section_flags,
                view_section_flags=view_section_flags,
                include_diagrams=include_diagrams,
                template_path=template_path,
                diagram_options=graph_options,
                include_database_info=include_database_info,
                database_info_flags=database_info_flags,
                include_columns_charset=resolved.get("include_columns_charset", False),
            )

            total_chunks: int = len(table_chunks)
            for idx, table_chunk in enumerate(table_chunks, start=1):
                self.logger.info(f"📄 Generando documento Word {idx}/{total_chunks}")
                self._generate_single_document_chunk(
                    idx=idx,
                    total_chunks=total_chunks,
                    table_chunk=table_chunk,
                    views=views,
                    routines=routines,
                    data_provider=data_provider,
                    output_file=output_file,
                    config=doc_config,
                    graph_generator=graph_generator,
                )

            self.logger.info(f"✅ Generación Word finalizada: {total_chunks} documento(s)")
        except Exception as error:
            self.logger.exception(f"❌ Error en generate_document para Word: {error}")
            raise

    def _generate_single_document_chunk(
        self,
        idx: int,
        total_chunks: int,
        table_chunk: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: Any,
        output_file: Path,
        config: DocumentChunkConfig,
        graph_generator: Any | None,
    ) -> None:
        """Genera y guarda un documento Word para un chunk de tablas.

        Args:
            idx: Índice del chunk actual
            total_chunks: Total de chunks a generar
            table_chunk: Tabla(s) del chunk actual
            views: lista de vistas
            routines: lista de rutinas
            data_provider: Proveedor de metadatos
            output_file: Ruta de salida
            config: Configuración del documento (encapsula 10 parámetros)
            graph_generator: Generador de grafos opcional
        """
        try:
            document: Document = self._initialize_document(config.template_path)
            self._configure_document_orientation(document, config.template_path)
            document.add_heading(f"Documentación de la Base de Datos - {self.database}", 0)

            self._add_tables_content(
                document=document,
                table_chunk=table_chunk,
                data_provider=data_provider,
                table_section_flags=config.table_section_flags,
                include_tables=config.include_tables,
                include_diagrams=config.include_diagrams,
                graph_generator=graph_generator,
                diagram_options=config.diagram_options,
                include_columns_charset=config.include_columns_charset,
            )

            self._add_views_content(
                document=document,
                views=views,
                data_provider=data_provider,
                view_section_flags=config.view_section_flags,
                include_views=config.include_views,
                idx=idx,
                total_chunks=total_chunks,
                include_columns_charset=config.include_columns_charset,
            )

            self._add_routines_content(
                document=document,
                routines=routines,
                data_provider=data_provider,
                include_procedures=config.include_procedures,
                include_functions=config.include_functions,
                idx=idx,
                total_chunks=total_chunks,
            )

            if config.include_database_info and idx == total_chunks:
                self._add_database_info_section(
                    document=document,
                    data_provider=data_provider,
                    database_info_flags=config.database_info_flags,
                )

            if config.include_storage and idx == total_chunks:
                self._add_storage_inventory_section(document=document, data_provider=data_provider)

            target_file: Path = self._build_output_file_for_chunk(output_file, idx, total_chunks)
            document.save(str(target_file))
            self.logger.info(f"✅ Documento Word generado: {target_file}")
        except Exception as chunk_error:
            self.logger.exception(f"❌ Error generando documento Word {idx}/{total_chunks}: {chunk_error}")
            raise

    def _configure_document_orientation(self, document: Document, template_path: Path | None) -> None:
        """Configura la orientación del documento según la plantilla."""
        if template_path is None:
            self._configure_landscape(document=document, apply_to_all_sections=True)
        else:
            self.logger.debug("📄 Se respeta la orientación definida en la plantilla Word")

    def _add_tables_content(
        self,
        document: Document,
        table_chunk: list[tuple],
        data_provider: Any,
        table_section_flags: list[bool],
        include_tables: bool,
        include_diagrams: bool,
        graph_generator: Any,
        diagram_options: dict[str, Any],
        include_columns_charset: bool = False,
    ) -> None:
        """Agrega el contenido de tablas al documento."""
        if include_tables and table_chunk:
            document.add_heading("Tablas", level=1)
            for row in table_chunk:
                tabla, comentario, charset_collation = self._extract_table_row_data(row)
                self._add_table_section(
                    document=document,
                    tabla=tabla,
                    comentario=comentario,
                    charset_collation=charset_collation,
                    data_provider=data_provider,
                    section_flags=table_section_flags,
                    include_table_diagrams=include_diagrams,
                    graph_generator=graph_generator,
                    diagram_options=diagram_options,
                    include_columns_charset=include_columns_charset,
                )

    def _extract_table_row_data(self, row: tuple) -> tuple[str, str, str | None]:
        """Extrae tabla, comentario y charset_collation de una fila de tabla.

        Args:
            row: Tupla con datos de tabla (tabla, comentario, [charset/collation])

        Returns:
            Tupla con (tabla, comentario, charset_collation)
        """
        tabla: str = row[0]
        comentario: str = row[1] if len(row) > 1 else ""

        # Manejar charset_collation: 4 columnas (MariaDB) o 2-3 columnas (otros)
        if len(row) > 3:
            # MariaDB: row[2]=charset, row[3]=collation
            charset = row[2]
            collation = row[3]
            charset_collation = f"{charset} {collation}".strip() if charset or collation else None
        else:
            # Otros motores: row[2]=charset_collation (opcional)
            charset_collation = row[2] if len(row) > 2 else None

        return tabla, comentario, charset_collation

    def _add_views_content(
        self,
        document: Document,
        views: list[tuple],
        data_provider: Any,
        view_section_flags: list[bool],
        include_views: bool,
        idx: int,
        total_chunks: int,
        include_columns_charset: bool = False,
    ) -> None:
        """Agrega el contenido de vistas al documento."""
        if include_views and views and idx == total_chunks:
            document.add_heading("Vistas", level=1)
            for vista, comentario in views:
                self._add_view_section(
                    document,
                    vista,
                    comentario,
                    data_provider,
                    view_section_flags,
                    include_columns_charset,
                )

    def _add_routines_content(
        self,
        document: Document,
        routines: list[tuple],
        data_provider: Any,
        include_procedures: bool,
        include_functions: bool,
        idx: int,
        total_chunks: int,
    ) -> None:
        """Agrega el contenido de rutinas al documento."""
        if routines and idx == total_chunks and (include_procedures or include_functions):
            self._add_routines_sections(
                document=document,
                routines=routines,
                data_provider=data_provider,
                include_procedures=include_procedures,
                include_functions=include_functions,
                include_ddl=True,
            )

    def _initialize_document(self, template_path: Path | None) -> Document:
        """Inicializa el documento desde plantilla o en blanco con control de errores y logging."""
        try:
            if template_path is None:
                self.logger.debug("🟢 Inicializando documento Word sin plantilla")
                return load_document()

            resolved_template_path: Path = template_path.expanduser().resolve()
            if not resolved_template_path.exists():
                error_msg: str = f"Plantilla no encontrada: {resolved_template_path}"
                self.logger.error(f"❌ {error_msg}")
                raise FileNotFoundError(error_msg)

            if not resolved_template_path.is_file():
                error_msg = f"La plantilla no es un archivo válido: {resolved_template_path}"
                self.logger.error(f"❌ {error_msg}")
                raise FileNotFoundError(error_msg)

            self.logger.info(f"📄 Cargando plantilla Word: {resolved_template_path}")
            return load_document(str(resolved_template_path))
        except FileNotFoundError:
            raise
        except Exception as error:
            self.logger.exception(f"❌ Error inicializando documento Word: {error}")
            raise

    def _chunk_tables(self, tables: list[tuple], tables_per_document: int) -> list[list[tuple]]:
        """Divide tablas en lotes para crear múltiples documentos."""
        if not tables:
            return []

        chunk_size = tables_per_document if tables_per_document > 0 else 50
        return [tables[i : i + chunk_size] for i in range(0, len(tables), chunk_size)]

    def _build_output_file_for_chunk(self, output_file: Path, chunk_index: int, total_chunks: int) -> Path:
        """Construye nombre de salida para cada documento segmentado."""
        if total_chunks <= 1:
            return output_file
        return output_file.with_name(f"{output_file.stem}_part{chunk_index}{output_file.suffix}")

    def _add_table_section(
        self,
        document: Document,
        tabla: str,
        comentario: str,
        data_provider: Any,
        section_flags: list[bool],
        charset_collation: str | None = None,
        include_table_diagrams: bool = False,
        graph_generator: Any = None,
        diagram_options: dict[str, Any] | None = None,
        include_columns_charset: bool = False,
    ) -> None:
        """Agrega una sección completa para una tabla."""
        document.add_page_break()
        document.add_heading(f"Tabla: {tabla}", level=1)

        # Comentario con etiqueta en negrita
        p = document.add_paragraph()
        p.add_run("Comentario:").bold = True
        p.add_run(f" {comentario if comentario else ''}")

        # Charset & Collation con etiqueta en negrita
        if charset_collation and str(charset_collation).strip():
            p = document.add_paragraph()
            p.add_run("Charset & Collation:").bold = True
            p.add_run(f" {charset_collation}")

        secciones = [
            (0, lambda: self._add_ddl_section(document, tabla, data_provider)),
            (
                1,
                lambda: self._add_columns_section(document, tabla, data_provider, include_columns_charset),
            ),
            (2, lambda: self._add_primary_keys_section(document, tabla, data_provider)),
            (3, lambda: self._add_foreign_keys_section(document, tabla, data_provider)),
            (4, lambda: self._add_unique_constraints_section(document, tabla, data_provider)),
            (5, lambda: self._add_indices_section(document, tabla, data_provider)),
        ]

        for idx, metodo in secciones:
            if section_flags[idx]:
                metodo()

        # Solo tablas: insertar diagrama con salto de página
        if include_table_diagrams and graph_generator is not None:
            self._add_table_diagram_page(
                document=document,
                tabla=tabla,
                graph_generator=graph_generator,
                diagram_options=diagram_options or {},
            )

    def _build_graph_generator(self, data_provider: Any, options: dict[str, Any]) -> Any:
        """Crea GraphvizRelationshipGraphExt para generar diagramas al vuelo."""
        db_manager = data_provider.db_manager
        return GraphvizRelationshipGraphExt(
            db_manager=db_manager,
            show_columns=bool(options.get("show_columns", True)),
        )

    def _add_table_diagram_page(
        self,
        document: Document,
        tabla: str,
        graph_generator: Any,
        diagram_options: dict[str, Any],
    ) -> None:
        """Inserta una página con el diagrama de una tabla."""
        fmt: str = str(diagram_options.get("format", "png")).lower()
        if fmt == "svg":
            # Word no maneja SVG de forma fiable en python-docx
            fmt = "png"

        output_dir = Path(diagram_options.get("output_dir", Path.cwd() / "_table_diagrams"))
        output_dir.mkdir(parents=True, exist_ok=True)
        images_paginated: bool = bool(diagram_options.get("images_paginated", False))

        try:
            generated_paths: list[Path]
            if images_paginated and hasattr(graph_generator, "generate_graphviz_graph_paginated_ext"):
                paginated_method = graph_generator.generate_graphviz_graph_paginated_ext
                kwargs_paginated: dict[str, Any] = {
                    "table_name": tabla,
                    "output_dir": output_dir,
                    "format": fmt,
                    "max_subnodes": int(diagram_options.get("max_subnodes", 10)),
                    "show_columns": bool(diagram_options.get("show_columns", True)),
                }
                generated_paths = [Path(path) for path in paginated_method(**kwargs_paginated)]
            else:
                output_file: Path = output_dir / f"{tabla}.{fmt}"
                method = graph_generator.generate_single_table_graph_ext
                kwargs: dict[str, Any] = {
                    "table_name": tabla,
                    "output_file": output_file,
                    "format": fmt,
                    "show_columns": bool(diagram_options.get("show_columns", True)),
                }

                params = inspect.signature(method).parameters
                if "first_level_only" in params:
                    kwargs["first_level_only"] = bool(diagram_options.get("first_level_only", True))
                generated_paths = [Path(method(**kwargs))]

            for page_idx, generated_path in enumerate(generated_paths, start=1):
                document.add_page_break()
                title: str = f"Diagrama de relaciones: {tabla}"
                if len(generated_paths) > 1:
                    title += f" (Página {page_idx})"
                title_paragraph: Paragraph = document.add_heading(title, level=2)
                self._add_picture_fit_to_page(
                    document=document, image_path=generated_path, title_paragraph=title_paragraph
                )
        except Exception as e:
            document.add_page_break()
            document.add_heading(f"Diagrama de relaciones: {tabla}", level=2)
            document.add_paragraph(f"⚠️ No se pudo generar el diagrama: {e}")

    def _add_picture_fit_to_page(
        self, document: Document, image_path: Path, title_paragraph: Paragraph | None = None
    ) -> None:
        """Inserta imagen ajustándola proporcionalmente al área imprimible de la página."""
        if not image_path.exists():
            document.add_paragraph(f"⚠️ No se encontró el archivo de imagen: {image_path}")
            return

        section: Section = document.sections[-1]
        page_width: int = int(section.page_width) if section.page_width is not None else int(Emu(0))
        page_height: int = int(section.page_height) if section.page_height is not None else int(Emu(0))
        left_margin: int = int(section.left_margin) if section.left_margin is not None else 0
        right_margin: int = int(section.right_margin) if section.right_margin is not None else 0
        top_margin: int = int(section.top_margin) if section.top_margin is not None else 0
        bottom_margin: int = int(section.bottom_margin) if section.bottom_margin is not None else 0
        reserved_title_height: int = self._estimate_paragraph_reserved_height_emu(title_paragraph)
        safety_padding = int(Pt(24))
        picture_paragraph_reserved = int(Pt(18))

        max_width: int = page_width - left_margin - right_margin
        max_height: int = (
            page_height
            - top_margin
            - bottom_margin
            - reserved_title_height
            - picture_paragraph_reserved
            - safety_padding
        )
        if max_height <= 0:
            max_height = int(Pt(72))

        if max_width <= 0:
            max_width = int(Pt(72))

        image = DocxImage.from_file(str(image_path))
        image_width = int(image.width)
        image_height = int(image.height)

        if image_width <= 0 or image_height <= 0:
            document.add_picture(str(image_path), width=Emu(max_width))
            return

        width_ratio: float = max_width / image_width
        height_ratio: float = max_height / image_height
        scale: float = min(width_ratio, height_ratio, 1.0)
        scale *= 0.98

        scaled_width = Emu(max(1, int(image_width * scale)))
        scaled_height = Emu(max(1, int(image_height * scale)))
        document.add_picture(str(image_path), width=scaled_width, height=scaled_height)

    def _estimate_paragraph_reserved_height_emu(self, paragraph: Paragraph | None) -> int:
        """Estima espacio vertical a reservar para un título en la página de imagen."""
        if paragraph is None:
            return 0

        run_font_size = next((run.font.size for run in paragraph.runs if run.font.size is not None), None)
        style_font_size = paragraph.style.font.size if paragraph.style is not None else None
        font_size = run_font_size or style_font_size or Pt(16)

        paragraph_format = paragraph.paragraph_format
        space_before_pt = paragraph_format.space_before.pt if paragraph_format.space_before is not None else 0.0
        space_after_pt = paragraph_format.space_after.pt if paragraph_format.space_after is not None else 0.0

        reserved_points: float = (font_size.pt * 1.8) + float(space_before_pt) + float(space_after_pt) + 8.0
        return int(Pt(reserved_points))

    def _configure_landscape(self, document: Document, apply_to_all_sections: bool = False) -> None:
        """Configura la página en orientación apaisada sin invertir secciones ya horizontales."""
        sections: list[Section] = list(document.sections) if apply_to_all_sections else [document.sections[-1]]

        for section in sections:
            if section.orientation == WD_ORIENT.LANDSCAPE:
                continue

            new_width, new_height = section.page_height, section.page_width
            section.orientation = WD_ORIENT.LANDSCAPE
            section.page_width = new_width
            section.page_height = new_height

    def _add_view_section(
        self,
        document: Document,
        vista: str,
        comentario: str,
        data_provider: Any,
        section_flags: list[bool],
        include_columns_charset: bool = False,
    ) -> None:
        """Agrega una sección para una vista (solo DDL y Columnas)"""
        document.add_page_break()
        document.add_heading(f"Vista: {vista}", level=2)
        document.add_paragraph(f"Comentario: {comentario if comentario else ''}")

        # Secciones para vistas: [DDL, Columnas]
        if len(section_flags) > 0 and section_flags[0]:
            try:
                self._add_ddl_section(document, vista, data_provider, is_view=True)
            except Exception:
                document.add_paragraph("⚠️ No se pudo obtener el DDL de la vista")

        if len(section_flags) > 1 and section_flags[1]:
            try:
                self._add_columns_section(document, vista, data_provider, include_columns_charset)
            except Exception:
                document.add_paragraph("⚠️ No se pudieron obtener las columnas de la vista")

    def _normalize_routine_entry(self, routine: tuple) -> tuple[str, str, str]:
        """Normaliza una fila de rutina al formato (nombre, tipo, comentario)."""
        routine_name: str = str(routine[0]) if len(routine) > 0 and routine[0] is not None else ""
        routine_type: str = str(routine[1]) if len(routine) > 1 and routine[1] is not None else "FUNCTION"
        routine_comment: str = str(routine[2]) if len(routine) > 2 and routine[2] is not None else ""
        return routine_name, routine_type.upper(), routine_comment

    def _split_routines_by_type(self, routines: list[tuple]) -> tuple[list[tuple], list[tuple]]:
        """Separa routines en procedures y funciones."""
        procedures: list[tuple] = []
        functions: list[tuple] = []

        for routine in routines:
            _, routine_type, _ = self._normalize_routine_entry(routine)
            if routine_type == "PROCEDURE":
                procedures.append(routine)
            elif routine_type == "FUNCTION":
                functions.append(routine)

        return procedures, functions

    def _add_routines_sections(
        self,
        document: Document,
        routines: list[tuple],
        data_provider: Any,
        include_procedures: bool,
        include_functions: bool,
        include_ddl: bool,
    ) -> None:
        """Agrega secciones de procedures, funciones y otras rutinas al documento."""
        procedures, functions = self._split_routines_by_type(routines)

        if include_procedures and procedures:
            self._add_routine_type_section(
                document=document,
                routines=procedures,
                routine_type="Procedures",
                data_provider=data_provider,
                include_ddl=include_ddl,
            )

        if include_functions and functions:
            self._add_routine_type_section(
                document=document,
                routines=functions,
                routine_type="Funciones",
                data_provider=data_provider,
                include_ddl=include_ddl,
            )

        self._add_other_routines_section(
            document=document,
            routines=routines,
            data_provider=data_provider,
            include_ddl=include_ddl,
        )

    def _add_routine_type_section(
        self,
        document: Document,
        routines: list[tuple],
        routine_type: str,
        data_provider: Any,
        include_ddl: bool,
    ) -> None:
        """Agrega rutinas de un tipo específico (Procedures o Funciones)."""
        document.add_heading(routine_type, level=1)
        for routine in routines:
            routine_name, routine_type_normalized, routine_comment = self._normalize_routine_entry(routine)
            self._add_routine_section(
                document=document,
                routine_name=routine_name,
                routine_type=routine_type_normalized,
                comentario=routine_comment,
                data_provider=data_provider,
                include_ddl=include_ddl,
            )

    def _add_other_routines_section(
        self,
        document: Document,
        routines: list[tuple],
        data_provider: Any,
        include_ddl: bool,
    ) -> None:
        """Procesa rutinas que no son PROCEDURE ni FUNCTION."""
        for routine in routines:
            routine_name, routine_type, routine_comment = self._normalize_routine_entry(routine)
            if routine_type in {"PROCEDURE", "FUNCTION"}:
                continue
            self._add_routine_section(
                document=document,
                routine_name=routine_name,
                routine_type=routine_type,
                comentario=routine_comment,
                data_provider=data_provider,
                include_ddl=include_ddl,
            )

    def _add_routine_section(
        self,
        document: Document,
        routine_name: str,
        routine_type: str,
        comentario: str,
        data_provider: Any,
        include_ddl: bool,
    ) -> None:
        """Agrega una sección para una rutina (procedure/función)."""
        document.add_page_break()
        document.add_heading(f"{routine_type.title()}: {routine_name}", level=2)
        document.add_paragraph(f"Tipo: {routine_type.title()}")
        document.add_paragraph(f"Comentario: {comentario if comentario else ''}")

        if include_ddl:
            try:
                ddl: str = data_provider.get_routine_ddl(routine_name, routine_type)
                text_ddl: str = ddl if ddl is not None else ""
                document.add_heading("DDL", level=3)
                paragraph: Paragraph = document.add_paragraph()
                run: Run = paragraph.add_run(text_ddl)
                run.font.name = "Courier New"
                run.font.size = Pt(10.5)
                paragraph.style = "No Spacing"
                document.add_paragraph("")
            except Exception:
                document.add_paragraph("⚠️ No se pudo obtener el DDL de la rutina")

        self._add_routine_parameters_section(
            document=document,
            routine_name=routine_name,
            routine_type=routine_type,
            data_provider=data_provider,
        )

    def _add_routine_parameters_section(
        self, document: Document, routine_name: str, routine_type: str, data_provider: Any
    ) -> None:
        """Agrega la tabla de parámetros de una rutina."""
        try:
            parameters = data_provider.get_routine_parameters(routine_name, routine_type)
        except Exception:
            self._add_empty_section(
                document,
                self.SECTION_PARAMETROS,
                "No se pudieron obtener los parámetros de la rutina.",
            )
            return

        if not parameters:
            self._add_empty_section(document, self.SECTION_PARAMETROS, "No se encontraron parámetros.")
            return

        headers = self.headers.get("PARAMETROS_RUTINA", ["Modo", "Parámetro", "Tipo", "Valor por defecto", "Posición"])
        rows = self._process_routine_parameters(parameters)
        self._add_table(document, self.SECTION_PARAMETROS, headers, rows)

    def _process_routine_parameters(self, parameters: list[Any]) -> list[list[str]]:
        """Normaliza filas de parámetros de rutina para impresión."""
        rows: list[list[str]] = []
        for row in parameters:
            values: list[str] = []
            for idx in range(5):
                value = row[idx] if len(row) > idx else ""
                values.append(str(value) if value is not None else "")
            rows.append(values)
        return rows

    def _add_ddl_section(self, document: Document, tabla: str, data_provider: Any, is_view: bool = False) -> None:
        """Agrega la sección DDL"""
        ddl: str = data_provider.get_view_ddl(tabla) if is_view else data_provider.get_ddl(tabla)
        text_ddl: str = ddl if ddl is not None else ""

        document.add_heading("DDL", level=2)
        paragraph: Paragraph = document.add_paragraph()
        run: Run = paragraph.add_run(text_ddl)
        run.font.name = "Courier New"
        run.font.size = Pt(10.5)
        paragraph.style = "No Spacing"
        document.add_paragraph("")

    def _add_columns_section(
        self,
        document: Document,
        tabla: str,
        data_provider: Any,
        include_columns_charset: bool = False,
    ) -> None:
        """Agrega la sección de columnas"""
        columnas = data_provider.get_columns(tabla)
        if not columnas:
            self._add_empty_section(document, "Columnas", "No se encontraron columnas.")
            if include_columns_charset:
                self._add_empty_section(
                    document,
                    self.SECTION_CHARSET_COLLATION,
                    "No hay información de charset/collation disponible.",
                )
            return

        headers = self.headers["COLUMNAS"]

        # Procesar datos según tipo de BD para reordenarlos correctamente
        columnas_procesadas = self._process_columns_data(columnas, data_provider.db_type)

        self._add_table(document, "Columnas", headers, columnas_procesadas)

        # Agregar sección de charset/collation si está habilitado
        if include_columns_charset:
            try:
                charset_info = data_provider.get_columns_charset_collation(tabla)
                if charset_info:
                    charset_headers = ["Columna", "Charset", "Collation"]
                    charset_rows = [[row[0], row[1] or "", row[2] or ""] for row in charset_info]
                    self._add_table(document, self.SECTION_CHARSET_COLLATION, charset_headers, charset_rows)
                else:
                    self._add_empty_section(
                        document,
                        self.SECTION_CHARSET_COLLATION,
                        "No hay información de charset/collation disponible.",
                    )
            except Exception as e:
                self.logger.debug(f"⚠️  No se pudo obtener charset/collation de columnas para {tabla}: {e}")
                self._add_empty_section(
                    document,
                    self.SECTION_CHARSET_COLLATION,
                    f"Error obteniendo información: {str(e)}",
                )

    def _add_primary_keys_section(self, document: Document, tabla: str, data_provider: Any) -> None:
        """Agrega la sección de claves primarias"""
        claves = data_provider.get_primary_keys(tabla)
        if claves:
            self._add_table(document, "Claves Primarias", ["Campo"], claves)
        else:
            self._add_empty_section(document, "Claves Primarias", "No se encontraron claves primarias.")

    def _add_foreign_keys_section(self, document: Document, tabla: str, data_provider: Any) -> None:
        """Agrega la sección de claves foráneas"""
        claves = data_provider.get_foreign_keys(tabla)
        if claves:
            self._add_table(document, "Relaciones (Claves Foráneas)", self.headers["FK"], claves)
        else:
            self._add_empty_section(document, "Relaciones (Claves Foráneas)", "No se encontraron claves foráneas.")

    def _add_unique_constraints_section(self, document: Document, tabla: str, data_provider: Any) -> None:
        """Agrega la sección de restricciones únicas"""
        claves = data_provider.get_unique_constraints(tabla)
        if claves:
            self._add_table(document, "Restricciones Únicas", self.headers["UNIQUE"], claves)
        else:
            self._add_empty_section(document, "Restricciones Únicas", "No se encontraron claves únicas.")

    def _add_indices_section(self, document: Document, tabla: str, data_provider: Any) -> None:
        """Agrega la sección de índices"""
        indices = data_provider.get_indices(tabla)
        if indices:
            datos_procesados = self._process_indices_data(indices, data_provider.db_type)
            self._add_table(document, "Índices", self.headers["INDICES"], datos_procesados)
        else:
            self._add_empty_section(document, "Índices", "No se encontraron índices.")

    def _add_empty_section(self, document: Document, title: str, message: str) -> None:
        """Agrega título de sección y mensaje cuando no hay resultados."""
        document.add_heading(title, level=2)
        document.add_paragraph(message)
        document.add_paragraph("")

    def _add_database_info_section(
        self,
        document: Document,
        data_provider: Any,
        database_info_flags: list[bool],
    ) -> None:
        """Agrega una sección con información de la base de datos (versión, charset/collation).

        Args:
            document: Documento Word
            data_provider: Proveedor de metadatos (SyncDatabaseManager)
            database_info_flags: [version_flag, charset_collation_flag]
        """
        self.logger.info(f"📚 Agregando sección de información de BD con flags: {database_info_flags}")
        document.add_page_break()
        document.add_heading("Información de la Base de Datos", level=1)

        include_version: bool = bool(database_info_flags[0]) if len(database_info_flags) > 0 else False
        include_charset: bool = bool(database_info_flags[1]) if len(database_info_flags) > 1 else False

        try:
            info_data: list[list[str]] = self.__build_database_info_data(
                data_provider, include_version, include_charset
            )
            self.__render_database_info_to_document(document, info_data)
        except Exception as error:
            self.logger.exception(f"❌ Error agregando sección de información de BD: {error}")
            self._add_empty_section(
                document=document,
                title="Información de Base de Datos",
                message=f"Error al obtener información: {error}",
            )

    def __build_database_info_data(
        self,
        data_provider: Any,
        include_version: bool,
        include_charset: bool,
    ) -> list[list[str]]:
        """Construye la lista de datos de información de BD.

        Args:
            data_provider: Proveedor de metadatos
            include_version: Si incluir versión
            include_charset: Si incluir charset/collation

        Returns:
            lista de filas [etiqueta, valor]
        """
        info_data: list[list[str]] = []

        if include_version:
            self.__append_version_info(data_provider, info_data)

        if include_charset:
            self.__append_charset_info(data_provider, info_data)

        return info_data

    def __append_version_info(self, data_provider: Any, info_data: list[list[str]]) -> None:
        """Agrega información de versión a la lista de datos.

        Args:
            data_provider: Proveedor de metadatos
            info_data: lista acumulativa de datos
        """
        try:
            version = data_provider.get_database_version()
            if version and str(version).strip() != "Unknown":
                info_data.append(["Versión", str(version)])
                self.logger.debug(f"✅ Versión de BD obtenida: {version}")
            else:
                self.logger.debug("ℹ️ No hay información de versión disponible")
        except Exception as e:
            self.logger.warning(f"⚠️ Error obteniendo versión: {e}")
            info_data.append(["Versión", f"Error: {str(e)}"])

    def __append_charset_info(self, data_provider: Any, info_data: list[list[str]]) -> None:
        """Agrega información de charset/collation a la lista de datos.

        Args:
            data_provider: Proveedor de metadatos
            info_data: lista acumulativa de datos
        """
        try:
            charset_info = data_provider.get_database_charset_collation()
            if charset_info and isinstance(charset_info, dict):
                for key, value in charset_info.items():
                    if value and str(value).strip():
                        info_data.append([key.replace("_", " ").title(), str(value)])
                self.logger.debug(f"✅ Charset/Collation obtenido: {charset_info}")
            else:
                self.logger.debug("ℹ️ No hay información de charset/collation disponible")
        except Exception as e:
            self.logger.warning(f"⚠️ Error obteniendo charset/collation: {e}")
            info_data.append(["Charset/Collation", f"Error: {str(e)}"])

    def __render_database_info_to_document(self, document: Document, info_data: list[list[str]]) -> None:
        """Renderiza información de BD al documento.

        Args:
            document: Documento Word
            info_data: Datos a renderizar
        """
        if info_data:
            self._add_table(
                document=document,
                title="Propiedades",
                headers=["Propiedad", "Valor"],
                data=info_data,
            )
        else:
            self._add_empty_section(
                document=document,
                title="Información",
                message="No se configuró información de base de datos para mostrar",
            )

    def _add_storage_inventory_section(self, document: Document, data_provider: Any) -> None:
        """Agrega al final un resumen de almacenamiento físico/tablespaces."""
        document.add_page_break()
        document.add_heading("Almacenamiento", level=1)

        try:
            report: dict[str, Any] = data_provider.get_storage_inventory_report()
        except Exception as error:
            self._add_empty_section(
                document=document,
                title="Inventario de almacenamiento",
                message=f"No se pudo obtener la información de almacenamiento: {error}",
            )
            return

        sections: list[dict[str, Any]] = list(report.get("sections", []))
        summary_rows: list[list[str]] = []
        for section in sections:
            summary_rows.append(
                [
                    str(section.get("title", "")),
                    str(section.get("status", "")),
                    str(len(section.get("rows", []))),
                    str(section.get("message", "")),
                ]
            )

        if summary_rows:
            self._add_table(
                document=document,
                title="Resumen",
                headers=["Consulta", "Estado", "Filas", "Mensaje"],
                data=summary_rows,
                right_align_indices=[2],
            )

        for section in sections:
            title: str = str(section.get("title", "Consulta"))
            headers: list[str] = [str(h) for h in section.get("headers", [])]
            rows: list[list[Any]] = list(section.get("rows", []))
            if not headers and rows:
                max_cols: int = max(len(row) for row in rows)
                headers = [f"Columna {idx}" for idx in range(1, max_cols + 1)]

            if rows:
                numeric_columns: list[int] = [int(idx) for idx in section.get("numeric_columns", [])]
                self._add_table(
                    document=document,
                    title=title,
                    headers=headers,
                    data=rows,
                    right_align_indices=numeric_columns,
                )
            else:
                self._add_empty_section(
                    document=document,
                    title=title,
                    message=str(section.get("message", "Sin datos")),
                )

    def _add_table(
        self,
        document: Document,
        title: str,
        headers: list[str],
        data: list,
        right_align_indices: list[int] | None = None,
    ) -> None:
        """Agrega una tabla al documento Word"""
        align_right_set: set[int] = set(right_align_indices or [])
        document.add_heading(title, level=2)
        table: Table = document.add_table(rows=1, cols=len(headers))
        self._apply_table_style(table=table, document=document)
        self._repeat_header(table.rows[0])

        # Agregar encabezados
        hdr_cells = table.rows[0].cells
        for i, header in enumerate(headers):
            hdr_cells[i].text = header

        # Agregar datos
        for row_data in data:
            row_cells = table.add_row().cells
            max_cols = min(len(headers), len(row_data))
            for i in range(max_cols):
                val = row_data[i]
                row_cells[i].text = str(val) if val is not None else ""
                if i in align_right_set:
                    for paragraph in row_cells[i].paragraphs:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        document.add_paragraph("")

    def _apply_table_style(self, table: Table, document: Document) -> None:
        """Aplica estilo a la tabla y usa "Table Grid" por defecto si el solicitado no existe."""
        preferred_style: str = self.table_style
        fallback_styles: list[str] = ["Table Grid", "Normal Table"]

        def normalize_style_name(style_name: str) -> str:
            return " ".join(style_name.replace("–", "-").replace("—", "-").split()).casefold()

        available_styles: list[str] = [
            str(style.name) for style in document.styles if style.type is not None and style.name
        ]
        normalized_available: dict[str, str] = {
            normalize_style_name(style_name): style_name for style_name in available_styles
        }

        resolved_preferred_style: str = normalized_available.get(normalize_style_name(preferred_style), preferred_style)
        try:
            table.style = resolved_preferred_style
            return
        except KeyError:
            pass

        self.logger.warning(f"⚠️ Estilo de tabla '{preferred_style}' no disponible en el documento. Aplicando fallback.")
        for fallback_style in fallback_styles:
            resolved_style: str = normalized_available.get(normalize_style_name(fallback_style), fallback_style)
            try:
                table.style = resolved_style
                self.logger.info(f"🟢 Usando estilo de tabla de respaldo: {resolved_style}")
                return
            except KeyError:
                continue

        self.logger.warning("⚠️ No se encontró un estilo de tabla de respaldo. Se usa el estilo por defecto de Word.")

    def _repeat_header(self, row: _Row) -> None:
        """Configura la repetición de cabecera en tablas Word"""
        tr = row._tr
        tr_pr = tr.get_or_add_trPr()
        tbl_header = OxmlElement("w:tblHeader")
        tbl_header.set(qn("w:val"), "true")
        tr_pr.append(tbl_header)

    def _process_indices_data(self, indices: list, db_type: str) -> list:
        """Procesa los datos de índices según el tipo de base de datos"""
        if db_type == "mariadb":
            # MariaDB: [INDEX_NAME, COLUMN_NAME, NON_UNIQUE, INDEX_TYPE]
            return [[idx[0], idx[1], "No" if idx[2] else "Sí", idx[3]] for idx in indices]

        if db_type == "oracle":
            # Oracle: [index_name, uniqueness, index_type, column_name, column_position]
            return [[idx[0], idx[3], "Sí" if self._is_unique(idx, db_type) else "No", idx[2]] for idx in indices]

        # PostgreSQL/HSQLDB/SQL Server: [index_name, column_name, uniqueness, index_type]
        return [[idx[0], idx[1], "Sí" if self._is_unique(idx, db_type) else "No", idx[3]] for idx in indices]

    def _is_unique(self, index_data: tuple, db_type: str) -> bool:
        """Determina si un índice es único según el tipo de BD"""
        if db_type == "oracle":
            return index_data[1] == "UNIQUE"
        elif db_type == "postgresql":
            return index_data[2] is True
        elif db_type == "hsqldb":
            return index_data[2] == "UNIQUE"
        elif db_type == "sqlite":
            return str(index_data[2]).strip().lower() in ("1", "true", "yes", "unique")
        return False

    def _get_value(self, row: Any, index: int, as_str: bool = False) -> Any:
        """
        Obtiene un valor por índice de forma segura.

        Args:
            row: Fila origen
            index: Índice a leer
            as_str: Si True convierte a string cuando no es None

        Returns:
            Valor seguro o cadena vacía
        """
        if len(row) <= index:
            return ""

        value = row[index]
        if as_str:
            return str(value) if value is not None else ""

        return value if value is not None else ""

    def _format_column_row(self, col: Any, specs: list[tuple[int, bool]]) -> list[Any]:
        """
        Formatea una fila de metadatos de columna según especificación.

        Args:
            col: Fila original de columna
            specs: lista de tuplas (index, as_str)

        Returns:
            lista formateada
        """
        return [self._get_value(col, idx, as_str=as_str) for idx, as_str in specs]

    def _process_columns_data(self, columnas: list, db_type: str) -> list:
        """Procesa los datos de columnas para reordenarlos según el tipo de BD"""
        specs_by_db: dict[str, list[tuple[int, bool]]] = {
            # MariaDB: [Campo, Tipo, Nulo, Clave, Por defecto, Extra, Comentario]
            "mariadb": [
                (0, False),
                (1, False),
                (2, False),
                (3, False),
                (4, False),
                (5, False),
                (6, False),
            ],
            # Oracle: [Campo, Tipo, Nulo, Por defecto, Longitud, Precisión, Escala, Comentario]
            "oracle": [
                (0, False),
                (1, False),
                (2, False),
                (3, True),
                (4, True),
                (5, True),
                (6, True),
                (7, True),
            ],
            # PostgreSQL: [Campo, Tipo, Nulo, Por defecto, Longitud, Precisión, Escala, Comentario]
            "postgresql": [
                (0, False),
                (1, False),
                (2, False),
                (3, True),
                (4, True),
                (5, True),
                (6, True),
                (7, True),
            ],
            # HSQLDB: [Campo, Tipo, Nulo, Por defecto, Longitud, Precisión, Escala, Comentario]
            "hsqldb": [
                (0, False),
                (1, False),
                (2, False),
                (3, True),
                (4, True),
                (5, True),
                (6, True),
                (7, True),
            ],
            # SQLite: [Campo, Tipo, Nulo, Por defecto, Longitud, Precisión, Comentario]
            "sqlite": [
                (0, False),
                (1, False),
                (2, False),
                (3, True),
                (4, True),
                (5, True),
                (7, True),
            ],
            # SQL Server: [Campo, Tipo, Nulo, Es Identity, Por defecto, Longitud, Precisión, Escala, Comentario]
            "sqlserver": [
                (0, False),
                (1, False),
                (2, False),
                (3, True),
                (4, True),
                (5, True),
                (6, True),
                (7, True),
                (8, True),
            ],
        }

        # Fallback genérico: [Campo, Tipo, Nulo, Por defecto, Longitud, Precisión, Escala, Comentario]
        default_specs: list[tuple[int, bool]] = [
            (0, False),
            (1, False),
            (2, False),
            (3, True),
            (4, True),
            (5, True),
            (6, True),
            (7, True),
        ]
        specs: list[tuple[int, bool]] = specs_by_db.get(db_type, default_specs)

        return [self._format_column_row(col, specs) for col in columnas]
