"""Tests de integración del MigrationPlanner con PostgreSQL como source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate.planner import MigrationPlanner


def _make_manager(
    tables: list[tuple] | None = None,
    columns: list[tuple] | None = None,
    pks: list[tuple] | None = None,
) -> MagicMock:
    """Manager mock con respuestas mínimas para ejecutar plan().

    Columnas y PK se leen por schema (D1): cada tabla del mock recibe las mismas filas, con su nombre delante.
    """
    manager = MagicMock()
    table_names = [str(t[0]) for t in tables or []]

    def per_table(rows: list[tuple] | None) -> list[tuple]:
        return [(name, *row) for name in table_names for row in rows or []]

    def side_effect(sql: str, params: dict) -> list:
        sql_upper = sql.upper()
        if "INFORMATION_SCHEMA.VIEWS" in sql_upper and "VIEW_DEFINITION" in sql_upper:
            return []
        if "INFORMATION_SCHEMA.TABLES" in sql_upper:
            return tables or []
        if "CONTYPE = 'P'" in sql_upper:
            return per_table(pks)
        if "PG_CATALOG" in sql_upper:
            return []
        if "INFORMATION_SCHEMA.COLUMNS" in sql_upper:
            return per_table(columns)
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


def _col_row(
    name: str = "id",
    data_type: str = "integer",
    ordinal: int = 1,
) -> tuple:
    return (name, data_type, None, 32, 0, "NO", None, ordinal)


# ── Validación de motores ─────────────────────────────────────────────────────


class TestPlannerEngineValidation:
    def test_postgresql_source_accepted(self) -> None:
        planner = MigrationPlanner(source_engine="postgresql", target_engine="oracle")
        assert planner is not None

    def test_postgresql_to_oracle(self) -> None:
        planner = MigrationPlanner(source_engine="postgresql", target_engine="oracle")
        assert planner is not None

    def test_postgresql_to_mariadb(self) -> None:
        planner = MigrationPlanner(source_engine="postgresql", target_engine="mariadb")
        assert planner is not None

    def test_postgresql_to_sqlserver(self) -> None:
        planner = MigrationPlanner(source_engine="postgresql", target_engine="sqlserver")
        assert planner is not None

    def test_postgresql_to_postgresql_raises(self) -> None:
        with pytest.raises(ValueError, match="mismo"):
            MigrationPlanner(source_engine="postgresql", target_engine="postgresql")

    def test_unsupported_source_raises(self) -> None:
        with pytest.raises(ValueError, match="origen"):
            MigrationPlanner(source_engine="db2", target_engine="oracle")

    def test_existing_oracle_source_unaffected(self) -> None:
        planner = MigrationPlanner(source_engine="oracle", target_engine="mariadb")
        assert planner is not None

    def test_existing_mariadb_source_unaffected(self) -> None:
        planner = MigrationPlanner(source_engine="mariadb", target_engine="oracle")
        assert planner is not None

    def test_existing_sqlserver_source_unaffected(self) -> None:
        planner = MigrationPlanner(source_engine="sqlserver", target_engine="oracle")
        assert planner is not None


# ── Tests plan() con schema vacío ────────────────────────────────────────────


class TestPlanEmptySchema:
    def test_pg_to_oracle_empty_schema(self) -> None:
        manager = _make_manager(tables=[])
        planner = MigrationPlanner(source_engine="postgresql", target_engine="oracle")
        plan = planner.plan(manager, "public")
        assert plan.tables == []
        assert plan.source_engine == "postgresql"
        assert plan.target_engine == "oracle"

    def test_pg_to_mariadb_empty_schema(self) -> None:
        manager = _make_manager(tables=[])
        planner = MigrationPlanner(source_engine="postgresql", target_engine="mariadb")
        plan = planner.plan(manager, "public")
        assert plan.tables == []
        assert plan.target_engine == "mariadb"

    def test_pg_to_sqlserver_empty_schema(self) -> None:
        manager = _make_manager(tables=[])
        planner = MigrationPlanner(source_engine="postgresql", target_engine="sqlserver")
        plan = planner.plan(manager, "public")
        assert plan.tables == []
        assert plan.target_engine == "sqlserver"


# ── Tests pipeline completo ───────────────────────────────────────────────────


class TestPlanFullPipeline:
    def test_pg_to_oracle_single_table(self) -> None:
        manager = _make_manager(
            tables=[("orders",)],
            columns=[_col_row("id", "integer", 1)],
            pks=[("id",)],
        )
        planner = MigrationPlanner(source_engine="postgresql", target_engine="oracle")
        plan = planner.plan(manager, "public")
        assert len(plan.tables) == 1
        assert plan.tables[0].columns[0].target_type == "NUMBER(10,0)"

    def test_pg_to_mariadb_serial_column(self) -> None:
        manager = _make_manager(
            tables=[("users",)],
            columns=[("id", "integer", None, 32, 0, "NO", "nextval('users_id_seq'::regclass)", 1)],
            pks=[("id",)],
        )
        planner = MigrationPlanner(source_engine="postgresql", target_engine="mariadb")
        plan = planner.plan(manager, "public")
        assert len(plan.tables) == 1
        col = plan.tables[0].columns[0]
        assert col.auto_increment is True
        assert col.target_type == "INT"

    def test_pg_to_sqlserver_text_column(self) -> None:
        manager = _make_manager(
            tables=[("articles",)],
            columns=[
                _col_row("id", "integer", 1),
                ("body", "text", None, None, None, "YES", None, 2),
            ],
        )
        planner = MigrationPlanner(source_engine="postgresql", target_engine="sqlserver")
        plan = planner.plan(manager, "public")
        body_col = next(c for c in plan.tables[0].columns if c.original_name == "body")
        assert body_col.target_type == "NVARCHAR(MAX)"

    def test_emit_ddl_produces_output_oracle(self) -> None:
        manager = _make_manager(
            tables=[("products",)],
            columns=[
                _col_row("id", "integer", 1),
                ("name", "character varying", 200, None, None, "NO", None, 2),
            ],
            pks=[("id",)],
        )
        planner = MigrationPlanner(source_engine="postgresql", target_engine="oracle")
        plan = planner.plan(manager, "public")
        ddl = plan.emit_ddl()
        assert isinstance(ddl, str)
        assert len(ddl) > 0

    def test_emit_ddl_produces_output_mariadb(self) -> None:
        manager = _make_manager(
            tables=[("products",)],
            columns=[_col_row("id", "integer", 1)],
            pks=[("id",)],
        )
        planner = MigrationPlanner(source_engine="postgresql", target_engine="mariadb")
        plan = planner.plan(manager, "public")
        ddl = plan.emit_ddl()
        assert isinstance(ddl, str)
        assert len(ddl) > 0

    def test_emit_ddl_produces_output_sqlserver(self) -> None:
        manager = _make_manager(
            tables=[("products",)],
            columns=[_col_row("id", "integer", 1)],
            pks=[("id",)],
        )
        planner = MigrationPlanner(source_engine="postgresql", target_engine="sqlserver")
        plan = planner.plan(manager, "public")
        ddl = plan.emit_ddl()
        assert isinstance(ddl, str)
        assert len(ddl) > 0


# ── Test charset/collation para MariaDB target ────────────────────────────────


class TestMariaDBTargetOptions:
    def test_custom_charset_accepted(self) -> None:
        planner = MigrationPlanner(
            source_engine="postgresql",
            target_engine="mariadb",
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
        assert planner is not None

    def test_sqlserver_collation_accepted(self) -> None:
        planner = MigrationPlanner(
            source_engine="postgresql",
            target_engine="sqlserver",
            sql_server_collation="SQL_Latin1_General_CP1_CI_AS",
        )
        assert planner is not None
