"""Tests de integración del MigrationPlanner con SQL Server como source."""

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

    ``columns``: ``(nombre, tipo, longitud, precisión, escala, nulable, default, identidad, ordinal)``.
    """
    objects: list[object] = []
    for name, *_rest in tables or []:
        objects.append(table(name))
        for c_name, data_type, length, precision, scale, nullable, default, identity, ordinal in columns or []:
            declared = f"{data_type}(max)" if length == -1 else f"{data_type}({length})" if length else data_type
            exact = data_type in ("decimal", "numeric")
            objects.append(
                col(
                    name,
                    c_name,
                    ordinal,
                    declared,
                    data_type,
                    nullable=nullable == "YES",
                    length=length if length and length > 0 else None,
                    precision=precision if exact else None,
                    scale=scale if exact else None,
                    default=default,
                    identity="by default" if identity else None,
                )
            )
        if pks:
            objects.append(pk(name, *(r[0] for r in pks)))
    return fake_manager("sqlserver", *objects)


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
