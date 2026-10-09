"""S-01: el SVG que la página HTML incrusta con ``|safe`` no deja pasar marcado de los nombres del catálogo."""

from __future__ import annotations

import shutil

from collections.abc import Collection
from typing import Any

import pytest

from util_bbdd.analysis.graphviz_ext import GRAPHVIZ_AVAILABLE, GraphvizRelationshipGraphExt
from util_bbdd.doc.infrastructure.renderers.html_generator import HtmlGenerator
from util_bbdd.metadata.model import ALL_KINDS, ColumnMeta, ForeignKeyMeta, Kind, SchemaSnapshot, TableMeta

pytestmark = pytest.mark.skipif(
    not GRAPHVIZ_AVAILABLE or shutil.which("dot") is None, reason="Graphviz (paquete y ejecutable dot) no instalado"
)

HOSTILE = 'evil"><script>alert(1)</script>'


class _Source:
    db_type = "postgresql"

    def get_query_context_database(self) -> str:
        return "demo"

    def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind] = ALL_KINDS) -> SchemaSnapshot:
        data: dict[Kind, tuple[Any, ...]] = {
            Kind.TABLES: (TableMeta("parent"), TableMeta(HOSTILE)),
            Kind.COLUMNS: (
                ColumnMeta("parent", "id", 1, "integer", "integer", False),
                ColumnMeta(HOSTILE, "<b>col</b>", 1, "integer", "integer", True),
            ),
            Kind.PRIMARY_KEYS: (),
            Kind.UNIQUES: (),
            Kind.FOREIGN_KEYS: (ForeignKeyMeta(HOSTILE, "fk_<i>x</i>", ("<b>col</b>",), "demo", "parent", ("id",)),),
        }
        return SchemaSnapshot("postgresql", "demo", {kind: data.get(kind, ()) for kind in kinds})


def test_hostile_catalog_names_are_escaped_in_the_inline_svg(tmp_path: Any) -> None:
    graph = GraphvizRelationshipGraphExt(_Source(), show_constraint_name=True, render_workers=1)
    html_generator = HtmlGenerator(database="demo", headers={})

    tabs, _, _ = html_generator._generate_svg_for_table(
        table_name="parent",
        graph_generator=graph,
        diagram_options={"max_depth": 1, "direction": "both"},
        output_dir=tmp_path,
        navigation_links={HOSTILE: "../tables/evil.html"},
        file_stem="parent",
    )

    markup = "".join(item["inline_svg"] for tab in tabs for item in tab["items"])
    assert "evil" in markup  # la tabla hostil sí aparece en el diagrama…
    assert "<script" not in markup  # …pero como texto escapado, sin marcado
    assert "<b>" not in markup and "<i>" not in markup
