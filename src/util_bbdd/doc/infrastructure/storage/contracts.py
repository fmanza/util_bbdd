"""Tipos compartidos del runtime de inventario de almacenamiento."""

from __future__ import annotations

from typing import Any, Protocol


class ResolvedStorageQueryProtocol(Protocol):
    """Resultado mínimo de una query resuelta por nombre."""

    final_sql: str | None


class StorageInventoryManagerProtocol(Protocol):
    """Contrato mínimo del manager requerido por el runtime de inventario."""

    db_type: str
    database: str
    conn_params: dict[str, Any]

    def resolve_query(self, query_name: str, **params: Any) -> ResolvedStorageQueryProtocol: ...

    def execute_query_many(self, query_name: str, **params: Any) -> Any: ...

    def execute_custom_one(self, query: str) -> Any: ...


class StorageInventoryStrategyPort(Protocol):
    """Contrato de estrategia por motor para inventario de almacenamiento."""

    def get_query_specs(self) -> list[tuple[str, str]]: ...

    def resolve_default_tablespace(self) -> str: ...

    def process_query(
        self,
        *,
        query_name: str,
        query_title: str,
        database_name: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any] | None: ...

    def build_error_section(
        self,
        *,
        query_name: str,
        query_title: str,
        error_msg: str,
    ) -> dict[str, Any] | None: ...
