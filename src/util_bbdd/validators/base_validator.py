"""
Base validator: Clase abstracta para todos los validadores de BD
"""

import re

from abc import ABC, abstractmethod
from typing import Any

from ..models import QueryDefinition

# Allowlist compartida para identificadores (tabla, rutina, tipo_rutina, tablespace, database,
# schema/esquema) que QueryResolver._interpolate_sql() interpola crudo en el SQL final vía
# str.format(). Sin esta allowlist, un valor como "x; DROP TABLE y; --" pasaba la validación de
# varios motores sin objeción (ver AUDIT_CODE SVC-02, 2026-09-22).
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_$#]+$")


class QueryParameterValidator(ABC):
    """Clase base para validadores de parámetros de query específicos de motor de BD.

    Cada motor (MariaDB, Oracle, PostgreSQL, etc.) puede tener reglas
    de validación específicas. Esta clase define la interfaz común.

    Renombrada desde ``DatabaseTypeValidator`` (SVC-05, AUDIT_CODE 2026-09-22):
    colisionaba en nombre con ``_drivers.validator.DatabaseTypeValidator`` (una
    clase totalmente distinta que valida si un db_type está soportado, no
    parámetros de query) — superficie de import confusa entre ambas.

    Subclases:
    - MariaDBValidator (y MySQLValidator, que hereda de ella)
    - OracleValidator
    - PostgreSQLValidator
    - HSQLDBValidator
    - SQLServerValidator
    - SQLiteValidator
    """

    db_type: str
    """Tipo de BD que valida (ej: "mariadb")"""

    @staticmethod
    def _validate_identifier(value: Any, label: str, *, max_length: int | None = None) -> tuple[bool, list[str]]:
        """Valida que ``value`` sea un identificador SQL simple (allowlist de caracteres).

        Usar para todo parámetro que ``QueryResolver`` vaya a interpolar crudo en el SQL final
        (nombres de tabla, rutina, tipo de rutina, tablespace, schema/database).

        Args:
            value: Valor a validar.
            label: Nombre legible del parámetro, usado en el mensaje de error.
            max_length: Longitud máxima opcional (p. ej. 30 para identificadores Oracle).

        Returns:
            (is_valid, warnings_list)
        """
        if not isinstance(value, str) or len(value.strip()) == 0:
            return False, [f"{label} cannot be empty"]

        if max_length is not None and len(value) > max_length:
            return False, [f"{label} cannot exceed {max_length} characters (got {len(value)})"]

        if not _IDENTIFIER_RE.match(value):
            msg = f"{label} contains invalid characters: '{value}'. Allowed: alphanumeric, underscore, $, #"
            return False, [msg]

        return True, []

    @staticmethod
    def _check_required_params(query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]] | None:
        """Verifica que los parámetros requeridos por ``query_def`` estén presentes y no vacíos.

        Returns:
            ``None`` si la comprobación pasa (el caller debe seguir validando); una tupla
            ``(False, [mensaje])`` si falla.
        """
        for required_param in query_def.required_params:
            if required_param not in params:
                return False, [f"Missing required parameter '{required_param}' for query '{query_def.name}'"]
            value = params[required_param]
            if value is None or (isinstance(value, str) and value.strip() == ""):
                return False, [f"Parameter '{required_param}' cannot be empty or None"]
        return None

    @classmethod
    def _check_optional_identifiers(
        cls, params: dict[str, Any], specs: tuple[tuple[str, str, int | None], ...]
    ) -> tuple[bool, list[str]] | None:
        """Valida, si están presentes, los parámetros identificador-shaped de ``specs``.

        Args:
            params: Parámetros proporcionados a la query.
            specs: Tuplas ``(nombre_parametro, etiqueta, max_length)``.

        Returns:
            ``None`` si todos los presentes son válidos; ``(False, [mensaje])`` si alguno falla.
        """
        for param_name, label, max_length in specs:
            if param_name in params:
                is_valid, errors = cls._validate_identifier(params[param_name], label, max_length=max_length)
                if not is_valid:
                    return False, errors
        return None

    #: Parámetros que ``QueryResolver`` interpola como nombres de objeto (no schema/database,
    #: que cada validador trata con su propia regla más específica). Comunes a los 6 motores.
    _COMMON_IDENTIFIER_SPECS: tuple[tuple[str, str, int | None], ...] = (
        ("tabla", "Table name", None),
        ("table", "Table name", None),
        ("rutina", "Routine name", None),
        ("tipo_rutina", "Routine type", None),
        ("tablespace", "Tablespace", None),
    )

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
