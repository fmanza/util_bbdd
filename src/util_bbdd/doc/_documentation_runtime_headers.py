"""Helpers internos para carga y construcción de cabeceras documentales."""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any, cast

from ._documentation_runtime_types import HeadersConfig


class DocumentationHeadersRuntime:
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

    def build_headers(self, headers_config: HeadersConfig, db_type: str) -> dict[str, list[str]]:
        """Construye cabeceras legibles combinando base y overrides por motor."""
        headers: dict[str, list[str]] = {}
        headers_cfg = cast(dict[str, dict[str, Any]], headers_config["headers"])
        labels_cfg = cast(dict[str, dict[str, dict[str, str]]], headers_config["labels"])

        for section, config in headers_cfg.items():
            base_headers: list[str] = list(config["base"])
            db_specific_headers: list[str] = list(config.get(db_type, []))
            labels: dict[str, str] = labels_cfg.get(section, {}).get(db_type, {})
            header_list: list[str] = base_headers + db_specific_headers
            headers[section] = [labels.get(header, header) for header in header_list]

        return headers


__all__: list[str] = [
    "DocumentationHeadersRuntime",
]
