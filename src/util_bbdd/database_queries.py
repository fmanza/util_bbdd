"""
Módulo unificado para manejo de consultas de base de datos - Version refactorizada PR 5
Delegación de responsabilidades:
- QueryRegistry: Carga de queries desde SQL
- QueryResolver: Validación y resolución de queries
- DatabaseTypeValidator: Validación especializada por motor

Soporta MariaDB, Oracle, PostgreSQL, HSQLDB, SQL Server y SQLite
"""

import json
import logging
import re

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .database_type_validator import DatabaseTypeValidator
from .query import QueryRegistry, QueryResolver

# Patrón regex para encontrar parámetros en plantillas de consultas
PARAMETER_PATTERN = r"\{(\w+)\}"


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

        # Validar que el tipo de base de datos esté soportado
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

        # PR 5: Delegar carga de queries a QueryRegistry
        self.registry: QueryRegistry = QueryRegistry(queries_file)
        self.logger.debug("✅ QueryRegistry inicializado")

        # PR 5: Delegar resolución de queries a QueryResolver
        self.resolver: QueryResolver = QueryResolver(self.registry)
        self.logger.debug("✅ QueryResolver inicializado")

        # Mantener queries accesible para backward compatibility
        # (algunos métodos aún los utilizan)
        self.queries: dict[Any, Any] = self.registry.queries
        self.logger.debug(f"✅ {len(self.queries.get(self.db_type, {}))} consultas cargadas")

        # Inicializar validador de tipos de BD para obtener metadatos
        self.db_validator: DatabaseTypeValidator = DatabaseTypeValidator(config_file)
        # Nota: No redundar validate_db_type() aquí, ya validado en línea 68

        # Cargar metadatos adicionales del tipo de BD
        self.db_metadata: dict[str, Any] = self.db_validator.get_db_type_info(db_type)
        self.config_examples: dict[str, Any] = self.db_validator.get_db_type_examples(db_type)

    # PR 5: _load_queries now delegated to QueryRegistry
    # This method is kept for backward compatibility but should not be called directly

    # ==================== MÉTODOS DE CONSULTA BÁSICOS ====================

    def get_query(self, query_name: str, **kwargs) -> str:
        """
        Obtiene una consulta SQL formateada con los parámetros proporcionados

        PR 5: Now delegates to QueryResolver for validation and parameter interpolation
        Para backward compatibility: si no hay kwargs, devuelve el template directo

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
            # PR 5: For backward compatibility, allow getting template without params
            if not kwargs:
                # Get template directly from registry without validation
                qdef = self.registry.get_query_definition(self.db_type, query_name)
                return qdef.sql_template

            # PR 5: With params, delegate to resolver for validation and interpolation
            resolved = self.resolver.resolve(query_name, self.db_type, kwargs)
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
        if self.db_type == "mariadb":
            if not schema:
                raise ValueError("Para MariaDB debe informar 'schema'/'database' para cargar metadata batched de rutinas")
            return self.get_query("rutinas_mariadb_detalle", database=schema)

        return self.get_query("create_rutina", rutina=routine_name, tipo_rutina=routine_type.upper(), esquema=schema)

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
            Diccionario con llaves `primary` y opcionalmente `secondary`.
        """
        if self.db_type == "sqlserver":
            return {"primary": self.get_query("ficheros_fisicos")}
        if self.db_type == "oracle":
            if not tablespace:
                raise ValueError("Para Oracle debe indicar 'tablespace'")
            return {"primary": self.get_query("ficheros_fisicos", tablespace=tablespace)}
        if self.db_type == "mariadb":
            if not database:
                raise ValueError("Para MariaDB debe indicar 'database'")
            return {
                "primary": self.get_query("ficheros_fisicos", database=database),
                "secondary": self.get_query("ficheros_fisicos_adicional", database=database),
                "temp_tablespaces": self.get_query("temp_tablespaces"),
            }
        if self.db_type == "postgresql":
            if not tablespace:
                raise ValueError("Para PostgreSQL debe indicar 'tablespace'")
            return {
                "primary": self.get_query("ficheros_fisicos", tablespace=tablespace),
                "secondary": self.get_query("temp_tablespaces"),
            }
        if self.db_type == "sqlite":
            return {
                "primary": self.get_query("ficheros_fisicos"),
                "secondary": self.get_query("ficheros_fisicos_adicional"),
            }
        # HSQLDB no expone vista SQL estándar para tamaños de fichero físico.
        return {}

    def _build_context_kwargs(self, context: str | None) -> dict[str, str]:
        """Construye kwargs de contexto para plantillas SQL."""
        if not context or self.db_type == "mariadb":
            return {}

        kwargs: dict[str, str] = {}
        if self.db_type in {"oracle", "sqlserver"}:
            kwargs["esquema"] = context
        if self.db_type in {"postgresql", "hsqldb", "sqlserver"}:
            kwargs["database"] = context
        return kwargs

    # ==================== MÉTODOS DE INFORMACIÓN DE CONSULTAS ====================

    def get_all_queries(self) -> dict[str, str]:
        """Obtiene todas las consultas disponibles para el tipo de base de datos"""
        return self.queries.get(self.db_type, {})

    def get_available_query_names(self) -> list[str]:
        """Obtiene los nombres de las consultas disponibles"""
        return list(self.queries.get(self.db_type, {}).keys())

    def get_query_info(self) -> dict[str, Any]:
        """
        Obtiene información sobre las consultas disponibles

        Returns:
            Diccionario con información de las consultas
        """
        queries: dict[str, str] = self.get_all_queries()
        info = {
            "db_type": self.db_type,
            "total_queries": len(queries),
            "query_names": self.get_available_query_names(),
            "queries": {},
        }

        for name, query in queries.items():
            required_params = list(set(re.findall(PARAMETER_PATTERN, query)))
            info["queries"][name] = {
                "template": query,
                "required_parameters": required_params,
                "parameter_count": len(required_params),
            }

        return info

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
            resolved = self.resolver.resolve(query_name, self.db_type, kwargs)
            return True, list(resolved.warnings)
        except Exception as e:
            return False, [f"Parámetros inválidos o faltantes para la consulta '{query_name}': {str(e)}"]

    def _validate_sqlserver_query(self, query_name: str, **kwargs) -> list[str]:
        """Valida específicamente consultas SQL Server"""
        errors = []
        table_queries: list[str] = [
            "columnas_tabla",
            "create_table",
            "indices",
            "claves_primarias",
            "claves_foraneas",
            "claves_unicas",
        ]
        if query_name in table_queries:
            errors.extend(self._validate_sqlserver_table_parameter(**kwargs))
        elif query_name == "obtener_tablas":
            errors.extend(self._validate_sqlserver_database_parameter(**kwargs))
        return errors

    def _validate_sqlserver_table_parameter(self, **kwargs) -> list[str]:
        """Valida el parámetro tabla para consultas SQL Server"""
        errors = []
        if "tabla" not in kwargs:
            errors.append(self.ERROR_TABLA_PARAMETER_REQUIRED)
            return errors
        table_name = kwargs["tabla"]
        if not isinstance(table_name, str) or not table_name.strip():
            errors.append(self.ERROR_TABLE_NAME_EMPTY)
            return errors
        if len(table_name) > 128:
            errors.append("SQL Server no permite nombres de tabla con más de 128 caracteres")
        if not re.match(r"^[\w\-]+$", table_name):
            errors.append("El nombre de la tabla solo puede contener letras, números, guiones y guiones bajos")
        return errors

    def _validate_sqlserver_database_parameter(self, **kwargs) -> list[str]:
        """Valida el parámetro database para consultas SQL Server"""
        errors = []
        if "database" not in kwargs:
            errors.append(self.ERROR_OBTENER_TABLAS_REQUIRES_DATABASE)
            return errors
        database = kwargs["database"]
        if not isinstance(database, str) or not database.strip():
            errors.append(self.ERROR_DATABASE_NAME_EMPTY)
        if len(database) > 128:
            errors.append("SQL Server no permite nombres de base de datos con más de 128 caracteres")
        return errors

    def _validate_postgresql_query(self, query_name: str, **kwargs) -> list[str]:
        """Valida específicamente consultas PostgreSQL"""
        errors = []
        if query_name == "obtener_tablas":
            errors.extend(self._validate_postgresql_obtener_tablas(**kwargs))
        elif query_name == "columnas_tabla":
            errors.extend(self._validate_postgresql_columnas_tabla(**kwargs))
        elif query_name == "create_table":
            errors.extend(self._validate_postgresql_create_table(**kwargs))
        return errors

    def _validate_postgresql_obtener_tablas(self, **kwargs) -> list[str]:
        """Valida parámetros para obtener_tablas en PostgreSQL"""
        errors = []
        if "database" not in kwargs:
            errors.append(self.ERROR_OBTENER_TABLAS_REQUIRES_DATABASE)
        else:
            database = kwargs["database"]
            if not isinstance(database, str) or not database.strip():
                errors.append("El nombre del schema/database no puede estar vacío")
            reserved_schemas: list[str] = ["information_schema", "pg_catalog", "pg_toast"]
            if database.lower() in reserved_schemas:
                errors.append(f"'{database}' es un schema reservado de PostgreSQL")
        return errors

    def _validate_postgresql_columnas_tabla(self, **kwargs) -> list[str]:
        """Valida parámetros para columnas_tabla en PostgreSQL"""
        errors = []
        if "database" not in kwargs:
            errors.append(self.ERROR_COLUMNAS_TABLA_REQUIRES_DATABASE)
        if "tabla" not in kwargs:
            errors.append(self.ERROR_COLUMNAS_TABLA_REQUIRES_TABLA)
        else:
            tabla = kwargs["tabla"]
            if not isinstance(tabla, str) or not tabla.strip():
                errors.append(self.ERROR_TABLE_NAME_EMPTY)
            if not tabla.replace("_", "").replace("-", "").isalnum():
                errors.append(self.ERROR_TABLE_NAME_INVALID_HSQLDB)
        return errors

    def _validate_postgresql_create_table(self, **kwargs) -> list[str]:
        """Valida parámetros para create_table en PostgreSQL"""
        errors = []
        if "tabla" not in kwargs:
            errors.append(self.ERROR_CREATE_TABLE_REQUIRES_TABLA)
        else:
            tabla = kwargs["tabla"]
            if not isinstance(tabla, str) or not tabla.strip():
                errors.append(self.ERROR_TABLE_NAME_EMPTY)
            if len(tabla) > 63:
                errors.append("PostgreSQL no permite nombres de tabla con más de 63 caracteres")
            if tabla.lower().startswith("pg_"):
                errors.append("Los nombres que empiezan con 'pg_' están reservados en PostgreSQL")
        return errors

    def _validate_oracle_query(self, query_name: str, **kwargs) -> list[str]:
        """Valida específicamente consultas Oracle"""
        errors = []
        table_queries: list[str] = [
            "columnas_tabla",
            "create_table",
            "indices",
            "claves_primarias",
            "claves_foraneas",
            "claves_unicas",
        ]
        if query_name in table_queries:
            errors.extend(self._validate_oracle_table_parameter(**kwargs))
        elif query_name == "obtener_tablas":
            errors.extend(self._validate_oracle_database_parameter(**kwargs))
        return errors

    def _validate_oracle_table_parameter(self, **kwargs) -> list[str]:
        """Valida el parámetro tabla para consultas Oracle"""
        errors = []
        if "tabla" not in kwargs:
            errors.append(self.ERROR_TABLA_PARAMETER_REQUIRED)
            return errors
        table_name = kwargs["tabla"]
        if not isinstance(table_name, str) or not table_name.strip():
            errors.append(self.ERROR_TABLE_NAME_EMPTY)
            return errors
        if len(table_name) > 30:
            errors.append("Oracle no permite nombres de tabla con más de 30 caracteres")
        if not table_name.replace("_", "").replace("$", "#").isalnum():
            errors.append("El nombre de la tabla solo puede contener letras, números, guiones bajos y $")
        return errors

    def _validate_oracle_database_parameter(self, **kwargs) -> list[str]:
        """Valida el parámetro database para consultas Oracle"""
        errors = []
        if "database" not in kwargs:
            errors.append(self.ERROR_OBTENER_TABLAS_REQUIRES_DATABASE)
            return errors
        database = kwargs["database"]
        if not isinstance(database, str) or not database.strip():
            errors.append("El nombre del esquema/database no puede estar vacío")
        return errors

    def _validate_mariadb_query(self, query_name: str, **kwargs) -> list[str]:
        """Valida específicamente consultas MariaDB"""
        errors = []
        table_queries: list[str] = [
            "columnas_tabla",
            "create_table",
            "indices",
            "claves_primarias",
            "claves_foraneas",
            "claves_unicas",
        ]
        if query_name in table_queries:
            errors.extend(self._validate_mariadb_table_parameter(**kwargs))
        elif query_name == "obtener_tablas":
            errors.extend(self._validate_mariadb_database_parameter(**kwargs))
        return errors

    def _validate_mariadb_table_parameter(self, **kwargs) -> list[str]:
        """Valida el parámetro tabla para consultas MariaDB"""
        errors = []
        if "tabla" not in kwargs:
            errors.append(self.ERROR_TABLA_PARAMETER_REQUIRED)
            return errors
        table_name = kwargs["tabla"]
        if not isinstance(table_name, str) or not table_name.strip():
            errors.append(self.ERROR_TABLE_NAME_EMPTY)
            return errors
        if len(table_name) > 64:
            errors.append("MariaDB no permite nombres de tabla con más de 64 caracteres")
        if not table_name.replace("_", "").replace("$", "").isalnum():
            errors.append("El nombre de la tabla solo puede contener letras, números, guiones bajos y $")
        return errors

    def _validate_mariadb_database_parameter(self, **kwargs) -> list[str]:
        """Valida el parámetro database para consultas MariaDB"""
        errors = []
        if "database" not in kwargs:
            errors.append(self.ERROR_OBTENER_TABLAS_REQUIRES_DATABASE)
            return errors
        database = kwargs["database"]
        if not isinstance(database, str) or not database.strip():
            errors.append(self.ERROR_DATABASE_NAME_EMPTY)
        return errors

    def _validate_hsqldb_query(self, query_name: str, **kwargs) -> list[str]:
        """Valida específicamente consultas HSQLDB"""
        errors = []
        table_queries: list[str] = [
            "columnas_tabla",
            "create_table",
            "indices",
            "claves_primarias",
            "claves_foraneas",
            "claves_unicas",
        ]
        if query_name in table_queries:
            errors.extend(self._validate_hsqldb_table_parameter(**kwargs))
        elif query_name == "obtener_tablas":
            errors.extend(self._validate_hsqldb_database_parameter(**kwargs))
        return errors

    def _validate_hsqldb_table_parameter(self, **kwargs) -> list[str]:
        """Valida el parámetro tabla para consultas HSQLDB"""
        errors = []
        if "tabla" not in kwargs:
            errors.append(self.ERROR_TABLA_PARAMETER_REQUIRED)
            return errors
        table_name = kwargs["tabla"]
        if not isinstance(table_name, str) or not table_name.strip():
            errors.append(self.ERROR_TABLE_NAME_EMPTY)
            return errors
        if not table_name.replace("_", "").replace("-", "").isalnum():
            errors.append(self.ERROR_TABLE_NAME_INVALID_HSQLDB)
        return errors

    def _validate_hsqldb_database_parameter(self, **kwargs) -> list[str]:
        """Valida el parámetro database para consultas HSQLDB"""
        errors = []
        if "database" not in kwargs:
            errors.append("La consulta 'obtener_tablas' requiere el parámetro 'database'")
            return errors
        database = kwargs["database"]
        if not isinstance(database, str) or not database.strip():
            errors.append("El nombre de la base de datos no puede estar vacío")
        return errors

    # ==================== MÉTODOS AVANZADOS DE METADATOS ====================

    def get_database_metadata(self) -> dict[str, Any]:
        """Obtiene metadatos completos del tipo de base de datos"""
        return self.db_metadata

    def get_supported_features(self) -> list[str]:
        """Obtiene las características soportadas por el tipo de base de datos"""
        return self.db_metadata.get("supported_features", [])

    def get_driver_requirements(self) -> dict[str, Any]:
        """Obtiene los requisitos del driver para el tipo de base de datos"""
        return self.db_metadata.get("driver_info", {})

    def get_connection_examples(self) -> dict[str, dict[str, Any]]:
        """Obtiene ejemplos de conexión para el tipo de base de datos"""
        return self.config_examples

    def get_default_port(self) -> int:
        """Obtiene el puerto por defecto para el tipo de base de datos"""
        return self.db_metadata.get("default_port", 0)

    def get_installation_commands(self) -> dict[str, Any]:
        """Obtiene los comandos de instalación para el tipo de base de datos"""
        driver_info = self.get_driver_requirements()
        return {
            "pip": driver_info.get("install_command", ""),
            "system_requirements": driver_info.get("system_requirements", []),
        }

    def get_query_dependencies(self, query_name: str) -> dict[str, list[str]]:
        """Obtiene las dependencias de una consulta (tablas, vistas, etc.)"""
        query_template = self.queries[self.db_type].get(query_name, "")
        dependencies = {"tables": [], "views": [], "schemata": [], "columns": []}

        # Buscar tablas en FROM, JOIN, etc.
        from_pattern = r"(?:FROM|JOIN)\s+(\w+)"
        tables = re.findall(from_pattern, query_template, re.IGNORECASE)
        dependencies["tables"] = list(set(tables))

        # Buscar schemas
        schema_pattern = r'(?:schema|database)\s*=\s*[\'"]([^\'"]+)[\'"]'
        schemas = re.findall(schema_pattern, query_template, re.IGNORECASE)
        dependencies["schemata"] = list(set(schemas))

        return dependencies

    def get_query_documentation(self, query_name: str) -> dict[str, Any]:
        """Obtiene documentación completa de una consulta"""
        query_template = self.queries[self.db_type].get(query_name, "")
        parameters = self._get_required_parameters(query_name)
        dependencies = self.get_query_dependencies(query_name)

        return {
            "query_name": query_name,
            "db_type": self.db_type,
            "description": self._get_query_description(query_name),
            "template": query_template,
            "parameters": parameters,
            "dependencies": dependencies,
            "examples": self._get_query_examples(query_name),
        }

    def _get_query_description(self, query_name: str) -> str:
        """Obtiene descripción legible de una consulta"""
        descriptions = {
            "obtener_tablas": "Obtiene la lista de tablas de la base de datos",
            "columnas_tabla": "Obtiene información detallada de las columnas de una tabla",
            "create_table": "Genera el DDL (Data Definition Language) para crear una tabla",
            "obtener_rutinas": "Obtiene la lista de rutinas (procedures y funciones)",
            "parametros_rutina": "Obtiene la lista de parámetros de una rutina",
            "create_rutina": "Obtiene el DDL de una rutina (procedure/función)",
            "indices": "Obtiene la lista de índices de una tabla",
            "claves_primarias": "Obtiene las claves primarias de una tabla",
            "claves_foraneas": "Obtiene las claves foráneas (foreign keys) de una tabla",
            "claves_unicas": "Obtiene las restricciones únicas de una tabla",
            "ficheros_fisicos": "Obtiene inventario de ficheros físicos y tamaños",
            "ficheros_fisicos_adicional": "Obtiene inventario adicional de ficheros/tablespaces según motor",
            "temp_tablespaces": "Obtiene configuración de tablespaces temporales",
            "temp_storage_variables": "Obtiene variables de configuración del almacenamiento temporal",
        }
        return descriptions.get(query_name, "Consulta SQL personalizada")

    def _get_required_parameters(self, query_name: str) -> list[str]:
        """Obtiene la lista de parámetros requeridos para una consulta"""
        query_template = self.queries[self.db_type].get(query_name, "")
        return list(set(re.findall(PARAMETER_PATTERN, query_template)))

    def _get_query_examples(self, query_name: str) -> list[dict[str, Any]]:
        """Obtiene ejemplos de uso para una consulta"""
        examples_factory: dict[str, Callable[[], list[dict[str, Any]]]] = {
            "obtener_tablas": self._examples_obtener_tablas,
            "obtener_rutinas": self._examples_obtener_rutinas,
            "parametros_rutina": self._examples_parametros_rutina,
            "create_rutina": self._examples_create_rutina,
            "columnas_tabla": self._examples_columnas_tabla,
            "create_table": self._examples_create_table,
            "ficheros_fisicos": self._examples_ficheros_fisicos,
            "ficheros_fisicos_adicional": self._examples_ficheros_fisicos_adicional,
            "temp_tablespaces": self._examples_temp_tablespaces,
            "temp_storage_variables": self._examples_temp_storage_variables,
        }
        return examples_factory.get(query_name, lambda: [])()

    def _examples_obtener_tablas(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta obtener_tablas"""
        return [
            {
                "description": "Obtener todas las tablas del schema public",
                "parameters": {"database": "public"},
            }
        ]

    def _examples_obtener_rutinas(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta obtener_rutinas"""
        return [
            {
                "description": "Obtener procedures y funciones del schema public",
                "parameters": {"database": "public"},
            }
        ]

    def _examples_parametros_rutina(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta parametros_rutina"""
        return [
            {
                "description": "Obtener parámetros de la rutina calcular_totales",
                "parameters": {
                    "database": "public",
                    "rutina": "calcular_totales",
                    "tipo_rutina": "FUNCTION",
                },
            }
        ]

    def _examples_create_rutina(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta create_rutina"""
        return [
            {
                "description": "Generar DDL de la rutina actualizar_stock",
                "parameters": {"rutina": "actualizar_stock", "tipo_rutina": "PROCEDURE"},
            }
        ]

    def _examples_columnas_tabla(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta columnas_tabla"""
        return [
            {
                "description": "Obtener columnas de la tabla usuarios",
                "parameters": {"database": "public", "tabla": "usuarios"},
            }
        ]

    def _examples_create_table(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta create_table"""
        return [
            {
                "description": "Generar DDL de la tabla productos",
                "parameters": {"tabla": "productos"},
            }
        ]

    def _examples_ficheros_fisicos(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta ficheros_fisicos según motor"""
        examples_by_db: dict[str, dict[str, Any]] = {
            "oracle": {
                "description": "Inventario de ficheros para un tablespace Oracle",
                "parameters": {"tablespace": "USERS"},
            },
            "postgresql": {
                "description": "Tamaño y ruta de un tablespace PostgreSQL",
                "parameters": {"tablespace": "pg_default"},
            },
            "mariadb": {
                "description": "Tamaño por tabla en MariaDB",
                "parameters": {"database": "mi_bd"},
            },
            "sqlite": {
                "description": "Listado de ficheros de bases adjuntas en SQLite",
                "parameters": {},
            },
        }
        example: dict[str, Any] = examples_by_db.get(
            self.db_type,
            {"description": "Inventario de ficheros físicos SQL Server", "parameters": {}},
        )
        return [example]

    def _examples_ficheros_fisicos_adicional(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta ficheros_fisicos_adicional según motor"""
        examples_by_db: dict[str, dict[str, Any]] = {
            "mariadb": {
                "description": "Tablespaces InnoDB para una base en MariaDB",
                "parameters": {"database": "mi_bd"},
            },
            "sqlite": {"description": "Resumen de tamaño del fichero SQLite", "parameters": {}},
        }
        example: dict[str, Any] | None = examples_by_db.get(self.db_type)
        return [example] if example else []

    def _examples_temp_tablespaces(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta temp_tablespaces"""
        examples_by_db: dict[str, dict[str, Any]] = {
            "mariadb": {
                "description": "Inventario de ficheros temporales desde information_schema.FILES en MariaDB",
                "parameters": {},
            },
            "postgresql": {
                "description": "Ver configuración de tablespaces temporales PostgreSQL",
                "parameters": {},
            },
        }
        example: dict[str, Any] = examples_by_db.get(
            self.db_type,
            {"description": "Consultar tablespaces temporales del motor", "parameters": {}},
        )
        return [example]

    def _examples_temp_storage_variables(self) -> list[dict[str, Any]]:
        """Ejemplos para consulta temp_storage_variables."""
        if self.db_type != "mariadb":
            return []
        return [
            {
                "description": "Leer innodb_temp_data_file_path para documentar el almacenamiento temporal InnoDB",
                "parameters": {},
            }
        ]

    def export_documentation(self, output_file: Path) -> None:
        """Exporta documentación completa de todas las consultas a un archivo"""
        documentation = {
            "db_type": self.db_type,
            "db_metadata": self.get_database_metadata(),
            "queries": {},
        }

        for query_name in self.get_available_query_names():
            documentation["queries"][query_name] = self.get_query_documentation(query_name)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(documentation, f, indent=2, ensure_ascii=False)
            self.logger.info(f"✅ Documentación exportada a {output_file}")
        except Exception as e:
            self.logger.error(f"❌ Error al exportar documentación: {e}")
            raise OSError(f"Error al exportar documentación: {e}") from e
