"""
Oracle Query Validator
"""

import logging
import re

from typing import Any

from ..models import QueryDefinition
from .base_validator import QueryParameterValidator


class OracleValidator(QueryParameterValidator):
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
        3. Resto de identificadores (tabla, rutina, tipo_rutina, tablespace) con allowlist compartida

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

        # Oracle templates reales usan "esquema", pero se mantiene compatibilidad con "schema".
        schema_value = params.get("esquema", params.get("schema"))
        if schema_value is not None:
            is_valid_schema, schema_errors = self._validate_oracle_identifier(schema_value, "Schema")
            if not is_valid_schema:
                return False, schema_errors

        identifier_check = self._check_optional_identifiers(params, self._COMMON_IDENTIFIER_SPECS)
        if identifier_check is not None:
            return identifier_check

        self.logger.debug(f"✅ Oracle validation passed (warnings={len(warnings)})")
        return True, warnings
