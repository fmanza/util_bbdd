"""Puertos internos de orquestación del flujo documental.

No forman parte de la API pública de ``doc/``.  Solo deben importarse desde
código de infraestructura y use-cases internos.  Los puertos públicos del módulo
están en :mod:`ports`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .ports import (
    DocumentationManagerPort,
    DocumentRendererPort,
    HeadersConfig,
    LoggerProtocol,
    MetadataReaderPort,
)


class PrintConfigPolicyPort(Protocol):
    """Normalización de configuración de impresión/secciones."""

    def normalize(self, imprimir: dict[str, Any] | None) -> dict[str, Any]: ...


class HeadersRuntimePort(Protocol):
    """Carga y composición de cabeceras del documento."""

    def load_headers_config(self, headers_file: Path) -> HeadersConfig: ...

    def build_headers(self, headers_config: HeadersConfig, db_type: str) -> dict[str, list[str]]: ...


class MetadataRuntimePort(Protocol):
    """Runtime de metadata opcional para enriquecimiento documental."""

    def get_database_version_metadata(self, *, db_manager: MetadataReaderPort) -> str | None: ...

    def get_database_charset_collation_metadata(self, *, db_manager: MetadataReaderPort) -> dict[str, Any] | None: ...

    def get_columns_charset_collation_metadata(
        self,
        *,
        db_manager: MetadataReaderPort,
        table_name: str,
    ) -> list[tuple[str, str | None, str | None]] | None: ...


class MetadataRuntimeFactoryPort(Protocol):
    """Fábrica para crear runtime de metadata por sesión/documento."""

    def create(self, *, logger: LoggerProtocol) -> MetadataRuntimePort: ...


class StorageReportServicePort(Protocol):
    """Servicio de obtención del reporte de almacenamiento."""

    def get_storage_inventory_report(
        self,
        *,
        db_manager: DocumentationManagerPort,
        logger: LoggerProtocol,
        print_config: dict[str, Any],
    ) -> dict[str, Any]: ...


class RendererFactoryPort(Protocol):
    """Factory de instancias renderer para un formato concreto."""

    def __call__(self, *, database: str, headers: HeadersConfig, table_style: str) -> DocumentRendererPort: ...


class RendererRegistrationPort(Protocol):
    """Definición de formato registrada en el registry de renderers."""

    output_format: str
    output_extension: str | None
    include_graph_generator: bool
    accepts_graph_generator: bool
    factory: RendererFactoryPort


class RendererRegistryPort(Protocol):
    """Registro de renderers por formato soportado."""

    def get(self, output_format: str) -> RendererRegistrationPort | None: ...


__all__ = [
    "HeadersRuntimePort",
    "MetadataRuntimeFactoryPort",
    "MetadataRuntimePort",
    "PrintConfigPolicyPort",
    "RendererFactoryPort",
    "RendererRegistrationPort",
    "RendererRegistryPort",
    "StorageReportServicePort",
]
