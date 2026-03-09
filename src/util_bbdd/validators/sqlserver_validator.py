"""
SQL Server Query Validator
"""

import logging

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

    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para SQL Server.

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

        # SQL Server: esquema default es 'dbo' pero puede ser otro
        if "esquema" in params:
            schema = params["esquema"]
            if not isinstance(schema, str) or len(schema.strip()) == 0:
                return False, ["Schema cannot be empty"]

        self.logger.debug(f"✅ SQL Server validation passed (warnings={len(warnings)})")
        return True, warnings
