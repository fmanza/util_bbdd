"""Tests para MigrationPlanner usando MagicMock (sin BD real)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate import MigrationPlan, MigrationPlanner


def _make_mock_manager(tables: list[tuple] | None = None) -> MagicMock:
    """Crea un mock de SyncDatabaseManager que devuelve datos Oracle simulados."""
    manager = MagicMock()

    # Filas de tablas: (table_name, table_type, table_comment)
    table_rows = tables or [("USERS", "TABLE", "Tabla de usuarios")]

    # Filas de columnas: 9 elementos (name, type, nullable, ordinal, default,
    #                                  data_length, precision, scale, comment)
    col_rows = [
        ("ID", "NUMBER", "NO", 1, None, None, 10, 0, "PK"),
        ("NAME", "VARCHAR2", "YES", 2, None, 100, None, None, "Nombre"),
    ]

    pk_rows = [("PK_USERS", "ID", 1)]
    fk_rows: list = []
    idx_rows: list = []

    def side_effect(sql: str, params: dict) -> list:
        if "all_tables" in sql:
            return table_rows
        if "all_tab_columns" in sql:
            return col_rows
        if "constraint_type = 'P'" in sql:
            return pk_rows
        if "constraint_type = 'R'" in sql:
            return fk_rows
        if "all_indexes" in sql:
            return idx_rows
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


class TestMigrationPlannerInit:
    def test_default_init(self) -> None:
        p = MigrationPlanner()
        assert p._source_engine == "oracle"
        assert p._target_engine == "mariadb"
        assert p._charset == "utf8mb4"

    def test_invalid_source_raises(self) -> None:
        with pytest.raises(ValueError, match="origen"):
            MigrationPlanner(source_engine="mysql")

    def test_invalid_target_raises(self) -> None:
        with pytest.raises(ValueError, match="destino"):
            MigrationPlanner(target_engine="postgresql")

    def test_invalid_charset_raises(self) -> None:
        with pytest.raises(ValueError, match="Charset"):
            MigrationPlanner(charset="cp932_NOT_VALID")

    def test_invalid_collation_raises(self) -> None:
        with pytest.raises(ValueError, match="Collation"):
            MigrationPlanner(collation="utf8mb4_weird_ci_INVALID")


class TestMigrationPlannerPlan:
    def test_plan_returns_migration_plan(self) -> None:
        manager = _make_mock_manager()
        planner = MigrationPlanner()
        plan = planner.plan(connection=manager, schema="TEST_SCHEMA")
        assert isinstance(plan, MigrationPlan)

    def test_plan_has_tables(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        assert len(plan.tables) == 1
        assert plan.tables[0].name == "USERS"

    def test_plan_columns_transformed(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        table = plan.tables[0]
        col_id = next(c for c in table.columns if c.name == "ID")
        assert col_id.target_type != ""
        assert col_id.target_type in ("BIGINT", "INT", "SMALLINT")

    def test_plan_pk_preserved(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        assert "ID" in plan.tables[0].primary_key

    def test_plan_warnings_consolidated(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        assert isinstance(plan.warnings, list)

    def test_emit_ddl_returns_string(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        ddl = plan.emit_ddl()
        assert isinstance(ddl, str)
        assert "CREATE TABLE" in ddl

    def test_emit_statements_returns_list(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        stmts = plan.emit_statements()
        assert isinstance(stmts, list)
        assert len(stmts) >= 1

    def test_source_schema_captured(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "MY_SCHEMA")
        assert plan.source_schema == "MY_SCHEMA"

    def test_warning_counts(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        total = plan.error_count + plan.warning_count + plan.info_count
        assert total == len(plan.warnings)

    def test_suggested_filename_default(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "VENTAS")
        assert plan.suggested_filename() == "ventas_oracle_to_mariadb.sql"

    def test_suggested_filename_with_suffix(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "HR")
        assert plan.suggested_filename(suffix="report", ext="md") == "hr_oracle_to_mariadb_report.md"

    def test_suggested_filename_schema_lowercase(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "CONTABILIDAD")
        name = plan.suggested_filename()
        assert name.startswith("contabilidad_")

    def test_suggested_filename_no_suffix_no_underscore(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        name = plan.suggested_filename()
        assert "__" not in name
        assert not name.endswith("_.sql")


class TestMigrationPlanExecute:
    def test_execute_calls_target_manager(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")

        target = MagicMock()
        target.execute_custom_one.return_value = None

        plan.execute(target_connection=target)
        assert target.execute_custom_one.called

    def test_execute_passes_ddl_statements(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")

        target = MagicMock()
        target.execute_custom_one.return_value = None

        plan.execute(target_connection=target)
        calls = target.execute_custom_one.call_args_list
        # Debe haberse llamado al menos una vez con SQL de CREATE TABLE
        assert any("CREATE TABLE" in str(call) for call in calls)
