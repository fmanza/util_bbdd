"""Modulo para validacion y gestion de drivers de bases de datos.

Maneja la configuración y validación de tipos de bases de datos desde
database_types.json, centralizando la lógica de drivers.
"""

import json

from pathlib import Path
from typing import Any

from .._core import InvalidDatabaseType
from ._config_loader import (
    ConfigTypeCoercer,
    JsonDict,
    JsonObjectMap,
    OptionalParamsConfig,
    load_database_type_config,
)


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
        self._config_data: JsonDict = {}
        self._load_config()

    def _metadata_config(self) -> JsonDict:
        """Devuelve la sección metadata tipada del archivo de configuración."""
        return ConfigTypeCoercer.to_json_dict(self._config_data.get("metadata"))

    def _database_types_config(self) -> JsonObjectMap:
        """Devuelve la sección database_types tipada del archivo de configuración."""
        return ConfigTypeCoercer.to_json_object_map(self._config_data.get("database_types"))

    def _examples_config(self) -> JsonObjectMap:
        """Devuelve la sección examples tipada del archivo de configuración."""
        return ConfigTypeCoercer.to_json_object_map(self._config_data.get("examples"))

    def _error_messages_config(self) -> dict[str, str]:
        """Devuelve la sección error_messages tipada del archivo de configuración."""
        return ConfigTypeCoercer.to_error_messages_config(self._config_data.get("error_messages"))

    def _load_config(self) -> None:
        """Carga la configuracion desde el archivo JSON.

        Raises:
            FileNotFoundError: Si no se encuentra el archivo
            ValueError: Si el JSON es inválido
        """
        self._config_data = load_database_type_config(self.config_file)

    def get_supported_db_types(self) -> list[str]:
        """Obtiene la lista de tipos de bases de datos soportados.

        Returns:
            Lista de tipos de BD soportados (ej: ['mariadb', 'postgresql', ...])
        """
        return ConfigTypeCoercer.to_string_list(self._metadata_config().get("supported_db_types"))

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
        return self._database_types_config().get(db_type.lower(), {})

    def get_db_type_name(self, db_type: str) -> str:
        """Obtiene el nombre descriptivo de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Nombre descriptivo (ej: 'MariaDB', 'PostgreSQL')
        """
        info = self.get_db_type_info(db_type)
        name = info.get("name")
        return str(name) if isinstance(name, str) else db_type.title()

    def get_db_type_description(self, db_type: str) -> str:
        """Obtiene la descripción de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Descripción del tipo de BD
        """
        info = self.get_db_type_info(db_type)
        description = info.get("description")
        return str(description) if isinstance(description, str) else "Sin descripción disponible"

    def get_db_type_features(self, db_type: str) -> list[str]:
        """Obtiene las características soportadas de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de características soportadas (ej: ['async', 'transactions', ...])
        """
        info = self.get_db_type_info(db_type)
        return ConfigTypeCoercer.to_string_list(info.get("supported_features"))

    def get_db_type_default_port(self, db_type: str) -> int:
        """Obtiene el puerto por defecto de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Puerto por defecto (ej: 3306 para MariaDB)
        """
        info = self.get_db_type_info(db_type)
        default_port = info.get("default_port", 0)
        return int(default_port) if isinstance(default_port, int) and not isinstance(default_port, bool) else 0

    def get_db_type_driver_info(self, db_type: str) -> JsonDict:
        """Obtiene información del driver de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con información del driver
        """
        info = self.get_db_type_info(db_type)
        return ConfigTypeCoercer.to_json_dict(info.get("driver_info"))

    def get_db_type_connection_params(self, db_type: str) -> JsonDict:
        """Obtiene la configuración de parámetros de conexión de un tipo de BD.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Diccionario con configuración de parámetros (required, optional, etc)
        """
        info = self.get_db_type_info(db_type)
        return ConfigTypeCoercer.to_json_dict(info.get("connection_params"))

    def get_required_params(self, db_type: str) -> list[str]:
        """Obtiene los parámetros requeridos para un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de nombres de parámetros requeridos
        """
        params_config = self.get_db_type_connection_params(db_type)
        return ConfigTypeCoercer.to_string_list(params_config.get("required"))

    def get_optional_params(self, db_type: str) -> OptionalParamsConfig:
        """Obtiene los parámetros opcionales de un tipo de base de datos.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de parámetros opcionales con su configuración
        """
        params_config = self.get_db_type_connection_params(db_type)
        return ConfigTypeCoercer.to_optional_params_config(params_config.get("optional"))

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
        required_params = self.get_required_params(db_type)
        optional_params_list = self.get_optional_params(db_type)
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

    def get_param_info(self, db_type: str, param_name: str) -> JsonDict | None:
        """Obtiene información de un parámetro específico.

        Args:
            db_type: Tipo de base de datos
            param_name: Nombre del parámetro

        Returns:
            Información del parámetro o None si no existe
        """
        optional_params = self.get_optional_params(db_type)
        for param in optional_params:
            if param.get("name") == param_name:
                return param
        return None

    def get_db_type_examples(self, db_type: str) -> JsonDict:
        """Obtiene ejemplos de configuración para un tipo de base de datos."""
        return self._examples_config().get(db_type.lower(), {})

    def get_error_message(self, error_key: str, **kwargs: Any) -> str:
        """Obtiene un mensaje de error formateado."""
        template = self._error_messages_config().get(error_key, "Error desconocido")
        return template.format(**kwargs)

    def get_all_db_types_summary(self) -> JsonObjectMap:
        """Obtiene un resumen de todos los tipos de bases de datos."""
        summary: JsonObjectMap = {}
        for db_type in self.get_supported_db_types():
            info = self.get_db_type_info(db_type)
            summary[db_type] = {
                "name": info.get("name", ""),
                "description": info.get("description", ""),
                "default_port": info.get("default_port", 0),
                "required_params": self.get_required_params(db_type),
                "optional_params_count": len(self.get_optional_params(db_type)),
                "features_count": len(self.get_db_type_features(db_type)),
            }
        return summary

    def get_compatibility_info(self) -> JsonDict:
        """Obtiene información de compatibilidad."""
        return ConfigTypeCoercer.to_json_dict(self._config_data.get("compatibility"))

    def get_metadata(self) -> JsonDict:
        """Obtiene metadatos del archivo de configuración."""
        return self._metadata_config()

    def reload_config(self) -> None:
        """Recarga la configuración desde el archivo actual."""
        self._load_config()

    def export_config(self, output_file: Path) -> None:
        """Exporta la configuración actual a un archivo JSON."""
        try:
            with output_file.open("w", encoding="utf-8") as file_handle:
                json.dump(self._config_data, file_handle, indent=2, ensure_ascii=False)
        except OSError as e:
            raise OSError(f"Error al exportar configuración: {e}") from e


