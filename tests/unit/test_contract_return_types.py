"""Tests del contrato de retorno y aliases de dominio (PR1)."""

from __future__ import annotations

from typing import get_args, get_origin, get_type_hints

from util_bbdd import (
    DatabaseException,
    QueryExecutionError,
    QueryTimeoutError,
    QueryValidationError,
)
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.managers import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.metadata import AsyncMetadataProvider, SyncMetadataProvider
from util_bbdd.metadata.model import ColumnMeta, TableMeta
from util_bbdd.results import QueryResult, Row, RowOrNone, Rows


def test_result_type_aliases_shape() -> None:
    assert get_origin(Row) is tuple
    assert get_origin(Rows) is list
    assert get_args(Rows)[0] == Row


def test_query_result_alias_shape() -> None:
    args = get_args(QueryResult)
    assert Row in args
    assert type(None) in args
    assert Rows in args


def test_executors_use_query_result_annotation() -> None:
    sync_many_hints = get_type_hints(SyncQueryExecutor.execute_query_many)
    sync_one_hints = get_type_hints(SyncQueryExecutor.execute_query_one)
    async_many_hints = get_type_hints(AsyncQueryExecutor.execute_query_many)
    async_one_hints = get_type_hints(AsyncQueryExecutor.execute_query_one)

    assert sync_many_hints["return"] == Rows
    assert sync_one_hints["return"] == RowOrNone
    assert async_many_hints["return"] == Rows
    assert async_one_hints["return"] == RowOrNone


def test_managers_use_split_contract_annotations() -> None:
    sync_many_hints = get_type_hints(SyncDatabaseManager.execute_query_many)
    sync_one_hints = get_type_hints(SyncDatabaseManager.execute_query_one)
    async_many_hints = get_type_hints(AsyncDatabaseManager.execute_query_many)
    async_one_hints = get_type_hints(AsyncDatabaseManager.execute_query_one)

    assert sync_many_hints["return"] == Rows
    assert sync_one_hints["return"] == RowOrNone
    assert async_many_hints["return"] == Rows
    assert async_one_hints["return"] == RowOrNone


def test_metadata_protocols_return_typed_models() -> None:
    """E2 de ADR-003: los ``get_*`` de metadatos devuelven modelos neutros, no filas."""
    sync_hints = get_type_hints(SyncMetadataProvider.get_tables)
    async_hints = get_type_hints(AsyncMetadataProvider.get_columns)

    assert sync_hints["return"] == list[TableMeta]
    assert async_hints["return"] == list[ColumnMeta]


def test_domain_aliases_map_to_existing_hierarchy() -> None:
    # QueryTimeoutError and QueryValidationError are canonical classes
    assert issubclass(QueryTimeoutError, DatabaseException)
    assert issubclass(QueryValidationError, DatabaseException)

    # QueryExecutionError inherits from QueryError -> DatabaseException
    err = QueryExecutionError("boom")
    assert isinstance(err, DatabaseException)
