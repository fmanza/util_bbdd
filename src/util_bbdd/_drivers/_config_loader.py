"""Carga y coercion tipada del JSON de tipos de bases de datos."""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any, cast

JsonDict = dict[str, Any]
JsonObjectMap = dict[str, JsonDict]
OptionalParamsConfig = list[JsonDict]
ErrorMessagesConfig = dict[str, str]


def as_json_dict(value: Any) -> JsonDict:
    """Coerciona un valor a diccionario JSON plano."""
    return cast(JsonDict, value) if isinstance(value, dict) else {}


def as_json_object_map(value: Any) -> JsonObjectMap:
    """Coerciona un valor a mapa de objetos JSON."""
    return cast(JsonObjectMap, value) if isinstance(value, dict) else {}


def as_string_list(value: Any) -> list[str]:
    """Coerciona un valor a lista de strings."""
    return cast(list[str], value) if isinstance(value, list) else []


def as_optional_params_config(value: Any) -> OptionalParamsConfig:
    """Coerciona la lista de parametros opcionales del JSON."""
    return cast(OptionalParamsConfig, value) if isinstance(value, list) else []


def as_error_messages_config(value: Any) -> ErrorMessagesConfig:
    """Coerciona la seccion de mensajes de error."""
    return cast(ErrorMessagesConfig, value) if isinstance(value, dict) else {}


def load_database_type_config(config_file: Path) -> JsonDict:
    """Carga el JSON de configuracion de tipos de base de datos."""
    try:
        with config_file.open(encoding="utf-8") as file_handle:
            return as_json_dict(json.load(file_handle))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_file}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Error al leer archivo JSON: {error}") from error


__all__: list[str] = [
    "ErrorMessagesConfig",
    "JsonDict",
    "JsonObjectMap",
    "OptionalParamsConfig",
    "as_error_messages_config",
    "as_json_dict",
    "as_json_object_map",
    "as_optional_params_config",
    "as_string_list",
    "load_database_type_config",
]
