"""
HSQLDB Query Validator
"""

import logging
import re

from typing import Any

from ..models import QueryDefinition
from .base_validator import DatabaseTypeValidator


class HSQLDBValidator(DatabaseTypeValidator):
    """Validador de queries para HSQLDB.

    Reglas específicas de HSQLDB:
    - Nombres de tabla: solo letras, números, guiones, guiones bajos
    - Sin características avanzadas
    """

    db_type = "hsqldb"

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para HSQLDB.

        Verifica:
        1. Parámetros requeridos presentes
        2. Nombre de tabla válido para HSQLDB

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

        # Validar nombre de tabla si está presente (HSQLDB es muy restrictivo)
        if "table" in params:
            table_name = params["table"]
            if not isinstance(table_name, str) or len(table_name.strip()) == 0:
                return False, ["Table name cannot be empty"]

            # HSQLDB: solo alfanumérico, guión, guión bajo
            # La validación de HSQLDB es bastante permisiva en realidad,
            # pero históricamente podría tener restricciones
            if not re.match(r"^[A-Za-z0-9_\-]+$", table_name):
                msg = (
                    f"HSQLDB: Table name contains invalid characters: '{table_name}'. "
                    f"Allowed: alphanumeric, dash, underscore"
                )
                return False, [msg]

        self.logger.debug(f"✅ HSQLDB validation passed (warnings={len(warnings)})")
        return True, warnings
