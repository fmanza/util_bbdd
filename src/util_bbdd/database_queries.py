"""
Módulo unificado para manejo de consultas de base de datos
Integra funcionalidad de:
- database_queries.py (base)
- database_queries_simplified.py (simplificado)
- advanced_database_queries.py (avanzado)

Soporta MariaDB, Oracle, PostgreSQL, HSQLDB, SQL Server y SQLite
"""

import json
import logging
import re

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .database_type_validator import DatabaseTypeValidator

# Patrón regex para encontrar parámetros en plantillas de consultas
PARAMETER_PATTERN = r"\{(\w+)\}"


class DatabaseQueryError(Exception):
    """Excepción personalizada para errores en consultas de base de datos"""

    pass


class DatabaseQueries:
    """
    Clase unificada para manejar consultas SQL de base de datos.

    Integra:
    - Funcionalidad básica de consultas
    - Validación simplificada
    - Capacidades avanzadas de validación y documentación
    """

    # Error message constants
    ERROR_OBTENER_TABLAS_REQUIRES_DATABASE = (
        "La consulta 'obtener_tablas' requiere el parámetro 'database'"
    )
    ERROR_COLUMNAS_TABLA_REQUIRES_DATABASE = (
        "La consulta 'columnas_tabla' requiere el parámetro 'database'"
    )
    ERROR_COLUMNAS_TABLA_REQUIRES_TABLA = (
        "La consulta 'columnas_tabla' requiere el parámetro 'tabla'"
    )
    ERROR_CREATE_TABLE_REQUIRES_TABLA = "La consulta 'create_table' requiere el parámetro 'tabla'"
    ERROR_OBTENER_RUTINAS_REQUIRES_DATABASE = (
        "La consulta 'obtener_rutinas' requiere el parámetro 'database'"
    )
    ERROR_PARAMETROS_RUTINA_REQUIRES_DATABASE = (
        "La consulta 'parametros_rutina' requiere el parámetro 'database'"
    )
    ERROR_PARAMETROS_RUTINA_REQUIRES_RUTINA = (
        "La consulta 'parametros_rutina' requiere el parámetro 'rutina'"
    )
    ERROR_PARAMETROS_RUTINA_REQUIRES_TIPO = (
        "La consulta 'parametros_rutina' requiere el parámetro 'tipo_rutina'"
    )
    ERROR_CREATE_RUTINA_REQUIRES_RUTINA = (
        "La consulta 'create_rutina' requiere el parámetro 'rutina'"
    )
    ERROR_CREATE_RUTINA_REQUIRES_TIPO = (
        "La consulta 'create_rutina' requiere el parámetro 'tipo_rutina'"
    )
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
            raise ValueError(
                f"Tipo de base de datos no soportado. Use: {', '.join(supported_types)}"
            )

        self.db_type: str = db_type.lower()
        self.logger.debug(f"✅ Inicializando DatabaseQueries para {self.db_type}")

        # Cargar consultas SQL
        default_queries_path: Path = Path(__file__).parent / "data" / "sql_queries.json"
        self.queries: dict[Any, Any] = self._load_queries(queries_file or default_queries_path)
        self.logger.debug(f"✅ {len(self.queries.get(self.db_type, {}))} consultas cargadas")

        # Inicializar validador de tipos de BD para obtener metadatos
        self.db_validator: DatabaseTypeValidator = DatabaseTypeValidator(config_file)
        # Nota: No redundar validate_db_type() aquí, ya validado en línea 68

        # Cargar metadatos adicionales del tipo de BD
        self.db_metadata: dict[str, Any] = self.db_validator.get_db_type_info(db_type)
        self.config_examples: dict[str, Any] = self.db_validator.get_db_type_examples(db_type)

    def _load_queries(self, queries_file: Path) -> dict:
        """
        Carga las consultas SQL desde el fichero JSON

        Args:
            queries_file: Ruta al archivo JSON con las consultas

        Returns:
            Diccionario con las consultas SQL

        Raises:
            FileNotFoundError: Si no se encuentra el archivo de consultas
            ValueError: Si hay un error al leer el JSON
        """
        try:
            with open(queries_file, encoding="utf-8") as f:
                queries = json.load(f)
            self.logger.debug(f"✅ Consultas cargadas desde {queries_file}")
            return queries
        except FileNotFoundError as e:
            self.logger.error(f"❌ Fichero de consultas no encontrado: {queries_file}")
            raise FileNotFoundError(f"Fichero de consultas no encontrado: {queries_file}") from e
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Error al leer fichero JSON: {e}")
            raise ValueError(f"Error al leer fichero JSON: {e}") from e

    # ==================== MÉTODOS DE CONSULTA BÁSICOS ====================

    def get_query(self, query_name: str, **kwargs) -> str:
        """
        Obtiene una consulta SQL formateada con los parámetros proporcionados

        Args:
            query_name: Nombre de la consulta a obtener
            **kwargs: Parámetros para formatear la consulta

        Returns:
            Consulta SQL formateada

        Raises:
            KeyError: Si no existe la consulta especificada
        """
        try:
            query = self.queries[self.db_type][query_name]
            return query.format(**kwargs) if kwargs else query
        except KeyError as e:
            self.logger.error(f"❌ Consulta no encontrada: {query_name} para tipo {self.db_type}")
            raise KeyError(f"Consulta no encontrada: {query_name} para tipo {self.db_type}") from e

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

    def get_routine_parameters_query(
        self, database: str, routine_name: str, routine_type: str
    ) -> str:
        """Obtiene la consulta para listar parámetros de una rutina."""
        return self.get_query(
            "parametros_rutina",
            database=database,
            rutina=routine_name,
            tipo_rutina=routine_type.upper(),
        )

    def get_routine_ddl_query(
        self, routine_name: str, routine_type: str, schema: str | None = None
    ) -> str:
        """Obtiene la consulta para recuperar el DDL de una rutina."""
        if self.db_type == "mariadb":
            return self.get_query(
                "create_rutina", rutina=routine_name, tipo_rutina=routine_type.upper()
            )

        return self.get_query(
            "create_rutina", rutina=routine_name, tipo_rutina=routine_type.upper(), esquema=schema
        )

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

    def validate_query_parameters(self, query_name: str, **kwargs) -> bool:
        """
        Valida si los parámetros proporcionados son suficientes para formatear una consulta

        Args:
            query_name: Nombre de la consulta a validar
            **kwargs: Parámetros a validar

        Returns:
            True si los parámetros son suficientes, False en caso contrario
        """
        try:
            analysis: dict[str, Any] = self.analyze_query_parameters(query_name, kwargs)
            return (
                bool(analysis.get("supported"))
                and not analysis.get("missing_required")
                and not analysis.get("provided_empty")
            )
        except (ValueError, KeyError):
            return False
        except Exception as e:
            self.logger.error(f"❌ Error validando parámetros para consulta '{query_name}': {e}")
            return False

    def analyze_query_parameters(
        self, query_name: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Analiza parámetros de una query para distinguir soporte/faltantes/vacíos.

        Returns:
            Diccionario con:
            - supported (bool): si la consulta existe para el motor actual.
            - required_parameters (list[str]): placeholders requeridos por plantilla.
            - missing_required (list[str]): requeridos ausentes en `params`.
            - provided_empty (list[str]): presentes pero con valor vacío (None o str vacío).
        """
        provided_params: dict[str, Any] = dict(params or {})
        engine_queries: dict[str, str] = self.queries.get(self.db_type, {})

        if query_name not in engine_queries:
            return {
                "supported": False,
                "required_parameters": [],
                "missing_required": [],
                "provided_empty": [],
            }

        query_template: str = engine_queries[query_name]
        required_parameters: list[str] = sorted(set(re.findall(PARAMETER_PATTERN, query_template)))

        missing_required: list[str] = [
            param for param in required_parameters if param not in provided_params
        ]

        def _is_empty(value: Any) -> bool:
            if value is None:
                return True
            if isinstance(value, str):
                return value.strip() == ""
            return False

        provided_empty: list[str] = [
            param
            for param in required_parameters
            if param in provided_params and _is_empty(provided_params[param])
        ]

        return {
            "supported": True,
            "required_parameters": required_parameters,
            "missing_required": missing_required,
            "provided_empty": provided_empty,
        }

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
        errors = []

        # Validar que la consulta exista
        if not self.validate_query_parameters(query_name, **kwargs):
            errors.append(f"Parámetros inválidos o faltantes para la consulta '{query_name}'")
            return False, errors

        # Validaciones específicas por tipo de BD
        if self.db_type == "postgresql":
            errors.extend(self._validate_postgresql_query(query_name, **kwargs))
        elif self.db_type == "oracle":
            errors.extend(self._validate_oracle_query(query_name, **kwargs))
        elif self.db_type == "mariadb":
            errors.extend(self._validate_mariadb_query(query_name, **kwargs))
        elif self.db_type == "hsqldb":
            errors.extend(self._validate_hsqldb_query(query_name, **kwargs))
        elif self.db_type == "sqlserver":
            errors.extend(self._validate_sqlserver_query(query_name, **kwargs))

        return len(errors) == 0, errors

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
            errors.append(
                "El nombre de la tabla solo puede contener letras, números, guiones y guiones bajos"
            )
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
            errors.append(
                "SQL Server no permite nombres de base de datos con más de 128 caracteres"
            )
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
            errors.append(
                "El nombre de la tabla solo puede contener letras, números, guiones bajos y $"
            )
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
            errors.append(
                "El nombre de la tabla solo puede contener letras, números, guiones bajos y $"
            )
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
        return [
            {
                "description": "Ver configuración de tablespaces temporales PostgreSQL",
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


class DatabaseQueryExecutor:
    """Clase para ejecutar consultas de base de datos"""

    def __init__(
        self,
        connection: Any,
        cursor: Any,
        queries: DatabaseQueries,
        connection_provider: Callable[[], Any] | None = None,
        connection_releaser: Callable[[Any], None] | None = None,
    ):
        """
        Inicializa el ejecutor de consultas

        Args:
            connection: Conexión a la base de datos
            cursor: Cursor de la base de datos
            queries: Instancia de DatabaseQueries con las consultas
            connection_provider: Callable opcional para obtener conexión por operación.
            connection_releaser: Callable opcional para liberar/devolver conexión.
        """
        self.connection = connection
        self.cursor = cursor
        self.queries: DatabaseQueries = queries
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._connection_provider: Callable[[], Any] | None = connection_provider
        self._connection_releaser: Callable[[Any], None] = connection_releaser or (
            lambda _conn: None
        )

    def _acquire_execution_resources(self) -> tuple[Any, Any, bool]:
        """Obtiene conexión/cursor para ejecutar una operación.

        Returns:
            Tupla (connection, cursor, managed_resources), donde managed_resources
            indica si deben liberarse al finalizar.
        """
        if self._connection_provider is None:
            return self.connection, self.cursor, False

        connection: Any = self._connection_provider()
        cursor: Any = connection.cursor()
        return connection, cursor, True

    def _release_execution_resources(
        self, connection: Any, cursor: Any, managed_resources: bool
    ) -> None:
        """Libera recursos adquiridos para una operación."""
        if not managed_resources:
            return

        if cursor is not None:
            try:
                cursor.close()
            except Exception as e:
                self.logger.warning(f"⚠️ Error cerrando cursor temporal: {e}")

        if connection is not None:
            try:
                self._connection_releaser(connection)
            except Exception as e:
                self.logger.warning(f"⚠️ Error liberando conexión temporal: {e}")

    def _materialize_value(self, value: Any, visited: set[int] | None = None) -> Any:
        """Materializa valores dependientes de conexión activa (ej. LOBs)."""
        if visited is None:
            visited = set()

        if value is None:
            return None

        if hasattr(value, "read") and callable(value.read):
            try:
                return value.read()
            except Exception:
                return value

        if isinstance(value, tuple):
            container_id: int = id(value)
            if container_id in visited:
                self.logger.debug(
                    "⚠️ Ciclo detectado materializando tuple; se devuelve valor original"
                )
                return value
            visited.add(container_id)
            return tuple(self._materialize_value(item, visited) for item in value)

        if isinstance(value, list):
            container_id = id(value)
            if container_id in visited:
                self.logger.debug(
                    "⚠️ Ciclo detectado materializando list; se devuelve valor original"
                )
                return value
            visited.add(container_id)
            return [self._materialize_value(item, visited) for item in value]

        if isinstance(value, dict):
            container_id = id(value)
            if container_id in visited:
                self.logger.debug(
                    "⚠️ Ciclo detectado materializando dict; se devuelve valor original"
                )
                return value
            visited.add(container_id)
            return {key: self._materialize_value(item, visited) for key, item in value.items()}

        return value

    def _materialize_result(self, result: Any) -> Any:
        """Materializa el resultado completo antes de liberar recursos."""
        return self._materialize_value(result)

    def _validate_and_check_query_existence(self, query_name: str) -> None:
        """Valida la existencia de la consulta en el tipo de base de datos actual.

        Args:
            query_name: Nombre de la consulta a validar

        Raises:
            ValueError: Si la consulta no existe para el tipo de BD actual
        """
        if query_name not in self.queries.queries.get(self.queries.db_type, {}):
            available = list(self.queries.queries.get(self.queries.db_type, {}).keys())
            error_msg = f"Consulta '{query_name}' no disponible para {self.queries.db_type}. Disponibles: {available}"
            self.logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

    def _validate_query_parameters_and_build_error(
        self, query_name: str, kwargs: dict[str, Any]
    ) -> None:
        """Valida parámetros de consulta y genera errores descriptivos.

        Args:
            query_name: Nombre de la consulta a validar
            kwargs: Parámetros de la consulta

        Raises:
            ValueError: Si los parámetros son inválidos
        """
        analysis: dict[str, Any] = self.queries.analyze_query_parameters(query_name, kwargs)
        if (
            (not analysis.get("supported"))
            or analysis.get("missing_required")
            or analysis.get("provided_empty")
        ):
            missing_params: list[str] = list(analysis.get("missing_required", []))
            empty_params: list[str] = list(analysis.get("provided_empty", []))
            parts: list[str] = []
            if missing_params:
                parts.append(f"faltantes={missing_params}")
            if empty_params:
                parts.append(f"vacíos={empty_params}")
            details: str = ", ".join(parts) if parts else "parámetros inválidos"
            error_msg: str = f"Parámetros inválidos para la consulta '{query_name}': {details}"
            self.logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

    def execute_query(self, query_name: str, fetch_one: bool = False, **kwargs) -> Any:
        """
        Ejecuta una consulta con los parámetros proporcionados

        Args:
            query_name: Nombre de la consulta a ejecutar
            fetch_one: Si es True, devuelve solo un resultado con fetchone()
            **kwargs: Parámetros para formatear la consulta

        Returns:
            Resultado de la consulta

        Raises:
            ValueError: Si los parámetros son inválidos
            DatabaseQueryError: Si hay un error en la ejecución
        """
        connection: Any = None
        cursor: Any = None
        managed_resources: bool = False

        try:
            connection, cursor, managed_resources = self._acquire_execution_resources()

            # Verificar que la consulta existe
            self._validate_and_check_query_existence(query_name)

            # Validar parámetros
            self._validate_query_parameters_and_build_error(query_name, kwargs)

            if self.queries.db_type == "mariadb" and query_name == "ficheros_fisicos_adicional":
                database_name: str = str(kwargs.get("database", "") or "").strip()
                return self._execute_mariadb_additional_storage_query(database=database_name)

            query: str = self.queries.get_query(query_name, **kwargs)
            self.logger.debug(f"📝 Ejecutando consulta: {query_name}")
            cursor.execute(query)
            result = cursor.fetchone() if fetch_one else cursor.fetchall()
            result = self._materialize_result(result)
            self.logger.debug(f"✅ Consulta '{query_name}' ejecutada exitosamente")
            return result
        except DatabaseQueryError:
            raise
        except (ValueError, KeyError):
            raise
        except Exception as e:
            error_msg = f"Error al ejecutar consulta '{query_name}': {e}"
            self.logger.error(f"❌ {error_msg}")
            raise DatabaseQueryError(error_msg) from e
        finally:
            self._release_execution_resources(connection, cursor, managed_resources)

    def _mariadb_information_schema_has_table(self, table_name: str) -> bool:
        """Indica si existe una tabla en INFORMATION_SCHEMA de MariaDB."""
        escaped_table: str = self._escape_sql_literal(str(table_name or "").upper())
        probe_query: str = (
            "SELECT COUNT(*) "
            "FROM information_schema.tables "
            "WHERE UPPER(table_schema) = 'INFORMATION_SCHEMA' "
            f"AND UPPER(table_name) = '{escaped_table}'"
        )
        result: Any = self.execute_custom_query(probe_query, fetch_one=True)
        try:
            return bool(result) and int(result[0]) > 0
        except (TypeError, ValueError, IndexError):
            return False

    def _mariadb_information_schema_has_column(self, table_name: str, column_name: str) -> bool:
        """Indica si existe una columna en una tabla de INFORMATION_SCHEMA."""
        escaped_table: str = self._escape_sql_literal(str(table_name or "").upper())
        escaped_column: str = self._escape_sql_literal(str(column_name or "").upper())
        probe_query: str = (
            "SELECT COUNT(*) "
            "FROM information_schema.columns "
            "WHERE UPPER(table_schema) = 'INFORMATION_SCHEMA' "
            f"AND UPPER(table_name) = '{escaped_table}' "
            f"AND UPPER(column_name) = '{escaped_column}'"
        )
        result: Any = self.execute_custom_query(probe_query, fetch_one=True)
        try:
            return bool(result) and int(result[0]) > 0
        except (TypeError, ValueError, IndexError):
            return False

    def _execute_mariadb_additional_storage_query(self, database: str) -> list:
        """Ejecuta consulta adaptativa de ficheros físicos adicionales para MariaDB."""
        if not database:
            raise ValueError(
                "La consulta 'ficheros_fisicos_adicional' requiere el parámetro 'database'"
            )

        tablespaces_table: str = "INNODB_SYS_TABLESPACES"
        if not self._mariadb_information_schema_has_table(tablespaces_table):
            self.logger.warning(
                "⚠️ INFORMATION_SCHEMA.INNODB_SYS_TABLESPACES no disponible en MariaDB. "
                "Se omite inventario adicional."
            )
            return []

        file_name_expr: str = "''"
        join_clause: str = ""
        if self._mariadb_information_schema_has_column(tablespaces_table, "FILE_NAME"):
            file_name_expr = "t.FILE_NAME"
        elif self._mariadb_information_schema_has_column(tablespaces_table, "FILENAME"):
            file_name_expr = "t.FILENAME"
        elif (
            self._mariadb_information_schema_has_table("INNODB_SYS_DATAFILES")
            and self._mariadb_information_schema_has_column("INNODB_SYS_DATAFILES", "PATH")
            and self._mariadb_information_schema_has_column(tablespaces_table, "SPACE")
        ):
            file_name_expr = "d.PATH"
            join_clause = (
                " LEFT JOIN information_schema.INNODB_SYS_DATAFILES d ON d.SPACE = t.SPACE "
            )

        file_size_expr: str = (
            "t.FILE_SIZE/1024/1024"
            if self._mariadb_information_schema_has_column(tablespaces_table, "FILE_SIZE")
            else "NULL"
        )
        allocated_expr: str = (
            "t.ALLOCATED_SIZE/1024/1024"
            if self._mariadb_information_schema_has_column(tablespaces_table, "ALLOCATED_SIZE")
            else "NULL"
        )
        escaped_database: str = self._escape_sql_literal(database)
        query: str = (
            "SELECT "
            "t.NAME AS tablespace_name, "
            f"{file_name_expr} AS archivo_fisico, "
            f"{file_size_expr} AS file_size_mb, "
            f"{allocated_expr} AS allocated_mb "
            f"FROM information_schema.{tablespaces_table} t "
            f"{join_clause}"
            f"WHERE t.NAME LIKE '{escaped_database}/%' "
            "ORDER BY allocated_mb DESC"
        )
        self.logger.debug("📝 Ejecutando consulta adaptativa: ficheros_fisicos_adicional")
        result: Any = self.execute_custom_query(query, fetch_one=False)
        return list(result or [])

    def _get_missing_parameters(self, query_name: str, **kwargs) -> list[str]:
        """Obtiene los parámetros faltantes para una consulta"""
        analysis: dict[str, Any] = self.queries.analyze_query_parameters(query_name, kwargs)
        return list(analysis.get("missing_required", []))

    # ==================== MÉTODOS DE CONVENIENCIA ====================

    def get_tables(self, database: str) -> list:
        """Obtiene la lista de tablas de la base de datos"""
        return self.execute_query("obtener_tablas", fetch_one=False, database=database)

    def get_views(self, database: str) -> list:
        """Obtiene la lista de vistas de la base de datos"""
        return self.execute_query("obtener_vistas", fetch_one=False, database=database)

    def get_routines(self, database: str) -> list:
        """Obtiene la lista de rutinas (procedures y funciones) de la base de datos."""
        return self.execute_query("obtener_rutinas", fetch_one=False, database=database)

    def _normalize_ddl_result(self, ddl: Any) -> str:
        """Normaliza cualquier resultado DDL a texto plano.

        Convierte resultados crudos de drivers (str, tuple/list, LOB/streams,
        objetos arbitrarios) a una cadena consistente para capas de salida.
        """
        if ddl is None:
            return ""
        if isinstance(ddl, str):
            return ddl
        if self._is_lob(ddl):
            return self._read_lob(ddl)
        if not isinstance(ddl, (tuple, list)):
            return str(ddl)
        if len(ddl) == 1:
            return self._normalize_single_element(ddl[0])
        result: str = self._extract_preferred_ddl(ddl)
        if result:
            return result
        result = self._extract_any_ddl(ddl)
        if result:
            return result
        return ""

    def _is_lob(self, value: Any) -> bool:
        return hasattr(value, "read") and callable(value.read)

    def _read_lob(self, value: Any) -> str:
        try:
            return str(value.read())
        except Exception:
            return str(value)

    def _normalize_single_element(self, element: Any) -> str:
        if element is None:
            return ""
        if isinstance(element, (tuple, list)) or self._is_lob(element):
            return self._normalize_ddl_result(element)
        return str(element)

    def _extract_preferred_ddl(self, ddl: Any) -> str:
        preferred_positions: list[int] = [2, 1, 0]
        for pos in preferred_positions:
            if len(ddl) <= pos:
                continue
            candidate: Any = ddl[pos]
            result: str = self._evaluate_candidate_for_ddl(candidate)
            if result:
                return result
        return ""

    def _evaluate_candidate_for_ddl(self, candidate: Any) -> str:
        if candidate is None:
            return ""
        if self._is_lob(candidate):
            candidate = self._read_lob(candidate)
        if isinstance(candidate, (tuple, list)):
            nested_text: str = self._normalize_ddl_result(candidate)
            if self._contains_create(nested_text):
                return nested_text
            if nested_text.strip():
                return nested_text
            return ""
        candidate_text: str = str(candidate)
        if self._contains_create(candidate_text):
            return candidate_text
        return ""

    def _extract_any_ddl(self, ddl: Any) -> str:
        for value in ddl:
            if value is None:
                continue
            if self._is_lob(value):
                value: str = self._read_lob(value)
            text: str = str(value)
            if text.strip():
                return text
        return ""

    def _contains_create(self, text: str) -> bool:
        return "CREATE " in text.upper()

    def _add_metadata_context_params(
        self, params: dict[str, str], context: str | None
    ) -> dict[str, str]:
        """Agrega parámetros de contexto (`database`/`esquema`) según motor."""
        if not context or self.queries.db_type == "mariadb":
            return params

        # Oracle y SQL Server usan `esquema` en DDL de objetos.
        if self.queries.db_type in {"oracle", "sqlserver"}:
            params["esquema"] = context

        # PostgreSQL/HSQLDB/SQL Server usan `database` en queries de metadatos tabulares.
        if self.queries.db_type in {"postgresql", "hsqldb", "sqlserver"}:
            params["database"] = context

        return params

    def get_ddl(self, table: str, schema: str | None = None) -> str:
        """Obtiene el DDL de una tabla"""
        params: dict[str, str] = {"tabla": table}
        params = self._add_metadata_context_params(params, schema)
        try:
            ddl_raw: Any = self.execute_query("create_table", fetch_one=True, **params)
            return self._normalize_ddl_result(ddl_raw)
        except DatabaseQueryError as error:
            if not self._should_retry_mariadb_ddl_with_hex(error):
                raise
            self.logger.warning(
                "⚠️ Error de decodificación detectado en create_table (MariaDB). "
                "Se aplica fallback de DDL sintético desde metadatos."
            )
            fallback_ddl: str = self._get_mariadb_table_ddl_fallback(table=table, schema=schema)
            if fallback_ddl:
                return fallback_ddl
            raise

    def get_view_ddl(self, view: str, schema: str | None = None) -> str:
        """Obtiene el DDL de una vista."""
        params: dict[str, str] = {"tabla": view}
        params = self._add_metadata_context_params(params, schema)

        available_queries: dict[str, str] = self.queries.queries.get(self.queries.db_type, {})
        query_name: str = "create_view" if "create_view" in available_queries else "create_table"
        try:
            ddl_raw: Any = self.execute_query(query_name, fetch_one=True, **params)
            return self._normalize_ddl_result(ddl_raw)
        except DatabaseQueryError as error:
            if not self._should_retry_mariadb_ddl_with_hex(error):
                raise
            self.logger.warning(
                "⚠️ Error de decodificación detectado en create_view (MariaDB). "
                "Se aplica fallback HEX desde INFORMATION_SCHEMA.VIEWS."
            )
            fallback_ddl: str = self._get_mariadb_view_ddl_with_hex_fallback(
                view=view, schema=schema
            )
            if fallback_ddl:
                return fallback_ddl
            raise

    def _should_retry_mariadb_ddl_with_hex(self, error: Exception) -> bool:
        """Indica si procede fallback por decode para DDL de tabla/vista en MariaDB."""
        if self.queries.db_type != "mariadb":
            return False

        text: str = str(error).lower()
        if "fetchone" in text or "fetchrows" in text or "unicode" in text or "utf-8" in text:
            return True

        cause: BaseException | None = error.__cause__
        while cause is not None:
            cause_text: str = str(cause).lower()
            if "unicode" in cause_text or "utf-8" in cause_text:
                return True
            cause = cause.__cause__

        return False

    def _get_mariadb_table_ddl_fallback(self, table: str, schema: str | None) -> str:
        """Construye un DDL básico de tabla MariaDB a partir de metadatos."""
        database_name: str = self._resolve_mariadb_database_name(schema)
        if not database_name:
            return ""

        columns: list = self.get_columns(database_name, table)
        if not columns:
            return ""

        column_lines: list[str] = self._build_mariadb_column_definitions(columns)
        if not column_lines:
            return ""

        pk_lines: list[str] = self._build_mariadb_primary_key_definitions(table, database_name)
        all_lines: list[str] = column_lines + pk_lines
        body: str = ",\n  ".join(all_lines)
        return f"CREATE TABLE `{table}` (\n  {body}\n);"

    def _resolve_mariadb_database_name(self, schema: str | None) -> str:
        """Resuelve el nombre de la base de datos, consultando DATABASE() si es necesario."""
        database_name: str = str(schema or "").strip()
        if database_name:
            return database_name

        try:
            db_row: Any = self.execute_custom_query("SELECT DATABASE()", fetch_one=True)
            if db_row and len(db_row) > 0 and db_row[0]:
                return str(db_row[0]).strip()
        except Exception:
            pass

        return ""

    def _build_mariadb_column_definitions(self, columns: list) -> list[str]:
        """Construye las definiciones de columnas para el DDL."""
        column_lines: list[str] = []
        for col in columns:
            line: str | None = self._build_mariadb_column_line(col)
            if line:
                column_lines.append(line)
        return column_lines

    def _build_mariadb_column_line(self, col: tuple) -> str | None:
        """Construye una línea de definición de columna."""
        name: str = str(col[0] if len(col) > 0 else "").strip()
        col_type: str = str(col[1] if len(col) > 1 else "").strip()

        if not name or not col_type:
            return None

        nullable: str = str(col[2] if len(col) > 2 and col[2] is not None else "").strip().upper()
        default_value: Any = col[4] if len(col) > 4 else None
        extra: str = str(col[5] if len(col) > 5 and col[5] is not None else "").strip()

        line: str = f"`{name}` {col_type}"
        if nullable == "NO":
            line += " NOT NULL"
        if default_value is not None:
            line += f" DEFAULT {self._format_mariadb_default_literal(default_value)}"
        if extra:
            line += f" {extra}"

        return line

    def _build_mariadb_primary_key_definitions(self, table: str, database_name: str) -> list[str]:
        """Construye las definiciones de claves primarias para el DDL."""
        pk_lines: list[str] = []
        try:
            primary_keys: list = self.get_primary_keys(table, schema=database_name)
            pk_columns: list[str] = self._extract_primary_key_column_names(primary_keys)
            if pk_columns:
                pk_lines.append(f"PRIMARY KEY ({', '.join(pk_columns)})")
        except Exception:
            pass
        return pk_lines

    def _extract_primary_key_column_names(self, primary_keys: list) -> list[str]:
        """Extrae nombres de columnas de claves primarias."""
        pk_columns: list[str] = []
        for pk in primary_keys:
            pk_name: str = self._extract_primary_key_name(pk)
            if pk_name:
                pk_columns.append(f"`{pk_name}`")
        return pk_columns

    def _extract_primary_key_name(self, pk: Any) -> str:
        """Extrae el nombre de una clave primaria individual."""
        if isinstance(pk, (list, tuple)):
            pk_name = str(pk[0] if pk else "").strip()
        else:
            pk_name = str(pk).strip()
        return pk_name

    def _format_mariadb_default_literal(self, value: Any) -> str:
        """Formatea literales DEFAULT en DDL sintético MariaDB."""
        text: str = str(value)
        upper_text: str = text.strip().upper()
        if upper_text in {"NULL", "CURRENT_TIMESTAMP"}:
            return upper_text

        if re.fullmatch(r"-?\d+(\.\d+)?", text.strip()):
            return text.strip()

        escaped: str = text.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    def _get_mariadb_view_ddl_with_hex_fallback(self, view: str, schema: str | None) -> str:
        """Obtiene DDL de vista MariaDB decodificando VIEW_DEFINITION vía HEX."""
        escaped_view: str = self._escape_sql_literal(view)
        escaped_schema: str = self._escape_sql_literal(str(schema or "").strip())
        schema_filter: str = (
            f"UPPER(v.TABLE_SCHEMA) = UPPER('{escaped_schema}')"
            if escaped_schema
            else "UPPER(v.TABLE_SCHEMA) = UPPER(DATABASE())"
        )
        query: str = (
            "SELECT CASE WHEN v.VIEW_DEFINITION IS NULL THEN NULL ELSE HEX(v.VIEW_DEFINITION) END AS ddl_hex "
            "FROM INFORMATION_SCHEMA.VIEWS v "
            f"WHERE {schema_filter} "
            f"AND UPPER(v.TABLE_NAME) = UPPER('{escaped_view}') "
            "LIMIT 1"
        )

        row: Any = self.execute_custom_query(query, fetch_one=True)
        if not row or len(row) == 0:
            return ""

        definition: str = str(self._decode_hex_text(row[0], preserve_none=False) or "").strip()
        if not definition:
            return ""
        if self._contains_create(definition):
            return definition

        return f"CREATE VIEW `{view}` AS\n{definition}"

    def get_routine_parameters(self, database: str, routine_name: str, routine_type: str) -> list:
        """Obtiene los parámetros de una rutina."""
        if self.queries.db_type == "mariadb":
            return self._get_mariadb_routine_parameters(
                database=database, routine_name=routine_name, routine_type=routine_type
            )

        if self.queries.db_type == "oracle":
            return self._get_oracle_routine_parameters(database=database, routine_name=routine_name)

        params: dict[str, str] = {
            "database": database,
            "rutina": routine_name,
            "tipo_rutina": routine_type.upper(),
        }
        return self.execute_query("parametros_rutina", fetch_one=False, **params)

    def _get_mariadb_routine_parameters(
        self, database: str, routine_name: str, routine_type: str
    ) -> list:
        """Obtiene parámetros de rutina para MariaDB con estrategia adaptativa por columnas disponibles."""
        include_parameter_default: bool = self._mariadb_parameters_has_column("PARAMETER_DEFAULT")

        parameters: list = self._query_mariadb_routine_parameters_by_name_field(
            database=database,
            routine_name=routine_name,
            routine_type=routine_type,
            name_field="specific_name",
            include_parameter_default=include_parameter_default,
        )

        if parameters:
            return parameters

        if not self._mariadb_parameters_has_column("ROUTINE_NAME"):
            return []

        self.logger.debug(
            "⚠️ MariaDB fallback activo para parámetros de rutina por ROUTINE_NAME: "
            f"{routine_type.upper()} {routine_name}"
        )
        return self._query_mariadb_routine_parameters_by_name_field(
            database=database,
            routine_name=routine_name,
            routine_type=routine_type,
            name_field="routine_name",
            include_parameter_default=include_parameter_default,
        )

    def _query_mariadb_routine_parameters_by_name_field(
        self,
        database: str,
        routine_name: str,
        routine_type: str,
        name_field: str,
        include_parameter_default: bool,
    ) -> list:
        """Consulta parámetros de rutina en MariaDB filtrando por campo de nombre (specific_name/routine_name)."""
        escaped_database: str = self._escape_sql_literal(database)
        escaped_routine_name: str = self._escape_sql_literal(routine_name)
        escaped_routine_type: str = self._escape_sql_literal(routine_type.upper())

        parameter_default_sql: str = (
            "COALESCE(p.parameter_default, '') AS parameter_default"
            if include_parameter_default
            else "'' AS parameter_default"
        )

        query: str = (
            "SELECT "
            "CASE WHEN UPPER(p.routine_type) = 'FUNCTION' AND p.ordinal_position = 0 THEN 'RETURN' "
            "ELSE COALESCE(p.parameter_mode, '') END AS parameter_mode, "
            "CASE WHEN UPPER(p.routine_type) = 'FUNCTION' AND p.ordinal_position = 0 THEN 'RETURN_VALUE' "
            "ELSE COALESCE(p.parameter_name, '') END AS parameter_name, "
            "COALESCE(p.dtd_identifier, '') AS data_type, "
            f"{parameter_default_sql}, "
            "p.ordinal_position "
            "FROM information_schema.parameters p "
            f"WHERE p.specific_schema = '{escaped_database}' "
            f"AND UPPER(p.{name_field}) = UPPER('{escaped_routine_name}') "
            f"AND UPPER(p.routine_type) = UPPER('{escaped_routine_type}') "
            "ORDER BY p.ordinal_position"
        )

        try:
            return self.execute_custom_query(query, fetch_one=False)
        except Exception as error:
            self.logger.warning(
                "⚠️ Error consultando parámetros de rutina MariaDB "
                f"por {name_field} para {routine_name}: {error}"
            )
            return []

    def _mariadb_parameters_has_column(self, column_name: str) -> bool:
        """Indica si INFORMATION_SCHEMA.PARAMETERS expone una columna dada."""
        escaped_column_name: str = self._escape_sql_literal(column_name.upper())
        probe_query: str = (
            "SELECT COUNT(*) "
            "FROM information_schema.columns "
            "WHERE UPPER(table_schema) = 'INFORMATION_SCHEMA' "
            "AND UPPER(table_name) = 'PARAMETERS' "
            f"AND UPPER(column_name) = '{escaped_column_name}'"
        )

        result: Any = self.execute_custom_query(probe_query, fetch_one=True)
        if result is None:
            return False

        try:
            count_value: int = int(result[0])
        except (TypeError, ValueError, IndexError):
            return False

        return count_value > 0

    def _escape_sql_literal(self, value: str) -> str:
        """Escapa comillas simples para interpolación segura en literales SQL."""
        return str(value).replace("'", "''")

    def get_routine_ddl(
        self, routine_name: str, routine_type: str, schema: str | None = None
    ) -> str:
        """Obtiene el DDL de una rutina (procedure/función)."""
        if self.queries.db_type == "oracle" and "." in str(routine_name):
            return self._get_oracle_packaged_routine_ddl(routine_name=routine_name, schema=schema)

        params: dict[str, str] = {
            "rutina": routine_name,
            "tipo_rutina": routine_type.upper(),
        }
        if schema and self.queries.db_type != "mariadb":
            params["esquema"] = schema
        try:
            ddl_raw: Any = self.execute_query("create_rutina", fetch_one=True, **params)
            return self._normalize_ddl_result(ddl_raw)
        except DatabaseQueryError as error:
            if not self._should_retry_mariadb_routine_ddl_with_hex(error):
                raise
            self.logger.warning(
                "⚠️ Error de decodificación detectado en create_rutina (MariaDB). "
                "Se aplica fallback HEX desde INFORMATION_SCHEMA.ROUTINES."
            )
            fallback_ddl: str = self._get_mariadb_routine_ddl_with_hex_fallback(
                routine_name=routine_name,
                routine_type=routine_type,
                schema=schema,
            )
            if fallback_ddl:
                return fallback_ddl
            raise

    def _should_retry_mariadb_routine_ddl_with_hex(self, error: Exception) -> bool:
        """Indica si procede fallback HEX para DDL de rutina en MariaDB."""
        if self.queries.db_type != "mariadb":
            return False

        text: str = str(error).lower()
        if "fetchone" in text or "fetchrows" in text or "unicode" in text or "utf-8" in text:
            return True

        cause: BaseException | None = error.__cause__
        while cause is not None:
            cause_text: str = str(cause).lower()
            if "unicode" in cause_text or "utf-8" in cause_text:
                return True
            cause = cause.__cause__

        return False

    def _get_mariadb_routine_ddl_with_hex_fallback(
        self,
        routine_name: str,
        routine_type: str,
        schema: str | None,
    ) -> str:
        """Obtiene DDL de rutina en MariaDB con consulta HEX para evitar errores de decode."""
        escaped_routine_name: str = self._escape_sql_literal(routine_name)
        escaped_routine_type: str = self._escape_sql_literal(
            str(routine_type or "").upper().strip() or "PROCEDURE"
        )
        escaped_schema: str = self._escape_sql_literal(str(schema or "").strip())

        schema_filter: str = (
            f"UPPER(r.ROUTINE_SCHEMA) = UPPER('{escaped_schema}')"
            if escaped_schema
            else "UPPER(r.ROUTINE_SCHEMA) = UPPER(DATABASE())"
        )
        query: str = (
            "SELECT CASE WHEN r.ROUTINE_DEFINITION IS NULL THEN NULL ELSE HEX(r.ROUTINE_DEFINITION) END AS ddl_hex "
            "FROM INFORMATION_SCHEMA.ROUTINES r "
            f"WHERE {schema_filter} "
            f"AND UPPER(r.ROUTINE_NAME) = UPPER('{escaped_routine_name}') "
            f"AND UPPER(r.ROUTINE_TYPE) = UPPER('{escaped_routine_type}') "
            "LIMIT 1"
        )

        row: Any = self.execute_custom_query(query, fetch_one=True)
        if not row or len(row) == 0:
            return ""

        ddl_body: str = str(self._decode_hex_text(row[0], preserve_none=False) or "").strip()
        if not ddl_body:
            return ""

        if self._contains_create(ddl_body):
            return ddl_body

        normalized_type: str = str(routine_type or "").upper().strip() or "PROCEDURE"
        signature: str = f"CREATE {normalized_type} `{routine_name}`"
        return f"{signature}\n{ddl_body}"

    def _parse_oracle_routine_identifier(
        self, routine_name: str
    ) -> tuple[str | None, str, str | None]:
        """Parsea identificador de rutina Oracle en formato PACKAGE.RUTINA#OVERLOAD."""
        raw_value: str = str(routine_name or "").strip()
        overload: str | None = None

        if "#" in raw_value:
            raw_value, overload = raw_value.rsplit("#", 1)
            overload = overload.strip() or None

        package_name: str | None = None
        object_name: str = raw_value
        if "." in raw_value:
            package_name, object_name = raw_value.split(".", 1)
            package_name = package_name.strip() or None
            object_name = object_name.strip()

        return package_name, object_name, overload

    def _get_oracle_routine_parameters(self, database: str, routine_name: str) -> list:
        """Obtiene parámetros Oracle soportando rutinas empaquetadas."""
        package_name, object_name, overload = self._parse_oracle_routine_identifier(routine_name)

        escaped_database: str = self._escape_sql_literal(database)
        escaped_object_name: str = self._escape_sql_literal(object_name)
        escaped_package_name: str = self._escape_sql_literal(package_name) if package_name else ""
        escaped_overload: str = self._escape_sql_literal(overload) if overload else ""

        package_filter: str
        if package_name:
            package_filter = f"AND UPPER(a.package_name) = UPPER('{escaped_package_name}') "
        else:
            package_filter = "AND a.package_name IS NULL "

        overload_filter: str = (
            f"AND NVL(a.overload, '0') = NVL('{escaped_overload}', '0') " if overload else ""
        )

        query: str = (
            "SELECT "
            "COALESCE(a.in_out, '') AS parameter_mode, "
            "COALESCE(a.argument_name, '') AS parameter_name, "
            "COALESCE(a.data_type, '') AS data_type, "
            "CASE WHEN a.defaulted = 'Y' THEN 'YES' ELSE '' END AS parameter_default, "
            "a.position AS ordinal_position "
            "FROM all_arguments a "
            f"WHERE a.owner = '{escaped_database}' "
            f"AND UPPER(a.object_name) = UPPER('{escaped_object_name}') "
            f"{package_filter}"
            "AND a.data_level = 0 "
            f"{overload_filter}"
            "ORDER BY NVL(a.overload, '0'), a.position"
        )

        result: Any = self.execute_custom_query(query, fetch_one=False)
        return result or []

    def _get_oracle_packaged_routine_ddl(self, routine_name: str, schema: str | None) -> str:
        """Obtiene DDL Oracle para rutinas empaquetadas devolviendo DDL del package y body."""
        package_name, _, _ = self._parse_oracle_routine_identifier(routine_name)
        if not package_name:
            ddl_raw: Any = self.execute_query(
                "create_rutina",
                fetch_one=True,
                rutina=routine_name,
                tipo_rutina="PROCEDURE",
                esquema=schema,
            )
            return self._normalize_ddl_result(ddl_raw)

        escaped_schema: str = self._escape_sql_literal(schema or "")
        escaped_package: str = self._escape_sql_literal(package_name)
        ddl_parts: list[str] = []

        queries: list[str] = [
            (
                "SELECT DBMS_METADATA.GET_DDL('PACKAGE', "
                f"'{escaped_package}', '{escaped_schema}') AS ddl FROM DUAL"
            ),
            (
                "SELECT DBMS_METADATA.GET_DDL('PACKAGE_BODY', "
                f"'{escaped_package}', '{escaped_schema}') AS ddl FROM DUAL"
            ),
        ]

        for query in queries:
            try:
                ddl_row: Any = self.execute_custom_query(query, fetch_one=True)
                if ddl_row and len(ddl_row) > 0 and ddl_row[0]:
                    ddl_parts.append(self._normalize_ddl_result(ddl_row))
            except Exception:
                continue

        if ddl_parts:
            return "\n\n".join(ddl_parts)

        return ""

    def get_columns(self, database: str, table: str) -> list:
        """Obtiene las columnas de una tabla"""
        try:
            return self.execute_query(
                "columnas_tabla", fetch_one=False, database=database, tabla=table
            )
        except DatabaseQueryError as error:
            if not self._should_retry_mariadb_columns_with_hex(error):
                raise
            self.logger.warning(
                "⚠️ Error de decodificación detectado en columnas_tabla (MariaDB). "
                "Se aplica fallback HEX para preservar caracteres extendidos."
            )
            return self._get_mariadb_columns_with_hex_fallback(database=database, table=table)

    def _should_retry_mariadb_columns_with_hex(self, error: Exception) -> bool:
        """Indica si procede fallback HEX para columnas en MariaDB."""
        if self.queries.db_type != "mariadb":
            return False

        text: str = str(error).lower()
        if "fetchrows" in text or "unicode" in text or "utf-8" in text:
            return True

        cause: BaseException | None = error.__cause__
        while cause is not None:
            cause_text: str = str(cause).lower()
            if "unicode" in cause_text or "utf-8" in cause_text:
                return True
            cause = cause.__cause__

        return False

    def _get_mariadb_columns_with_hex_fallback(self, database: str, table: str) -> list:
        """Obtiene columnas de MariaDB usando HEX para evitar errores de decodificación del driver."""
        escaped_database: str = self._escape_sql_literal(database)
        escaped_table: str = self._escape_sql_literal(table)
        query: str = (
            "SELECT "
            "CASE WHEN c.column_name IS NULL THEN NULL ELSE HEX(c.column_name) END AS column_name_hex, "
            "CASE WHEN c.column_type IS NULL THEN NULL ELSE HEX(c.column_type) END AS column_type_hex, "
            "CASE WHEN c.is_nullable IS NULL THEN NULL ELSE HEX(c.is_nullable) END AS is_nullable_hex, "
            "CASE WHEN c.column_key IS NULL THEN NULL ELSE HEX(c.column_key) END AS column_key_hex, "
            "CASE WHEN c.column_default IS NULL THEN NULL ELSE HEX(c.column_default) END AS column_default_hex, "
            "CASE WHEN c.extra IS NULL THEN NULL ELSE HEX(c.extra) END AS extra_hex, "
            "CASE WHEN c.column_comment IS NULL THEN NULL ELSE HEX(c.column_comment) END AS column_comment_hex "
            "FROM information_schema.columns c "
            f"WHERE c.table_schema = '{escaped_database}' AND c.table_name = '{escaped_table}' "
            "ORDER BY c.ordinal_position"
        )

        rows: list = self.execute_custom_query(query, fetch_one=False)
        return [self._decode_mariadb_hex_column_row(row) for row in rows]

    def _decode_mariadb_hex_column_row(self, row: tuple[Any, ...]) -> tuple[Any, ...]:
        """Decodifica fila de columnas MariaDB obtenida por HEX."""
        return (
            self._decode_hex_text(row[0], preserve_none=False),
            self._decode_hex_text(row[1], preserve_none=False),
            self._decode_hex_text(row[2], preserve_none=False),
            self._decode_hex_text(row[3], preserve_none=False),
            self._decode_hex_text(row[4], preserve_none=True),
            self._decode_hex_text(row[5], preserve_none=False),
            self._decode_hex_text(row[6], preserve_none=False),
        )

    def _decode_hex_text(self, value: Any, preserve_none: bool = True) -> Any:
        """Decodifica un valor HEX textual con fallback de codificaciones comunes."""
        if value is None:
            return None if preserve_none else ""

        if isinstance(value, memoryview):
            value = value.tobytes()

        if isinstance(value, (bytes, bytearray)):
            hex_text: str = bytes(value).decode("ascii", errors="ignore").strip()
        else:
            hex_text = str(value).strip()

        if not hex_text:
            return None if preserve_none else ""

        try:
            raw: bytes = bytes.fromhex(hex_text)
        except ValueError:
            return hex_text

        for encoding in ("utf-8", "latin1", "cp1252"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw.decode("latin1", errors="replace")

    def get_indices(self, table: str, schema: str | None = None) -> list:
        """Obtiene los índices de una tabla"""
        params: dict[str, str] = {"tabla": table}
        params = self._add_metadata_context_params(params, schema)
        return self.execute_query("indices", fetch_one=False, **params)

    def get_primary_keys(self, table: str, schema: str | None = None) -> list:
        """Obtiene las claves primarias de una tabla"""
        params: dict[str, str] = {"tabla": table}
        params = self._add_metadata_context_params(params, schema)
        return self.execute_query("claves_primarias", fetch_one=False, **params)

    def get_foreign_keys(self, table: str, schema: str | None = None) -> list:
        """Obtiene las claves foráneas de una tabla"""
        params: dict[str, str] = {"tabla": table}
        params = self._add_metadata_context_params(params, schema)
        return self.execute_query("claves_foraneas", fetch_one=False, **params)

    def get_unique_constraints(self, table: str, schema: str | None = None) -> list:
        """Obtiene las restricciones únicas de una tabla"""
        params: dict[str, str] = {"tabla": table}
        params = self._add_metadata_context_params(params, schema)
        return self.execute_query("claves_unicas", fetch_one=False, **params)

    def get_storage_inventory(
        self, database: str | None = None, tablespace: str | None = None
    ) -> dict[str, Any]:
        """Obtiene inventario de ficheros/tablespaces por motor.

        Returns:
            Diccionario con:
            - `primary`: resultado principal (list)
            - `secondary`: resultado secundario opcional (list)
        """
        results: dict[str, Any] = {"primary": [], "secondary": []}

        if self.queries.db_type == "sqlserver":
            results["primary"] = self.execute_query("ficheros_fisicos", fetch_one=False)
            return results

        if self.queries.db_type == "oracle":
            if not tablespace:
                raise ValueError("Para Oracle debe proporcionar 'tablespace'")
            results["primary"] = self.execute_query(
                "ficheros_fisicos", fetch_one=False, tablespace=tablespace
            )
            return results

        if self.queries.db_type == "mariadb":
            if not database:
                raise ValueError("Para MariaDB debe proporcionar 'database'")
            results["primary"] = self.execute_query(
                "ficheros_fisicos", fetch_one=False, database=database
            )
            results["secondary"] = self.execute_query(
                "ficheros_fisicos_adicional", fetch_one=False, database=database
            )
            return results

        if self.queries.db_type == "postgresql":
            if not tablespace:
                raise ValueError("Para PostgreSQL debe proporcionar 'tablespace'")
            results["primary"] = self.execute_query(
                "ficheros_fisicos", fetch_one=False, tablespace=tablespace
            )
            results["secondary"] = self.execute_query("temp_tablespaces", fetch_one=False)
            return results

        if self.queries.db_type == "sqlite":
            results["primary"] = self.execute_query("ficheros_fisicos", fetch_one=False)
            results["secondary"] = self.execute_query("ficheros_fisicos_adicional", fetch_one=False)
            try:
                temp_cfg = self.execute_query("temp_tablespaces", fetch_one=False)
                results["temp_tablespaces"] = temp_cfg
            except Exception:
                results["temp_tablespaces"] = []
            return results

        # HSQLDB: no hay consulta SQL estándar para tamaño de ficheros físicos.
        return results

    def execute_custom_query(
        self, sql: str, fetch_one: bool = False, params: tuple | None = None
    ) -> Any:
        """
        Ejecuta una consulta SQL personalizada

        Args:
            sql: Consulta SQL a ejecutar
            fetch_one: Si es True, devuelve solo un resultado
            params: Parámetros para la consulta (opcional)

        Returns:
            Resultado de la consulta
        """
        connection: Any = None
        cursor: Any = None
        managed_resources: bool = False

        try:
            connection, cursor, managed_resources = self._acquire_execution_resources()
            self.logger.debug("📝 Ejecutando consulta SQL personalizada")
            cursor.execute(sql, params or ())
            result = cursor.fetchone() if fetch_one else cursor.fetchall()
            result = self._materialize_result(result)
            self.logger.debug("✅ Consulta SQL personalizada ejecutada exitosamente")
            return result
        except DatabaseQueryError:
            raise
        except Exception as e:
            error_msg = f"Error al ejecutar consulta personalizada: {e}"
            self.logger.error(f"❌ {error_msg}")
            raise DatabaseQueryError(error_msg) from e
        finally:
            self._release_execution_resources(connection, cursor, managed_resources)

    def execute_batch(self, queries: list[tuple[str, bool, tuple | None]]) -> list[Any]:
        """
        Ejecuta múltiples consultas en batch

        Args:
            queries: Lista de tuplas (query, fetch_one, params)

        Returns:
            Lista de resultados
        """
        connection: Any = None
        cursor: Any = None
        managed_resources: bool = False

        try:
            connection, cursor, managed_resources = self._acquire_execution_resources()
            results = []
            for sql, fetch_one, params in queries:
                cursor.execute(sql, params or ())
                result = cursor.fetchone() if fetch_one else cursor.fetchall()
                results.append(self._materialize_result(result))
            return results
        except Exception as e:
            error_msg = f"Error ejecutando batch de consultas: {e}"
            self.logger.error(f"❌ {error_msg}")
            raise DatabaseQueryError(error_msg) from e
        finally:
            self._release_execution_resources(connection, cursor, managed_resources)

    def get_query_explanation(self, query_name: str, **kwargs) -> dict[str, Any]:
        """
        Obtiene información explicativa sobre una consulta

        Args:
            query_name: Nombre de la consulta
            **kwargs: Parámetros para formatear la consulta

        Returns:
            Diccionario con información de la consulta
        """
        query: str = self.queries.get_query(query_name, **kwargs)
        return {
            "query_name": query_name,
            "formatted_query": query,
            "db_type": self.queries.db_type,
            "parameters": kwargs,
            "is_valid": self.queries.validate_query_parameters(query_name, **kwargs),
        }


# Funciones de conveniencia para mantener retrocompatibilidad
def create_advanced_queries(
    db_type: str, queries_file: Path | None = None, config_file: Path | None = None
) -> DatabaseQueries:
    """
    Función de conveniencia para crear una instancia de DatabaseQueries
    (antes: AdvancedDatabaseQueries)
    """
    return DatabaseQueries(db_type, queries_file, config_file)
