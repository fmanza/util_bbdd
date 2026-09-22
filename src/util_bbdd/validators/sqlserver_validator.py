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

        Verifica también, con la allowlist compartida, los identificadores tabla/rutina/
        tipo_rutina/tablespace que ``QueryResolver`` interpola crudo en el SQL final.

        Args:
            query_def: Definición de la query
            params: Parámetros proporcionados

        Returns:
            (is_valid, warnings)
        """
        warnings: list[str] = []

        required_check = self._check_required_params(query_def, params)
        if required_check is not None:
            self.logger.debug(f"❌ Validation failed: {required_check[1][0]}")
            return required_check

        # SQL Server templates pueden usar "esquema" o "schema".
        schema_value = params.get("esquema", params.get("schema"))
        if schema_value is not None:
            is_valid_schema, schema_errors = self._validate_schema_name(schema_value)
            if not is_valid_schema:
                return False, schema_errors

        identifier_check = self._check_optional_identifiers(params, self._COMMON_IDENTIFIER_SPECS)
        if identifier_check is not None:
            return identifier_check

        self.logger.debug(f"✅ SQL Server validation passed (warnings={len(warnings)})")
        return True, warnings
