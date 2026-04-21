"""Carga y coercion tipada del JSON de tipos de bases de datos."""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any, cast

JsonDict = dict[str, Any]
JsonObjectMap = dict[str, JsonDict]
OptionalParamsConfig = list[JsonDict]
ErrorMessagesConfig = dict[str, str]


class ConfigTypeCoercer:
    """Coerción de tipos para configuración JSON (patrón: Type Object).

    Centraliza la lógica de validación y casting de tipos JSON a estructuras
    tipadas, manteniendo consistencia y facilitando testing.
    """

    @staticmethod
    def to_json_dict(value: Any) -> JsonDict:
        """Coerciona un valor a diccionario JSON plano.

        Args:
            value: Valor a coercionar

        Returns:
            JsonDict: Diccionario tipado o {} si casting falla
        """
        return cast(JsonDict, value) if isinstance(value, dict) else {}

    @staticmethod
    def to_json_object_map(value: Any) -> JsonObjectMap:
        """Coerciona un valor a mapa de objetos JSON.

        Args:
            value: Valor a coercionar

        Returns:
            JsonObjectMap: Mapa tipado o {} si casting falla
        """
        return cast(JsonObjectMap, value) if isinstance(value, dict) else {}

    @staticmethod
    def to_string_list(value: Any) -> list[str]:
        """Coerciona un valor a lista de strings.

        Args:
            value: Valor a coercionar

        Returns:
            list[str]: Lista de strings o [] si casting falla
        """
        return cast(list[str], value) if isinstance(value, list) else []

    @staticmethod
    def to_optional_params_config(value: Any) -> OptionalParamsConfig:
        """Coerciona la lista de parametros opcionales del JSON.

        Args:
            value: Valor a coercionar

        Returns:
            OptionalParamsConfig: Configuración de parámetros o [] si casting falla
        """
        return cast(OptionalParamsConfig, value) if isinstance(value, list) else []

    @staticmethod
    def to_error_messages_config(value: Any) -> ErrorMessagesConfig:
        """Coerciona la seccion de mensajes de error.

        Args:
            value: Valor a coercionar

        Returns:
            ErrorMessagesConfig: Configuración de mensajes o {} si casting falla
        """
        return cast(ErrorMessagesConfig, value) if isinstance(value, dict) else {}


def load_database_type_config(config_file: Path) -> JsonDict:
    """Carga el JSON de configuracion de tipos de base de datos."""
    try:
        with config_file.open(encoding="utf-8") as file_handle:
            return ConfigTypeCoercer.to_json_dict(json.load(file_handle))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_file}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Error al leer archivo JSON: {error}") from error


__all__: list[str] = [
    "ConfigTypeCoercer",
    "ErrorMessagesConfig",
    "JsonDict",
    "JsonObjectMap",
    "OptionalParamsConfig",
    "load_database_type_config",
]
