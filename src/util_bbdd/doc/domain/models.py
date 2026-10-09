"""Modelos de dominio para la ejecución documental."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class DocumentationSettings:
    """Configuración validada de una documentación (se resuelve sin consultar la base de datos)."""

    print_config: dict[str, Any]
    formatos: list[str]
    headers_config: dict[str, Any]
    headers: dict[str, list[str]]
    table_style: str


@dataclass(slots=True, frozen=True)
class DocumentationBootstrapState:
    """Estado inicial de una generación: la configuración, la salida y el inventario leído del catálogo."""

    settings: DocumentationSettings
    directorio_salida: Path
    fichero_salida: Path
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


@dataclass(slots=True, frozen=True)
class DocumentationResult:
    """Lo que ha generado :meth:`DatabaseDocumentation.generate`.

    Attributes:
        outputs: Ruta de cada formato generado: el ``.docx`` (con varios documentos Word, el nombre base al que se
            añade ``_parte_N``), el ``.xlsx`` o la carpeta del sitio HTML.
        tables: Tablas del schema documentado.
        views: Vistas.
        routines: Procedimientos y funciones.

    Example:
        >>> result = DatabaseDocumentation(manager, Path("out"), formatos=["html"]).generate()
        >>> result.outputs["html"].name
        'HTML'
        >>> result.tables
        42
    """

    outputs: dict[str, Path]
    tables: int
    views: int
    routines: int
