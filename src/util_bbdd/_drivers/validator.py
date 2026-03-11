"""Módulo para validación y gestión de drivers de bases de datos.

Maneja la configuración y validación de tipos de bases de datos desde
database_types.json, centralizando la lógica de drivers.
"""

import json

from pathlib import Path
from typing import Any

from .._core import InvalidDatabaseType


class DatabaseTypeValidator:
    """Validador centralizado para tipos de bases de datos.

    Lee configuración desde database_types.json y proporciona:
    - Validación de tipos de BD soportados
    - Información y metadatos de BD
    - Validación de parámetros de conexión
    - Información de drivers
    """

    def __init__(self, config_file: Path | None = None) -> None:
        """Inicializa el validador con archivo de configuración.

        Args:
            config_file: Ruta al archivo JSON de configuración.
                        Si es None, usa data/database_types.json

        Raises:
            FileNotFoundError: Si no se encuentra el archivo de configuración
            ValueError: Si el JSON es inválido
        """
        self.config_file: Path = config_file or (Path(__file__).parents[1] / "data" / "database_types.json")
        self._config_data: dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Carga la configuración desde el archivo JSON.

        Raises:
            FileNotFoundError: Si no se encuentra el archivo
            ValueError: Si el JSON es inválido
        """
        try:
            with open(self.config_file, encoding="utf-8") as f:
                self._config_data = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {self.config_file}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Error al leer archivo JSON: {e}") from e

    def get_supported_db_types(self) -> list[str]:
        """Obtiene la lista de tipos de bases de datos soportados.

        Returns:
            Lista de tipos de BD soportados (ej: ['mariadb', 'postgresql', ...])
        """
        return self._config_data.get("metadata", {}).get("supported_db_types", [])

    def is_db_type_supported(self, db_type: str) -> bool:
        """Verifica si un tipo de base de datos está soportado.

        Args:
            db_type: Tipo de base de datos a verificar (case-insensitive)

        Returns:
            True si está soportado, False en caso contrario
        """
        return db_type.lower() in self.get_supported_db_types()

    def validate_db_type(self, db_type: str) -> bool:
        """Valida si un tipo de base de datos es válido.

        Args:
            db_type: Tipo de base de datos a validar

        Returns:
            True si es válido

        Raises:
            InvalidDatabaseType: Si el tipo no está soportado
        """
        if not self.is_db_type_supported(db_type):
            supported: str = ", ".join(self.get_supported_db_types())
            raise InvalidDatabaseType(
                message=f"Tipo de base de datos '{db_type}' no soportado",
                db_type=db_type,
                details=f"Tipos soportados: {supported}",
            )
        return True

    def get_db_type_info(self, db_type: str) -> dict[str, Any]:
        """Obtiene información completa de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con información del tipo de BD

        Raises:
            InvalidDatabaseType: Si el tipo no está soportado
        """
        self.validate_db_type(db_type)
        return self._config_data.get("database_types", {}).get(db_type.lower(), {})

    def get_db_type_name(self, db_type: str) -> str:
        """Obtiene el nombre descriptivo de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Nombre descriptivo (ej: 'MariaDB', 'PostgreSQL')
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("name", db_type.title())

    def get_db_type_description(self, db_type: str) -> str:
        """Obtiene la descripción de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Descripción del tipo de BD
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("description", "Sin descripción disponible")

    def get_db_type_features(self, db_type: str) -> list[str]:
        """Obtiene las características soportadas de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de características soportadas (ej: ['async', 'transactions', ...])
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("supported_features", [])

    def get_db_type_default_port(self, db_type: str) -> int:
        """Obtiene el puerto por defecto de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Puerto por defecto (ej: 3306 para MariaDB)
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("default_port", 0)

    def get_db_type_driver_info(self, db_type: str) -> dict[str, Any]:
        """Obtiene información del driver de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con información del driver
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("driver_info", {})

    def get_db_type_connection_params(self, db_type: str) -> dict[str, Any]:
        """Obtiene la configuración de parámetros de conexión de un tipo de BD.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con configuración de parámetros (required, optional, etc)
        """
        info: dict[str, Any] = self.get_db_type_info(db_type)
        return info.get("connection_params", {})

    def get_required_params(self, db_type: str) -> list[str]:
        """Obtiene los parámetros requeridos para un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de nombres de parámetros requeridos
        """
        params_config: dict[str, Any] = self.get_db_type_connection_params(db_type)
        return params_config.get("required", [])

    def get_optional_params(self, db_type: str) -> list[dict[str, Any]]:
        """Obtiene los parámetros opcionales de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de parámetros opcionales con su configuración
        """
        params_config: dict[str, Any] = self.get_db_type_connection_params(db_type)
        return params_config.get("optional", [])

    def validate_connection_params(self, db_type: str, conn_params: dict[str, Any]) -> bool:
        """Valida los parámetros de conexión para un tipo de base de datos.

        Verifica que estén todos los parámetros requeridos y que no haya
        parámetros inválidos.

        Args:
            db_type: Tipo de base de datos
            conn_params: Diccionario de parámetros de conexión a validar

        Returns:
            True si los parámetros son válidos

        Raises:
            InvalidDatabaseType: Si el tipo no está soportado
            ValueError: Si faltan parámetros requeridos o hay inválidos
        """
        self.validate_db_type(db_type)

        # Obtener parámetros válidos (requeridos + opcionales)
        required_params: list[str] = self.get_required_params(db_type)
        optional_params_list: list[dict[str, Any]] = self.get_optional_params(db_type)
        optional_param_names: list[str] = [str(p.get("name")) for p in optional_params_list if p.get("name")]

        valid_params: list[str] = required_params + optional_param_names

        # Verificar parámetros faltantes
        missing_params: list[str] = [p for p in required_params if p not in conn_params]
        if missing_params:
            raise ValueError(f"Faltan parámetros requeridos para {db_type}: {', '.join(missing_params)}")

        # Verificar parámetros sobrantes (no válidos)
        provided_params: list[str] = list(conn_params.keys())
        extra_params: list[str] = [p for p in provided_params if p not in valid_params]
        if extra_params:
            raise ValueError(
                f"Parámetros no válidos para {db_type}: {', '.join(extra_params)}. "
                f"Parámetros válidos: {', '.join(sorted(valid_params))}"
            )

        return True

    def get_param_info(self, db_type: str, param_name: str) -> dict[str, Any] | None:
        """Obtiene información de un parámetro específico.

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
