"""
Query Resolver: Capa de resolución y validación de consultas

El QueryResolver es responsable de:
1. Obtener QueryDefinition desde el registry
2. Validar parámetros usando validadores por motor
3. Interpolar parámetros en el SQL template
4. Retornar ResolvedQuery listo para ejecutar
"""

from __future__ import annotations

import logging
import time

from typing import Any

from util_bbdd.models import QueryDefinition
from util_bbdd.validators.base_validator import QueryParameterValidator

from .._core.exceptions import (
    QueryNotFoundError,
    QueryParameterError,
    QueryValidationError,
)
from ..models import ResolvedQuery
from ..validators import get_type_validator
from .registry import QueryRegistry


class QueryResolver:
    """Resuelve queries: obtiene definición, valida, interpola parámetros.

    Responsabilidades:
    - Obtener QueryDefinition desde QueryRegistry
    - Validar parámetros usando QueryParameterValidator específico
    - Interpolar parámetros en SQL template
    - Retornar ResolvedQuery con SQL final y metadatos

    Example:
        La librería no trae queries registradas: se leen de un JSON ``{motor: {nombre: SQL}}``.

        ```python
        registry = QueryRegistry(Path("queries.json"))  # {"mariadb": {"get_tabla": "SELECT * FROM {tabla}"}}
        resolver = QueryResolver(registry, db_type="mariadb")
        resolved = resolver.resolve("get_tabla", {"tabla": "users"})
        assert resolved.final_sql == "SELECT * FROM users"
        assert resolved.validated
        ```
    """

    def __init__(self, registry: QueryRegistry | None = None, *, db_type: str | None = None) -> None:
        """Inicializa el resolver con un QueryRegistry.

        Args:
            registry: QueryRegistry para obtener definiciones.
                     Si es None, crea uno nuevo con ruta por defecto.
            db_type: Tipo de BD opcional ligado a la instancia.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.registry: QueryRegistry = registry or QueryRegistry()
        self._bound_db_type: str | None = self._normalize_db_type(db_type) if db_type is not None else None
        self.logger.debug("✅ QueryResolver initialized")

    def resolve(
        self,
        query_name: str,
        params: dict[str, Any] | None = None,
    ) -> ResolvedQuery:
        """Resuelve una query: validación + interpolación.

        Flujo:
        1. Obtiene QueryDefinition del registry
        2. Valida parámetros con validador por motor
        3. Interpola parámetros en SQL template
        4. Retorna ResolvedQuery

        Args:
            query_name: Nombre de la query (ej: "obtener_tablas")
            params: Parámetros para interpolar en la query

        Returns:
            ResolvedQuery con SQL final validado

        Raises:
            QueryNotFoundError: Si query no existe
            QueryValidationError: Si validación falla
            QueryParameterError: Si interpolación falla

        Example:
            ```python
            resolved = resolver.resolve("get_tabla", {"tabla": "users"})
            # ResolvedQuery(final_sql="SELECT * FROM users", validated=True, ...)
            ```
        """
        params = params or {}
        start_time: float = time.time()
        effective_db_type: str = self._resolve_db_type()

        try:
            # Paso 1: Obtener QueryDefinition
            self.logger.debug(f"Resolving query: {query_name} for db_type={effective_db_type}")
            query_def: QueryDefinition = self.registry.get_query_definition(effective_db_type, query_name)

            # Paso 2: Validar parámetros con validador específico del motor
            validator: QueryParameterValidator = get_type_validator(effective_db_type)
            is_valid, warnings = validator.validate_parameters(query_def, params)

            if not is_valid:
                msg: str = (
                    f"Validation failed for query '{query_name}' on db_type '{effective_db_type}'. "
                    f"Provided params: {list(params.keys())}"
                )
                self.logger.error(f"❌ {msg}")
                raise QueryValidationError(msg)

            # Paso 3: Interpolar SQL
            final_sql: str = self._interpolate_sql(query_def.sql_template, params)

            # Calcular elapsed time
            elapsed_ms: float = (time.time() - start_time) * 1000

            self.logger.debug(
                f"✅ Query resolved successfully: name={query_name}, "
                f"db_type={effective_db_type}, elapsed_ms={elapsed_ms:.2f}, "
                f"param_count={len(params)}, warnings={len(warnings)}"
            )

            # Paso 4: Crear ResolvedQuery
            return ResolvedQuery(
                query_definition=query_def,
                final_sql=final_sql,
                validated=True,
                warnings=warnings,
                metadata={"elapsed_ms": elapsed_ms, "db_type": effective_db_type},
            )

        except (QueryValidationError, QueryParameterError, QueryNotFoundError):
            # Re-raise errores conocidos sin envolver
            raise

        except Exception as e:
            self.logger.error(
                f"❌ Error resolving query '{query_name}' for db_type '{effective_db_type}': {e}",
                exc_info=True,
            )
            raise QueryParameterError(
                f"Failed to resolve query '{query_name}' for db_type '{effective_db_type}'"
            ) from e

    def bind(self, db_type: str) -> QueryResolver:
        """Crea un resolver ligado a un db_type manteniendo el mismo registry."""
        return QueryResolver(registry=self.registry, db_type=db_type)

    @staticmethod
    def _normalize_db_type(db_type: str) -> str:
        """Normaliza el tipo de base de datos."""
        return db_type.lower().strip()

    def _resolve_db_type(self) -> str:
        """Resuelve el db_type efectivo; este resolver debe estar ligado."""
        if self._bound_db_type is None:
            raise QueryParameterError("QueryResolver must be bound to a database type before resolving queries")
        return self._bound_db_type

    def _interpolate_sql(self, template: str, params: dict[str, Any]) -> str:
        """Interpola parámetros en SQL template.

        Reemplaza placeholders {param} con valores de params dict.

        Args:
            template: SQL template con placeholders
            params: Diccionario de parámetros

        Returns:
            SQL con parámetros interpolados

        Raises:
            QueryParameterError: Si falta parámetro requerido

        Example:
            sql = resolver._interpolate_sql(
                "SELECT * FROM {tabla} WHERE id = {id}",
                {"tabla": "users", "id": "123"}
            )
            # "SELECT * FROM users WHERE id = 123"
        """
        try:
            return template.format(**params)

        except KeyError as e:
            missing_param = e.args[0]
            msg: str = f"Missing required parameter: '{missing_param}'"
            self.logger.error(f"❌ {msg}")
            raise QueryParameterError(msg) from e
