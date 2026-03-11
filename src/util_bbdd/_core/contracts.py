"""Protocols e interfaces comunes para util_bbdd.

Define contratos que deben cumplir diferentes componentes
para garantizar compatibilidad y extensibilidad.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConnectionProvider(Protocol):
    """Protocol para proveedor de conexiones."""

    def get_connection(self) -> Any:
        """Obtiene una conexión a la base de datos.

        Returns:
            Conexión disponible

        Raises:
            ConnectionError: Si no hay conexiones disponibles
            TimeoutError: Si timeout esperando conexión
        """
        ...


@runtime_checkable
class ConnectionReleaser(Protocol):
    """Protocol para liberador de conexiones."""

    def close_connection(self, connection: Any) -> None:
        """Libera/devuelve una conexión.

        Args:
            connection: Conexión a liberar
        """
        ...


@runtime_checkable
class QueryExecutor(Protocol):
    """Protocol para ejecutor de queries."""

    def execute_query_one(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> tuple[Any, ...] | None:
        """Ejecuta una query registrada que retorna una fila.

        Args:
            query_name: Nombre de la query registrada
            db_type: Tipo de base de datos
            params: Parámetros de la query
            timeout: Timeout en segundos

        Returns:
            Tupla con fila o None si sin resultados

        Raises:
            QueryError: Si hay error ejecutando
        """
        ...

    def execute_query_many(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any],
        timeout: float | None = None,
    ) -> list[tuple[Any, ...]]:
        """Ejecuta una query registrada que retorna múltiples filas.

        Args:
            query_name: Nombre de la query registrada
            db_type: Tipo de base de datos
            params: Parámetros de la query
            timeout: Timeout en segundos

        Returns:
            Lista de tuplas con filas

        Raises:
            QueryError: Si hay error ejecutando
        """
        ...


@runtime_checkable
class PoolConnection(Protocol):
    """Protocol para pool de conexiones."""

    def get_connection(self) -> Any:
        """Obtiene conexión del pool."""
        ...

    def close_connection(self, connection: Any) -> None:
        """Devuelve conexión al pool."""
        ...

    def close(self, timeout_seconds: float | None = None, force: bool = False) -> None:
        """Cierra el pool."""
        ...


@runtime_checkable
class DatabaseValidator(Protocol):
    """Protocol para validador de tipo de base de datos."""

    def validate_db_type(self, db_type: str) -> None:
        """Valida que tipo de BD sea soportado.

        Args:
            db_type: Tipo de BD a validar

        Raises:
            ValidationError: Si tipo no es válido
        """
        ...

    def get_supported_types(self) -> list[str]:
        """Obtiene lista de tipos soportados.

        Returns:
            Lista de tipos BD válidos
        """
        ...


@runtime_checkable
class MetadataFetcher(Protocol):
    """Protocol para obtención de metadatos."""

    def get_tables(self) -> list[tuple[Any, ...]]:
        """Obtiene lista de tablas."""
        ...

    def get_columns(self, table: str) -> list[tuple[Any, ...]]:
        """Obtiene columnas de una tabla."""
        ...

    def get_primary_keys(self, table: str) -> list[tuple[Any, ...]]:
        """Obtiene claves primarias de una tabla."""
        ...


__all__ = [
    "ConnectionProvider",
    "ConnectionReleaser",
    "QueryExecutor",
    "PoolConnection",
    "DatabaseValidator",
    "MetadataFetcher",
]
