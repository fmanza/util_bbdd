"""``imprimir["grafo"]["orthogonal_edges"]`` llega al generador de diagramas de la documentación (web G39, 4.1.0)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("graphviz")

from util_bbdd.doc.infrastructure.renderers.shared.generator_shared import (  # noqa: E402
    build_graph_generator_from_options,
)
from util_bbdd.doc.infrastructure.renderers.shared.print_config_manager import PrintConfigManager  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("imprimir", "expected"), [({}, True), ({"orthogonal_edges": False}, False)])
def test_orthogonal_edges_is_normalized_and_resolved_for_every_format(
    imprimir: dict[str, Any], expected: bool, tmp_path: Path
) -> None:
    normalized = PrintConfigManager.normalize({"grafo": {"enabled": True, **imprimir}})

    assert normalized["grafo"]["orthogonal_edges"] is expected
    assert PrintConfigManager.resolve_for_word(normalized)["graph_options"]["orthogonal_edges"] is expected
    html = PrintConfigManager.resolve_for_html(normalized, tmp_path, tmp_path / "plantilla.html")
    assert html["diagram_options"]["orthogonal_edges"] is expected


@pytest.mark.parametrize(("value", "splines"), [(True, "ortho"), (False, "true")])
def test_generator_built_from_options_uses_the_requested_splines(value: bool, splines: str) -> None:
    options = PrintConfigManager.normalize({"grafo": {"orthogonal_edges": value}})["grafo"]

    generator = build_graph_generator_from_options(object(), options)

    assert generator.orthogonal_edges is value
    dot, _, _ = generator._create_configured_graph("t", "svg", True)
    assert f"splines={splines}" in dot.source
