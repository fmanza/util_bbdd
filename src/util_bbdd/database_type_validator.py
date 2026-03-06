"""
Módulo para validación y gestión de tipos de bases de datos
Carga configuración desde database_types.json
"""

import json

from pathlib import Path
from typing import Any


class DatabaseTypeValidator:
    """Clase para validar y gestionar tipos de bases de datos"""

    def __init__(self, config_file: Path | None = None):
        """
        Inicializa el validador de tipos de bases de datos

        Args:
            config_file: Ruta al archivo JSON de configuración (opcional)
        """
        self.config_file: Path = config_file or (Path(__file__).parent / "data" / "database_types.json")
        self._config_data: dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Carga la configuración desde el archivo JSON"""
        try:
            with open(self.config_file, encoding="utf-8") as f:
                self._config_data = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {self.config_file}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Error al leer archivo JSON: {e}") from e

    def get_supported_db_types(self) -> list[str]:
        """
        Obtiene la lista de tipos de bases de datos soportados

        Returns:
            Lista de tipos de bases de datos soportados
        """
        return self._config_data.get("metadata", {}).get("supported_db_types", [])

    def is_db_type_supported(self, db_type: str) -> bool:
        """
        Verifica si un tipo de base de datos está soportado

        Args:
            db_type: Tipo de base de datos a verificar

        Returns:
            True si está soportado, False en caso contrario
        """
        return db_type.lower() in self.get_supported_db_types()

    def validate_db_type(self, db_type: str) -> bool:
        """
        Valida si un tipo de base de datos es válido

        Args:
            db_type: Tipo de base de datos a validar

        Returns:
            True si es válido, False en caso contrario

        Raises:
            ValueError: Si el tipo no es válido
        """
        if not self.is_db_type_supported(db_type):
            supported: str = ", ".join(self.get_supported_db_types())
            raise ValueError(f"Tipo de base de datos '{db_type}' no soportado. Tipos soportados: {supported}")
        return True

    def get_db_type_info(self, db_type: str) -> dict[str, Any]:
        """
        Obtiene información completa de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con información del tipo de base de datos

        Raises:
            ValueError: Si el tipo no es soportado
        """
        self.validate_db_type(db_type)
        return self._config_data["database_types"].get(db_type.lower(), {})

    def get_db_type_name(self, db_type: str) -> str:
        """
        Obtiene el nombre descriptivo de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Nombre descriptivo del tipo de base de datos
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("name", db_type.title())

    def get_db_type_description(self, db_type: str) -> str:
        """
        Obtiene la descripción de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Descripción del tipo de base de datos
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("description", "Sin descripción disponible")

    def get_db_type_features(self, db_type: str) -> list[str]:
        """
        Obtiene las características soportadas de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de características soportadas
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("supported_features", [])

    def get_db_type_default_port(self, db_type: str) -> int:
        """
        Obtiene el puerto por defecto de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Puerto por defecto
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("default_port", 0)

    def get_db_type_driver_info(self, db_type: str) -> dict[str, Any]:
        """
        Obtiene información del driver de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con información del driver
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("driver_info", {})

    def get_db_type_connection_params(self, db_type: str) -> dict[str, Any]:
        """
        Obtiene la configuración de parámetros de conexión de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con configuración de parámetros
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("connection_params", {})

    def get_required_params(self, db_type: str) -> list[str]:
        """
        Obtiene los parámetros requeridos para un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de parámetros requeridos
        """
        params_config: dict[str, Any] = self.get_db_type_connection_params(db_type)
        return params_config.get("required", [])

    def get_optional_params(self, db_type: str) -> list[dict[str, Any]]:
        """
        Obtiene los parámetros opcionales de un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de parámetros opcionales con su configuración
        """
        params_config: dict[str, Any] = self.get_db_type_connection_params(db_type)
        return params_config.get("optional", [])

    def validate_connection_params(self, db_type: str, conn_params: dict[str, Any]) -> bool:
        """
        Valida los parámetros de conexión para un tipo de base de datos.
        Verifica que estén todos los parámetros requeridos y que no haya parámetros inválidos.

        Args:
            db_type: Tipo de base de datos
            conn_params: Parámetros de conexión a validar

        Returns:
            True si los parámetros son válidos

        Raises:
            ValueError: Si faltan parámetros requeridos o hay parámetros inválidos
        """
        self.validate_db_type(db_type)

        # Obtener parámetros válidos (requeridos + opcionales)
        required_params: list[str] = self.get_required_params(db_type)
        optional_params_list: list[dict[str, Any]] = self.get_optional_params(db_type)
        optional_param_names: list[str] = [str(p.get("name")) for p in optional_params_list if p.get("name")]

        valid_params: list[str] = required_params + optional_param_names

        # Verificar parámetros faltantes
        missing_params: list[str] = [param for param in required_params if param not in conn_params]
        if missing_params:
            raise ValueError(f"Faltan parámetros requeridos para {db_type}: {', '.join(missing_params)}")

        # Verificar parámetros sobrantes (no válidos)
        provided_params: list[str] = list(conn_params.keys())
        extra_params: list[str] = [param for param in provided_params if param not in valid_params]
        if extra_params:
            raise ValueError(
                f"Parámetros no válidos para {db_type}: {', '.join(extra_params)}. Parámetros válidos: {', '.join(sorted(valid_params))}"
            )

        return True

    def get_param_info(self, db_type: str, param_name: str) -> dict[str, Any] | None:
        """
        Obtiene información de un parámetro específico

        Args:
            db_type: Tipo de base de datos
            param_name: Nombre del parámetro

        Returns:
            Información del parámetro o None si no existe
        """
        optional_params: list[dict[str, Any]] = self.get_optional_params(db_type)
        for param in optional_params:
            if param.get("name") == param_name:
                return param
        return None

    def get_db_type_examples(self, db_type: str) -> dict[str, Any]:
        """
        Obtiene ejemplos de configuración para un tipo de base de datos

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con ejemplos de configuración
        """
        examples = self._config_data.get("examples", {})
        return examples.get(db_type, {})

    def get_error_message(self, error_key: str, **kwargs) -> str:
        """
        Obtiene un mensaje de error formateado

        Args:
            error_key: Clave del mensaje de error
            **kwargs: Parámetros para formatear el mensaje

        Returns:
            Mensaje de error formateado
        """
        error_messages = self._config_data.get("error_messages", {})
        template = error_messages.get(error_key, "Error desconocido")
        return template.format(**kwargs)

    def get_all_db_types_summary(self) -> dict[str, dict[str, Any]]:
        """
        Obtiene un resumen de todos los tipos de bases de datos

        Returns:
            Diccionario con resumen de todos los tipos
        """
        summary = {}
        for db_type in self.get_supported_db_types():
            info: dict[str, Any] = self.get_db_type_info(db_type)
            summary[db_type] = {
                "name": info.get("name", ""),
                "description": info.get("description", ""),
                "default_port": info.get("default_port", 0),
                "required_params": self.get_required_params(db_type),
                "optional_params_count": len(self.get_optional_params(db_type)),
                "features_count": len(self.get_db_type_features(db_type)),
            }
        return summary

    def get_compatibility_info(self) -> dict[str, Any]:
        """
        Obtiene información de compatibilidad

        Returns:
            Diccionario con información de compatibilidad
        """
        return self._config_data.get("compatibility", {})

    def get_metadata(self) -> dict[str, Any]:
        """
        Obtiene metadatos del archivo de configuración

        Returns:
            Diccionario con metadatos
        """
        return self._config_data.get("metadata", {})

    def reload_config(self) -> None:
        """Recarga la configuración desde el archivo"""
        self._load_config()

    def export_config(self, output_file: Path) -> None:
        """
        Exporta la configuración actual a un archivo

        Args:
            output_file: Ruta del archivo de salida
        """
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise OSError(f"Error al exportar configuración: {e}") from e


# Instancia global para uso conveniente
_db_validator = None


def get_database_validator(config_file: Path | None = None) -> DatabaseTypeValidator:
    """
    Obtiene una instancia del validador de tipos de bases de datos

    Args:
        config_file: Ruta al archivo de configuración (opcional)

    Returns:
        Instancia de DatabaseTypeValidator
    """
    global _db_validator
    if _db_validator is None or config_file is not None:
        _db_validator = DatabaseTypeValidator(config_file)
    return _db_validator


def validate_db_type(db_type: str) -> bool:
    """
    Función de conveniencia para validar un tipo de base de datos

    Args:
        db_type: Tipo de base de datos a validar

    Returns:
        True si es válido

    Raises:
        ValueError: Si el tipo no es válido
    """
    validator: DatabaseTypeValidator = get_database_validator()
    return validator.validate_db_type(db_type)


def get_db_type_info(db_type: str) -> dict[str, Any]:
    """
    Función de conveniencia para obtener información de un tipo de base de datos

    Args:
        db_type: Tipo de base de datos

    Returns:
        Información del tipo de base de datos
    """
    validator: DatabaseTypeValidator = get_database_validator()
    return validator.get_db_type_info(db_type)


def get_supported_db_types() -> list[str]:
    """
    Función de conveniencia para obtener tipos de bases de datos soportados

    Returns:
        Lista de tipos soportados
    """
    validator: DatabaseTypeValidator = get_database_validator()
    return validator.get_supported_db_types()
