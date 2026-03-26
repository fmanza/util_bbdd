"""Fuente de verdad compartida para textos y leyenda visual de diagramas."""

from __future__ import annotations

from typing import Any

from ..analysis.graphviz_ext import GraphvizRelationshipGraphExt


def build_diagram_direction_help(direction_key: str) -> str:
    """Devuelve ayuda contextual por sentido del diagrama."""
    if direction_key == "outgoing":
        return "Relaciones de salida hacia tablas hijas o dependientes de la tabla actual."
    return "Relaciones de entrada desde tablas padre o referenciadoras hacia la tabla actual."


def build_hidden_levels_help(direction_key: str, hidden_levels: int | None = None) -> str:
    """Explica qué significa que existan niveles ocultos por dirección."""
    if direction_key == "outgoing":
        base = (
            "Salida oculta: niveles de tablas hijas o dependientes que existen en el grafo, "
            "pero no se muestran por el límite de profundidad visible."
        )
    else:
        base = (
            "Entrada oculta: niveles de tablas padre o referenciadoras que existen en el grafo, "
            "pero no se muestran por el límite de profundidad visible."
        )

    if hidden_levels is None:
        return base

    label, remainder = base.split(": ", maxsplit=1)
    return f"{label}: {hidden_levels} nivel(es) de {remainder[len('niveles de ') :]}"


def build_diagram_navigation_tips(
    *,
    visible_outgoing_levels: int,
    visible_incoming_levels: int,
    hidden_outgoing_levels: int,
    hidden_incoming_levels: int,
) -> list[str]:
    """Construye consejos de lectura para diagramas con varias pestañas o profundidad oculta."""
    tips: list[str] = []
    if visible_outgoing_levels > 0 and visible_incoming_levels > 0:
        tips.append(
            "Revisa salida y entrada por separado para evitar mezclar dependencias hijas con tablas referenciadoras."
        )
    if hidden_outgoing_levels > 0 or hidden_incoming_levels > 0:
        tips.append(
            "Hay niveles no visibles por límite de profundidad: usa el resumen para decidir si necesitas ampliar el alcance del diagrama."
        )
    if visible_outgoing_levels + visible_incoming_levels > 2:
        tips.append(
            "Cuando existan varios niveles visibles, empieza por Nivel 1 y avanza de forma incremental para conservar contexto."
        )
    return tips


def build_diagram_reading_aids(
    *,
    visible_outgoing_levels: int,
    visible_incoming_levels: int,
    hidden_outgoing_levels: int,
    hidden_incoming_levels: int,
) -> list[str]:
    """Combina ayudas de dirección y navegación para reutilizarlas en distintos renderers."""
    reading_aids: list[str] = []

    if visible_outgoing_levels > 0:
        reading_aids.append(f"Salida: {build_diagram_direction_help('outgoing')}")
    if visible_incoming_levels > 0:
        reading_aids.append(f"Entrada: {build_diagram_direction_help('incoming')}")

    reading_aids.extend(
        build_diagram_navigation_tips(
            visible_outgoing_levels=visible_outgoing_levels,
            visible_incoming_levels=visible_incoming_levels,
            hidden_outgoing_levels=hidden_outgoing_levels,
            hidden_incoming_levels=hidden_incoming_levels,
        )
    )
    return reading_aids


def build_diagram_legend_payload() -> dict[str, Any]:
    """Devuelve la leyenda visual compartida por HTML y Word."""
    return {
        "title": "Leyenda visual",
        "direction_items": [
            {
                "label": "Salida",
                "swatch": "#1D70B8",
                "description": "Aristas salientes hacia tablas hijas o dependientes visibles en el diagrama.",
            },
            {
                "label": "Entrada",
                "swatch": "#A61C00",
                "description": "Aristas entrantes desde tablas padre o referenciadoras visibles en el diagrama.",
            },
        ],
        "table_type_items": [
            {
                "label": "Entidad",
                "swatch": GraphvizRelationshipGraphExt.ENTITY_TABLE_COLOR,
                "description": "Tabla de negocio general que no encaja en las heurísticas de asociación o jerarquía.",
            },
            {
                "label": "Asociación",
                "swatch": GraphvizRelationshipGraphExt.ASSOCIATION_TABLE_COLOR,
                "description": "Tabla puente detectada por varias FKs y, cuando aplica, PK compuesta basada en columnas relacionales.",
            },
            {
                "label": "Jerarquía",
                "swatch": GraphvizRelationshipGraphExt.HIERARCHY_TABLE_COLOR,
                "description": "Tabla con autorreferencia que representa relaciones padre-hijo dentro de la misma entidad.",
            },
        ],
        "cardinality_items": [
            {"marker": "1", "description": "Un registro relacionado."},
            {"marker": "N", "description": "Muchos registros relacionados."},
            {"marker": "M", "description": "Muchos registros en relaciones de tabla intermedia."},
        ],
        "relation_type_items": [
            {
                "label": "FK",
                "description": "Tipo de relación soportado hoy por el renderer de diagramas: clave foránea.",
            }
        ],
        "notes": [
            "Los marcadores de cardinalidad se muestran separados de la arista para mejorar la legibilidad.",
            "Los colores de tabla representan una tipología visual heurística del nodo, no una taxonomía absoluta del modelo de datos.",
            "La leyenda de tipos de relación podrá ampliarse cuando analysis exponga más tipos reales además de FK.",
        ],
    }


def build_diagram_legend_rows(legend_payload: dict[str, Any] | None = None) -> list[list[str]]:
    """Convierte la leyenda compartida a filas tabulares para Word."""
    payload: dict[str, Any] = build_diagram_legend_payload() if legend_payload is None else legend_payload
    rows: list[list[str]] = []

    for item in payload.get("direction_items", []):
        rows.append(["Dirección", str(item.get("label", "")), str(item.get("description", ""))])

    for item in payload.get("cardinality_items", []):
        rows.append(["Cardinalidad", str(item.get("marker", "")), str(item.get("description", ""))])

    for item in payload.get("table_type_items", []):
        rows.append(["Tipo de tabla", str(item.get("label", "")), str(item.get("description", ""))])

    for item in payload.get("relation_type_items", []):
        rows.append(["Tipo de relación", str(item.get("label", "")), str(item.get("description", ""))])

    return rows
