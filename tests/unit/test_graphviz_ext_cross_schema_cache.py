"""Tests de regresión: GraphvizRelationshipGraphExt no colisiona el caché de
relaciones entre esquemas con tabla homónima [MDC-02].

Antes de este fix, RelationshipMetadataCache indexaba _is_pk_cache/_is_uk_cache/
_cardinality_cache/_table_columns_typed_cache solo por nombre de tabla; dos
esquemas ("sales"/"archive") con una tabla "orders" homónima compartían la misma
entrada de caché, devolviendo resultados de PK/UK/cardinalidad del esquema
incorrecto.
"""

from __future__ import annotations

import logging

from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt
from util_bbdd.metadata import RelationshipMetadataCache


class _FakeDbManager:
    """db_manager con PKs/UKs distintas por schema para la misma tabla 'orders'."""

    def __init__(self) -> None:
        self.relationship_cache = RelationshipMetadataCache()
        self._context = "sales"
        self._pks_by_context: dict[str, list] = {
            "sales": [("id",)],
            "archive": [],  # 'orders' en archive no tiene PK 'id' (p.ej. tabla histórica)
        }
        self._ucs_by_context: dict[str, list] = {
            "sales": [("code",)],
            "archive": [],
        }

    def get_query_context_database(self) -> str:
        return self._context

    def get_primary_keys(self, table_name: str) -> list:
        return self._pks_by_context[self._context]

    def get_unique_constraints(self, table_name: str) -> list:
        return self._ucs_by_context[self._context]


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
