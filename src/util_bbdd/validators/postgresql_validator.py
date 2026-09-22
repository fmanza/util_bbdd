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

        Verifica también, con la allowlist compartida, los identificadores (database/schema/
        esquema, tabla, rutina, tipo_rutina, tablespace) que ``QueryResolver`` interpola crudo
        en el SQL final.

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

        # Validar contexto de esquema. Algunas plantillas usan "esquema".
        schema_specs = tuple((name, "Schema", None) for name in ("database", "schema", "esquema"))
        identifier_check = self._check_optional_identifiers(params, (*schema_specs, *self._COMMON_IDENTIFIER_SPECS))
        if identifier_check is not None:
            return identifier_check

        self.logger.debug(f"✅ PostgreSQL validation passed (warnings={len(warnings)})")
        return True, warnings
