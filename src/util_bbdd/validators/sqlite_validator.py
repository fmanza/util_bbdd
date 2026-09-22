"""
SQLite Query Validator
"""

import logging

from typing import Any

from ..models import QueryDefinition
from .base_validator import QueryParameterValidator


class SQLiteValidator(QueryParameterValidator):
    """Validador de queries para SQLite.

    Reglas específicas de SQLite:
    - No requiere esquema explícito (single file database)
    - Valida ruta del archivo de BD si se proporciona
    """

    db_type = "sqlite"

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(__name__)

    def validate_parameters(self, query_def: QueryDefinition, params: dict[str, Any]) -> tuple[bool, list[str]]:
        """Valida parámetros para SQLite.

        Verifica también, con la allowlist compartida, los identificadores (tabla, rutina,
        tipo_rutina, tablespace) que ``QueryResolver`` interpola crudo en el SQL final.
        ``database_file`` no pasa por esa allowlist porque es una ruta de archivo, no un
        identificador SQL (puede contener ``/``, ``.``, etc.).

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

        # SQLite: puede tener un archivo de BD especificado
        if "database_file" in params:
            db_file = params["database_file"]
            if not isinstance(db_file, str) or len(db_file.strip()) == 0:
                warnings.append("database_file parameter should be a valid path")

        identifier_check = self._check_optional_identifiers(params, self._COMMON_IDENTIFIER_SPECS)
        if identifier_check is not None:
            return identifier_check

        self.logger.debug(f"✅ SQLite validation passed (warnings={len(warnings)})")
        return True, warnings
