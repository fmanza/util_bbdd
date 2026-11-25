"""Jinja2 template engine for standalone HTML documentation rendering."""

from __future__ import annotations

import re

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from markupsafe import Markup

from ....._core.i18n import Translator

#: Escapes para incrustar un texto dentro de un literal de cadena JavaScript (comillas simples o dobles) en un
#: ``<script>`` HTML: barra, comillas, saltos de línea y ``<``/``>``/``&`` (evita cerrar el ``<script>``).
_JS_ESCAPES: dict[str, str] = {
    "\\": r"\\",
    "'": r"\'",
    '"': r"\u0022",
    "\n": r"\n",
    "\r": r"\r",
    "<": r"\u003C",
    ">": r"\u003E",
    "&": r"\u0026",
    "\u2028": r"\u2028",
    "\u2029": r"\u2029",
}


def header_key(value: Any) -> str:
    """Normaliza un valor de cabecera a una clave CSS segura."""
    text: str = str(value or "").strip().lower()
    normalized: str = re.sub(r"[^a-z0-9]+", "-", text)
    return normalized.strip("-") or "column"


def status_class(value: Any) -> str:
    """Normaliza un estado para usarlo como clase CSS."""
    return str(value or "").strip().lower().replace("_", "-")


def routine_label(value: Any, translator: Translator | None = None) -> str:
    """Devuelve una etiqueta legible para el tipo de rutina en el idioma de ``translator`` (español por defecto)."""
    tr: Translator = translator or Translator()
    normalized: str = str(value or "").strip().upper()
    if normalized == "PROCEDURE":
        return tr.t("doc_html.routine.procedure")
    if normalized == "FUNCTION":
        return tr.t("doc_html.routine.function")
    return normalized or tr.t("doc_html.routine.default")


def js_string(value: Any) -> Markup:
    """Escapa un texto para insertarlo DENTRO de un literal de cadena JavaScript (sin añadir las comillas).

    Un texto sin caracteres especiales queda igual, de modo que ``'{{ t("...")|js_str }}'`` produce el mismo literal
    que el texto escrito a mano en la plantilla.
    """
    return Markup("".join(_JS_ESCAPES.get(char, char) for char in str(value)))


class TemplateEngine:
    """Encapsula la carga y renderizado de plantillas Jinja2.

    Registra como globales ``t`` (textos del catálogo ``doc_html`` en el idioma del ``translator``) y ``lang`` (código
    de idioma para ``<html lang>`` y ``localeCompare``). ``header_aliases`` traduce cabeceras visibles al texto español
    del que sale su clase CSS (``header_key``), para que las clases no cambien con el idioma.
    """

    def __init__(
        self,
        templates_root: Path,
        extra_search_paths: list[Path] | None = None,
        translator: Translator | None = None,
        header_aliases: Mapping[str, str] | None = None,
    ) -> None:
        self.templates_root: Path = templates_root
        self.extra_search_paths: list[Path] = extra_search_paths or []
        self._tr: Translator = translator or Translator()
        self._header_aliases: dict[str, str] = dict(header_aliases or {})
        self.environment: Environment = self._build_environment()

    def _build_environment(self) -> Environment:
        """Construye el entorno Jinja2 y registra filtros personalizados."""
        search_paths: list[str] = [str(path) for path in self.extra_search_paths if path]
        search_paths.append(str(self.templates_root))

        environment = Environment(
            loader=FileSystemLoader(list(dict.fromkeys(search_paths))),
            # Todas las plantillas reales se nombran "*.html.j2"/"*.xml.j2": select_autoescape()
            # solo mira la extensión final del nombre de plantilla, así que "j2" debe declararse
            # aquí o el autoescape nunca se activa (ver AUDIT_CODE DOC-01, 2026-09-22).
            autoescape=select_autoescape(enabled_extensions=("html", "xml", "j2"), default_for_string=True),
            trim_blocks=True,
            lstrip_blocks=True,
            auto_reload=False,
        )
        environment.filters["header_key"] = self._header_key
        environment.filters["status_class"] = status_class
        environment.filters["routine_label"] = self._routine_label
        environment.filters["js_str"] = js_string
        environment.globals["t"] = self._tr.t
        environment.globals["lang"] = self._tr.locale
        return environment

    def _header_key(self, value: Any) -> str:
        """``header_key`` de la cabecera española equivalente (clase CSS estable entre idiomas)."""
        return header_key(self._header_aliases.get(str(value), value))

    def _routine_label(self, value: Any) -> str:
        """``routine_label`` en el idioma del motor de plantillas."""
        return routine_label(value, self._tr)

    def get_template(self, template_name: str) -> Template:
        """Obtiene una plantilla por nombre lógico."""
        return self.environment.get_template(template_name)

    def render(self, template_name: str, **context: Any) -> str:
        """Renderiza una plantilla con el contexto indicado."""
        return self.get_template(template_name).render(**context)
