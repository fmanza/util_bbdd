"""Fuente de verdad compartida para textos y leyenda visual de diagramas (en el idioma del ``Translator``, 5.10.0)."""

from __future__ import annotations

import functools

from typing import Any

from ....._core.i18n import Locale, Translator
from .....analysis.graphviz_ext import GraphvizRelationshipGraphExt


def build_diagram_direction_help(direction_key: str, translator: Translator | None = None) -> str:
    """Devuelve ayuda contextual por sentido del diagrama (``outgoing``, ``incoming`` o ``isolated``)."""
    tr = translator or Translator()
    if direction_key == "outgoing":
        return tr.t("doc.diagram.help.outgoing")
    if direction_key == "isolated":
        return tr.t("doc.diagram.help.isolated")
    return tr.t("doc.diagram.help.incoming")


def build_hidden_levels_help(
    direction_key: str, hidden_levels: int | None = None, translator: Translator | None = None
) -> str:
    """Explica qué significa que existan niveles ocultos por dirección."""
    tr = translator or Translator()
    direction: str = "outgoing" if direction_key == "outgoing" else "incoming"
    if hidden_levels is None:
        return tr.t(f"doc.diagram.hidden.{direction}")
    return tr.t(f"doc.diagram.hidden.{direction}_count", count=hidden_levels)


def build_diagram_navigation_tips(
    *,
    visible_outgoing_levels: int,
    visible_incoming_levels: int,
    hidden_outgoing_levels: int,
    hidden_incoming_levels: int,
    translator: Translator | None = None,
) -> list[str]:
    """Construye consejos de lectura para diagramas con varias pestañas o profundidad oculta."""
    tr = translator or Translator()
    tips: list[str] = []
    if visible_outgoing_levels > 0 and visible_incoming_levels > 0:
        tips.append(tr.t("doc.diagram.tip.separate_directions"))
    if hidden_outgoing_levels > 0 or hidden_incoming_levels > 0:
        tips.append(tr.t("doc.diagram.tip.hidden_levels"))
    if visible_outgoing_levels + visible_incoming_levels > 2:
        tips.append(tr.t("doc.diagram.tip.incremental"))
    return tips


def build_diagram_reading_aids(
    *,
    visible_outgoing_levels: int,
    visible_incoming_levels: int,
    hidden_outgoing_levels: int,
    hidden_incoming_levels: int,
    translator: Translator | None = None,
) -> list[str]:
    """Combina ayudas de dirección y navegación para reutilizarlas en distintos renderers."""
    tr = translator or Translator()
    reading_aids: list[str] = []

    if visible_outgoing_levels > 0:
        reading_aids.append(
            tr.t("doc.diagram.aid.outgoing", help=build_diagram_direction_help("outgoing", translator=tr))
        )
    if visible_incoming_levels > 0:
        reading_aids.append(
            tr.t("doc.diagram.aid.incoming", help=build_diagram_direction_help("incoming", translator=tr))
        )

    reading_aids.extend(
        build_diagram_navigation_tips(
            visible_outgoing_levels=visible_outgoing_levels,
            visible_incoming_levels=visible_incoming_levels,
            hidden_outgoing_levels=hidden_outgoing_levels,
            hidden_incoming_levels=hidden_incoming_levels,
            translator=tr,
        )
    )
    return reading_aids


def build_diagram_legend_payload(translator: Translator | None = None) -> dict[str, Any]:
    """Devuelve la leyenda visual compartida por HTML y Word en el idioma de ``translator`` (español por defecto)."""
    return _legend_payload((translator or Translator()).locale)


@functools.lru_cache(maxsize=4)
def _legend_payload(locale: Locale) -> dict[str, Any]:
    """Leyenda de un idioma (una por idioma y proceso)."""
    tr = Translator(locale)
    return {
        "title": tr.t("doc.legend.title"),
        "direction_items": [
            {
                "label": tr.t("doc.legend.direction.outgoing"),
                "swatch": "#1D70B8",
                "description": tr.t("doc.legend.direction.outgoing_description"),
            },
            {
                "label": tr.t("doc.legend.direction.incoming"),
                "swatch": "#A61C00",
                "description": tr.t("doc.legend.direction.incoming_description"),
            },
        ],
        "table_type_items": [
            {
                "label": tr.t("doc.legend.table_type.entity"),
                "swatch": GraphvizRelationshipGraphExt.ENTITY_TABLE_COLOR,
                "description": tr.t("doc.legend.table_type.entity_description"),
            },
            {
                "label": tr.t("doc.legend.table_type.association"),
                "swatch": GraphvizRelationshipGraphExt.ASSOCIATION_TABLE_COLOR,
                "description": tr.t("doc.legend.table_type.association_description"),
            },
            {
                "label": tr.t("doc.legend.table_type.hierarchy"),
                "swatch": GraphvizRelationshipGraphExt.HIERARCHY_TABLE_COLOR,
                "description": tr.t("doc.legend.table_type.hierarchy_description"),
            },
        ],
        "cardinality_items": [
            {"marker": "1", "description": tr.t("doc.legend.cardinality.one")},
            {"marker": "N", "description": tr.t("doc.legend.cardinality.many")},
        ],
        "relation_type_items": [
            {
                "label": "FK",
                "description": tr.t("doc.legend.relation_type.fk_description"),
            }
        ],
        "notes": [
            tr.t("doc.legend.note.cardinality"),
            tr.t("doc.legend.note.colors"),
            tr.t("doc.legend.note.relation_types"),
        ],
    }


def build_diagram_legend_rows(
    legend_payload: dict[str, Any] | None = None, translator: Translator | None = None
) -> list[list[str]]:
    """Convierte la leyenda compartida a filas tabulares para Word."""
    tr = translator or Translator()
    payload: dict[str, Any] = build_diagram_legend_payload(tr) if legend_payload is None else legend_payload
    rows: list[list[str]] = []
    direction: str = tr.t("doc.legend.category.direction")
    cardinality: str = tr.t("doc.legend.category.cardinality")
    table_type: str = tr.t("doc.legend.category.table_type")
    relation_type: str = tr.t("doc.legend.category.relation_type")

    for item in payload.get("direction_items", []):
        rows.append([direction, str(item.get("label", "")), str(item.get("description", ""))])

    for item in payload.get("cardinality_items", []):
        rows.append([cardinality, str(item.get("marker", "")), str(item.get("description", ""))])

    for item in payload.get("table_type_items", []):
        rows.append([table_type, str(item.get("label", "")), str(item.get("description", ""))])

    for item in payload.get("relation_type_items", []):
        rows.append([relation_type, str(item.get("label", "")), str(item.get("description", ""))])

    return rows
