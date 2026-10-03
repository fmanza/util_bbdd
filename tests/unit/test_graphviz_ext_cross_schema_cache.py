"""Tests de regresión: GraphvizRelationshipGraphExt no mezcla PK/UK/cardinalidad entre schemas con tabla
homónima [MDC-02].

Antes, la caché de relaciones se indexaba solo por nombre de tabla y dos schemas ("sales"/"archive") con una tabla
"orders" homónima compartían entrada. Desde E2 de ADR-003 todo sale del snapshot del manager (cacheado por schema) y
el generador no guarda cachés propias; estos tests fijan que no vuelva a aparecer la fuga.
"""

from __future__ import annotations

import logging

from _catalog_fakes import FakeCatalogManager, build_catalog

from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt


class _FakeDbManager(FakeCatalogManager):
    """Manager con PK/UK distintas por schema para la misma tabla 'orders'."""

    def __init__(self) -> None:
        super().__init__(
            data_by_context={
                "sales": build_catalog(pk_by_table={"orders": ("id",)}, uniques_by_table={"orders": [("code",)]}),
                # 'orders' en archive no tiene PK 'id' (p.ej. tabla histórica)
                "archive": build_catalog(),
            },
            context="sales",
        )

    @property
    def _context(self) -> str:
        return self.context

    @_context.setter
    def _context(self, value: str) -> None:
        self.context = value


def _build_graph(db_manager: _FakeDbManager) -> GraphvizRelationshipGraphExt:
    graph = object.__new__(GraphvizRelationshipGraphExt)
    graph.db_manager = db_manager
    graph.logger = logging.getLogger(__name__)
    return graph


def test_is_primary_key_does_not_leak_across_schemas_for_homonymous_table() -> None:
    db_manager = _FakeDbManager()
    graph = _build_graph(db_manager)

    db_manager._context = "sales"
    assert graph._is_primary_key("orders", "id") is True

    db_manager._context = "archive"
    assert graph._is_primary_key("orders", "id") is False  # no debe heredar el True de 'sales'


def test_is_unique_column_does_not_leak_across_schemas_for_homonymous_table() -> None:
    db_manager = _FakeDbManager()
    graph = _build_graph(db_manager)

    db_manager._context = "sales"
    assert graph._is_unique_column("orders", "code") is True

    db_manager._context = "archive"
    assert graph._is_unique_column("orders", "code") is False


def test_determine_cardinality_does_not_leak_across_schemas_for_homonymous_tables() -> None:
    db_manager = _FakeDbManager()
    graph = _build_graph(db_manager)

    db_manager._context = "sales"
    sales_result = graph._determine_cardinality("id", "id", "orders", "orders")

    db_manager._context = "archive"
    archive_result = graph._determine_cardinality("id", "id", "orders", "orders")

    # 'sales.orders.id' es PK ('id' existe en _pks_by_context["sales"]); 'archive.orders.id' no.
    assert sales_result == "M:N"  # ambos lados son PK en sales → M:N
    assert archive_result == "N:1"  # ninguno es PK en archive → fallback N:1
