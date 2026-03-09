"""
PostgreSQL Query Validator
"""

import logging

from typing import Any

from ..models import QueryDefinition
from .base_validator import DatabaseTypeValidator


class PostgreSQLValidator(DatabaseTypeValidator):
    """Validador de queries para PostgreSQL.

    Reglas específicas de PostgreSQL:
    - Parámetro 'database' o 'schema' (PostgreSQL usa nspname)
    - Nombres case-insensitive por defecto (pero se preservan si citados)
    """

    db_type = "postgresql"

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(__name__)

    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para PostgreSQL.

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
                msg: str = f"Missing required parameter '{required_param}' for query '{query_def.name}'"
                self.logger.debug(f"❌ Validation failed: {msg}")
                return False, [msg]

            if params[required_param] is None or (
                isinstance(params[required_param], str) and params[required_param].strip() == ""
            ):
                msg = f"Parameter '{required_param}' cannot be empty or None"
                return False, [msg]

        # Validar database/schema si está presente
        for param_name in ["database", "schema"]:
            if param_name in params:
                db_name = params[param_name]
                if not isinstance(db_name, str) or len(db_name.strip()) == 0:
                    msg = f"Parameter '{param_name}' cannot be empty"
                    return False, [msg]

        self.logger.debug(f"✅ PostgreSQL validation passed (warnings={len(warnings)})")
        return True, warnings
