"""Reporter de SchemaDiff en formato Word usando python-docx."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import ClassVar

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tc, CT_TcPr
from docx.section import Section
from docx.shared import Mm, Pt, RGBColor
from docx.table import Table, _Cell, _Row
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from util_bbdd.comparar.reporters._base import DiffSummary

from ..models import RoutineDiff, SchemaDiff, TableDiff, ViewDiff
from ._base import STATUS_ES, build_diff_summary

logger: logging.Logger = logging.getLogger(__name__)


class WordDiffReporter:
    """Genera un reporte Word del SchemaDiff con tablas formateadas.

    Implementa ``DiffReporterProtocol``.

    El documento incluye:
    - Portada con labels origen/destino y resumen numérico.
    - Sección de tablas con columnas, índices, FKs y comentarios.
    - Sección de vistas con DDL en bloque de código.
    - Sección de rutinas con DDL en bloque de código.

    Args:
        template_path: Ruta opcional a una plantilla Word (``.dotx`` o ``.docx``).
            Si se proporciona, el documento se crea a partir de esa plantilla
            (estilos, márgenes y cabeceras/pies de la plantilla quedan activos).
            Si es ``None`` se usa un documento en blanco con formato A4.
    """

    # Colores de TEXTO por estado — oscuros, legibles sobre fondo blanco y en impresión B&W.
    # Cumple WCAG AA (ratio > 4.5:1 sobre sus respectivos fondos de celda).
    _COLOR_ADDED: ClassVar[RGBColor] = RGBColor(0x16, 0x65, 0x34)  # verde oscuro  (#166534)
    _COLOR_REMOVED: ClassVar[RGBColor] = RGBColor(0x99, 0x1B, 0x1B)  # rojo oscuro   (#991B1B)
    _COLOR_MODIFIED: ClassVar[RGBColor] = RGBColor(0x78, 0x35, 0x0F)  # ámbar oscuro (#78350F)
    _COLOR_HEADER: ClassVar[RGBColor] = RGBColor(0x1E, 0x3A, 0x5F)  # azul oscuro   (#1E3A5F)

    _STATUS_TEXT_COLOR: ClassVar[dict[str, RGBColor]] = {
        "added": RGBColor(0x16, 0x65, 0x34),
        "removed": RGBColor(0x99, 0x1B, 0x1B),
        "modified": RGBColor(0x78, 0x35, 0x0F),
    }

    # Colores de FONDO de celda — distinguibles en impresión en escala de grises.
    _STATUS_HEX: ClassVar[dict[str, str]] = {
        "added": "BBF7D0",  # verde medio  — ~87 % L
        "removed": "FECACA",  # rojo medio   — ~90 % L
        "modified": "FDE68A",  # ámbar medio  — ~93 % L
    }

    _HEADER_HEX: ClassVar[str] = "1E3A5F"
    _TABLE_STYLE: ClassVar[str] = "Table Grid"

    def __init__(self, template_path: Path | None = None) -> None:
        self._template_path: Path | None = template_path

    def render(self, diff: SchemaDiff, output: Path) -> Path:
        """Genera el fichero ``.docx`` en la ruta indicada.

        Args:
            diff: Resultado de la comparación de esquemas.
            output: Ruta **completa** del fichero ``.docx`` a generar,
                incluyendo nombre y extensión (p.ej. ``reports/diff.docx``).
                Pasar un directorio provoca ``PermissionError`` en el guardado.

        Returns:
            La ruta del fichero generado.

        Raises:
            ValueError: Si ``output`` no tiene extensión (es probable que sea
                un directorio en lugar de un fichero).
        """
        if not output.suffix:
            raise ValueError(
                f"'output' debe ser la ruta completa del fichero .docx, "
                f"no un directorio. Recibido: {output!r}\n"
                f"Ejemplo correcto: {output / 'diff.docx'!r}"
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        summary: DiffSummary = build_diff_summary(diff)

        if self._template_path is not None:
            doc: DocumentType = self._open_from_template(self._template_path)
        else:
            doc = Document()
            self._setup_page(doc)

        self._add_title(doc, diff, summary)
        if diff.table_diffs:
            self._add_tables_section(doc, diff.table_diffs)
        if diff.view_diffs:
            self._add_views_section(doc, diff.view_diffs)
        if diff.routine_diffs:
            self._add_routines_section(doc, diff.routine_diffs)

        doc.save(str(output))
        logger.info("Word diff report generado: %s", output)
        return output

    # ------------------------------------------------------------------
    # Inicialización del documento
    # ------------------------------------------------------------------

    @staticmethod
    def _open_from_template(template_path: Path) -> DocumentType:
        """Abre una plantilla Word para usarla como base del documento.

        Args:
            template_path: Ruta al fichero ``.docx`` o ``.dotx``.

        Returns:
            Documento Word listo para recibir contenido nuevo.

        Raises:
            FileNotFoundError: Si la ruta no existe o no es un fichero.
        """
        resolved: Path = template_path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Plantilla no encontrada: {resolved}")
        if not resolved.is_file():
            raise FileNotFoundError(f"La plantilla no es un archivo válido: {resolved}")
        logger.info("Cargando plantilla Word: %s", resolved)
        return Document(str(resolved))

    @staticmethod
    def _setup_page(doc: DocumentType) -> None:
        """Ajusta el tamaño de página a A4."""
        section: Section = doc.sections[0]
        section.page_width = Mm(210)
        section.page_height = Mm(297)

    # ------------------------------------------------------------------
    # Helpers de formato de celda y fila
    # ------------------------------------------------------------------

    @staticmethod
    def _set_cell_shading(cell: _Cell, hex_color: str) -> None:
        """Aplica color de fondo a una celda de tabla Word (OOXML)."""
        tc: CT_Tc = cell._tc
        tc_pr: CT_TcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hex_color)
        tc_pr.append(shd)

    def _add_header_row(self, table: Table, headers: list[str]) -> None:
        """Rellena la primera fila de una tabla Word como cabecera."""
        row: _Row = table.rows[0]
        for idx, text in enumerate(headers):
            cell: _Cell = row.cells[idx]
            cell.text = text
            self._set_cell_shading(cell, self._HEADER_HEX)
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in para.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    run.font.size = Pt(9)

    def _add_data_row(self, table: Table, values: list[str], status: str | None = None) -> None:
        """Añade una fila de datos a la tabla Word con color de fondo opcional."""
        row: _Row = table.add_row()
        hex_bg: str = self._STATUS_HEX.get(status or "", "") if status else ""
        for idx, val in enumerate(values):
            cell: _Cell = row.cells[idx]
            cell.text = val
            if hex_bg:
                self._set_cell_shading(cell, hex_bg)
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in para.runs:
                    run.font.size = Pt(8)

    # ------------------------------------------------------------------
    # Helpers de contenido inline
    # ------------------------------------------------------------------

    @staticmethod
    def _mini_heading(doc: DocumentType, text: str) -> None:
        """Renderiza un encabezado de sección secundaria."""
        p: Paragraph = doc.add_paragraph()
        run: Run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

    @staticmethod
    def _code_block(doc: DocumentType, code: str) -> None:
        """Renderiza un bloque de código con fuente monoespaciada."""
        p: Paragraph = doc.add_paragraph()
        run: Run = p.add_run(code)
        run.font.name = "Courier New"
        run.font.size = Pt(8)

    # ------------------------------------------------------------------
    # Secciones del documento
    # ------------------------------------------------------------------

    def _add_title(self, doc: DocumentType, diff: SchemaDiff, summary: object) -> None:
        title_para: Paragraph = doc.add_paragraph()
        title_run: Run = title_para.add_run("Reporte de diferencias de esquema")
        title_run.bold = True
        title_run.font.size = Pt(18)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()
        meta_table: Table = doc.add_table(rows=1, cols=2)
        meta_table.style = self._TABLE_STYLE
        self._add_header_row(meta_table, ["Concepto", "Valor"])

        meta_rows: list[tuple[str, str]] = [
            ("Origen", diff.source_label),
            ("Destino", diff.target_label),
            ("Tablas añadidas", str(summary.tables_added)),  # type: ignore[attr-defined]
            ("Tablas eliminadas", str(summary.tables_removed)),  # type: ignore[attr-defined]
            ("Tablas modificadas", str(summary.tables_modified)),  # type: ignore[attr-defined]
            ("Vistas con diff", str(summary.total_views)),  # type: ignore[attr-defined]
            ("Rutinas con diff", str(summary.total_routines)),  # type: ignore[attr-defined]
        ]
        if diff.summary:
            meta_rows.append(("Resumen", diff.summary))

        for key, val in meta_rows:
            self._add_data_row(meta_table, [key, val])

        doc.add_paragraph()

    def _add_columns_table(self, doc: DocumentType, column_diffs: tuple) -> None:
        """Renderiza tabla de diferencias de columnas."""
        self._mini_heading(doc, f"Columnas ({len(column_diffs)})")
        tbl: Table = doc.add_table(rows=1, cols=4)
        tbl.style = self._TABLE_STYLE
        self._add_header_row(tbl, ["Columna", "Atributo", "Valor origen", "Valor destino"])
        for cd in column_diffs:
            self._add_data_row(tbl, [cd.column_name, cd.attribute, cd.source_value, cd.target_value])
        doc.add_paragraph()

    def _add_indices_table(self, doc: DocumentType, index_diffs: tuple) -> None:
        """Renderiza tabla de diferencias de índices."""
        self._mini_heading(doc, f"Índices ({len(index_diffs)})")
        tbl: Table = doc.add_table(rows=1, cols=4)
        tbl.style = self._TABLE_STYLE
        self._add_header_row(tbl, ["Índice", "Estado", "Cols origen", "Cols destino"])
        for idx in index_diffs:
            self._add_data_row(
                tbl,
                [
                    idx.index_name,
                    STATUS_ES.get(idx.status, idx.status) or idx.status,
                    idx.source_columns,
                    idx.target_columns,
                ],
                status=idx.status,
            )
        doc.add_paragraph()

    def _add_fk_table(self, doc: DocumentType, fk_diffs: tuple) -> None:
        """Renderiza tabla de diferencias de Foreign Keys."""
        self._mini_heading(doc, f"Foreign Keys ({len(fk_diffs)})")
        tbl: Table = doc.add_table(rows=1, cols=5)
        tbl.style = self._TABLE_STYLE
        self._add_header_row(tbl, ["FK", "Estado", "Cols origen", "Tabla ref. origen", "Tabla ref. destino"])
        for fk in fk_diffs:
            self._add_data_row(
                tbl,
                [
                    fk.fk_name,
                    STATUS_ES.get(fk.status, fk.status) or fk.status,
                    fk.source_columns,
                    fk.source_referred_table,
                    fk.target_referred_table,
                ],
                status=fk.status,
            )
        doc.add_paragraph()

    def _add_comments_table(self, doc: DocumentType, comment_diffs: tuple) -> None:
        """Renderiza tabla de diferencias de comentarios."""
        self._mini_heading(doc, f"Comentarios ({len(comment_diffs)})")
        tbl: Table = doc.add_table(rows=1, cols=4)
        tbl.style = self._TABLE_STYLE
        self._add_header_row(tbl, ["Objeto", "Columna", "Comentario origen", "Comentario destino"])
        for cm in comment_diffs:
            self._add_data_row(
                tbl,
                [cm.object_name, cm.column_name or "(tabla)", cm.source_comment, cm.target_comment],
            )
        doc.add_paragraph()

    def _add_table_heading(self, doc: DocumentType, td: TableDiff) -> None:
        """Renderiza encabezado de tabla con nombre y estado."""
        estado: str = STATUS_ES.get(td.status, td.status)
        sub: Paragraph = doc.add_paragraph()
        sub_run: Run = sub.add_run(f"{td.table_name}  —  {estado}")
        sub_run.bold = True
        sub_run.font.size = Pt(11)
        if td.status in self._STATUS_TEXT_COLOR:
            sub_run.font.color.rgb = self._STATUS_TEXT_COLOR[td.status]

    def _add_tables_section(self, doc: DocumentType, table_diffs: tuple[TableDiff, ...]) -> None:
        heading: Paragraph = doc.add_paragraph()
        run: Run = heading.add_run(f"Tablas ({len(table_diffs)})")
        run.bold = True
        run.font.size = Pt(14)

        for td in table_diffs:
            self._add_table_heading(doc, td)

            if td.column_diffs:
                self._add_columns_table(doc, td.column_diffs)
            if td.index_diffs:
                self._add_indices_table(doc, td.index_diffs)
            if td.fk_diffs:
                self._add_fk_table(doc, td.fk_diffs)
            if td.comment_diffs:
                self._add_comments_table(doc, td.comment_diffs)

            doc.add_paragraph()

    def _add_views_section(self, doc: DocumentType, view_diffs: tuple[ViewDiff, ...]) -> None:
        heading: Paragraph = doc.add_paragraph()
        run: Run = heading.add_run(f"Vistas ({len(view_diffs)})")
        run.bold = True
        run.font.size = Pt(14)

        for vd in view_diffs:
            estado: str = STATUS_ES.get(vd.status, vd.status)
            sub: Paragraph = doc.add_paragraph()
            sub.add_run(f"{vd.view_name}  —  {estado}").bold = True

            if vd.source_definition:
                self._mini_heading(doc, "Definición origen")
                self._code_block(doc, vd.source_definition)
            if vd.target_definition:
                self._mini_heading(doc, "Definición destino")
                self._code_block(doc, vd.target_definition)
            doc.add_paragraph()

    def _add_routines_section(self, doc: DocumentType, routine_diffs: tuple[RoutineDiff, ...]) -> None:
        heading: Paragraph = doc.add_paragraph()
        run: Run = heading.add_run(f"Rutinas ({len(routine_diffs)})")
        run.bold = True
        run.font.size = Pt(14)

        for rd in routine_diffs:
            estado: str = STATUS_ES.get(rd.status, rd.status)
            sub: Paragraph = doc.add_paragraph()
            sub.add_run(f"{rd.routine_name} ({rd.routine_type})  —  {estado}").bold = True

            if rd.source_definition:
                self._mini_heading(doc, "Definición origen")
                self._code_block(doc, rd.source_definition)
            if rd.target_definition:
                self._mini_heading(doc, "Definición destino")
                self._code_block(doc, rd.target_definition)
            doc.add_paragraph()
