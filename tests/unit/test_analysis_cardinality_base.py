"""Cardinalidad de las relaciones en ``DatabaseRelationshipGraphBase`` (movida desde ``graphviz_ext.py`` en 5.3.0).

Debe funcionar sin Graphviz, porque la usa también ``MermaidRelationshipGraph``. Estos casos fijan la regla corregida en 5.3.0 (A-2 de la sesión ``2026-11-05-doc-markdown``): el padre es siempre «1» y la hija es «1»
solo si las columnas de la FK son toda su PK o una ``UNIQUE``.
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
        tables=["clientes", "pedidos", "perfiles", "codigos", "lineas", "cab", "det", "ext"],
        pk_by_table={
            "clientes": ("id",),
            "pedidos": ("id",),
            "perfiles": ("cliente_id",),
            "codigos": ("id",),
            "lineas": ("pedido_id", "n"),
            "cab": ("a", "b"),
            "det": ("a", "b", "n"),
            "ext": ("a", "b"),
        },
        uniques_by_table={"pedidos": [("numero",)], "codigos": [("codigo",)]},
        fk_by_table={
            "pedidos": [("fk_ped_cli", "cliente_id", "clientes", "id"), ("fk_ped_cod", "codigo", "codigos", "codigo")],
            "perfiles": [("fk_per_cli", "cliente_id", "clientes", "id")],
            "lineas": [("fk_lin_ped", "pedido_id", "pedidos", "id")],
            "det": [("fk_det_cab", "a", "cab", "a"), ("fk_det_cab", "b", "cab", "b")],
            "ext": [("fk_ext_cab", "a", "cab", "a"), ("fk_ext_cab", "b", "cab", "b")],
        },
    )
    return DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, FakeCatalogManager(data=data)))


@pytest.mark.parametrize(
    ("source_col", "target_col", "source_table", "target_table", "expected"),
    [
        ("cliente_id", "id", "pedidos", "clientes", "1:N"),  # FK simple
        ("numero", "id", "pedidos", "clientes", "1:1"),  # columna UNIQUE de la hija (relación no catalogada)
        ("cliente_id", "id", "perfiles", "clientes", "1:1"),  # la FK es toda la PK (antes de 5.3.0, M:N)
        ("pedido_id", "id", "lineas", "pedidos", "1:N"),  # parte de la PK: cabecera-detalle (antes M:N)
        ("codigo", "codigo", "pedidos", "codigos", "1:N"),  # a una UNIQUE del padre (antes N:1, «N» en el padre)
        ("a", "a", "det", "cab", "1:N"),  # FK compuesta dentro de una PK más larga
        ("b", "b", "ext", "cab", "1:1"),  # FK compuesta que es toda la PK
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
