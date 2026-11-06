"""Escape de Markdown, nombres de fichero e índices de la documentación Markdown (5.3.0, grupo B).

El texto del catálogo es un dato no confiable: Zensical y MkDocs publican el HTML en línea tal cual (SPIKE_C3).
"""

from __future__ import annotations

import json

import pytest

from util_bbdd.doc.infrastructure.renderers.markdown._site_pages import IndexEntry, index_pages
from util_bbdd.doc.infrastructure.renderers.markdown._slugs import index_letter, sort_key, unique_slugs
from util_bbdd.doc.infrastructure.renderers.markdown._text import (
    admonition,
    front_matter,
    md_code_block,
    md_link,
    md_table,
    md_text,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
        ("<img src=x onerror=alert(2)>", "&lt;img src=x onerror=alert(2)&gt;"),
        ("a & b &lt;", "a &amp; b &amp;lt;"),
        ("*y* ~z~", r"\*y\* \~z\~"),
        ("_inicio fin_", r"\_inicio fin\_"),
        ("cliente_id", "cliente_id"),  # «_» entre letras: no es énfasis, se deja limpio
        ("`x`", r"\`x\`"),
        ("[a](javascript:alert(1))", r"\[a\](javascript:alert(1))"),
        ("a|b", r"a\|b"),
        ("# título", r"\# título"),
        ("c:\\ruta", r"c:\\ruta"),
        ("línea 1\nlínea 2\r\nfin\u2028x", "línea 1 línea 2 fin x"),
        (None, ""),
    ],
)
def test_md_text_escapes_html_and_markdown(raw: object, expected: str) -> None:
    assert md_text(raw) == expected


def test_md_table_escapes_cells_and_keeps_safe_renderers() -> None:
    lines = md_table(
        ["Campo", "Ref"],
        [["a|b", ("x", "x.md")], ["solo"]],
        raw_first_cell=['<a id="col-a"></a>', '<a id="col-b"></a>'],
        cell_renderers={1: lambda value: md_link(value[0], value[1])},
    )

    assert lines == [
        "| Campo | Ref |",
        "|---|---|",
        r'| <a id="col-a"></a>a\|b | [x](x.md) |',
        '| <a id="col-b"></a>solo |  |',
    ]


def test_code_block_fence_is_longer_than_any_backtick_run() -> None:
    assert md_code_block("SELECT 1", "sql") == ["```sql", "SELECT 1", "```"]
    assert md_code_block("DEFAULT '```'\r\n", "sql") == ["````sql", "DEFAULT '```'", "````"]
    assert md_code_block("a ````` b") == ["``````", "a ````` b", "``````"]


def test_front_matter_is_one_json_line() -> None:
    lines = front_matter({"title": 'x "y": ---\nz', "id": "table:s.x"})

    assert lines[0] == "---"
    assert lines[2] == "---"
    assert json.loads(lines[1]) == {"title": 'x "y": ---\nz', "id": "table:s.x"}
    assert "\n" not in lines[1]


def test_admonition_title_cannot_close_its_quotes() -> None:
    assert admonition("warning", 'a "b"', "cuerpo") == ['!!! warning "a &quot;b&quot;"', "    cuerpo", ""]


def test_unique_slugs_are_stable_and_safe() -> None:
    names = ["Clientes", "clientes", "pedidos", "CON", "index", "../../etc", "x" * 200, "Año fiscal"]
    slugs = unique_slugs(names)
    reordered = unique_slugs(reversed(names))

    assert slugs == reordered  # no depende del orden
    assert slugs["pedidos"] == "pedidos"
    assert slugs["Clientes"] != slugs["clientes"]
    assert slugs["Clientes"].startswith("clientes-")
    assert slugs["CON"].startswith("con-")
    assert slugs["index"].startswith("index-") and len(slugs["index"]) == len("index-") + 8
    assert slugs["../../etc"] == "etc"
    assert len(slugs["x" * 200]) == 80
    assert slugs["Año fiscal"] == "año-fiscal"


@pytest.mark.parametrize(
    ("name", "letter"), [("Árbol", "a"), ("ñandu", "n"), ("9x", "0-9"), ("_x", "otros"), ("日本", "otros")]
)
def test_index_letter(name: str, letter: str) -> None:
    assert index_letter(name) == letter


def test_sort_key_ignores_case_then_exact_name() -> None:
    assert sorted(["b", "B", "a", "C"], key=sort_key) == ["a", "B", "b", "C"]


def test_index_pages_paginate_by_letter() -> None:
    entries = [IndexEntry(f"a{i:03d}", f"a{i:03d}.md", "") for i in range(450)]
    entries += [IndexEntry("9z", "9z.md", "c"), IndexEntry("_raro", "raro.md", "")]

    pages = index_pages("Tablas", entries, 200)

    assert sorted(pages) == ["index-0-9.md", "index-a-2.md", "index-a-3.md", "index-a.md", "index-otros.md", "index.md"]
    assert "| [A](index-a.md) | 450 |" in pages["index.md"]
    letters = [line for line in pages["index.md"] if line.startswith("| [")]
    assert letters == ["| [A](index-a.md) | 450 |", "| [0-9](index-0-9.md) | 1 |", "| [OTROS](index-otros.md) | 1 |"]
    assert pages["index-a-3.md"][0] == "# Tablas: A (3 de 3)"
    assert sum(line.startswith("| [a") for line in pages["index-a-3.md"]) == 50
    assert "[Página 1](index-a.md) · [Página 2](index-a-2.md)" in pages["index-a-3.md"]
