"""
SQL Server Query Validator
"""

import logging
import re

from typing import Any

from ..models import QueryDefinition
from .base_validator import DatabaseTypeValidator


class SQLServerValidator(DatabaseTypeValidator):
    """Validador de queries para SQL Server.

    Reglas específicas de SQL Server:
    - Parámetro 'esquema' (default 'dbo')
    - Nombres pueden citarse con brackets [name]
    """

    db_type = "sqlserver"

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _validate_schema_name(value: Any) -> tuple[bool, list[str]]:
        if not isinstance(value, str) or len(value.strip()) == 0:
            return False, ["Schema cannot be empty"]

        # Soporte básico para identificadores sin brackets.
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_#$@]*$", value):
            return False, [f"Schema contains invalid characters: '{value}'"]

        return True, []

    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para SQL Server.

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

        # SQL Server templates pueden usar "esquema" o "schema".
        schema_value = params.get("esquema", params.get("schema"))
        if schema_value is not None:
            is_valid_schema, schema_errors = self._validate_schema_name(schema_value)
            if not is_valid_schema:
                return False, schema_errors

        self.logger.debug(f"✅ SQL Server validation passed (warnings={len(warnings)})")
        return True, warnings
