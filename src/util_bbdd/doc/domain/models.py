"""Modelos de dominio para la ejecución documental."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class DocumentationBootstrapState:
    """Estado inicial resuelto para la fachada documental."""

    print_config: dict[str, Any]
    formatos: list[str]
    directorio_salida: Path
    fichero_salida: Path
    table_style: str
    headers_config: dict[str, Any]
    headers: dict[str, list[str]]
    tablas: list[Any]
    vistas: list[Any]
    rutinas: list[Any]
    catalog: Any  # CatalogRows: filas neutras de la documentación desde el snapshot (D1)


@dataclass(slots=True, frozen=True)
class DocumentationFormatPlan:
    """Plan de salida para un formato documental concreto."""

    output_format: str
    output_path: Path
    include_graph_generator: bool
