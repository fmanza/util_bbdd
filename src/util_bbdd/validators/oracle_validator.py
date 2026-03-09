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
        warnings = []

        # Verificar parámetros requeridos
        for required_param in query_def.required_params:
            if required_param not in params:
                msg = f"Missing required parameter '{required_param}' for query '{query_def.name}'"
                self.logger.debug(f"❌ Validation failed: {msg}")
                return False, [msg]

            if params[required_param] is None or (
                isinstance(params[required_param], str) and params[required_param].strip() == ""
            ):
                msg = f"Parameter '{required_param}' cannot be empty or None"
                return False, [msg]

        # Validar esquema si está presente
        if "schema" in params:
            schema = params["schema"]
            if not isinstance(schema, str) or len(schema.strip()) == 0:
                return False, ["Schema cannot be empty"]

            # Oracle schema names: alphanumeric + underscore + $ + #, max 30 chars
            if len(schema) > 30:
                msg = f"Oracle schema name cannot exceed 30 characters (got {len(schema)})"
                return False, [msg]

            if not re.match(r"^[A-Za-z0-9_$#]+$", schema):
                msg = f"Oracle schema name contains invalid characters: '{schema}'. Allowed: alphanumeric, underscore, $, #"
                return False, [msg]

        self.logger.debug(f"✅ Oracle validation passed (warnings={len(warnings)})")
        return True, warnings
