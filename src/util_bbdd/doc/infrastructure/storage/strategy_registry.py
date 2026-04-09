"""Registro OCP de estrategias de inventario de almacenamiento."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .contracts import StorageInventoryStrategyPort

_ResolveTablespaceFn = Callable[[], str]
_ProcessQueryFn = Callable[[str, str, str, dict[str, Any]], dict[str, Any]]
_BuildErrorFn = Callable[[str, str, str], dict[str, Any]]


@dataclass(slots=True)
class StorageInventoryEngineStrategy(StorageInventoryStrategyPort):
    """Estrategia parametrizable por motor para runtime de almacenamiento."""

    query_specs: tuple[tuple[str, str], ...]
    resolve_default_tablespace_fn: _ResolveTablespaceFn
    query_processors: dict[str, _ProcessQueryFn] = field(default_factory=dict)
    error_processors: dict[str, _BuildErrorFn] = field(default_factory=dict)

    def get_query_specs(self) -> list[tuple[str, str]]:
        return list(self.query_specs)

    def resolve_default_tablespace(self) -> str:
        return self.resolve_default_tablespace_fn()

    def process_query(
        self,
        *,
        query_name: str,
        query_title: str,
        database_name: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any] | None:
        processor = self.query_processors.get(query_name)
        if processor is None:
            return None
        return processor(query_name, query_title, database_name, query_params)

    def build_error_section(
        self,
        *,
        query_name: str,
        query_title: str,
        error_msg: str,
    ) -> dict[str, Any] | None:
        processor = self.error_processors.get(query_name)
        if processor is None:
            return None
        return processor(query_name, query_title, error_msg)
