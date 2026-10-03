"""Tests para mejoras de Phase 3 del tech debt (resumen compartido y excepciones específicas)."""

from __future__ import annotations

from util_bbdd.doc.infrastructure.renderers.shared.generator_shared import GeneratorInventoryRuntime


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
