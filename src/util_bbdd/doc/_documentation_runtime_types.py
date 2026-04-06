"""Tipos y contratos internos para el runtime documental."""

from __future__ import annotations

from typing import Any, Protocol

HeadersConfig = dict[str, Any]
ConnectionParams = dict[str, Any]
OutputCache = dict[tuple[str, str], tuple[float, str]]


class LoggerProtocol(Protocol):
    """Contrato mínimo de logger usado por helpers documentales."""

    def info(self, msg: str, *args: Any, **kwargs: Any) -> Any: ...

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> Any: ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> Any: ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> Any: ...


class DocumentationOutputManagerProtocol(Protocol):
    """Contrato mínimo para resolver nombres de salida documentales."""

    db_type: str
    database: str
    conn_params: ConnectionParams


class MetadataVersionManagerProtocol(Protocol):
    """Contrato de versión de base de datos para metadata opcional."""

    def get_database_version(self) -> Any: ...


class MetadataCharsetManagerProtocol(Protocol):
    """Contrato de charset/collation de base de datos para metadata opcional."""

    def get_database_charset_collation(self) -> Any: ...


class MetadataColumnsCharsetManagerProtocol(Protocol):
    """Contrato de charset/collation por columna para metadata opcional."""

    def get_columns_charset_collation(self, table_name: str, /) -> Any: ...


class DocumentationRuntimeManagerProtocol(
    DocumentationOutputManagerProtocol,
    MetadataVersionManagerProtocol,
    MetadataCharsetManagerProtocol,
    MetadataColumnsCharsetManagerProtocol,
    Protocol,
):
    """Contrato interno consolidado del manager consumido por el runtime documental."""

    def get_query_context_database(self) -> str: ...

    def get_tables(self) -> list[Any]: ...

    def get_views(self) -> list[Any]: ...

    def get_routines(self) -> list[Any]: ...

    def get_ddl(self, table_name: str, /) -> str: ...

    def get_view_ddl(self, view_name: str, /) -> str: ...

    def get_columns(self, table_name: str, /) -> list[Any]: ...

    def get_routine_ddl(self, routine_name: str, routine_type: str, /) -> str: ...

    def get_routine_parameters(self, routine_name: str, routine_type: str, /) -> list[Any]: ...

    def get_primary_keys(self, table_name: str, /) -> list[Any]: ...

    def get_foreign_keys(self, table_name: str, /) -> list[Any]: ...

    def get_unique_constraints(self, table_name: str, /) -> list[Any]: ...

    def get_indices(self, table_name: str, /) -> list[Any]: ...
