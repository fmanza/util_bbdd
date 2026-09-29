"""A8 (fix 2026-09-29): nombres que solo difieren en mayúsculas, con severidad según el destino.

Verificado en el banco (``.ai/sessions/2026-09-29d-migrate-audit/a8_case_collision.py``): columnas ``"Nombre"`` y
``nombre`` de PostgreSQL → ORA-00957 (Oracle), 1060 (MySQL/MariaDB), 2705 (SQL Server); tablas ``"ZZAUD_T"`` y
``zzaud_t`` → ORA-00955 (Oracle), 2714 (SQL Server). El plan no tenía errores y el aviso de tablas afirmaba que el DDL
no colisionaba.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate import MigrationPlan
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable, CanonicalView
from util_bbdd.migrate.planner import _case_collision_warnings


def _table(name: str, *columns: str) -> CanonicalTable:
    cols = [
        CanonicalColumn(
            name=c,
            original_name=c,
            oracle_type="VARCHAR",
            target_type="VARCHAR(20)",
            nullable=True,
            default=None,
            comment="",
            ordinal=n,
        )
        for n, c in enumerate(columns or ("id",), start=1)
    ]
    return CanonicalTable(name, name, "s", cols, [], [], [], "", [])


def _severities(target: str, tables: list[CanonicalTable], views: list[CanonicalView] | None = None) -> list[str]:
    return [w.severity for w in _case_collision_warnings(target, tables, views or [])]


class TestColumns:
    @pytest.mark.parametrize(
        ("target", "expected"),
        [
            ("oracle", ["ERROR"]),
            ("mariadb", ["ERROR"]),
            ("mysql", ["ERROR"]),
            ("sqlserver", ["WARNING"]),
            ("postgresql", []),
        ],
    )
    def test_severity_by_target(self, target: str, expected: list[str]) -> None:
        assert _severities(target, [_table("t", "id", "Nombre", "nombre")]) == expected

    def test_warning_names_table_and_columns(self) -> None:
        [warning] = _case_collision_warnings("oracle", [_table("clientes", "Nombre", "nombre")], [])
        assert warning.table == "clientes" and {warning.column, warning.target_type} == {"Nombre", "nombre"}
        assert "CREATE TABLE falla" in warning.message

    def test_omitted_columns_do_not_count(self) -> None:
        table = _table("t", "Nombre", "nombre")
        table.columns[1].omit = True
        assert _severities("oracle", [table]) == []

    def test_distinct_columns_are_fine(self) -> None:
        assert _severities("oracle", [_table("t", "id", "nombre", "apellido")]) == []


class TestTablesAndViews:
    @pytest.mark.parametrize(
        ("target", "expected"),
        [("oracle", ["ERROR"]), ("sqlserver", ["WARNING"]), ("mariadb", ["WARNING"]), ("postgresql", ["WARNING"])],
    )
    def test_severity_by_target(self, target: str, expected: list[str]) -> None:
        assert _severities(target, [_table("ZZ_T"), _table("zz_t")]) == expected

    def test_view_colliding_with_table(self) -> None:
        view = CanonicalView("Clientes", "Clientes", "s", "SELECT 1", [], "", [])
        [warning] = _case_collision_warnings("oracle", [_table("CLIENTES")], [view])
        assert warning.severity == "ERROR" and "mismo nombre" in warning.message

    def test_postgresql_message_keeps_the_quoted_ddl_explanation(self) -> None:
        [warning] = _case_collision_warnings("postgresql", [_table("T"), _table("t")], [])
        assert "no colisiona" in warning.message


def test_execute_is_blocked_before_touching_the_target() -> None:
    warnings = _case_collision_warnings("oracle", [_table("t", "Nombre", "nombre")], [])
    plan = MigrationPlan(
        tables=[],
        warnings=warnings,
        source_schema="s",
        source_engine="postgresql",
        target_engine="oracle",
        emitter=MagicMock(),
    )
    target = MagicMock()
    with pytest.raises(ValueError, match="ERROR"):
        plan.execute(target)
    target.get_sqlalchemy_engine.assert_not_called()
