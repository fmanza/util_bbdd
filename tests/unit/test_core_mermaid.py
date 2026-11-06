"""Texto seguro para Mermaid en ``_core/mermaid.py`` (5.3.0): funciones movidas desde ``comparar`` y escape de ``erDiagram``.

Las reglas de ``erDiagram`` salen de SPIKE_C3 (sesión ``2026-11-05-doc-markdown``): validadas con Mermaid 11.17.2 y
12.2.0 en el navegador.
"""

from __future__ import annotations

import pytest

from util_bbdd._core import mermaid
from util_bbdd._core.mermaid import (
    escape_mermaid_er_text,
    escape_mermaid_label,
    mermaid_node_id,
    normalize_er_name,
    normalize_er_type,
)
from util_bbdd.comparar.reporters import _base, markdown_reporter

pytestmark = pytest.mark.unit


def test_comparar_reexports_the_same_functions() -> None:
    """``comparar`` sigue exponiendo las funciones movidas (mismo objeto, sin copia)."""
    assert _base.escape_mermaid_label is mermaid.escape_mermaid_label
    assert markdown_reporter._mermaid_node_id is mermaid.mermaid_node_id
    assert "escape_mermaid_label" in _base.__all__


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('a "b" [c]', "a 'b' (c)"),
        ("a\nb c\x00d", "a b c d"),
        ("%%{init: {'theme':'dark'}}%%", "% %{init: {'theme':'dark'}}% %"),
    ],
)
def test_escape_mermaid_label_keeps_g46_behaviour(raw: str, expected: str) -> None:
    assert escape_mermaid_label(raw) == expected


def test_mermaid_node_id_suffixes_collisions() -> None:
    used: set[str] = set()

    assert mermaid_node_id("A", "ventas.pedidos", used) == "A_ventas_pedidos"
    assert mermaid_node_id("A", "ventas-pedidos", used) == "A_ventas_pedidos_2"
    assert mermaid_node_id("A", "x\n-->y", used) == "A_x____y"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a%b", "a#37;b"),
        ("a\\b", "a#92;b"),
        ('x "y"', "x #quot;y#quot;"),
        ("t[1]", "t#91;1#93;"),
        # «#» primero: un nombre que ya contiene un código se muestra tal cual, no como el carácter
        ("x #quot; y", "x #35;quot; y"),
        ("%%{init: {'theme':'dark'}}%%", "#37;#37;{init: {'theme':'dark'}}#37;#37;"),
        ("a\nb\r\nc d", "a b  c d"),
        ("año 日本 <script>", "año 日本 <script>"),
    ],
)
def test_escape_mermaid_er_text(raw: str, expected: str) -> None:
    assert escape_mermaid_er_text(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("varchar(255)", "varchar(255)"),
        ("int[]", "int[]"),
        ("double precision", "double_precision"),
        ("decimal(10,2)", "decimal(10_2)"),
        ("timestamp(6) with time zone", "timestamp(6)_with_time_zone"),
        ("código_postal", "código_postal"),
        ("2D_POINT", "t_2D_POINT"),
        ("_interno", "t__interno"),
        ("PK", "PK_"),
        ("uk", "uk_"),
        ("", "t_"),
        ("  NUMBER(38,3)  ", "NUMBER(38_3)"),
    ],
)
def test_normalize_er_type(raw: str, expected: str) -> None:
    assert normalize_er_type(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("id", ("id", False)),
        ("año", ("año", False)),
        ("mi col", ("mi_col", True)),
        ("1col", ("c_1col", True)),
        ("FK", ("FK_", True)),
        ("pk", ("pk_", True)),
        ("a(b)", ("a_b_", True)),
        ("end", ("end", False)),  # válido como nombre de atributo (SPIKE_C3)
    ],
)
def test_normalize_er_name(raw: str, expected: tuple[str, bool]) -> None:
    assert normalize_er_name(raw) == expected