_db_validator: DatabaseTypeValidator | None = None


def get_database_validator(config_file: Path | None = None) -> DatabaseTypeValidator:
    """Obtiene una instancia reutilizable del validador de tipos de BD (Singleton).

    Implementa el patrón Singleton con lazy-loading para centralizar la carga
    de configuración de database_types.json y evitar múltiples lecturas de disco.

    **Patrón de Singleton:**
    - Primera llamada: Crea instancia de DatabaseTypeValidator y la almacena en
      variable global _db_validator
    - Llamadas posteriores: Retorna la instancia almacenada (reutilización)
    - Si config_file es fornecido: Reinicia la instancia (útil para testing)

    **Por qué Singleton aquí:**
    1. **Performance:** El archivo database_types.json se carga solo 1 vez
    2. **Consistency:** Todos los clientes usan la misma configuración
    3. **Memory efficiency:** Una única instancia en memoria
    4. **Simplicity:** Interfaz clara sin factory patterns complejos

    **Limitation:** Este patrón está limitado a single-threaded synchronous contexts.
    En contextos multi-threaded o async, puede causar race conditions.
    Futuro refactor considerará inyección de dependencias o thread-safe singleton.

    Args:
        config_file: Path al archivo JSON de configuración (opcional).
                     Si es None, usa `data/database_types.json` por defecto.
                     Si se fornece, reinicia la instancia con nuevo config_file.

    Returns:
        DatabaseTypeValidator: Instancia singleton del validador

    Examples:
        >>> # Primera llamada: crea instancia
        >>> validator = get_database_validator()
        >>> validator.is_db_type_supported('postgresql')
        True

        >>> # Segunda llamada: reutiliza la misma instancia
        >>> validator2 = get_database_validator()
        >>> validator is validator2  # mismo objeto
        True

        >>> # Con config_file: reinicia con nueva configuración (testing)
        >>> validator_test = get_database_validator(Path('tests/fixtures/db_types.json'))
        >>> validator_test is validator  # nueva instancia creada
        False

    Raises:
        FileNotFoundError: Si config_file no existe (delegado a DatabaseTypeValidator)
        ValueError: Si el JSON es inválido (delegado a DatabaseTypeValidator)

    See Also:
        DatabaseTypeValidator: Clase que encapsula validación de BD
        validate_db_type: Función de conveniencia que usa este singleton
        get_db_type_info: Función de conveniencia que usa este singleton
    """
    global _db_validator
    if _db_validator is None or config_file is not None:
        _db_validator = DatabaseTypeValidator(config_file)
    return _db_validator


def validate_db_type(db_type: str) -> bool:
    """Función de conveniencia para validar un tipo de base de datos.

    Obtiene el validador singleton y ejecuta validación.

    Args:
        db_type: Tipo de BD a validar (ej: 'postgresql', 'oracle', 'mariadb')

    Returns:
        bool: True si el tipo es válido. Nunca retorna False: un tipo no
        soportado lanza una excepción en su lugar.

    Raises:
        InvalidDatabaseType: Si el tipo de BD no es soportado

    Examples:
        >>> validate_db_type('postgresql')
        True
        >>> validate_db_type('invalid_db')
        Traceback (most recent call last):
            ...
        util_bbdd.InvalidDatabaseType: Tipo de base de datos 'invalid_db' no soportado

    See Also:
        get_database_validator: Obtiene la instancia singleton
        DatabaseTypeValidator.validate_db_type: Implementación real
    """
    validator = get_database_validator()
    return validator.validate_db_type(db_type)


def get_db_type_info(db_type: str) -> JsonDict:
    """Función de conveniencia para obtener información de un tipo de BD.

    Obtiene el validador singleton y retorna metadatos del tipo de BD.

    Args:
        db_type: Tipo de BD del cual obtener información

    Returns:
        JsonDict: Diccionario con información del tipo de BD
                 (driver, parameters, examples, etc.)

    Examples:
        >>> info = get_db_type_info('postgresql')
        >>> info['driver']
        'psycopg'
        >>> info['supports_async']
        True

    See Also:
        get_database_validator: Obtiene la instancia singleton
        DatabaseTypeValidator.get_db_type_info: Implementación real
    """
    validator = get_database_validator()
    return validator.get_db_type_info(db_type)


def get_supported_db_types() -> list[str]:
    """Función de conveniencia para listar tipos de bases de datos soportados."""
    validator = get_database_validator()
    return validator.get_supported_db_types()


__all__: list[str] = [
    "DatabaseTypeValidator",
    "get_database_validator",
    "validate_db_type",
    "get_db_type_info",
    "get_supported_db_types",
]
