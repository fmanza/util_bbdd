"""Helpers internos para carga y construcción de cabeceras documentales."""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any, cast

from ...application._internal_ports import HeadersRuntimePort
from ...application.ports import HeadersConfig


class DocumentationHeadersRuntime(HeadersRuntimePort):
    """Servicio OO para carga y construcción de cabeceras documentales."""

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


__all__: list[str] = [
    "DocumentationHeadersRuntime",
]
