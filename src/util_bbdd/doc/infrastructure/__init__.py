"""Adaptadores de infraestructura para documentación."""

from .adapters.sync_database_manager_adapter import SyncDatabaseManagerAdapter
from .renderers.registry import DocumentationRendererRegistry, build_default_renderer_registry
from .runtime.headers_runtime import DocumentationHeadersRuntime
from .runtime.metadata_runtime import DocumentationMetadataRuntime, DocumentationMetadataRuntimeFactory
from .runtime.output_runtime import DocumentationOutputRuntime
from .storage.runtime import StorageInventoryReportService, StorageInventoryRuntime, get_storage_inventory_report

__all__: list[str] = [
    "DocumentationHeadersRuntime",
    "DocumentationMetadataRuntime",
    "DocumentationMetadataRuntimeFactory",
    "DocumentationOutputRuntime",
    "DocumentationRendererRegistry",
    "StorageInventoryReportService",
    "StorageInventoryRuntime",
    "SyncDatabaseManagerAdapter",
    "build_default_renderer_registry",
    "get_storage_inventory_report",
]
