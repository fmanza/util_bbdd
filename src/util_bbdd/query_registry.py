"""
Query Registry: Centraliza carga y acceso a definiciones de queries desde sql_queries.json

El QueryRegistry es responsable de:
1. Cargar queries desde el archivo JSON
2. Normalizar información en objetos QueryDefinition
3. Proporcionar acceso a queries por db_type + query_name
4. Levantar excepciones consistentes cuando query no existe
"""

import json
import logging
import re

from pathlib import Path

from .database_exceptions import QueryNotFoundError
from .models import QueryDefinition

# Patrón regex para encontrar placeholders en templates SQL
PARAMETER_PATTERN = r"\{(\w+)\}"


class QueryRegistry:
    """Centraliza carga y acceso a definiciones de queries.

    Responsabilidades:
    - Cargar sql_queries.json
    - Crear objetos QueryDefinition normalizados
    - Proporcionar queries por db_type + query_name
    - Levantar QueryNotFoundError si query no existe

    Ejemplo:
        registry = QueryRegistry()
        qdef = registry.get_query_definition("mariadb", "obtener_tablas")
        print(qdef.sql_template)
        print(qdef.required_params)  # ['database']
    """

    def __init__(self, queries_file: Path | None = None) -> None:
        """Inicializa el registry con un archivo de queries.

        Args:
            queries_file: Ruta al archivo JSON con queries.
                         Si es None, usa la ruta por defecto.

        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el JSON es inválido
        """
        self.logger = logging.getLogger(__name__)

        # Ruta por defecto
        if queries_file is None:
            queries_file = Path(__file__).parent / "data" / "sql_queries.json"

        self.queries_file = Path(queries_file)
        self._queries = self._load_queries()
        self.logger.debug(f"✅ QueryRegistry initialized with {len(self._queries)} db_types")

    def _load_queries(self) -> dict[str, dict[str, str]]:
        """Carga y valida queries desde archivo JSON.

        Returns:
            Diccionario con estructura: {db_type: {query_name: sql_template}}

        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el JSON es inválido
        """
        try:
            with open(self.queries_file, encoding="utf-8") as f:
                queries = json.load(f)

            self.logger.debug(f"✅ Loaded {len(queries)} db_types from {self.queries_file}")

            # Validación básica
            if not isinstance(queries, dict):
                raise ValueError(f"Expected dict at root level, got {type(queries).__name__}")

            for db_type, queries_by_name in queries.items():
                if not isinstance(queries_by_name, dict):
                    raise ValueError(f"Expected dict for db_type '{db_type}', got {type(queries_by_name).__name__}")

            return queries

        except FileNotFoundError as e:
            msg = f"Queries file not found: {self.queries_file}"
            self.logger.error(f"❌ {msg}")
            raise FileNotFoundError(msg) from e

        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in queries file {self.queries_file}: {e}"
            self.logger.error(f"❌ {msg}")
            raise ValueError(msg) from e

    def get_query_definition(self, db_type: str, query_name: str) -> QueryDefinition:
        """Obtiene QueryDefinition para un db_type + query_name.

        Args:
            db_type: Tipo de base de datos (ej: "mariadb")
            query_name: Nombre de la query (ej: "obtener_tablas")

        Returns:
            QueryDefinition con metadatos normalizados

        Raises:
            QueryNotFoundError: Si db_type o query_name no existen

        Ejemplo:
            qdef = registry.get_query_definition("mariadb", "obtener_tablas")
            # QueryDefinition(
            #     name="obtener_tablas",
            #     db_type="mariadb",
            #     sql_template="SELECT ...",
            #     required_params=["database"]
            # )
        """
        db_type = db_type.lower().strip()

        try:
            sql_template = self._queries[db_type][query_name]
        except KeyError as e:
            msg = f"Query '{query_name}' not found for db_type '{db_type}'"
            self.logger.error(f"❌ {msg}")
            raise QueryNotFoundError(msg) from e

        # Extraer placeholders del template
        required_params = self._extract_placeholders(sql_template)

        # Crear QueryDefinition
        qdef = QueryDefinition(
            name=query_name,
            db_type=db_type,
            sql_template=sql_template,
            required_params=list(required_params),
            metadata={"source": "sql_queries.json", "motor": db_type},
        )

        self.logger.debug(
            f"✅ Query definition loaded: {query_name} (db_type={db_type}, params={len(qdef.required_params)})"
        )

        return qdef

    def get_available_queries(self, db_type: str) -> list[str]:
        """Lista nombres de queries disponibles para un db_type.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Lista de nombres de queries disponibles (vacía si db_type no existe)

        Ejemplo:
            queries = registry.get_available_queries("mariadb")
            # ["obtener_tablas", "columnas_tabla", "indices", ...]
        """
        db_type = db_type.lower().strip()
        return list(self._queries.get(db_type, {}).keys())

    def get_all_db_types(self) -> list[str]:
        """Lista todos los db_types cargados.

        Returns:
            Lista de db_types disponibles

        Ejemplo:
            types = registry.get_all_db_types()
            # ["mariadb", "oracle", "postgresql", "hsqldb", "sqlserver", "sqlite"]
        """
        return list(self._queries.keys())

    @property
    def queries(self) -> dict[str, dict[str, str]]:
        """Acceso público a todas las queries cargadas.

        Returns:
            Diccionario con estructura: {db_type: {query_name: sql_template}}
        """
        return self._queries

    @staticmethod
    def _extract_placeholders(sql_template: str) -> set[str]:
        """Extrae nombres de placeholders del template SQL.

        Busca patrones {nombre} en el template usando regex.

        Args:
            sql_template: Template SQL con {placeholders}

        Returns:
            Set de nombres de placeholders encontrados

        Ejemplo:
            placeholders = QueryRegistry._extract_placeholders(
                "SELECT * WHERE schema = '{database}' AND table = '{tabla}'"
            )
            # {'database', 'tabla'}
        """
        matches = re.findall(PARAMETER_PATTERN, sql_template)
        return set(matches)
