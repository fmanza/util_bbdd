"""Registry centralizado para resolución de adapters por driver (Patrón Registry).

Este módulo implementa el patrón Registry para:
- Registrar adapters por driver (MariaDB, PostgreSQL, Oracle, etc.)
- Resolver adapters dinámicamente sin hardcoding
- Soportar múltiples drivers sin modificar managers
- Validar conformidad de adapteras con Protocols
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

__all__ = [
    "SourceAdapterSync",
    "SourceAdapterAsync",
    "RoutineAdapterSync",
    "RoutineAdapterAsync",
    "AdapterRegistry",
]


# Type aliases para constructores (callables que retornan adapters)
SourceAdapterSync = TypeVar("SourceAdapterSync")
SourceAdapterAsync = TypeVar("SourceAdapterAsync")
RoutineAdapterSync = TypeVar("RoutineAdapterSync")
RoutineAdapterAsync = TypeVar("RoutineAdapterAsync")


class AdapterRegistry:
    """Registry centralizado para resolución de adapters por driver.

    Responsabilidades:
    - Registrar adapters sync/async para cada driver
    - Resolver adapters sin hardcoding
    - Validar que adapters implementen Protocols requeridos

    Patrón: Registry (GoF)
    Propósito: Desacoplar managers de drivers específicos
    """

    def __init__(self) -> None:
        """Inicializa registry vacío."""
        self._source_adapters_sync: dict[str, Callable[..., Any]] = {}
        self._source_adapters_async: dict[str, Callable[..., Any]] = {}
        self._routine_adapters_sync: dict[str, Callable[..., Any]] = {}
        self._routine_adapters_async: dict[str, Callable[..., Any]] = {}

    def register_source_adapter_sync(
        self,
        db_type: str,
        adapter_class: Callable[..., Any],
    ) -> None:
        """Registra adapter sync de source para un driver.

        Args:
            db_type: Tipo de base de datos (ej: "mariadb", "postgresql")
            adapter_class: Clase del adapter (constructor)

        Raises:
            ValueError: Si db_type está vacío o ya existe
        """
        normalized_db_type = self._normalize_db_type(db_type)
        if normalized_db_type in self._source_adapters_sync:
            msg = f"SourceAdapterSync ya registrado para {db_type}"
            raise ValueError(msg)
        self._source_adapters_sync[normalized_db_type] = adapter_class

    def register_source_adapter_async(
        self,
        db_type: str,
        adapter_class: Callable[..., Any],
    ) -> None:
        """Registra adapter async de source para un driver.

        Args:
            db_type: Tipo de base de datos
            adapter_class: Clase del adapter

        Raises:
            ValueError: Si db_type está vacío o ya existe
        """
        normalized_db_type = self._normalize_db_type(db_type)
        if normalized_db_type in self._source_adapters_async:
            msg = f"SourceAdapterAsync ya registrado para {db_type}"
            raise ValueError(msg)
        self._source_adapters_async[normalized_db_type] = adapter_class

    def register_routine_adapter_sync(
        self,
        db_type: str,
        adapter_class: Callable[..., Any],
    ) -> None:
        """Registra adapter sync de routines para un driver.

        Args:
            db_type: Tipo de base de datos
            adapter_class: Clase del adapter

        Raises:
            ValueError: Si db_type está vacío o ya existe
        """
        normalized_db_type = self._normalize_db_type(db_type)
        if normalized_db_type in self._routine_adapters_sync:
            msg = f"RoutineAdapterSync ya registrado para {db_type}"
            raise ValueError(msg)
        self._routine_adapters_sync[normalized_db_type] = adapter_class

    def register_routine_adapter_async(
        self,
        db_type: str,
        adapter_class: Callable[..., Any],
    ) -> None:
        """Registra adapter async de routines para un driver.

        Args:
            db_type: Tipo de base de datos
            adapter_class: Clase del adapter

        Raises:
            ValueError: Si db_type está vacío o ya existe
        """
        normalized_db_type = self._normalize_db_type(db_type)
        if normalized_db_type in self._routine_adapters_async:
            msg = f"RoutineAdapterAsync ya registrado para {db_type}"
            raise ValueError(msg)
        self._routine_adapters_async[normalized_db_type] = adapter_class

    def get_source_adapter_sync(self, db_type: str) -> Callable[..., Any] | None:
        """Resuelve adapter sync de source para un driver.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Clase del adapter (constructor) o None si no existe
        """
        normalized_db_type = self._normalize_db_type(db_type)
        return self._source_adapters_sync.get(normalized_db_type)

    def get_source_adapter_async(self, db_type: str) -> Callable[..., Any] | None:
        """Resuelve adapter async de source para un driver.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Clase del adapter (constructor) o None si no existe
        """
        normalized_db_type = self._normalize_db_type(db_type)
        return self._source_adapters_async.get(normalized_db_type)

    def get_routine_adapter_sync(self, db_type: str) -> Callable[..., Any] | None:
        """Resuelve adapter sync de routines para un driver.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Clase del adapter (constructor) o None si no existe
        """
        normalized_db_type = self._normalize_db_type(db_type)
        return self._routine_adapters_sync.get(normalized_db_type)

    def get_routine_adapter_async(self, db_type: str) -> Callable[..., Any] | None:
        """Resuelve adapter async de routines para un driver.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Clase del adapter (constructor) o None si no existe
        """
        normalized_db_type = self._normalize_db_type(db_type)
        return self._routine_adapters_async.get(normalized_db_type)

    def is_driver_registered(self, db_type: str) -> bool:
        """Indica si el driver tiene al menos un adapter registrado.

        Args:
            db_type: Tipo de base de datos

        Returns:
            True si adapter sync o async está registrado
        """
        normalized_db_type = self._normalize_db_type(db_type)
        return bool(
            self._source_adapters_sync.get(normalized_db_type)
            or self._source_adapters_async.get(normalized_db_type)
            or self._routine_adapters_sync.get(normalized_db_type)
            or self._routine_adapters_async.get(normalized_db_type)
        )

    @staticmethod
    def _normalize_db_type(db_type: str) -> str:
        """Normaliza tipo de DB para búsqueda en registry."""
        return str(db_type or "").lower().strip()

    def list_registered_drivers(self) -> set[str]:
        """Retorna conjunto de drivers con adapters registrados."""
        drivers: set[str] = set()
        drivers.update(self._source_adapters_sync.keys())
        drivers.update(self._source_adapters_async.keys())
        drivers.update(self._routine_adapters_sync.keys())
        drivers.update(self._routine_adapters_async.keys())
        return drivers

    def list_adapters_for_driver(self, db_type: str) -> dict[str, Callable[..., Any] | None]:
        """Retorna todos los adapters registrados para un driver.

        Args:
            db_type: Tipo de base de datos

        Returns:
            Dict con keys: source_sync, source_async, routine_sync, routine_async
            Los valores pueden ser None si el adapter no está registrado.
        """
        normalized_db_type = self._normalize_db_type(db_type)
        return {
            "source_sync": self._source_adapters_sync.get(normalized_db_type),
            "source_async": self._source_adapters_async.get(normalized_db_type),
            "routine_sync": self._routine_adapters_sync.get(normalized_db_type),
            "routine_async": self._routine_adapters_async.get(normalized_db_type),
        }


# Instancia global del registry
_global_adapter_registry = AdapterRegistry()


def get_global_adapter_registry() -> AdapterRegistry:
    """Obtiene instancia global del registry de adapters."""
    return _global_adapter_registry
