"""Tests para mejoras de Phase 3 del tech debt (resumen compartido y excepciones específicas)."""

from __future__ import annotations

from typing import cast

import pytest

from util_bbdd import DatabaseOperationError
from util_bbdd.analysis.base import DatabaseRelationshipGraphBase
from util_bbdd.doc.infrastructure.renderers.shared.generator_shared import GeneratorInventoryRuntime
from util_bbdd.managers import SyncDatabaseManager


def test_inventory_runtime_build_summary_rows_preserves_order() -> None:
    rows = GeneratorInventoryRuntime.build_summary_rows(
        tables_count=3,
        views_count=2,
        routines_count=4,
        procedures_count=1,
        functions_count=3,
        storage_count=7,
        include_routines=True,
    )

    assert rows == [
        ("Tablas", 3),
        ("Vistas", 2),
        ("Rutinas", 4),
        ("Procedures", 1),
        ("Funciones", 3),
        ("Almacenamiento", 7),
    ]


def test_inventory_runtime_build_summary_rows_can_skip_routines() -> None:
    rows = GeneratorInventoryRuntime.build_summary_rows(
        tables_count=1,
        views_count=0,
        routines_count=99,
        procedures_count=2,
        functions_count=5,
        storage_count=0,
        include_routines=False,
    )

    assert rows == [
        ("Tablas", 1),
        ("Vistas", 0),
        ("Procedures", 2),
        ("Funciones", 5),
        ("Almacenamiento", 0),
    ]


class _DatabaseErrorManager:
    def get_columns(self, table_name: str) -> list[tuple[str, str]]:
        raise DatabaseOperationError("columns error")

    def get_primary_keys(self, table_name: str) -> list[tuple[str]]:
        raise DatabaseOperationError("pk error")


def test_analysis_base_catches_only_database_error_for_metadata_helpers() -> None:
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, _DatabaseErrorManager()))

    assert graph._get_table_column_names("users") == []
    assert graph._get_primary_key_column_names("users") == []


class _RuntimeErrorManager:
    def get_columns(self, table_name: str) -> list[tuple[str, str]]:
        raise RuntimeError("unexpected columns")

    def get_primary_keys(self, table_name: str) -> list[tuple[str]]:
        raise RuntimeError("unexpected pk")


def test_analysis_base_does_not_swallow_non_database_errors_in_metadata_helpers() -> None:
    graph = DatabaseRelationshipGraphBase(cast(SyncDatabaseManager, _RuntimeErrorManager()))

    with pytest.raises(RuntimeError, match="unexpected columns"):
        graph._get_table_column_names("users")

    with pytest.raises(RuntimeError, match="unexpected pk"):
        graph._get_primary_key_column_names("users")
