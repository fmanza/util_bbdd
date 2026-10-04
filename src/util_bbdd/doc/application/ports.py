"""Puertos internos para la arquitectura por capas de documentación."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any, Protocol

from ..._core.types import Rows
from ...metadata.model import ALL_KINDS, Kind, SchemaSnapshot

HeadersConfig = dict[str, Any]
ConnectionParams = dict[str, Any]
OutputCache = dict[tuple[str, str], tuple[float, str]]


class LoggerProtocol(Protocol):
    """Contrato mínimo de logger usado por helpers documentales."""

    def info(self, msg: str, *args: Any, **kwargs: Any) -> Any: ...

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> Any: ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> Any: ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> Any: ...


class OutputNamingContextPort(Protocol):
    """Contexto mínimo del manager para naming/rutas de salida."""

    @property
    def db_type(self) -> str: ...

    @property
    def database(self) -> str: ...

    @property
    def conn_params(self) -> ConnectionParams: ...


class OutputPolicyPort(Protocol):
    """Política de formatos y rutas de salida."""

    def normalize_output_formats(self, formatos: list[str] | None) -> list[str]: ...

    def resolve_document_output_filename(
        self,
        *,
        fichero_salida: Path | None,
        db_manager: OutputNamingContextPort,
        output_dir: Path,
        output_cache: OutputCache,
        batch_window_seconds: int,
    ) -> Path: ...

    def get_format_output_dir(self, directorio_salida: Path, fichero_salida: Path, formato: str) -> Path: ...

    def get_output_base_filename(self, fichero_salida: Path) -> str: ...

    def resolve_generator_database_context(
        self,
        *,
        db_type: str,
        database: str,
        conn_params: ConnectionParams,
        query_context_database: str,
    ) -> str: ...


class MetadataReaderPort(Protocol):
    """Lectura opcional de metadata de base de datos."""

    def get_database_version(self) -> Any: ...

    def get_database_charset_collation(self) -> Any: ...

    def get_columns_charset_collation(self, table_name: str, /) -> Any: ...


class StorageInventoryPort(Protocol):
    """Lectura de inventario de almacenamiento ya normalizado."""

    def get_storage_inventory_report(self) -> dict[str, Any]: ...


class DocumentationCatalogPort(Protocol):
    """Lectura del catálogo del origen: contexto, metadatos por lotes (ADR-003) y DDL de tabla."""

    def get_query_context_database(self) -> str: ...

    def get_schema_metadata(
        self, schema: str | None = None, *, kinds: Collection[Kind] = ALL_KINDS
    ) -> SchemaSnapshot: ...

    def get_ddl(self, table_name: str, /) -> str: ...


class DocumentationIntrospectionPort(DocumentationCatalogPort, Protocol):
    """Lecturas por objeto que consumen los renderers.

    Las sirve ``DocumentationSession`` desde el snapshot del origen, en filas con el formato neutro de
    ``catalog_rows`` (iguales en todos los motores); el origen solo aporta ``DocumentationCatalogPort``.
    """

    def get_tables(self) -> Rows: ...

    def get_views(self) -> Rows: ...

    def get_routines(self) -> Rows: ...

    def get_view_ddl(self, view_name: str, /) -> str: ...

    def get_columns(self, table_name: str, /) -> Rows: ...

    def get_routine_ddl(self, routine_name: str, routine_type: str, /) -> str: ...

    def get_routine_parameters(self, routine_name: str, routine_type: str, /) -> Rows: ...

    def get_primary_keys(self, table_name: str, /) -> Rows: ...

    def get_foreign_keys(self, table_name: str, /) -> Rows: ...

    def get_unique_constraints(self, table_name: str, /) -> Rows: ...

    def get_indices(self, table_name: str, /) -> Rows: ...


class DocumentationQueryPort(Protocol):
    """Consultas de almacenamiento (`metadata.storage`)."""

    def get_storage_rows(self, query_name: str, **params: Any) -> Any: ...


class DocumentationManagerPort(
    OutputNamingContextPort,
    MetadataReaderPort,
    StorageInventoryPort,
    DocumentationIntrospectionPort,
    Protocol,
):
    """Lo que ven los renderers como ``data_provider`` (lo cumple ``DocumentationSession``)."""

    imprimir_config: dict[str, Any]


class DocumentationBackendPort(
    OutputNamingContextPort,
    MetadataReaderPort,
    StorageInventoryPort,
    DocumentationCatalogPort,
    DocumentationQueryPort,
    Protocol,
):
    """Origen de la documentación ya adaptado (``SyncDatabaseManagerAdapter``): lo que la sesión pide al manager."""

    imprimir_config: dict[str, Any]


class DocumentationSourcePort(
    OutputNamingContextPort,
    MetadataReaderPort,
    DocumentationCatalogPort,
    DocumentationQueryPort,
    Protocol,
):
    """Superficie del manager que consume el adaptador documental (``SyncDatabaseManagerAdapter``).

    La cumple estructuralmente ``SyncDatabaseManager``; ``doc/`` depende de este contrato y no del manager (Regla #6).
    """


class DocumentationDataProviderPort(Protocol):
    """Contrato mínimo del proveedor de datos consumido por renderers.

    Nota de diseño: el proveedor *contiene* un ``DocumentationManagerPort``
    como atributo ``db_manager`` pero no hereda de él.  La herencia anterior
    creaba una circularidad (el port era-un manager Y tenía-un manager).
    """

    imprimir_config: dict[str, Any]
    db_manager: DocumentationManagerPort


class DocumentRendererPort(Protocol):
    """Puerto mínimo de un generador de documentación por formato."""

    def generate_document(
        self,
        tables: list[tuple[Any, ...]],
        views: list[tuple[Any, ...]],
        routines: list[tuple[Any, ...]],
        data_provider: DocumentationManagerPort,
        output_target: Path,
        print_config: dict[str, Any] | None = None,
        graph_generator: Any | None = None,
    ) -> None: ...
