"""Escape del informe Markdown de la comparación (5.3.0, E0 de la sesión ``2026-11-05-doc-markdown``).

Antes, los nombres y valores iban entre backticks sin tratar: un backtick cerraba el *code span* y dejaba pasar HTML al
sitio o a la vista previa que publica el informe, y un ``|`` partía la fila. Los comentarios no escapaban el HTML.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from util_bbdd._core.markdown import code_span, escape_html
from util_bbdd.comparar.models import ColumnDiff, CommentDiff, ForeignKeyDiff, SchemaDiff, TableDiff
from util_bbdd.comparar.reporters._base import escape_markdown_table_cell
from util_bbdd.comparar.reporters.markdown_reporter import MarkdownDiffReporter

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "in_table", "expected"),
    [
        ("pedidos", False, "`pedidos`"),
        ("a`b", False, "``a`b``"),
        ("`x`", False, "`` `x` ``"),
        ("a``b`", False, "``` a``b` ```"),
        ("a|b", True, "`a\\|b`"),
        ("a|b", False, "`a|b`"),
        ("l1\nl2", False, "`l1 l2`"),
    ],
)
def test_code_span(text: str, in_table: bool, expected: str) -> None:
    assert code_span(text, in_table=in_table) == expected


def test_escape_html_and_table_cell() -> None:
    assert escape_html("<b>&</b>") == "&lt;b&gt;&amp;&lt;/b&gt;"
    assert escape_markdown_table_cell("<script>x</script>|`") == "&lt;script&gt;x&lt;/script&gt;\\|\\`"


def test_report_cannot_be_broken_by_catalog_values(tmp_path: Path) -> None:
    hostile = "x`<img src=x onerror=alert(1)>`|y"
    diff = SchemaDiff(
        source_label="a|b",
        target_label="c",
        table_diffs=(
            TableDiff(
                table_name=hostile,
                status="modified",
                column_diffs=(ColumnDiff(hostile, "default", "'a|b'", "`x`"),),
                fk_diffs=(
                    ForeignKeyDiff(hostile, hostile, "added", target_columns="c", target_referred_table=hostile),
                ),
                comment_diffs=(CommentDiff(hostile, None, "<script>alert(1)</script>", "ok"),),
            ),
        ),
    )

    text = MarkdownDiffReporter().render(diff, tmp_path / "diff.md").read_text(encoding="utf-8")

    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    # Fuera del bloque Mermaid (va en una fence: Mermaid lo muestra como texto) y de los code spans, ningún HTML
    before, _, rest = text.partition("```mermaid")
    outside_mermaid = before + rest.partition("```")[2]
    for span in ("``x`<img src=x onerror=alert(1)>`\\|y``", "``x`<img src=x onerror=alert(1)>`|y``"):
        outside_mermaid = outside_mermaid.replace(span, "")
    assert "<img" not in outside_mermaid
    assert "| ``x`<img src=x onerror=alert(1)>`\\|y`` | default | `'a\\|b'` | `` `x` `` |" in text
    assert "### ⚠️ ``x`<img src=x onerror=alert(1)>`|y`` — Modificado" in text
    assert "| **Origen** | `a\\|b` |" in text
    # Cada fila de tabla conserva su número de columnas (ningún | sin escapar dentro de las celdas)
    for line in text.split("\n"):
        if line.startswith("| ``x`"):
            assert line.replace("\\|", "").count("|") in {5, 7}
