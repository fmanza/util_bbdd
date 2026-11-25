"""Helpers internos para carga y construcción de cabeceras documentales."""

from __future__ import annotations

import functools
import json

from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, cast

from ...._core.i18n import Locale
from ...application._internal_ports import HeadersRuntimePort
from ...application.ports import HeadersConfig


class DocumentationHeadersRuntime(HeadersRuntimePort):
    """Servicio OO para carga y construcción de cabeceras documentales."""

    #: Cabeceras por defecto de cada idioma (las que usa ``DatabaseDocumentation`` si no se pasa ``headers_file``).
    DEFAULT_HEADERS_FILES: ClassVar[dict[str, str]] = {"es": "headers_config.json", "en": "headers_config.en.json"}

    def __init__(self, *, encoding: str = "utf-8") -> None:
        self._encoding: str = encoding

    def load_headers_config(self, headers_file: Path) -> HeadersConfig:
        """Carga la configuracion JSON de cabeceras."""
        try:
            with headers_file.open(encoding=self._encoding) as file_handle:
                loaded_headers: Any = json.load(file_handle)
                return cast(HeadersConfig, loaded_headers)
        except FileNotFoundError as error:
            raise FileNotFoundError(f"Fichero de headers no encontrado: {headers_file}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"Error al leer fichero JSON de headers: {error}") from error

    def build_headers(self, headers_config: HeadersConfig) -> dict[str, list[str]]:
        """Cabeceras de cada sección (``headers.<SECCIÓN>.base``): iguales en todos los motores desde D1 (ADR-003)."""
        headers_cfg = cast(dict[str, dict[str, Any]], headers_config["headers"])
        return {section: [str(header) for header in config["base"]] for section, config in headers_cfg.items()}

    @classmethod
    def default_headers(cls, locale: Locale, section: str) -> list[str]:
        """Cabeceras por defecto de ``section`` en un idioma (respaldo de los renderers si faltan en ``headers``).

        Args:
            locale: Idioma de salida.
            section: Clave de sección de ``headers_config.json`` (``UNIQUE``, ``PARAMETROS_RUTINA``…).

        Returns:
            Copia de las cabeceras de esa sección.

        Example:
            >>> DocumentationHeadersRuntime.default_headers("en", "UNIQUE")
            ['Constraint Name', 'Field']
        """
        return list(cls._default_headers(locale)[section])

    @staticmethod
    @functools.cache
    def _default_headers(locale: Locale) -> MappingProxyType[str, tuple[str, ...]]:
        """Cabeceras por defecto de un idioma, leídas una vez por proceso."""
        file_name = DocumentationHeadersRuntime.DEFAULT_HEADERS_FILES[locale]
        headers_file = Path(__file__).resolve().parents[2] / "data" / file_name
        runtime = DocumentationHeadersRuntime()
        built = runtime.build_headers(runtime.load_headers_config(headers_file))
        return MappingProxyType({name: tuple(values) for name, values in built.items()})


__all__: list[str] = [
    "DocumentationHeadersRuntime",
]
