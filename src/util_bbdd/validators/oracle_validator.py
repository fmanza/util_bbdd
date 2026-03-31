"""
Oracle Query Validator
"""

import logging
import re

from typing import Any

from ..models import QueryDefinition
from .base_validator import DatabaseTypeValidator


class OracleValidator(DatabaseTypeValidator):
    """Validador de queries para Oracle.

    Reglas específicas de Oracle:
    - Parámetro 'esquema' (equivalente a schema/owner en Oracle)
    - Sin validaciones de nombre de tabla complejas
    """

    db_type = "oracle"

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _validate_oracle_identifier(value: Any, label: str) -> tuple[bool, list[str]]:
        """Valida identificadores Oracle (schema/owner)."""
        if not isinstance(value, str) or len(value.strip()) == 0:
            return False, [f"{label} cannot be empty"]

        if len(value) > 30:
            msg = f"Oracle {label.lower()} cannot exceed 30 characters (got {len(value)})"
            return False, [msg]

        if not re.match(r"^[A-Za-z0-9_$#]+$", value):
            msg = (
                f"Oracle {label.lower()} contains invalid characters: '{value}'. "
                "Allowed: alphanumeric, underscore, $, #"
            )
            return False, [msg]

        return True, []

    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para Oracle.

        Verifica:
        1. Parámetros requeridos presentes y no vacíos
        2. Esquema tiene formato válido (alfanumérico, guión bajo)

        Args:
            query_def: Definición de la query
            params: Parámetros proporcionados

        Returns:
            (is_valid, warnings)
        """
        warnings: list[str] = []

        # Verificar parámetros requeridos
        for required_param in query_def.required_params:
            if required_param not in params:
                msg: str = f"Missing required parameter '{required_param}' for query '{query_def.name}'"
                self.logger.debug(f"❌ Validation failed: {msg}")
                return False, [msg]

            if params[required_param] is None or (
                isinstance(params[required_param], str) and params[required_param].strip() == ""
            ):
                msg = f"Parameter '{required_param}' cannot be empty or None"
                return False, [msg]

        # Oracle templates reales usan "esquema", pero se mantiene compatibilidad con "schema".
        schema_value = params.get("esquema", params.get("schema"))
        if schema_value is not None:
            is_valid_schema, schema_errors = self._validate_oracle_identifier(schema_value, "Schema")
            if not is_valid_schema:
                return False, schema_errors

        self.logger.debug(f"✅ Oracle validation passed (warnings={len(warnings)})")
        return True, warnings
