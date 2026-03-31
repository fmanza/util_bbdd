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
        self.logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def _validate_table_name(value: Any) -> tuple[bool, list[str]]:
        if not isinstance(value, str) or len(value.strip()) == 0:
            return False, ["Table name cannot be empty"]

        if not re.match(r"^[A-Za-z0-9_\-]+$", value):
            msg = f"HSQLDB: Table name contains invalid characters: '{value}'. Allowed: alphanumeric, dash, underscore"
            return False, [msg]

        return True, []

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

        # Plantillas usan "tabla", pero se mantiene alias legacy "table".
        table_name = params.get("tabla", params.get("table"))
        if table_name is not None:
            is_valid_table, table_errors = self._validate_table_name(table_name)
            if not is_valid_table:
                return False, table_errors

        self.logger.debug(f"✅ HSQLDB validation passed (warnings={len(warnings)})")
        return True, warnings
