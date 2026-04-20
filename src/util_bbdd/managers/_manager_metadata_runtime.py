"""Helpers internos para metadata read-side compartida de managers.

Fase 3: Runtime Metadata — strategies de fetching por motor.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from ._metadata_parser import CharsetCollationParser, ColumnCharsetCollationRow, DDLNormalizer
from ._metadata_request import MetadataFetchRequest, MetadataRequestBuilder

_T = TypeVar("_T")


# Estrategias de fetching: Protocols y implementaciones por motor
class MetadataFetchStrategy(Protocol):
    """Contrato para construir fetchers sync/async por motor."""

    def build_sync_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], _T],
        execute_many: Callable[[MetadataFetchRequest], _T],
    ) -> Callable[[], _T]: ...

    def build_sync_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], str],
        execute_one: Callable[[MetadataFetchRequest], Any],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], str]: ...

    def build_async_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[_T]],
        execute_many: Callable[[MetadataFetchRequest], Awaitable[_T]],
    ) -> Callable[[], Awaitable[_T]]: ...

    def build_async_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[str]],
        execute_one: Callable[[MetadataFetchRequest], Awaitable[Any]],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], Awaitable[str]]: ...


@dataclass(frozen=True)
class GenericMetadataFetchStrategy:
    """Estrategia por defecto para motores SQL estándar."""

    def build_sync_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], _T],
        execute_many: Callable[[MetadataFetchRequest], _T],
    ) -> Callable[[], _T]:
        del specialized_fetcher
        return lambda: execute_many(request)

    def build_sync_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], str],
        execute_one: Callable[[MetadataFetchRequest], Any],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], str]:
        del specialized_fetcher
        return lambda: normalize_one(execute_one(request))

    def build_async_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[_T]],
        execute_many: Callable[[MetadataFetchRequest], Awaitable[_T]],
    ) -> Callable[[], Awaitable[_T]]:
        del specialized_fetcher

        async def _fetch_many() -> _T:
            return await execute_many(request)

        return _fetch_many

    def build_async_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[str]],
        execute_one: Callable[[MetadataFetchRequest], Awaitable[Any]],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], Awaitable[str]]:
        del specialized_fetcher

        async def _fetch_one_normalized() -> str:
            return normalize_one(await execute_one(request))

        return _fetch_one_normalized


@dataclass(frozen=True)
class MariaDBMetadataFetchStrategy:
    """Estrategia especializada para MariaDB (ignora execute_many/execute_one).

    MariaDB usa stored procedures especializadas para metadata, por lo que
    sync y async implementan el mismo comportamiento: retornar specialized_fetcher
    sin invocar execute_many/execute_one.
    """

    @staticmethod
    def _return_specialized_fetcher_rows(
        specialized_fetcher: Callable,
        **_: Any,
    ) -> Callable:
        """Template method: retorna specialized_fetcher (ignora execute_many, etc).

        Usado por build_sync_rows_fetcher y build_async_rows_fetcher.
        """
        return specialized_fetcher

    @staticmethod
    def _return_specialized_fetcher_text(
        specialized_fetcher: Callable[[], str | Awaitable[str]],
        **_: Any,
    ) -> Callable:
        """Template method: retorna specialized_fetcher (ignora execute_one, etc).

        Usado por build_sync_text_fetcher y build_async_text_fetcher.
        """
        return specialized_fetcher

    def build_sync_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], _T],
        execute_many: Callable[[MetadataFetchRequest], _T],
    ) -> Callable[[], _T]:
        return self._return_specialized_fetcher_rows(specialized_fetcher, request=request, execute_many=execute_many)

    def build_sync_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], str],
        execute_one: Callable[[MetadataFetchRequest], Any],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], str]:
        return self._return_specialized_fetcher_text(
            specialized_fetcher,
            request=request,
            execute_one=execute_one,
            normalize_one=normalize_one,
        )

    def build_async_rows_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[_T]],
        execute_many: Callable[[MetadataFetchRequest], Awaitable[_T]],
    ) -> Callable[[], Awaitable[_T]]:
        """Mismo comportamiento que build_sync_rows_fetcher (delega al template method)."""
        return self._return_specialized_fetcher_rows(specialized_fetcher, request=request, execute_many=execute_many)

    def build_async_text_fetcher(
        self,
        *,
        request: MetadataFetchRequest,
        specialized_fetcher: Callable[[], Awaitable[str]],
        execute_one: Callable[[MetadataFetchRequest], Awaitable[Any]],
        normalize_one: Callable[[Any], str],
    ) -> Callable[[], Awaitable[str]]:
        """Mismo comportamiento que build_sync_text_fetcher (delega al template method)."""
        return self._return_specialized_fetcher_text(
            specialized_fetcher,
            request=request,
            execute_one=execute_one,
            normalize_one=normalize_one,
        )


_DEFAULT_METADATA_FETCH_STRATEGY = GenericMetadataFetchStrategy()
_METADATA_FETCH_STRATEGIES: dict[str, MetadataFetchStrategy] = {
    "mariadb": MariaDBMetadataFetchStrategy(),
}


def get_metadata_fetch_strategy(db_type: str) -> MetadataFetchStrategy:
    """Retorna la estrategia de metadata para el motor indicado."""
    normalized_db_type: str = str(db_type or "").lower().strip()
    return _METADATA_FETCH_STRATEGIES.get(normalized_db_type, _DEFAULT_METADATA_FETCH_STRATEGY)


__all__: list[str] = [
    "MetadataFetchRequest",
    "MetadataRequestBuilder",
    "CharsetCollationParser",
    "DDLNormalizer",
    "ColumnCharsetCollationRow",
    "MetadataFetchStrategy",
    "GenericMetadataFetchStrategy",
    "MariaDBMetadataFetchStrategy",
    "get_metadata_fetch_strategy",
]
