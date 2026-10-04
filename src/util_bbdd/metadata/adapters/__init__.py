"""Adaptadores multi-driver para introspección de metadatos.

Proporciona Protocols genéricos (Sync/Async) y clases base reutilizables
para implementaciones por motor (MariaDB, PostgreSQL, SQLite, etc.).

Responsabilidad: definir contratos agnósticos del motor y lógica compartida.
Sin SQL específico; diferencias entre drivers encapsuladas en adaptadores concretos.
"""

from __future__ import annotations

from ._adapter_protocol import (
    EngineMetadataAdapterAsync,
    EngineMetadataAdapterSync,
    RoutineAdapterAsync,
    RoutineAdapterSync,
    SourceAdapterAsync,
    SourceAdapterSync,
)
from ._adapter_registry import (
    AdapterRegistry,
    get_global_adapter_registry,
)

__all__: list[str] = [
    # Protocols (Sync)
    "SourceAdapterSync",
    "RoutineAdapterSync",
    # Protocols (Async)
    "SourceAdapterAsync",
    "RoutineAdapterAsync",
    # Protocols de lecturas especializadas por motor (managers)
    "EngineMetadataAdapterSync",
    "EngineMetadataAdapterAsync",
    # Registry
    "AdapterRegistry",
    "get_global_adapter_registry",
]
