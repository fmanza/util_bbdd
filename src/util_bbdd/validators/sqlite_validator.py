"""
SQLite Query Validator
"""

import logging

from typing import Any

from ..models import QueryDefinition
from .base_validator import DatabaseTypeValidator


class SQLiteValidator(DatabaseTypeValidator):
    """Validador de queries para SQLite.

    Reglas específicas de SQLite:
    - No requiere esquema explícito (single file database)
    - Valida ruta del archivo de BD si se proporciona
    """

    db_type = "sqlite"

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para SQLite.

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

        # SQLite: puede tener un archivo de BD especificado
        if "database_file" in params:
            db_file = params["database_file"]
            if not isinstance(db_file, str) or len(db_file.strip()) == 0:
                warnings.append("database_file parameter should be a valid path")

        self.logger.debug(f"✅ SQLite validation passed (warnings={len(warnings)})")
        return True, warnings
