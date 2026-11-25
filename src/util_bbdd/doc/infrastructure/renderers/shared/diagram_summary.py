"""Fuente de verdad compartida para el resumen de niveles de diagramas."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ....._core.i18n import Translator
from .diagram_legend import build_diagram_navigation_tips, build_hidden_levels_help

if TYPE_CHECKING:
    from .....analysis.base import GraphDocument


def build_diagram_summary_payload(
    *,
    max_depth: int,
    total_outgoing_levels: int,
    total_incoming_levels: int,
    visible_outgoing_levels: int,
    visible_incoming_levels: int,
    hidden_outgoing_levels: int,
    hidden_incoming_levels: int,
    title: str | None = None,
    translator: Translator | None = None,
) -> dict[str, Any]:
    """Construye un contrato compartido de resumen para HTML y Word (``title`` por defecto: «Resumen de niveles»)."""
    tr = translator or Translator()
    return {
        "title": tr.t("doc.diagram.summary.title") if title is None else title,
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
        "outgoing_hidden_help": build_hidden_levels_help("outgoing", translator=tr),
        "incoming_hidden_help": build_hidden_levels_help("incoming", translator=tr),
        "navigation_tips": build_diagram_navigation_tips(
            visible_outgoing_levels=int(visible_outgoing_levels),
            visible_incoming_levels=int(visible_incoming_levels),
            hidden_outgoing_levels=int(hidden_outgoing_levels),
            hidden_incoming_levels=int(hidden_incoming_levels),
            translator=tr,
        ),
    }


def build_diagram_summary_payload_from_document(
    document: GraphDocument, translator: Translator | None = None
) -> dict[str, Any]:
    """Resumen de niveles de un ``GraphDocument`` (el mismo cálculo que Word; lo usa el Markdown desde 5.3.0)."""
    hidden = document.hidden_levels
    return build_diagram_summary_payload(
        max_depth=document.max_depth,
        total_outgoing_levels=document.total_outgoing_levels,
        total_incoming_levels=document.total_incoming_levels,
        visible_outgoing_levels=max(0, document.total_outgoing_levels - hidden.outgoing_hidden_levels),
        visible_incoming_levels=max(0, document.total_incoming_levels - hidden.incoming_hidden_levels),
        hidden_outgoing_levels=hidden.outgoing_hidden_levels,
        hidden_incoming_levels=hidden.incoming_hidden_levels,
        translator=translator,
    )


def build_diagram_summary_line(summary_payload: dict[str, Any], translator: Translator | None = None) -> str:
    """Línea principal del resumen (Word y Markdown; el HTML usa las mismas etiquetas en su plantilla).

    Desde 5.5.0 dice «niveles por sentido»: con las dos direcciones, 1 nivel muestra la tabla entre su padre y su hija y
    «profundidad visible: 1» parecía contradecirlo. «de N» es el total de niveles que hay en ese sentido.
    """
    return (translator or Translator()).t(
        "doc.diagram.summary.line",
        depth=int(summary_payload.get("max_depth", 0)),
        visible_outgoing=int(summary_payload.get("visible_outgoing_levels", 0)),
        total_outgoing=int(summary_payload.get("total_outgoing_levels", 0)),
        visible_incoming=int(summary_payload.get("visible_incoming_levels", 0)),
        total_incoming=int(summary_payload.get("total_incoming_levels", 0)),
    )
