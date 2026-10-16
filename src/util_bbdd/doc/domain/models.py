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
class EngineConditionsSection:
    """Sección «Condiciones del motor» (``EngineReadinessAdvisor``) ya preparada, igual para todos los formatos.

    Attributes:
        headers: Cabeceras de ``rows``.
        rows: (nivel, parámetro, valor actual, recomendación), por severidad descendente y parámetro.
        summary: (nivel, hallazgos) en orden CRITICAL, WARNING, INFO, OK, más los niveles desconocidos.
        metadata: (etiqueta, valor) para la trazabilidad: motor, momento de la verificación (UTC) y checks dinámicos.
        notices: Avisos que explican una tabla vacía o incompleta (origen no compatible, motor sin checks, sin
            conexión para los checks dinámicos, sin hallazgos).
    """

    headers: tuple[str, ...]
    rows: tuple[tuple[str, str, str, str], ...]
    summary: tuple[tuple[str, int], ...]
    metadata: tuple[tuple[str, str], ...]
    notices: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class DocumentationResult:
    """Lo que ha generado :meth:`DatabaseDocumentation.generate`.

    Attributes:
        outputs: Ruta de cada formato generado: el ``.docx`` (con varios documentos Word, el nombre base al que se
            añade ``_parte_N``), el ``.xlsx`` o la carpeta del sitio HTML.
        tables: Tablas del schema documentado.
        views: Vistas.
        routines: Procedimientos y funciones.

    Examples:
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
