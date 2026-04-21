"""Registro interno de renderers documentales por formato."""

from __future__ import annotations

from dataclasses import dataclass

from ...application._internal_ports import (
    RendererFactoryPort,
    RendererRegistrationPort,
    RendererRegistryPort,
)
from ...application.ports import DocumentRendererPort
from .excel_generator import ExcelGenerator
from .html_generator import HtmlGenerator
from .word_generator import WordGenerator


@dataclass(slots=True, frozen=True)
class RendererRegistration(RendererRegistrationPort):
    """Definición concreta registrada para un formato."""

    output_format: str
    output_extension: str | None
    include_graph_generator: bool
    accepts_graph_generator: bool
    factory: RendererFactoryPort


class DocumentationRendererRegistry(RendererRegistryPort):
    """Registro interno de formatos de salida soportados."""

    def __init__(self, registrations: list[RendererRegistration]) -> None:
        self._registrations: dict[str, RendererRegistration] = {
            registration.output_format: registration for registration in registrations
        }

    def get(self, output_format: str) -> RendererRegistration | None:
        return self._registrations.get(str(output_format or "").strip().lower())


def build_default_renderer_registry(
    *,
    word_generator_cls: type[WordGenerator] = WordGenerator,
    excel_generator_cls: type[ExcelGenerator] = ExcelGenerator,
    html_generator_cls: type[HtmlGenerator] = HtmlGenerator,
) -> DocumentationRendererRegistry:
    """Construye el registry estándar de renderers Word/Excel/HTML."""

    def _word_factory(*, database: str, headers: dict[str, list[str]], table_style: str) -> DocumentRendererPort:
        return word_generator_cls(database=database, headers=headers, table_style=table_style)

    def _excel_factory(*, database: str, headers: dict[str, list[str]], table_style: str) -> DocumentRendererPort:
        return excel_generator_cls(database=database, headers=headers, table_style=table_style)

    def _html_factory(*, database: str, headers: dict[str, list[str]], table_style: str) -> DocumentRendererPort:
        _ = table_style
        return html_generator_cls(database=database, headers=headers)

    return DocumentationRendererRegistry(
        registrations=[
            RendererRegistration(
                output_format="word",
                output_extension=".docx",
                include_graph_generator=True,
                accepts_graph_generator=True,
                factory=_word_factory,
            ),
            RendererRegistration(
                output_format="excel",
                output_extension=".xlsx",
                include_graph_generator=False,
                accepts_graph_generator=False,
                factory=_excel_factory,
            ),
            RendererRegistration(
                output_format="html",
                output_extension=None,
                include_graph_generator=True,
                accepts_graph_generator=True,
                factory=_html_factory,
            ),
        ]
    )


__all__: list[str] = [
    "DocumentationRendererRegistry",
    "RendererRegistration",
    "build_default_renderer_registry",
]
