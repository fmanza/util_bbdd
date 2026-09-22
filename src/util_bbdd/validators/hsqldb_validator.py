"""
HSQLDB Query Validator
"""

import logging
import re

from typing import Any

from ..models import QueryDefinition
from .base_validator import QueryParameterValidator


class HSQLDBValidator(QueryParameterValidator):
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
        3. Resto de identificadores (rutina, tipo_rutina, tablespace) con allowlist compartida

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

        # Plantillas usan "tabla", pero se mantiene alias legacy "table" (regla propia de HSQLDB,
        # más permisiva que la allowlist compartida: admite guion).
        table_name = params.get("tabla", params.get("table"))
        if table_name is not None:
            is_valid_table, table_errors = self._validate_table_name(table_name)
            if not is_valid_table:
                return False, table_errors

        identifier_check = self._check_optional_identifiers(
            params,
            (
                ("rutina", "Routine name", None),
                ("tipo_rutina", "Routine type", None),
                ("tablespace", "Tablespace", None),
            ),
        )
        if identifier_check is not None:
            return identifier_check

        self.logger.debug(f"✅ HSQLDB validation passed (warnings={len(warnings)})")
        return True, warnings
