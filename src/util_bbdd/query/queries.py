"""Manejo unificado de consultas de base de datos multi-motor.

Delega en QueryRegistry (carga), QueryResolver (validación/resolución) y
DatabaseTypeValidator. Soporta MariaDB, Oracle, PostgreSQL, HSQLDB, SQL Server y SQLite.
"""

import json
import logging

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from util_bbdd.models import QueryDefinition, ResolvedQuery

from .._drivers.validator import DatabaseTypeValidator
from ._documentation import build_query_documentation, build_query_info, get_query_dependencies
from .registry import QueryRegistry
from .resolver import QueryResolver


class DatabaseQueries:
    """
    Clase unificada para manejar consultas SQL de base de datos.

    Integra:
    - Funcionalidad básica de consultas
    - Validación simplificada
    - Capacidades avanzadas de validación y documentación
    """

    # Error message constants
    ERROR_OBTENER_TABLAS_REQUIRES_DATABASE = "La consulta 'obtener_tablas' requiere el parámetro 'database'"
    ERROR_COLUMNAS_TABLA_REQUIRES_DATABASE = "La consulta 'columnas_tabla' requiere el parámetro 'database'"
    ERROR_COLUMNAS_TABLA_REQUIRES_TABLA = "La consulta 'columnas_tabla' requiere el parámetro 'tabla'"
    ERROR_CREATE_TABLE_REQUIRES_TABLA = "La consulta 'create_table' requiere el parámetro 'tabla'"
    ERROR_OBTENER_RUTINAS_REQUIRES_DATABASE = "La consulta 'obtener_rutinas' requiere el parámetro 'database'"
    ERROR_PARAMETROS_RUTINA_REQUIRES_DATABASE = "La consulta 'parametros_rutina' requiere el parámetro 'database'"
    ERROR_PARAMETROS_RUTINA_REQUIRES_RUTINA = "La consulta 'parametros_rutina' requiere el parámetro 'rutina'"
    ERROR_PARAMETROS_RUTINA_REQUIRES_TIPO = "La consulta 'parametros_rutina' requiere el parámetro 'tipo_rutina'"
    ERROR_CREATE_RUTINA_REQUIRES_RUTINA = "La consulta 'create_rutina' requiere el parámetro 'rutina'"
    ERROR_CREATE_RUTINA_REQUIRES_TIPO = "La consulta 'create_rutina' requiere el parámetro 'tipo_rutina'"
    ERROR_TABLE_NAME_EMPTY = "El nombre de la tabla no puede estar vacío"
    ERROR_TABLA_PARAMETER_REQUIRED = "El parámetro 'tabla' es requerido"

    # Constant for repeated error message
    ERROR_TABLE_NAME_INVALID_HSQLDB = (
        "El nombre de la tabla solo puede contener letras, números, guiones y guiones bajos"
    )
    ERROR_DATABASE_NAME_EMPTY = "El nombre de la base de datos no puede estar vacío"
    _CONTEXT_PARAMS_BY_DB: dict[str, tuple[str, ...]] = {
        "oracle": ("esquema",),
        "sqlserver": ("esquema", "database"),
        "postgresql": ("database",),
        "hsqldb": ("database",),
    }

    def __init__(
        self,
        db_type: str,
        queries_file: Path | None = None,
        config_file: Path | None = None,
    ):
        """
        Inicializa la clase unificada de consultas

        Args:
            db_type: Tipo de base de datos ('mariadb', 'oracle', 'postgresql', 'hsqldb', 'sqlserver', 'sqlite')
            queries_file: Ruta al archivo JSON con las consultas SQL
            config_file: Ruta al archivo de configuración de tipos de BD

        Raises:
            ValueError: Si el tipo de base de datos no está soportado
            FileNotFoundError: Si no se encuentra el archivo de consultas
        """
        self.logger: logging.Logger = logging.getLogger(__name__)

        supported_types: list[str] = [
            "mariadb",
            "oracle",
            "postgresql",
            "hsqldb",
            "sqlserver",
            "sqlite",
        ]
        if db_type.lower() not in supported_types:
            raise ValueError(f"Tipo de base de datos no soportado. Use: {', '.join(supported_types)}")

        self.db_type: str = db_type.lower()
        self.logger.debug(f"✅ Inicializando DatabaseQueries para {self.db_type}")

        self.registry: QueryRegistry = QueryRegistry(queries_file)
        self.logger.debug("✅ QueryRegistry inicializado")

        self.resolver: QueryResolver = QueryResolver(self.registry, db_type=self.db_type)
        self.logger.debug("✅ QueryResolver inicializado")

        self.logger.debug(f"✅ {len(self.registry.get_available_queries(self.db_type))} consultas cargadas")

        self.db_validator: DatabaseTypeValidator = DatabaseTypeValidator(config_file)
        self.db_metadata: dict[str, Any] = self.db_validator.get_db_type_info(db_type)
        self.config_examples: dict[str, Any] = self.db_validator.get_db_type_examples(db_type)

    # ==================== MÉTODOS DE CONSULTA BÁSICOS ====================

    def get_query(self, query_name: str, **kwargs) -> str:
        """
        Obtiene una consulta SQL formateada con los parámetros proporcionados

        Args:
            query_name: Nombre de la consulta a obtener
            **kwargs: Parámetros para formatear la consulta

        Returns:
            Consulta SQL formateada o template si no hay parámetros

        Raises:
            QueryNotFoundError: Si no existe la consulta especificada
            QueryValidationError: Si los parámetros no son válidos
        """
        try:
            if not kwargs:
                qdef: QueryDefinition = self.registry.get_query_definition(self.db_type, query_name)
                return qdef.sql_template

            resolved: ResolvedQuery = self.resolver.resolve(query_name, kwargs)
            return resolved.final_sql
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo query '{query_name}': {e}")
            raise

    # ==================== MÉTODOS DE CONVENIENCIA ====================

    def get_tables_query(self, database: str) -> str:
        """Obtiene la consulta para listar tablas"""
        return self.get_query("obtener_tablas", database=database)

    def get_views_query(self, database: str) -> str:
        """Obtiene la consulta para listar vistas"""
        return self.get_query("obtener_vistas", database=database)

    def get_ddl_query(self, table: str, schema: str | None = None) -> str:
        """Obtiene la consulta para obtener el DDL de una tabla"""
        context_kwargs: dict[str, str] = self._build_context_kwargs(schema)
        return self.get_query("create_table", tabla=table, **context_kwargs)

    def get_columns_query(self, database: str, table: str) -> str:
        """Obtiene la consulta para listar columnas de una tabla"""
        return self.get_query("columnas_tabla", database=database, tabla=table)

    def get_routines_query(self, database: str) -> str:
        """Obtiene la consulta para listar routines (procedures/funciones)."""
        return self.get_query("obtener_rutinas", database=database)

    def get_routine_parameters_query(self, database: str, routine_name: str, routine_type: str) -> str:
        """Obtiene la consulta para listar parámetros de una rutina."""
        return self.get_query(
            "parametros_rutina",
            database=database,
            rutina=routine_name,
            tipo_rutina=routine_type.upper(),
        )

    def get_routine_ddl_query(self, routine_name: str, routine_type: str, schema: str | None = None) -> str:
        """Obtiene la consulta para recuperar el DDL de una rutina."""
        strategy = self._get_routine_ddl_strategy()
        return strategy(routine_name, routine_type, schema)

    def get_indices_query(self, table: str, schema: str | None = None) -> str:
        """Obtiene la consulta para listar índices de una tabla"""
        context_kwargs: dict[str, str] = self._build_context_kwargs(schema)
        return self.get_query("indices", tabla=table, **context_kwargs)

    def get_primary_keys_query(self, table: str, schema: str | None = None) -> str:
        """Obtiene la consulta para listar claves primarias de una tabla"""
        context_kwargs: dict[str, str] = self._build_context_kwargs(schema)
        return self.get_query("claves_primarias", tabla=table, **context_kwargs)

    def get_foreign_keys_query(self, table: str, schema: str | None = None) -> str:
        """Obtiene la consulta para listar claves foráneas de una tabla"""
        context_kwargs: dict[str, str] = self._build_context_kwargs(schema)
        return self.get_query("claves_foraneas", tabla=table, **context_kwargs)

    def get_unique_constraints_query(self, table: str, schema: str | None = None) -> str:
        """Obtiene la consulta para listar restricciones únicas de una tabla"""
        context_kwargs: dict[str, str] = self._build_context_kwargs(schema)
        return self.get_query("claves_unicas", tabla=table, **context_kwargs)

    def get_storage_inventory_queries(
        self, database: str | None = None, tablespace: str | None = None
    ) -> dict[str, str]:
        """Obtiene consultas de inventario de ficheros/tablespaces según motor.

        Returns:
            Diccionario con llaves explicitas por capacidad (`primary`,
            `temp_tablespaces`, `temp_storage_variables`, `sqlite_file_summary`).
        """
        strategy = self._get_storage_inventory_strategy()
        return strategy(database, tablespace)

    def _build_context_kwargs(self, context: str | None) -> dict[str, str]:
        """Construye kwargs de contexto para plantillas SQL."""
        if not context or self.db_type == "mariadb":
            return {}
        context_params = self._CONTEXT_PARAMS_BY_DB.get(self.db_type, ())
        return dict.fromkeys(context_params, context)

    def _get_routine_ddl_strategy(self) -> Callable[[str, str, str | None], str]:
        strategies: dict[str, Callable[[str, str, str | None], str]] = {
            "mariadb": self._build_mariadb_routine_ddl_query,
        }
        return strategies.get(self.db_type, self._build_standard_routine_ddl_query)

    def _build_mariadb_routine_ddl_query(
        self,
        _routine_name: str,
        _routine_type: str,
        schema: str | None,
    ) -> str:
        if not schema:
            raise ValueError("Para MariaDB debe informar 'schema'/'database' para cargar metadata batched de rutinas")
        return self.get_query("rutinas_mariadb_detalle", database=schema)

    def _build_standard_routine_ddl_query(
        self,
        routine_name: str,
        routine_type: str,
        schema: str | None,
    ) -> str:
        return self.get_query(
            "create_rutina",
            rutina=routine_name,
            tipo_rutina=routine_type.upper(),
            esquema=schema,
        )

    def _get_storage_inventory_strategy(
        self,
    ) -> Callable[[str | None, str | None], dict[str, str]]:
        strategies: dict[str, Callable[[str | None, str | None], dict[str, str]]] = {
            "sqlserver": self._build_storage_inventory_queries_sqlserver,
            "oracle": self._build_storage_inventory_queries_oracle,
            "mariadb": self._build_storage_inventory_queries_mariadb,
            "postgresql": self._build_storage_inventory_queries_postgresql,
            "sqlite": self._build_storage_inventory_queries_sqlite,
        }
        return strategies.get(self.db_type, self._build_storage_inventory_queries_hsqldb)

    def _build_storage_inventory_queries_sqlserver(
        self,
        _database: str | None,
        _tablespace: str | None,
    ) -> dict[str, str]:
        return {
            "primary": self.get_query("ficheros_fisicos"),
            "temp_tablespaces": self.get_query("temp_tablespaces"),
        }

    def _build_storage_inventory_queries_oracle(
        self,
        _database: str | None,
        tablespace: str | None,
    ) -> dict[str, str]:
        if not tablespace:
            raise ValueError("Para Oracle debe indicar 'tablespace'")
        return {
            "primary": self.get_query("ficheros_fisicos", tablespace=tablespace),
            "temp_tablespaces": self.get_query("temp_tablespaces", tablespace=tablespace),
        }

    def _build_storage_inventory_queries_mariadb(
        self,
        database: str | None,
        _tablespace: str | None,
    ) -> dict[str, str]:
        if not database:
            raise ValueError("Para MariaDB debe indicar 'database'")
        return {
            "primary": self.get_query("ficheros_fisicos", database=database),
            "temp_tablespaces": self.get_query("temp_tablespaces"),
            "temp_storage_variables": self.get_query("temp_storage_variables"),
        }

    def _build_storage_inventory_queries_postgresql(
        self,
        _database: str | None,
        tablespace: str | None,
    ) -> dict[str, str]:
        if not tablespace:
            raise ValueError("Para PostgreSQL debe indicar 'tablespace'")
        return {
            "primary": self.get_query("ficheros_fisicos", tablespace=tablespace),
            "temp_tablespaces": self.get_query("temp_tablespaces"),
        }

    def _build_storage_inventory_queries_sqlite(
        self,
        _database: str | None,
        _tablespace: str | None,
    ) -> dict[str, str]:
        return {
            "primary": self.get_query("ficheros_fisicos"),
            "sqlite_file_summary": self.get_query("sqlite_file_summary"),
            "temp_tablespaces": self.get_query("temp_tablespaces"),
        }

    def _build_storage_inventory_queries_hsqldb(
        self,
        _database: str | None,
        _tablespace: str | None,
    ) -> dict[str, str]:
        # HSQLDB no expone vista SQL estándar para tamaños de fichero físico.
        return {}

    # ==================== MÉTODOS DE INFORMACIÓN DE CONSULTAS ====================

    def get_all_queries(self) -> dict[str, str]:
        """Obtiene todas las consultas disponibles para el tipo de base de datos"""
        raw_queries: Any = self.registry.queries.get(self.db_type, {})
        if not isinstance(raw_queries, dict):
            return {}
        return {str(name): str(query) for name, query in raw_queries.items()}

    def get_available_query_names(self) -> list[str]:
        """Obtiene los nombres de las consultas disponibles"""
        return self.registry.get_available_queries(self.db_type)

    def get_query_info(self) -> dict[str, Any]:
        """
        Obtiene información sobre las consultas disponibles

        Returns:
            Diccionario con información de las consultas
        """
        return build_query_info(db_type=self.db_type, queries=self.get_all_queries())

    # ==================== MÉTODOS AVANZADOS DE VALIDACIÓN ====================

    def validate_query_for_db_type(self, query_name: str, **kwargs) -> tuple[bool, list[str]]:
        """
        Valida una consulta específica para el tipo de base de datos actual

        Args:
            query_name: Nombre de la consulta a validar
            **kwargs: Parámetros para la consulta

        Returns:
            Tupla con (es_valido, lista_errores)
        """
        # Validación única: QueryResolver ya aplica validador por motor.
        try:
            resolved: ResolvedQuery = self.resolver.resolve(query_name, kwargs)
            return True, list(resolved.warnings)
        except Exception as e:
            return False, [f"Parámetros inválidos o faltantes para la consulta '{query_name}': {str(e)}"]

    # ==================== MÉTODOS AVANZADOS DE METADATOS ====================

    def get_database_metadata(self) -> dict[str, Any]:
        """Obtiene metadatos completos del tipo de base de datos"""
        return self.db_metadata

    def get_supported_features(self) -> list[str]:
        """Obtiene las características soportadas por el tipo de base de datos"""
        raw_features: Any = self.db_metadata.get("supported_features", [])
        if not isinstance(raw_features, list):
            return []
        return [str(feature) for feature in raw_features]

    def get_driver_requirements(self) -> dict[str, Any]:
        """Obtiene los requisitos del driver para el tipo de base de datos"""
        raw_driver_info: Any = self.db_metadata.get("driver_info", {})
        return cast(dict[str, Any], raw_driver_info if isinstance(raw_driver_info, dict) else {})

    def get_connection_examples(self) -> dict[str, dict[str, Any]]:
        """Obtiene ejemplos de conexión para el tipo de base de datos"""
        return self.config_examples

    def get_default_port(self) -> int:
        """Obtiene el puerto por defecto para el tipo de base de datos"""
        raw_port: Any = self.db_metadata.get("default_port", 0)
        try:
            return int(raw_port)
        except (TypeError, ValueError):
            return 0

    def get_installation_commands(self) -> dict[str, Any]:
        """Obtiene los comandos de instalación para el tipo de base de datos"""
        driver_info: dict[str, Any] = self.get_driver_requirements()
        return {
            "pip": driver_info.get("install_command", ""),
            "system_requirements": driver_info.get("system_requirements", []),
        }

    def get_query_dependencies(self, query_name: str) -> dict[str, list[str]]:
        """Obtiene las dependencias de una consulta (tablas, vistas, etc.)"""
        query_template: str = self.get_all_queries().get(query_name, "")
        return get_query_dependencies(query_template)

    def get_query_documentation(self, query_name: str) -> dict[str, Any]:
        """Obtiene documentación completa de una consulta"""
        query_template: str = self.get_all_queries().get(query_name, "")
        return build_query_documentation(
            db_type=self.db_type,
            query_name=query_name,
            query_template=query_template,
        )

    def export_documentation(self, output_file: Path) -> None:
        """Exporta documentación completa de todas las consultas a un archivo"""
        documentation_queries: dict[str, dict[str, Any]] = {}
        documentation: dict[str, Any] = {
            "db_type": self.db_type,
            "db_metadata": self.get_database_metadata(),
            "queries": documentation_queries,
        }

        for query_name in self.get_available_query_names():
            documentation_queries[query_name] = self.get_query_documentation(query_name)

        try:
            with output_file.open("w", encoding="utf-8") as f:
                json.dump(documentation, f, indent=2, ensure_ascii=False)
            self.logger.info(f"✅ Documentación exportada a {output_file}")
        except Exception as e:
            self.logger.error(f"❌ Error al exportar documentación: {e}")
            raise OSError(f"Error al exportar documentación: {e}") from e
