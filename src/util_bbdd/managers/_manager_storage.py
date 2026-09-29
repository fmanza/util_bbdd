"""Estrategias internas para inventario de almacenamiento por motor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..metadata.adapters import StorageInventoryAdapterAsync, StorageInventoryAdapterSync


class SyncStorageInventoryManagerProtocol(Protocol):
    """Contrato mínimo sync requerido por las estrategias."""

    def execute_query_many(self, query_name: str, **params: Any) -> Any: ...

    def _get_metadata_adapter(self) -> StorageInventoryAdapterSync: ...


class AsyncStorageInventoryManagerProtocol(Protocol):
    """Contrato mínimo async requerido por las estrategias."""

    async def execute_query_many(self, query_name: str, **params: Any) -> Any: ...

    def _get_metadata_adapter(self) -> StorageInventoryAdapterAsync: ...


class SyncStorageInventoryStrategy(Protocol):
    """Contrato de estrategia sync para inventario de almacenamiento."""

    def execute(
        self,
        manager: SyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]: ...


class AsyncStorageInventoryStrategy(Protocol):
    """Contrato de estrategia async para inventario de almacenamiento."""

    async def execute(
        self,
        manager: AsyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]: ...


def _require_tablespace(db_label: str, tablespace: str | None) -> str:
    """Valida que exista tablespace para motores que lo requieren."""
    if not tablespace:
        raise ValueError(f"Para {db_label} debe proporcionar 'tablespace'")
    return tablespace


@dataclass(frozen=True, slots=True)
class _SyncSqlServerStorageStrategy:
    def execute(
        self,
        manager: SyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del context_database, tablespace
        return {
            "primary": manager.execute_query_many("ficheros_fisicos"),
            "temp_tablespaces": manager.execute_query_many("temp_tablespaces"),
        }


@dataclass(frozen=True, slots=True)
class _SyncOracleStorageStrategy:
    def execute(
        self,
        manager: SyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del context_database
        resolved_tablespace: str = _require_tablespace("Oracle", tablespace)
        return {
            "primary": manager.execute_query_many("ficheros_fisicos", tablespace=resolved_tablespace),
            "temp_tablespaces": manager.execute_query_many("temp_tablespaces", tablespace=resolved_tablespace),
        }


@dataclass(frozen=True, slots=True)
class _SyncMariaDBStorageStrategy:
    def execute(
        self,
        manager: SyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del tablespace
        return manager._get_metadata_adapter().storage_inventory(context_database)


@dataclass(frozen=True, slots=True)
class _SyncPostgreSQLStorageStrategy:
    def execute(
        self,
        manager: SyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del context_database
        resolved_tablespace: str = _require_tablespace("PostgreSQL", tablespace)
        return {
            "primary": manager.execute_query_many("ficheros_fisicos", tablespace=resolved_tablespace),
            "temp_tablespaces": manager.execute_query_many("temp_tablespaces"),
        }


@dataclass(frozen=True, slots=True)
class _SyncSQLiteStorageStrategy:
    def execute(
        self,
        manager: SyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del context_database, tablespace
        return {
            "primary": manager.execute_query_many("ficheros_fisicos"),
            "sqlite_file_summary": manager.execute_query_many("sqlite_file_summary"),
            "temp_tablespaces": manager.execute_query_many("temp_tablespaces"),
        }


@dataclass(frozen=True, slots=True)
class _SyncHSQLDBStorageStrategy:
    def execute(
        self,
        manager: SyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del manager, context_database, tablespace
        return {"primary": []}


@dataclass(frozen=True, slots=True)
class _AsyncSqlServerStorageStrategy:
    async def execute(
        self,
        manager: AsyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del context_database, tablespace
        return {
            "primary": await manager.execute_query_many("ficheros_fisicos"),
            "temp_tablespaces": await manager.execute_query_many("temp_tablespaces"),
        }


@dataclass(frozen=True, slots=True)
class _AsyncOracleStorageStrategy:
    async def execute(
        self,
        manager: AsyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del context_database
        resolved_tablespace: str = _require_tablespace("Oracle", tablespace)
        return {
            "primary": await manager.execute_query_many("ficheros_fisicos", tablespace=resolved_tablespace),
            "temp_tablespaces": await manager.execute_query_many("temp_tablespaces", tablespace=resolved_tablespace),
        }


@dataclass(frozen=True, slots=True)
class _AsyncMariaDBStorageStrategy:
    async def execute(
        self,
        manager: AsyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del tablespace
        return await manager._get_metadata_adapter().storage_inventory(context_database)


@dataclass(frozen=True, slots=True)
class _AsyncPostgreSQLStorageStrategy:
    async def execute(
        self,
        manager: AsyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del context_database
        resolved_tablespace: str = _require_tablespace("PostgreSQL", tablespace)
        return {
            "primary": await manager.execute_query_many("ficheros_fisicos", tablespace=resolved_tablespace),
            "temp_tablespaces": await manager.execute_query_many("temp_tablespaces"),
        }


@dataclass(frozen=True, slots=True)
class _AsyncSQLiteStorageStrategy:
    async def execute(
        self,
        manager: AsyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del context_database, tablespace
        return {
            "primary": await manager.execute_query_many("ficheros_fisicos"),
            "sqlite_file_summary": await manager.execute_query_many("sqlite_file_summary"),
            "temp_tablespaces": await manager.execute_query_many("temp_tablespaces"),
        }


@dataclass(frozen=True, slots=True)
class _AsyncHSQLDBStorageStrategy:
    """HSQLDB: sin inventario de almacenamiento (no hace I/O)."""

    async def execute(
        self,
        manager: AsyncStorageInventoryManagerProtocol,
        context_database: str,
        tablespace: str | None,
    ) -> dict[str, Any]:
        del manager, context_database, tablespace
        return {"primary": []}


_SYNC_STORAGE_STRATEGY_REGISTRY: dict[str, SyncStorageInventoryStrategy] = {
    "sqlserver": _SyncSqlServerStorageStrategy(),
    "oracle": _SyncOracleStorageStrategy(),
    "mariadb": _SyncMariaDBStorageStrategy(),
    "postgresql": _SyncPostgreSQLStorageStrategy(),
    "sqlite": _SyncSQLiteStorageStrategy(),
    "hsqldb": _SyncHSQLDBStorageStrategy(),
}

_ASYNC_STORAGE_STRATEGY_REGISTRY: dict[str, AsyncStorageInventoryStrategy] = {
    "sqlserver": _AsyncSqlServerStorageStrategy(),
    "oracle": _AsyncOracleStorageStrategy(),
    "mariadb": _AsyncMariaDBStorageStrategy(),
    "postgresql": _AsyncPostgreSQLStorageStrategy(),
    "sqlite": _AsyncSQLiteStorageStrategy(),
    "hsqldb": _AsyncHSQLDBStorageStrategy(),
}


def get_sync_storage_inventory_strategy(db_type: str) -> SyncStorageInventoryStrategy:
    """Devuelve estrategia sync de inventario para el motor."""
    normalized_db_type: str = str(db_type or "").lower().strip()
    return _SYNC_STORAGE_STRATEGY_REGISTRY[normalized_db_type]


def get_async_storage_inventory_strategy(db_type: str) -> AsyncStorageInventoryStrategy:
    """Devuelve estrategia async de inventario para el motor."""
    normalized_db_type: str = str(db_type or "").lower().strip()
    return _ASYNC_STORAGE_STRATEGY_REGISTRY[normalized_db_type]


__all__: list[str] = [
    "AsyncStorageInventoryManagerProtocol",
    "AsyncStorageInventoryStrategy",
    "SyncStorageInventoryManagerProtocol",
    "SyncStorageInventoryStrategy",
    "get_async_storage_inventory_strategy",
    "get_sync_storage_inventory_strategy",
]
