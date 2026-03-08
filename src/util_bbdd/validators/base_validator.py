"""
Base validator: Clase abstracta para todos los validadores de BD
"""

from abc import ABC, abstractmethod
from typing import Any

from ..models import QueryDefinition


class DatabaseTypeValidator(ABC):
    """Clase base para validadores específicos de motor de BD.

    Cada motor (MariaDB, Oracle, PostgreSQL, etc.) puede tener reglas
    de validación específicas. Esta clase define la interfaz común.

    Subclases:
    - MariaDBValidator
    - OracleValidator
    - PostgreSQLValidator
    - HSQLDBValidator
    - SQLServerValidator
    - SQLiteValidator
    """

    db_type: str
    """Tipo de BD que valida (ej: "mariadb")"""

    @abstractmethod
    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para una query en este motor.

        Args:
            query_def: Definición de la query
            params: Parámetros proporcionados

        Returns:
            Tupla (is_valid, warnings_list):
            - is_valid: True si la validación pasó
            - warnings_list: Lista de advertencias (puede estar vacía)

        Raises:
            No debe levantar excepciones. Retornar (False, [error_msg])
        """
        pass
