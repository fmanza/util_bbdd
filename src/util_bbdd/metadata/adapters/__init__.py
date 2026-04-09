"""Adaptadores multi-driver para introspección de metadatos.

Proporciona Protocols genéricos (SourceAdapter, RoutineAdapter) y clases base
reutilizables para implementaciones por motor (MariaDB, PostgreSQL, SQLite, etc.).

Responsabilidad: definir contratos agnósticos del motor y lógica compartida.
Sin SQL específico; diferencias entre drivers encapsuladas en adaptadores concretos.

Uso en futuro:
- metadata/mariadb/sync_adapter.py → implementa SourceAdapter + RoutineAdapter
- metadata/postgresql/sync_adapter.py → implementa SourceAdapter + RoutineAdapter
- metadata/sqlite/sync_adapter.py → implementa SourceAdapter + RoutineAdapter
"""

from __future__ import annotations

from ._adapter_protocol import (
    RoutineAdapter,
    SourceAdapter,
)
from ._adapter_registry import (
    AdapterRegistry,
    get_global_adapter_registry,
)
from ._helpers import (
    extract_constraint_from_ddl,
    normalize_column_type,
    normalize_routine_type,
)

__all__: list[str] = [
    # Protocols (Sync)
    "SourceAdapterSync",
    "RoutineAdapterSync",
    # Protocols (Async)
    "SourceAdapterAsync",
    "RoutineAdapterAsync",
    # Backwards compatibility
    "SourceAdapter",
    "RoutineAdapter",
    # Registry
    "AdapterRegistry",
    "get_global_adapter_registry",
    # Helpers
    "normalize_column_type",
    "normalize_routine_type",
    "extract_constraint_from_ddl",
]
