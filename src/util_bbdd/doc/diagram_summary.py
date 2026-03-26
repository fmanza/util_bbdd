"""Fuente de verdad compartida para el resumen de niveles de diagramas."""

from __future__ import annotations

from typing import Any

from .diagram_legend import build_diagram_navigation_tips, build_hidden_levels_help


def build_diagram_summary_payload(
    *,
    max_depth: int,
    total_outgoing_levels: int,
    total_incoming_levels: int,
    visible_outgoing_levels: int,
    visible_incoming_levels: int,
    hidden_outgoing_levels: int,
    hidden_incoming_levels: int,
    title: str = "Resumen de niveles",
) -> dict[str, Any]:
    """Construye un contrato compartido de resumen para HTML y Word."""
    return {
        "title": title,
        "max_depth": int(max_depth),
        "total_outgoing_levels": int(total_outgoing_levels),
        "total_incoming_levels": int(total_incoming_levels),
        "hidden_outgoing_levels": int(hidden_outgoing_levels),
        "hidden_incoming_levels": int(hidden_incoming_levels),
        "visible_outgoing_levels": int(visible_outgoing_levels),
        "visible_incoming_levels": int(visible_incoming_levels),
        "has_hidden_outgoing_levels": int(hidden_outgoing_levels) > 0,
        "has_hidden_incoming_levels": int(hidden_incoming_levels) > 0,
        "has_any_hidden_levels": int(hidden_outgoing_levels) > 0 or int(hidden_incoming_levels) > 0,
        "outgoing_hidden_help": build_hidden_levels_help("outgoing"),
        "incoming_hidden_help": build_hidden_levels_help("incoming"),
        "navigation_tips": build_diagram_navigation_tips(
            visible_outgoing_levels=int(visible_outgoing_levels),
            visible_incoming_levels=int(visible_incoming_levels),
            hidden_outgoing_levels=int(hidden_outgoing_levels),
            hidden_incoming_levels=int(hidden_incoming_levels),
        ),
    }


def build_diagram_summary_line(summary_payload: dict[str, Any]) -> str:
    """Construye la línea principal del resumen con el formato actual de HTML."""
    return (
        f"Profundidad visible: {int(summary_payload.get('max_depth', 0))}"
        f" | Salida visible: {int(summary_payload.get('visible_outgoing_levels', 0))}"
        f" de {int(summary_payload.get('total_outgoing_levels', 0))}"
        f" | Entrada visible: {int(summary_payload.get('visible_incoming_levels', 0))}"
        f" de {int(summary_payload.get('total_incoming_levels', 0))}"
    )
