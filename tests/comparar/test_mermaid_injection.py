"""Etiquetas e ids de Mermaid sin saltos de línea ni directivas (G46 de util_bbdd_web, U-10.3, 5.2.0).

``escape_mermaid_label`` solo sustituía ``"``, ``[`` y ``]``: un nombre de tabla con saltos de línea añadía sentencias
o directivas (``%%{init: …}%%``) a los diagramas del HTML y del Markdown de la comparación, y el Markdown construía
además los ids de nodo con el mismo escape.
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from util_bbdd.comparar.models import ColumnDiff, SchemaDiff, TableDiff
from util_bbdd.comparar.reporters import HtmlDiffReporter, MarkdownDiffReporter
from util_bbdd.comparar.reporters._base import escape_mermaid_label

pytestmark = pytest.mark.unit

INJECTION = "t\n%%{init: {'theme':'dark'}}%%\nx"

DIFF = SchemaDiff(
    source_label="a",
    target_label="b",
    table_diffs=(
        TableDiff(table_name=INJECTION, status="added"),
        TableDiff(table_name="a-b", status="added"),
        TableDiff(table_name="a_b", status="added"),
        TableDiff(table_name="a --> b; c", status="removed"),
        TableDiff(
            table_name="m\r\nclick m call x()",
            status="modified",
            column_diffs=(ColumnDiff(column_name="c", attribute="type", source_value="A", target_value="B"),),
        ),
    ),
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a\nb", "a b"),
        ("a\r\nb", "a  b"),
        ("a\tb\x00c\x7fd\x85e", "a b c d e"),
        ("a b c", "a b c"),
        ("%%{init: {}}%%", "% %{init: {}}% %"),
        ("%%%", "% % %"),
        ("50%", "50%"),
        ('t"[x]"', "t'(x)'"),
        ("ñandú_1", "ñandú_1"),
    ],
)
def test_escape_mermaid_label(name: str, expected: str) -> None:
    assert escape_mermaid_label(name) == expected


def _markdown_block(tmp_path: Path) -> str:
    content = MarkdownDiffReporter().render(DIFF, tmp_path / "diff.md").read_text(encoding="utf-8")
    start = content.index("```mermaid")
    return content[start : content.index("```", start + 3) + 3]


def test_markdown_diagram_snapshot(tmp_path: Path) -> None:
    assert _markdown_block(tmp_path).splitlines() == [
        "```mermaid",
        "graph LR",
        '    subgraph added["✅ Añadidas"]',
        "        A_t____init____theme___dark______x[\"t % %{init: {'theme':'dark'}}% % x\"]",
        '        A_a_b["a-b"]',
        '        A_a_b_2["a_b"]',
        "    end",
        '    subgraph removed["❌ Eliminadas"]',
        '        R_a_____b__c["a --> b; c"]',
        "    end",
        '    subgraph modified["⚠️ Modificadas"]',
        '        M_m__click_m_call_x__["m  click m call x()\\n(1 cols)"]',
        "    end",
        "```",
    ]


def test_markdown_node_ids_are_ascii_and_unique(tmp_path: Path) -> None:
    node_lines = [line for line in _markdown_block(tmp_path).splitlines() if line.startswith("        ")]
    ids = [line.split("[", 1)[0].strip() for line in node_lines]

    assert all(re.fullmatch(r"[A-Za-z0-9_]+", node_id) for node_id in ids)
    assert len(set(ids)) == len(ids) == 5


def test_html_diagrams_gain_no_statements_or_directives(tmp_path: Path) -> None:
    html = HtmlDiffReporter(mermaid_src=None).render(DIFF, tmp_path / "diff.html").read_text(encoding="utf-8")
    blocks = re.findall(r'<div class="mermaid"[^>]*>(.*?)</div>', html, re.S)
    node_lines = [line.strip() for block in blocks for line in block.splitlines() if '["' in line]

    assert node_lines == [
        'A1["t % %{init: {&#39;theme&#39;:&#39;dark&#39;}}% % x"]:::nodeStyle',
        'A2["a-b"]:::nodeStyle',
        'A3["a_b"]:::nodeStyle',
        'M1["m  click m call x()"]:::nodeStyle',
        'R1["a --&gt; b; c"]:::nodeStyle',
    ]
    assert not any("%%" in block for block in blocks)
    assert not any(line.strip().startswith(("click", "x")) for block in blocks for line in block.splitlines())
