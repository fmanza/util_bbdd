"""
MariaDB Query Validator
"""

import logging

from typing import Any

from ..models import QueryDefinition
from .base_validator import DatabaseTypeValidator


class MariaDBValidator(DatabaseTypeValidator):
    """Validador de queries para MariaDB.

    Reglas específicas de MariaDB:
    - Parámetro 'database' casi siempre requerido (salvo algunas queries)
    - Charset optional pero validable
    - Sin validaciones complejas adicionales (SQL simple)
    """

    db_type = "mariadb"

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(__name__)

    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para MariaDB.

        Verifica:
        1. Todos los parámetros requeridos están presentes y no vacíos
        2. Parámetros conocidos tienen tipos válidos

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
                self.logger.debug(f"❌ Validation failed: {msg}")
                return False, [msg]

        # Validar parámetros específicos de MariaDB
        if "charset" in params:
            valid_charsets: list[str] = ["utf8", "utf8mb4", "utf16", "latin1", "ascii"]
            if params["charset"] not in valid_charsets:
                msg: str = f"Unusual charset: {params['charset']} (expected one of {valid_charsets})"
                warnings.append(msg)
                self.logger.debug(f"⚠️ {msg}")

        if "database" in params:
            db_name = params["database"]
            if not isinstance(db_name, str) or len(db_name) == 0:
                return False, ["Database name cannot be empty"]

        self.logger.debug(f"✅ MariaDB validation passed (warnings={len(warnings)})")
        return True, warnings
