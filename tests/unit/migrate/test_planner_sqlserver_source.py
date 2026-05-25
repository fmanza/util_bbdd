"""Tests de integración del MigrationPlanner con SQL Server como source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate.planner import MigrationPlanner


def _make_manager(
    tables: list[tuple] | None = None,
    columns: list[tuple] | None = None,
    pks: list[tuple] | None = None,
) -> MagicMock:
    """Manager mock con respuestas mínimas para ejecutar plan()."""
    manager = MagicMock()

    def side_effect(sql: str, params: dict) -> list:
        sql_upper = sql.upper()
        if "INFORMATION_SCHEMA.VIEWS" in sql_upper and "VIEW_DEFINITION" in sql_upper:
            return []
        if "INFORMATION_SCHEMA.TABLES" in sql_upper:
            return tables or []
        if "COLUMNPROPERTY" in sql_upper:
            return columns or []
        if "CONSTRAINT_TYPE = 'PRIMARY KEY'" in sql_upper:
            return pks or []
        if "REFERENTIAL_CONSTRAINTS" in sql_upper:
            return []
        if "SYS.INDEXES" in sql_upper:
            return []
        if "INFORMATION_SCHEMA.COLUMNS" in sql_upper:
            return []
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


# ── Validación de motores ─────────────────────────────────────────────────────


class TestPlannerEngineValidation:
    def test_sqlserver_source_accepted(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="oracle")
        assert planner is not None

    def test_sqlserver_to_oracle(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="oracle")
        assert planner is not None

    def test_sqlserver_to_mariadb(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="mariadb")
        assert planner is not None

    def test_sqlserver_to_postgresql(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="postgresql")
        assert planner is not None

    def test_sqlserver_to_sqlserver_raises(self) -> None:
        with pytest.raises(ValueError, match="mismo"):
            MigrationPlanner(source_engine="sqlserver", target_engine="sqlserver")

    def test_unsupported_source_raises(self) -> None:
        with pytest.raises(ValueError, match="origen"):
            MigrationPlanner(source_engine="db2", target_engine="oracle")

    def test_existing_oracle_source_still_works(self) -> None:
        planner = MigrationPlanner(source_engine="oracle", target_engine="mariadb")
        assert planner is not None

    def test_existing_mariadb_source_still_works(self) -> None:
        planner = MigrationPlanner(source_engine="mariadb", target_engine="oracle")
        assert planner is not None


# ── Tests plan() con schema vacío ────────────────────────────────────────────


class TestPlanEmptySchema:
    def test_sqlserver_to_oracle_empty(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="oracle")
        manager = _make_manager()
        plan = planner.plan(manager, "dbo")
        assert plan.tables == []
        assert plan.source_engine == "sqlserver"
        assert plan.target_engine == "oracle"

    def test_sqlserver_to_mariadb_empty(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="mariadb")
        manager = _make_manager()
        plan = planner.plan(manager, "dbo")
        assert plan.target_engine == "mariadb"

    def test_sqlserver_to_postgresql_empty(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="postgresql")
        manager = _make_manager()
        plan = planner.plan(manager, "dbo")
        assert plan.target_engine == "postgresql"


# ── Tests plan() con una tabla ────────────────────────────────────────────────


class TestPlanWithTable:
    def _col_row(
        self,
        name: str,
        data_type: str,
        char_length: int | None = None,
        precision: int | None = None,
        scale: int | None = None,
        nullable: str = "YES",
        identity: int = 0,
        ordinal: int = 1,
    ) -> tuple:
        return (name, data_type, char_length, precision, scale, nullable, None, identity, ordinal)

    def test_ss_int_to_oracle_number10(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="oracle")
        manager = _make_manager(
            tables=[("ORDERS",)],
            columns=[self._col_row("ID", "int", None, 10, 0, "NO", 1, 1)],
            pks=[("ID",)],
        )
        plan = planner.plan(manager, "dbo")
        assert len(plan.tables) == 1
        id_col = plan.tables[0].columns[0]
        assert id_col.target_type == "NUMBER(10,0)"
        assert id_col.auto_increment is True

    def test_ss_nvarchar_max_to_mariadb_longtext(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="mariadb")
        manager = _make_manager(
            tables=[("DOCS",)],
            columns=[self._col_row("BODY", "nvarchar", -1, None, None, "YES", 0, 1)],
        )
        plan = planner.plan(manager, "dbo")
        assert plan.tables[0].columns[0].target_type == "LONGTEXT"

    def test_ss_uniqueidentifier_to_postgresql_uuid(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="postgresql")
        manager = _make_manager(
            tables=[("ENTITIES",)],
            columns=[self._col_row("GUID", "uniqueidentifier", None, None, None, "NO", 0, 1)],
        )
        plan = planner.plan(manager, "dbo")
        assert plan.tables[0].columns[0].target_type == "UUID"

    def test_emit_ddl_returns_string(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="mariadb")
        manager = _make_manager(
            tables=[("PRODUCTS",)],
            columns=[
                self._col_row("ID", "int", None, 10, 0, "NO", 1, 1),
                self._col_row("NAME", "nvarchar", 200, None, None, "NO", 0, 2),
            ],
            pks=[("ID",)],
        )
        plan = planner.plan(manager, "dbo")
        ddl = plan.emit_ddl()
        assert isinstance(ddl, str)
        assert "PRODUCTS" in ddl


# ── Tests pg_schema y sql_server_collation no rompen SS source ───────────────


class TestPlannerOptionsWithSSSource:
    def test_pg_schema_passed_to_emitter(self) -> None:
        planner = MigrationPlanner(
            source_engine="sqlserver",
            target_engine="postgresql",
            pg_schema="reporting",
        )
        manager = _make_manager()
        plan = planner.plan(manager, "dbo")
        ddl = plan.emit_ddl()
        assert "search_path" in ddl

    def test_mariadb_charset_passed(self) -> None:
        planner = MigrationPlanner(
            source_engine="sqlserver",
            target_engine="mariadb",
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
        manager = _make_manager()
        plan = planner.plan(manager, "dbo")
        assert plan is not None
