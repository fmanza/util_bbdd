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
        3. Identificadores (database, tabla, rutina, tipo_rutina, tablespace) con allowlist
           compartida — ``QueryResolver`` los interpola crudo en el SQL final

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

        # Validar parámetros específicos de MariaDB
        if "charset" in params:
            valid_charsets: list[str] = ["utf8", "utf8mb4", "utf16", "latin1", "ascii"]
            if params["charset"] not in valid_charsets:
                warning_msg: str = f"Unusual charset: {params['charset']} (expected one of {valid_charsets})"
                warnings.append(warning_msg)
                self.logger.debug(f"⚠️ {warning_msg}")

        identifier_check = self._check_optional_identifiers(
            params, (("database", "Database name", None), *self._COMMON_IDENTIFIER_SPECS)
        )
        if identifier_check is not None:
            return identifier_check

        self.logger.debug(f"✅ MariaDB validation passed (warnings={len(warnings)})")
        return True, warnings
