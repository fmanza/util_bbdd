"""Tests unitarios para los reporters de SchemaDiff.

Verifican que cada reporter produce un fichero con el contenido esperado
usando datos sintéticos (sin conexión a BD).
"""

from __future__ import annotations

import zipfile

from pathlib import Path

import pytest

from util_bbdd.comparar.models import (
    ColumnDiff,
    CommentDiff,
    ForeignKeyDiff,
    IndexDiff,
    RoutineDiff,
    SchemaDiff,
    TableDiff,
    ViewDiff,
)
from util_bbdd.comparar.reporters import (
    ExcelDiffReporter,
    HtmlDiffReporter,
    MarkdownDiffReporter,
    SchemaDiffReporter,
    WordDiffReporter,
)
from util_bbdd.comparar.reporters._base import (
    build_diff_summary,
    build_output_stem,
    escape_mermaid_label,
    sanitize_filename,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_diff() -> SchemaDiff:
    """SchemaDiff sin diferencias."""
    return SchemaDiff(source_label="DB_A", target_label="DB_B")


@pytest.fixture()
def rich_diff() -> SchemaDiff:
    """SchemaDiff con un ejemplo completo de cada tipo de diferencia."""
    return SchemaDiff(
        source_label="prod",
        target_label="staging",
        summary="Comparación de entornos",
        table_diffs=(
            TableDiff(
                table_name="users",
                status="modified",
                column_diffs=(
                    ColumnDiff(
                        column_name="email",
                        attribute="type",
                        source_value="VARCHAR(100)",
                        target_value="VARCHAR(255)",
                    ),
                    ColumnDiff(
                        column_name="deleted_at",
                        attribute="existence",
                        source_value="present",
                        target_value="absent",
                    ),
                ),
                index_diffs=(
                    IndexDiff(
                        index_name="idx_email",
                        table_name="users",
                        status="modified",
                        source_columns="email",
                        target_columns="email, created_at",
                        source_unique=True,
                        target_unique=False,
                    ),
                ),
                fk_diffs=(
                    ForeignKeyDiff(
                        fk_name="fk_users_company",
                        table_name="users",
                        status="added",
                        target_columns="company_id",
                        target_referred_table="companies",
                    ),
                ),
                comment_diffs=(
                    CommentDiff(
                        object_name="users",
                        column_name="email",
                        source_comment="Email del usuario",
                        target_comment="Dirección de correo",
                    ),
                ),
            ),
            TableDiff(table_name="orders_archive", status="added"),
            TableDiff(table_name="legacy_log", status="removed"),
        ),
        view_diffs=(
            ViewDiff(
                view_name="v_active_users",
                status="modified",
                source_definition="SELECT * FROM users WHERE active=1",
                target_definition="SELECT id, name FROM users WHERE active=1",
            ),
        ),
        routine_diffs=(
            RoutineDiff(
                routine_name="sp_cleanup",
                routine_type="PROCEDURE",
                status="removed",
                source_definition="BEGIN DELETE FROM legacy_log; END",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Tests de utilidades base
# ---------------------------------------------------------------------------


class TestBase:
    def test_sanitize_filename_special_chars(self) -> None:
        assert sanitize_filename("DB/prod:2026") == "DB_prod_2026"

    def test_sanitize_filename_truncation(self) -> None:
        long_name = "a" * 100
        assert len(sanitize_filename(long_name)) == 64

    def test_build_output_stem(self, empty_diff: SchemaDiff) -> None:
        assert build_output_stem(empty_diff) == "DB_A_vs_DB_B_diff"

    def test_escape_mermaid_label(self) -> None:
        assert '"' not in escape_mermaid_label('table"name')
        assert "[" not in escape_mermaid_label("table[name]")

    def test_build_diff_summary_empty(self, empty_diff: SchemaDiff) -> None:
        s = build_diff_summary(empty_diff)
        assert s.tables_added == 0
        assert s.total_tables == 0
        assert not s.has_differences

    def test_build_diff_summary_rich(self, rich_diff: SchemaDiff) -> None:
        s = build_diff_summary(rich_diff)
        assert s.tables_added == 1
        assert s.tables_removed == 1
        assert s.tables_modified == 1
        assert s.total_views == 1
        assert s.total_routines == 1
        assert s.has_differences


# ---------------------------------------------------------------------------
# Tests de MarkdownDiffReporter
# ---------------------------------------------------------------------------


class TestMarkdownDiffReporter:
    def test_render_empty_diff(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        output = tmp_path / "diff.md"
        result = MarkdownDiffReporter().render(empty_diff, output)
        assert result == output
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "DB_A" in content
        assert "DB_B" in content
        assert "Sin diferencias" in content

    def test_render_rich_diff(self, tmp_path: Path, rich_diff: SchemaDiff) -> None:
        output = tmp_path / "diff.md"
        MarkdownDiffReporter().render(rich_diff, output)
        content = output.read_text(encoding="utf-8")
        # Diagrama Mermaid presente
        assert "```mermaid" in content
        assert "graph LR" in content
        # Tablas
        assert "users" in content
        assert "orders_archive" in content
        assert "legacy_log" in content
        # Columnas
        assert "email" in content
        assert "VARCHAR(100)" in content
        # Vistas
        assert "v_active_users" in content
        # Rutinas
        assert "sp_cleanup" in content

    def test_render_creates_parent_dir(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        output = tmp_path / "nested" / "dir" / "diff.md"
        MarkdownDiffReporter().render(empty_diff, output)
        assert output.exists()

    def test_summary_line_in_markdown(self, tmp_path: Path, rich_diff: SchemaDiff) -> None:
        output = tmp_path / "diff.md"
        MarkdownDiffReporter().render(rich_diff, output)
        content = output.read_text(encoding="utf-8")
        assert "Comparación de entornos" in content


# ---------------------------------------------------------------------------
# Tests de HtmlDiffReporter
# ---------------------------------------------------------------------------


class TestHtmlDiffReporter:
    def test_render_empty_diff(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        output = tmp_path / "diff.html"
        result = HtmlDiffReporter().render(empty_diff, output)
        assert result == output
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "DB_A" in content
        assert "DB_B" in content

    def test_render_rich_diff(self, tmp_path: Path, rich_diff: SchemaDiff) -> None:
        output = tmp_path / "diff.html"
        HtmlDiffReporter().render(rich_diff, output)
        content = output.read_text(encoding="utf-8")
        # Contiene el diagrama Mermaid
        assert "mermaid" in content
        # Tablas presentes
        assert "users" in content
        assert "orders_archive" in content
        # DDL de vista escapado
        assert "v_active_users" in content
        # Script Mermaid CDN
        assert "cdn.jsdelivr.net" in content

    def test_ddl_is_html_escaped(self, tmp_path: Path) -> None:
        """Verifica que el DDL con caracteres peligrosos se escapa en HTML."""
        diff = SchemaDiff(
            source_label="A",
            target_label="B",
            view_diffs=(
                ViewDiff(
                    view_name="v_xss",
                    status="modified",
                    source_definition="<script>alert(1)</script>",
                ),
            ),
        )
        output = tmp_path / "diff.html"
        HtmlDiffReporter().render(diff, output)
        content = output.read_text(encoding="utf-8")
        assert "<script>alert(1)</script>" not in content
        assert "&lt;script&gt;" in content


# ---------------------------------------------------------------------------
# Tests de ExcelDiffReporter
# ---------------------------------------------------------------------------


class TestExcelDiffReporter:
    def test_render_empty_diff(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        output = tmp_path / "diff.xlsx"
        result = ExcelDiffReporter().render(empty_diff, output)
        assert result == output
        assert output.exists()
        # Es un ZIP válido (xlsx)
        assert zipfile.is_zipfile(output)

    def test_render_rich_diff_sheets(self, tmp_path: Path, rich_diff: SchemaDiff) -> None:
        import openpyxl

        output = tmp_path / "diff.xlsx"
        ExcelDiffReporter().render(rich_diff, output)
        wb = openpyxl.load_workbook(output)
        sheet_names = wb.sheetnames
        assert "Resumen" in sheet_names
        assert "Tablas" in sheet_names
        assert "Columnas" in sheet_names
        assert "Indices" in sheet_names
        assert "ForeignKeys" in sheet_names
        assert "Vistas" in sheet_names
        assert "Rutinas" in sheet_names

    def test_summary_sheet_content(self, tmp_path: Path, rich_diff: SchemaDiff) -> None:
        import openpyxl

        output = tmp_path / "diff.xlsx"
        ExcelDiffReporter().render(rich_diff, output)
        wb = openpyxl.load_workbook(output)
        ws = wb["Resumen"]
        values = [str(row[1].value or "") for row in ws.iter_rows(min_row=2)]
        assert "prod" in values
        assert "staging" in values

    def test_render_empty_diff_no_extra_sheets(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        import openpyxl

        output = tmp_path / "diff.xlsx"
        ExcelDiffReporter().render(empty_diff, output)
        wb = openpyxl.load_workbook(output)
        # Solo Resumen cuando no hay diferencias
        assert wb.sheetnames == ["Resumen"]


# ---------------------------------------------------------------------------
# Tests de WordDiffReporter
# ---------------------------------------------------------------------------


class TestWordDiffReporter:
    def test_render_empty_diff(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        output = tmp_path / "diff.docx"
        result = WordDiffReporter().render(empty_diff, output)
        assert result == output
        assert output.exists()
        # docx es un ZIP válido
        assert zipfile.is_zipfile(output)

    def test_render_rich_diff_content(self, tmp_path: Path, rich_diff: SchemaDiff) -> None:
        from docx import Document

        output = tmp_path / "diff.docx"
        WordDiffReporter().render(rich_diff, output)
        doc = Document(str(output))
        # Labels prod/staging están en celdas de tabla (resumen), no en párrafos
        para_text = " ".join(p.text for p in doc.paragraphs)
        table_text = " ".join(
            cell.text for tbl in doc.tables for row in tbl.rows for cell in row.cells
        )
        all_text = para_text + " " + table_text
        assert "prod" in all_text
        assert "staging" in all_text
        assert "users" in para_text
        assert "v_active_users" in para_text
        assert "sp_cleanup" in para_text

    def test_template_report_content_is_present(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        """Con plantilla vacía, el contenido del reporte se genera correctamente."""
        from docx import Document

        # Plantilla vacía (solo estilos, sin contenido de ejemplo)
        tpl_path = tmp_path / "template.docx"
        Document().save(str(tpl_path))

        output = tmp_path / "diff_from_tpl.docx"
        WordDiffReporter(template_path=tpl_path).render(empty_diff, output)

        doc = Document(str(output))
        all_text = " ".join(p.text for p in doc.paragraphs)
        assert "Reporte de diferencias" in all_text

    def test_template_styles_are_inherited(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        """Usando plantilla el documento se genera correctamente (es un ZIP válido)."""
        from docx import Document

        tpl_path = tmp_path / "template.docx"
        Document().save(str(tpl_path))

        output = tmp_path / "diff_from_tpl.docx"
        WordDiffReporter(template_path=tpl_path).render(empty_diff, output)
        assert zipfile.is_zipfile(output)

    def test_render_raises_on_directory_output(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        """Pasar un directorio como output lanza ValueError con mensaje claro."""
        with pytest.raises(ValueError, match="ruta completa del fichero"):
            WordDiffReporter().render(empty_diff, output=tmp_path)

    def test_render_raises_on_path_without_extension(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        """Pasar una ruta sin extensión lanza ValueError."""
        with pytest.raises(ValueError, match="ruta completa del fichero"):
            WordDiffReporter().render(empty_diff, output=tmp_path / "nodotx")


# ---------------------------------------------------------------------------
# Tests de SchemaDiffReporter (facade)
# ---------------------------------------------------------------------------


class TestSchemaDiffReporter:
    def test_render_html(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        path = SchemaDiffReporter().render(empty_diff, output_dir=tmp_path, format="html")
        assert path.suffix == ".html"
        assert path.exists()

    def test_render_excel(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        path = SchemaDiffReporter().render(empty_diff, output_dir=tmp_path, format="excel")
        assert path.suffix == ".xlsx"
        assert path.exists()

    def test_render_word(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        path = SchemaDiffReporter().render(empty_diff, output_dir=tmp_path, format="word")
        assert path.suffix == ".docx"
        assert path.exists()

    def test_render_markdown(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        path = SchemaDiffReporter().render(empty_diff, output_dir=tmp_path, format="markdown")
        assert path.suffix == ".md"
        assert path.exists()

    def test_render_invalid_format(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        with pytest.raises(ValueError, match="no soportado"):
            SchemaDiffReporter().render(empty_diff, output_dir=tmp_path, format="pdf")

    def test_render_all_returns_four_files(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        paths = SchemaDiffReporter().render_all(empty_diff, output_dir=tmp_path)
        assert len(paths) == 4
        extensions = {p.suffix for p in paths}
        assert extensions == {".html", ".xlsx", ".docx", ".md"}

    def test_render_all_subset(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        paths = SchemaDiffReporter().render_all(
            empty_diff, output_dir=tmp_path, formats=["html", "markdown"]
        )
        assert len(paths) == 2

    def test_render_custom_filename(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        path = SchemaDiffReporter().render(
            empty_diff, output_dir=tmp_path, format="html", filename="custom.html"
        )
        assert path.name == "custom.html"

    def test_render_creates_output_dir(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        new_dir = tmp_path / "nested" / "output"
        SchemaDiffReporter().render(empty_diff, output_dir=new_dir, format="markdown")
        assert new_dir.exists()

    def test_auto_filename_derived_from_labels(self, tmp_path: Path, rich_diff: SchemaDiff) -> None:
        path = SchemaDiffReporter().render(rich_diff, output_dir=tmp_path, format="markdown")
        assert "prod" in path.stem
        assert "staging" in path.stem

    def test_word_template_path_passed_to_reporter(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        """word_template_path se propaga al WordDiffReporter desde la facade."""
        from docx import Document

        tpl_path = tmp_path / "corp.docx"
        Document().save(str(tpl_path))

        path = SchemaDiffReporter(word_template_path=tpl_path).render(
            empty_diff, output_dir=tmp_path, format="word"
        )
        assert path.suffix == ".docx"
        assert zipfile.is_zipfile(path)

    def test_word_template_not_found_raises(self, tmp_path: Path, empty_diff: SchemaDiff) -> None:
        """Si la plantilla no existe la facade propaga FileNotFoundError."""
        missing = tmp_path / "no_existe.docx"
        reporter = SchemaDiffReporter(word_template_path=missing)
        with pytest.raises(FileNotFoundError):
            reporter.render(empty_diff, output_dir=tmp_path, format="word")
