"""Obtención de metadatos de base de datos.

Responsabilidad: Interfaz limpia para obtener metadatos de BD
(tablas, vistas, columnas, índices, DDL, etc.) desde una conexión.
"""

from typing import Any

from ..query.registry import QueryRegistry
from ..query.resolver import QueryResolver
from .contracts import Rows


class MetadataFetcher:
    """Obtiene metadatos de base de datos.

    Responsabilidad única: Abstraer consultas de metadatos detrás de interfaz limpia.

    Utiliza QueryRegistry y QueryResolver para ejecutar consultas de metadatos
    organizas para cada motor de BD.
    """

    def __init__(
        self,
        executor: Any,  # AsyncQueryExecutor | SyncQueryExecutor
        registry: QueryRegistry | None = None,
        resolver: QueryResolver | None = None,
    ):
        """Inicializa fetcher de metadatos.

        Args:
            executor: Ejecutor de queries (sync o async)
            registry: Registry de queries (usa default si None)
            resolver: Resolver de queries (usa default si None)
        """
        self.executor = executor
        self.registry = registry or QueryRegistry()
        self.resolver = resolver or QueryResolver(self.registry)

    def get_tables(self, db_type: str, schema: str | None = None) -> Rows:
        """Obtiene lista de tablas.

        Args:
            db_type: Tipo de base de datos
            schema: Schema/database (opcional, contextual)

        Returns:
            Filas con información de tablas
        """
        # Esta es una interfaz que será implementada por subclases
        # Por ahora, lanza NotImplementedError para ser clara
        raise NotImplementedError("Implementar en subclase específica por motor")

    def get_views(self, db_type: str, schema: str | None = None) -> Rows:
        """Obtiene lista de vistas.

        Args:
            db_type: Tipo de base de datos
            schema: Schema/database (opcional, contextual)

        Returns:
            Filas con información de vistas
        """
        raise NotImplementedError("Implementar en subclase específica por motor")

    def get_routines(self, db_type: str, schema: str | None = None) -> Rows:
        """Obtiene lista de rutinas (funciones, procedimientos).

        Args:
            db_type: Tipo de base de datos
            schema: Schema/database (opcional, contextual)

        Returns:
            Filas con información de rutinas
        """
        raise NotImplementedError("Implementar en subclase específica por motor")

    def get_columns(self, db_type: str, table_name: str) -> Rows:
        """Obtiene columnas de tabla.

        Args:
            db_type: Tipo de base de datos
            table_name: Nombre de tabla

        Returns:
            Filas con información de columnas
        """
        raise NotImplementedError("Implementar en subclase específica por motor")

    def get_primary_keys(self, db_type: str, table_name: str) -> Rows:
        """Obtiene claves primarias de tabla.

        Args:
            db_type: Tipo de base de datos
            table_name: Nombre de tabla

        Returns:
            Filas con información de PKs
        """
        raise NotImplementedError("Implementar en subclase específica por motor")

    def get_indices(self, db_type: str, table_name: str) -> Rows:
        """Obtiene índices de tabla.

        Args:
            db_type: Tipo de base de datos
            table_name: Nombre de tabla

        Returns:
            Filas con información de índices
        """
        raise NotImplementedError("Implementar en subclase específica por motor")

    def get_foreign_keys(self, db_type: str, table_name: str) -> Rows:
        """Obtiene claves foráneas de tabla.

        Args:
            db_type: Tipo de base de datos
            table_name: Nombre de tabla

        Returns:
            Filas con información de FKs
        """
        raise NotImplementedError("Implementar en subclase específica por motor")

    def get_unique_constraints(self, db_type: str, table_name: str) -> Rows:
        """Obtiene constraints únicos de tabla.

        Args:
            db_type: Tipo de base de datos
            table_name: Nombre de tabla

        Returns:
            Filas con información de UCs
        """
        raise NotImplementedError("Implementar en subclase específica por motor")
