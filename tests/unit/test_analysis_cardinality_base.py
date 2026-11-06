"""Cardinalidad de las relaciones en ``DatabaseRelationshipGraphBase`` (movida desde ``graphviz_ext.py`` en 5.3.0).

Debe funcionar sin Graphviz, porque la usa también ``MermaidRelationshipGraph``. La lógica no cambia: estos casos fijan
el comportamiento heredado, incluida la deuda conocida (dos PK → ``M:N``; ver AUDIT_PLAN F3 de la sesión
``2026-11-05-doc-markdown``).
"""

from __future__ import annotations

from typing import cast

import pytest

from _catalog_fakes import FakeCatalogManager, build_catalog

from util_bbdd.analysis.base import DatabaseRelationshipGraphBase
from util_bbdd.managers import SyncDatabaseManager

pytestmark = pytest.mark.unit


def _graph() -> DatabaseRelationshipGraphBase:
    data = build_catalog(
        tables=["clientes", "pedidos", "perfiles", "codigos"],
        pk_by_table={"clientes": ("id",), "pedidos": ("id",), "perfiles": ("cliente_id",), "codigos": ("id",)},
        uniques_by_table={"pedidos": [("numero",)], "codigos": [("codigo",)]},
    )
    return DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, FakeCatalogManager(data=data)))


@pytest.mark.parametrize(
    ("source_col", "target_col", "source_table", "target_table", "expected"),
    [
        ("cliente_id", "id", "pedidos", "clientes", "1:N"),  # destino PK
        ("numero", "id", "pedidos", "clientes", "1:1"),  # origen UNIQUE + destino PK
        ("cliente_id", "id", "perfiles", "clientes", "M:N"),  # ambos PK (deuda heredada: en realidad 1:1)
        ("cliente_id", "codigo", "pedidos", "codigos", "N:1"),  # destino no PK
    ],
)
def test_determine_cardinality_without_graphviz(
    source_col: str, target_col: str, source_table: str, target_table: str, expected: str
) -> None:
    assert _graph()._determine_cardinality(source_col, target_col, source_table, target_table) == expected


@pytest.mark.parametrize(
    ("cardinality", "source_marker", "target_marker"),
    [("1:N", "N", "1"), ("1:1", "1", "1"), ("M:N", "N", "M"), ("N:1", "1", "N"), ("raro", "N", "1")],
)
def test_build_cardinality_markers(cardinality: str, source_marker: str, target_marker: str) -> None:
    markers = _graph()._build_cardinality_markers(cardinality)

    assert (markers.source_marker, markers.target_marker) == (source_marker, target_marker)


def test_pk_and_unique_helpers_are_case_insensitive() -> None:
    graph = _graph()

    assert graph._is_primary_key("pedidos", "ID") is True
    assert graph._is_unique_column("codigos", "Codigo") is True
    assert graph._is_unique_column("clientes", "id") is False
