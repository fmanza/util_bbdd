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


def default_driver(driver_info: Any) -> JsonDict:
    """Driver predeterminado de un motor con la misma forma en todos (G14 de util_bbdd_web, v4.6.0).

    ``driver_info`` es un ``dict`` en todos los motores salvo SQL Server, que lista una opción por driver: se toma la
    marcada con ``"default": true`` (o la primera). El resultado es una copia con ``name`` (el ``import_name`` si el
    ``dict`` no lo trae), ``pip_package``, ``install_command``, ``system_requirements``… del driver.

    Args:
        driver_info: Valor de ``driver_info`` del motor en ``database_types.json``.
    """
    if isinstance(driver_info, list):
        options = [ConfigTypeCoercer.to_json_dict(option) for option in driver_info]
        chosen = next((option for option in options if option.get("default") is True), options[0] if options else {})
    else:
        chosen = ConfigTypeCoercer.to_json_dict(driver_info)
    result = dict(chosen)
    result.pop("default", None)
    if "name" not in result and "import_name" in result:
        result["name"] = result["import_name"]
    return result


def with_default_drivers(config: JsonDict) -> JsonDict:
    """Añade ``default_driver`` (:func:`default_driver`) a cada motor de ``database_types``; ``driver_info`` no cambia."""
    for info in ConfigTypeCoercer.to_json_object_map(config.get("database_types")).values():
        if isinstance(info, dict) and "driver_info" in info:
            info["default_driver"] = default_driver(info["driver_info"])
    return config


def load_database_type_config(config_file: Path) -> JsonDict:
    """Carga el JSON de configuracion de tipos de base de datos, con ``default_driver`` en cada motor (v4.6.0)."""
    try:
        with config_file.open(encoding="utf-8") as file_handle:
            return with_default_drivers(ConfigTypeCoercer.to_json_dict(json.load(file_handle)))
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
    "default_driver",
    "load_database_type_config",
    "with_default_drivers",
]
