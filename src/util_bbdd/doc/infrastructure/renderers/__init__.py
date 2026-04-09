"""Renderers documentales por formato."""

from .excel_generator import ExcelGenerator
from .html_generator import HtmlGenerator
from .registry import DocumentationRendererRegistry, RendererRegistration, build_default_renderer_registry
from .word_generator import WordGenerator

__all__: list[str] = [
    "DocumentationRendererRegistry",
    "ExcelGenerator",
    "HtmlGenerator",
    "RendererRegistration",
    "WordGenerator",
    "build_default_renderer_registry",
]
