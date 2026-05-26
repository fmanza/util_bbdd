"""Reporter de SchemaDiff en formato Word usando python-docx.

El documento está compactado al máximo: no se usan párrafos vacíos como
separadores; el espaciado se controla con ``paragraph_format.space_before``
y ``space_after`` directamente sobre cada elemento.
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, ClassVar

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

if TYPE_CHECKING:
    from pathlib import Path

    from docx.document import Document as DocumentType
    from docx.table import Table, _Cell

    from util_bbdd.comparar.models import RoutineDiff, SchemaDiff, TableDiff, ViewDiff

from util_bbdd._core.exceptions import SchemaDiffValidationError
from util_bbdd.comparar.reporters._base import STATUS_ES, DdlNormalizer, build_diff_summary


class WordDiffReporter:
    """Genera un reporte Word compacto del SchemaDiff con tablas formateadas.

    Implementa ``DiffReporterProtocol``.

    El documento incluye:
    - Portada con labels origen/destino y resumen numérico.
    - Sección de tablas con columnas, índices, FKs y comentarios.
    - Sección de vistas con DDL en bloque de código.
    - Sección de rutinas con DDL en bloque de código.

    El espaciado se gestiona con ``paragraph_format`` — no se insertan
    párrafos vacíos como separadores.

    Args:
        template_path: Ruta opcional a una plantilla Word (``.dotx`` o ``.docx``).
            Si se proporciona, el documento se crea a partir de esa plantilla.
            Si es ``None`` se usa un documento en blanco con formato A4.
    """

    # Colores de TEXTO por estado — oscuros, WCAG AA sobre fondos de celda.
    _COLOR_ADDED: ClassVar[RGBColor] = RGBColor(0x16, 0x65, 0x34)  # #166534
    _COLOR_REMOVED: ClassVar[RGBColor] = RGBColor(0x99, 0x1B, 0x1B)  # #991B1B
    _COLOR_MODIFIED: ClassVar[RGBColor] = RGBColor(0x78, 0x35, 0x0F)  # #78350F

    _STATUS_TEXT_COLOR: ClassVar[dict[str, RGBColor]] = {
        "added": RGBColor(0x16, 0x65, 0x34),
        "removed": RGBColor(0x99, 0x1B, 0x1B),
        "modified": RGBColor(0x78, 0x35, 0x0F),
    }

    # Colores de FONDO de celda — distinguibles en escala de grises.
    _STATUS_HEX: ClassVar[dict[str, str]] = {
        "added": "BBF7D0",
        "removed": "FECACA",
        "modified": "FDE68A",
    }

    _HEADER_HEX: ClassVar[str] = "1E3A5F"
    _TABLE_STYLE: ClassVar[str] = "Table Grid"

    def __init__(self, template_path: Path | None = None) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._template_path: Path | None = template_path

    def render(self, diff: SchemaDiff, output: Path) -> Path:
        """Genera el fichero ``.docx`` en la ruta indicada.

        Args:
            diff: Resultado de la comparación de esquemas.
            output: Ruta **completa** del fichero ``.docx`` a generar,
                incluyendo nombre y extensión (p.ej. ``reports/diff.docx``).

        Returns:
            La ruta del fichero generado.

        Raises:
            ValueError: Si ``output`` no tiene extensión.
        """
        if not output.suffix:
            msg = (
                f"'output' debe ser la ruta completa del fichero .docx, "
                f"no un directorio. Recibido: {output!r}\n"
                f"Ejemplo correcto: {output / 'diff.docx'!r}"
            )
            raise SchemaDiffValidationError(
                msg,
                operation="WordDiffReporter.render",
                details=f"output_path={output}, suffix={output.suffix!r}",
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        summary = build_diff_summary(diff)

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
        self.logger.info("Word diff report generado: %s", output)
        return output

    # ------------------------------------------------------------------
    # Inicialización del documento
    # ------------------------------------------------------------------

    @staticmethod
    def _open_from_template(template_path: Path) -> DocumentType:
        """Abre una plantilla Word para usarla como base del documento."""
        resolved: Path = template_path.expanduser().resolve()
        if not resolved.exists():
            msg = f"Plantilla no encontrada: {resolved}"
            raise FileNotFoundError(msg)
        if not resolved.is_file():
            msg = f"La plantilla no es un archivo válido: {resolved}"
            raise FileNotFoundError(msg)
        # Note: This is a static method, so we cannot use self.logger here
        # The logger call will be handled by the caller via the instance
        logging.getLogger(__name__).info("Cargando plantilla Word: %s", resolved)
        return Document(str(resolved))

    @staticmethod
    def _setup_page(doc: DocumentType) -> None:
        """Ajusta el tamaño de página a A4."""
        section = doc.sections[0]
        section.page_width = Mm(210)
        section.page_height = Mm(297)

    # ------------------------------------------------------------------
    # Helpers de formato de celda
    # ------------------------------------------------------------------

    @staticmethod
    def _set_cell_shading(cell: _Cell, hex_color: str) -> None:
        """Aplica color de fondo a una celda de tabla Word (OOXML)."""
        tc = cell._tc  # noqa: SLF001 — API interna de python-docx necesaria para OOXML shading
        tc_pr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), hex_color)
        tc_pr.append(shd)

    def _add_header_row(self, table: Table, headers: list[str]) -> None:
        """Rellena la primera fila como cabecera con fondo oscuro."""
        row = table.rows[0]
        for idx, text in enumerate(headers):
            cell = row.cells[idx]
            cell.text = text
            self._set_cell_shading(cell, self._HEADER_HEX)
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                para.paragraph_format.space_before = Pt(1)
                para.paragraph_format.space_after = Pt(1)
                for run in para.runs:
                    run.bold = True
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    run.font.size = Pt(8)

    def _add_data_row(self, table: Table, values: list[str], status: str | None = None) -> None:
        """Añade una fila de datos con color de fondo opcional por estado."""
        row = table.add_row()
        hex_bg = self._STATUS_HEX.get(status or "", "") if status else ""
        for idx, val in enumerate(values):
            cell = row.cells[idx]
            cell.text = val
            if hex_bg:
                self._set_cell_shading(cell, hex_bg)
            for para in cell.paragraphs:
                para.alignment = WD_ALIGN_PARAGRAPH.LEFT
                para.paragraph_format.space_before = Pt(1)
                para.paragraph_format.space_after = Pt(1)
                for run in para.runs:
                    run.font.size = Pt(7)

    # ------------------------------------------------------------------
    # Helpers de contenido inline
    # ------------------------------------------------------------------

    def _mini_heading(self, doc: DocumentType, text: str) -> None:
        """Encabezado de subsección compacto."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(1)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)

    @staticmethod
    def _code_block(doc: DocumentType, code: str) -> None:
        """Bloque de código con fuente monoespaciada."""
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(code)
        run.font.name = "Courier New"
        run.font.size = Pt(7)

    # ------------------------------------------------------------------
    # Secciones del documento
    # ------------------------------------------------------------------

    def _add_title(self, doc: DocumentType, diff: SchemaDiff, summary: object) -> None:
        title_para = doc.add_paragraph()
        title_para.paragraph_format.space_before = Pt(0)
        title_para.paragraph_format.space_after = Pt(6)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run("Reporte de diferencias de esquema")
        title_run.bold = True
        title_run.font.size = Pt(16)

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

    def _add_columns_table(self, doc: DocumentType, column_diffs: tuple) -> None:
        """Renderiza tabla de diferencias de columnas."""
        self._mini_heading(doc, f"Columnas ({len(column_diffs)})")
        tbl: Table = doc.add_table(rows=1, cols=4)
        tbl.style = self._TABLE_STYLE
        self._add_header_row(tbl, ["Columna", "Atributo", "Valor origen", "Valor destino"])
        for cd in column_diffs:
            self._add_data_row(tbl, [cd.column_name, cd.attribute, cd.source_value, cd.target_value])

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

    def _add_comments_table(self, doc: DocumentType, comment_diffs: tuple) -> None:
        """Renderiza tabla de diferencias de comentarios."""
        self._mini_heading(doc, f"Comentarios ({len(comment_diffs)})")
        tbl: Table = doc.add_table(rows=1, cols=4)
        tbl.style = self._TABLE_STYLE
        self._add_header_row(tbl, ["Objeto", "Columna", "Comentario origen", "Comentario destino"])
        for cm in comment_diffs:
            self._add_data_row(
                tbl,
                [
                    cm.object_name,
                    cm.column_name or "(tabla)",
                    cm.source_comment,
                    cm.target_comment,
                ],
            )

    def _add_table_heading(self, doc: DocumentType, td: TableDiff) -> None:
        """Encabezado de tabla con nombre y estado coloreado."""
        estado = STATUS_ES.get(td.status, td.status)
        sub = doc.add_paragraph()
        sub.paragraph_format.space_before = Pt(8)
        sub.paragraph_format.space_after = Pt(2)
        sub_run = sub.add_run(f"{td.table_name}  —  {estado}")
        sub_run.bold = True
        sub_run.font.size = Pt(10)
        if td.status in self._STATUS_TEXT_COLOR:
            sub_run.font.color.rgb = self._STATUS_TEXT_COLOR[td.status]

    def _add_table_details(self, doc: DocumentType, td: TableDiff) -> None:
        """Encabezado + subtablas de columnas, índices, FKs y comentarios."""
        self._add_table_heading(doc, td)
        if td.column_diffs:
            self._add_columns_table(doc, td.column_diffs)
        if td.index_diffs:
            self._add_indices_table(doc, td.index_diffs)
        if td.fk_diffs:
            self._add_fk_table(doc, td.fk_diffs)
        if td.comment_diffs:
            self._add_comments_table(doc, td.comment_diffs)

    def _add_tables_section(self, doc: DocumentType, table_diffs: tuple[TableDiff, ...]) -> None:
        """Emite tres secciones Heading 1: añadidas, eliminadas y modificadas."""
        groups: list[tuple[str, str]] = [
            ("added", "Tablas añadidas"),
            ("removed", "Tablas eliminadas"),
            ("modified", "Tablas modificadas"),
        ]
        for status, label in groups:
            subset = [td for td in table_diffs if td.status == status]
            if not subset:
                continue
            doc.add_heading(label, level=1)
            for td in subset:
                self._add_table_details(doc, td)

    def _add_views_section(self, doc: DocumentType, view_diffs: tuple[ViewDiff, ...]) -> None:
        doc.add_heading("Vistas con diff", level=1)
        for vd in view_diffs:
            estado = STATUS_ES.get(vd.status, vd.status)
            sub = doc.add_paragraph()
            sub.paragraph_format.space_before = Pt(6)
            sub.paragraph_format.space_after = Pt(2)
            sub.add_run(f"{vd.view_name}  —  {estado}").bold = True

            if vd.source_definition:
                self._mini_heading(doc, "Definición origen")
                self._code_block(doc, DdlNormalizer.normalize_view_ddl(vd.source_definition))
            if vd.target_definition:
                self._mini_heading(doc, "Definición destino")
                self._code_block(doc, DdlNormalizer.normalize_view_ddl(vd.target_definition))

    def _add_routines_section(self, doc: DocumentType, routine_diffs: tuple[RoutineDiff, ...]) -> None:
        doc.add_heading("Rutinas con diff", level=1)
        for rd in routine_diffs:
            estado = STATUS_ES.get(rd.status, rd.status)
            sub = doc.add_paragraph()
            sub.paragraph_format.space_before = Pt(6)
            sub.paragraph_format.space_after = Pt(2)
            sub.add_run(f"{rd.routine_name} ({rd.routine_type})  —  {estado}").bold = True

            if rd.source_definition:
                self._mini_heading(doc, "Definición origen")
                self._code_block(doc, DdlNormalizer.normalize_routine_ddl(rd.source_definition))
            if rd.target_definition:
                self._mini_heading(doc, "Definición destino")
                self._code_block(doc, DdlNormalizer.normalize_routine_ddl(rd.target_definition))
