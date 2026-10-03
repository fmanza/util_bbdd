"""Tests de integración del MigrationPlanner con PostgreSQL como source."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate.planner import MigrationPlanner

from ._snapshot_source import col, fake_manager, pk, table


def _make_manager(
    tables: list[tuple] | None = None,
    columns: list[tuple] | None = None,
    pks: list[tuple] | None = None,
) -> MagicMock:
    """Manager simulado (snapshot de metadata/) con las mismas columnas y PK en cada tabla.

    ``columns``: ``(nombre, tipo, longitud, precisión, escala, nulable 'YES'/'NO', default, ordinal)``.
    """
    objects: list[object] = []
    for name, *_rest in tables or []:
        objects.append(table(name))
        for c_name, data_type, length, precision, scale, nullable, default, ordinal in columns or []:
            declared = f"{data_type}({length})" if length else data_type
            numeric = data_type == "numeric"
            objects.append(
                col(
                    name,
                    c_name,
                    ordinal,
                    declared,
                    data_type,
                    nullable=nullable == "YES",
                    length=length,
                    precision=precision if numeric else None,
                    scale=scale if numeric else None,
                    default=default,
                )
            )
        if pks:
            objects.append(pk(name, *(r[0] for r in pks)))
    return fake_manager("postgresql", *objects)


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
