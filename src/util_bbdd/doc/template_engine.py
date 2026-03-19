"""Jinja2 template engine for standalone HTML documentation rendering."""

from __future__ import annotations

import re

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape


def header_key(value: Any) -> str:
    """Normaliza un valor de cabecera a una clave CSS segura."""
    text = str(value or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", text)
    return normalized.strip("-") or "column"


def status_class(value: Any) -> str:
    """Normaliza un estado para usarlo como clase CSS."""
    return str(value or "").strip().lower().replace("_", "-")


def routine_label(value: Any) -> str:
    """Devuelve una etiqueta legible para el tipo de rutina."""
    normalized = str(value or "").strip().upper()
    if normalized == "PROCEDURE":
        return "Procedure"
    if normalized == "FUNCTION":
        return "Función"
    return normalized or "Rutina"


class TemplateEngine:
    """Encapsula la carga y renderizado de plantillas Jinja2."""

    def __init__(self, templates_root: Path, extra_search_paths: list[Path] | None = None) -> None:
        self.templates_root: Path = templates_root
        self.extra_search_paths: list[Path] = extra_search_paths or []
        self.environment: Environment = self._build_environment()

    def _build_environment(self) -> Environment:
        """Construye el entorno Jinja2 y registra filtros personalizados."""
        search_paths: list[str] = [str(path) for path in self.extra_search_paths if path]
        search_paths.append(str(self.templates_root))

        environment = Environment(
            loader=FileSystemLoader(list(dict.fromkeys(search_paths))),
            autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        environment.filters["header_key"] = header_key
        environment.filters["status_class"] = status_class
        environment.filters["routine_label"] = routine_label
        return environment

    def get_template(self, template_name: str) -> Template:
        """Obtiene una plantilla por nombre lógico."""
        return self.environment.get_template(template_name)

    def render(self, template_name: str, **context: Any) -> str:
        """Renderiza una plantilla con el contexto indicado."""
        return self.get_template(template_name).render(**context)
