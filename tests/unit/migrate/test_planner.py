"""Tests para MigrationPlanner usando MagicMock (sin BD real)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate import MigrationPlan, MigrationPlanner, MigrationWarning

from ._snapshot_source import col, fake_manager, pk, table


def _make_mock_manager(tables: list[tuple] | None = None) -> MagicMock:
    """Manager simulado con metadatos Oracle (snapshot de metadata/): ``tables`` = ``(nombre, tipo, comentario)``."""
    table_rows = tables or [("USERS", "TABLE", "Tabla de usuarios")]
    objects: list[Any] = []
    for row in table_rows:
        name = str(row[0])
        objects += [
            table(name, row[2] or None),
            col(name, "ID", 1, "NUMBER(10)", "NUMBER", precision=10, scale=0, nullable=False, comment="PK"),
            col(name, "NAME", 2, "VARCHAR2(100)", "VARCHAR2", length=100, comment="Nombre"),
            pk(name, "ID", name="PK_USERS"),
        ]
    return fake_manager("oracle", *objects)


class TestMigrationPlannerInit:
    def test_default_init(self) -> None:
        p = MigrationPlanner()
        assert p._source_engine == "oracle"
        assert p._target_engine == "mariadb"
        assert p._charset == "utf8mb4"

    def test_invalid_source_raises(self) -> None:
        with pytest.raises(ValueError, match="origen"):
            MigrationPlanner(source_engine="db2")

    def test_invalid_target_raises(self) -> None:
        with pytest.raises(ValueError, match="destino"):
            MigrationPlanner(target_engine="db2")

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


class TestMigrationPlannerCaseCollisionWarning:
    """CMP-02 (AUDIT_CODE 2026-09-22): dos tablas cuyo nombre solo difiere en case
    deben generar un MigrationWarning en plan.warnings — antes se ignoraba en
    silencio y el planner no detectaba el riesgo de colisión bajo case-folding."""

    def test_case_only_table_names_emit_collision_warning(self) -> None:
        manager = _make_mock_manager(
            tables=[
                ("USERS", "TABLE", ""),
                ("users", "TABLE", ""),
            ]
        )
        plan = MigrationPlanner().plan(manager, "SCHEMA")

        collision_warnings = [w for w in plan.warnings if w.category == "IDENTIFIER_CASE_COLLISION"]
        assert len(collision_warnings) == 1
        assert {collision_warnings[0].table, collision_warnings[0].target_type} == {"USERS", "users"}
        assert collision_warnings[0].severity == "WARNING"

    def test_distinct_table_names_no_collision_warning(self) -> None:
        manager = _make_mock_manager(
            tables=[
                ("USERS", "TABLE", ""),
                ("ORDERS", "TABLE", ""),
            ]
        )
        plan = MigrationPlanner().plan(manager, "SCHEMA")

        assert not any(w.category == "IDENTIFIER_CASE_COLLISION" for w in plan.warnings)


class TestMigrationPlannerSQLServer:
    def test_sqlserver_target_valid(self) -> None:
        p = MigrationPlanner(target_engine="sqlserver")
        assert p._target_engine == "sqlserver"

    def test_sqlserver_invalid_charset_not_raises(self) -> None:
        # charset/collation son MariaDB-specific; no deben validarse para sqlserver
        p = MigrationPlanner(target_engine="sqlserver", charset="cp932_NOT_VALID")
        assert p._target_engine == "sqlserver"

    def test_sqlserver_plan_returns_migration_plan(self) -> None:
        manager = _make_mock_manager()
        planner = MigrationPlanner(target_engine="sqlserver")
        from util_bbdd.migrate import MigrationPlan

        plan = planner.plan(connection=manager, schema="TEST_SCHEMA")
        assert isinstance(plan, MigrationPlan)
        assert plan.target_engine == "sqlserver"

    def test_sqlserver_emit_ddl_uses_brackets(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner(target_engine="sqlserver").plan(manager, "SCHEMA")
        ddl = plan.emit_ddl()
        assert "[USERS]" in ddl
        assert "ENGINE=" not in ddl

    def test_sqlserver_emit_ddl_no_auto_increment(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner(target_engine="sqlserver").plan(manager, "SCHEMA")
        ddl = plan.emit_ddl()
        assert "AUTO_INCREMENT" not in ddl

    def test_sqlserver_suggested_filename(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner(target_engine="sqlserver").plan(manager, "VENTAS")
        assert plan.suggested_filename() == "ventas_oracle_to_sqlserver.sql"

    def test_sqlserver_collation_param_accepted(self) -> None:
        p = MigrationPlanner(
            target_engine="sqlserver",
            sql_server_collation="SQL_Latin1_General_CP1_CI_AS",
        )
        assert p._sql_server_collation == "SQL_Latin1_General_CP1_CI_AS"

    def test_mariadb_still_validates_charset(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Charset"):
            MigrationPlanner(target_engine="mariadb", charset="cp932_NOT_VALID")


class TestMigrationPlanExecute:
    def test_execute_calls_target_manager(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")

        target = MagicMock(spec=["execute_custom_one"])  # solo execute_custom_one: vía sentencia a sentencia
        target.execute_custom_one.return_value = None

        plan.execute(target_connection=target)
        assert target.execute_custom_one.called

    def test_execute_passes_ddl_statements(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")

        target = MagicMock(spec=["execute_custom_one"])  # solo execute_custom_one: vía sentencia a sentencia
        target.execute_custom_one.return_value = None

        plan.execute(target_connection=target)
        calls = target.execute_custom_one.call_args_list
        # Debe haberse llamado al menos una vez con SQL de CREATE TABLE
        assert any("CREATE TABLE" in str(call) for call in calls)


class TestMigrationPlanExecuteErrorGate:
    """MIG-01 (AUDIT_CODE 2026-09-22, decisión confirmada por el usuario): execute()
    debe bloquear si el plan tiene warnings de severidad ERROR, sin flag de override."""

    @staticmethod
    def _error_warning() -> MigrationWarning:
        return MigrationWarning(
            table="USERS",
            column="ID",
            category="TYPE",
            source_type="LONG",
            target_type="UNKNOWN",
            message="Tipo no soportado",
            severity="ERROR",
        )

    def test_execute_raises_value_error_when_error_count_positive(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        plan.warnings.append(self._error_warning())
        assert plan.error_count == 1

        target = MagicMock()

        with pytest.raises(ValueError, match="ERROR"):
            plan.execute(target_connection=target)

        target.execute_custom_one.assert_not_called()

    def test_execute_error_message_includes_warning_text(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        plan.warnings.append(self._error_warning())

        target = MagicMock()

        with pytest.raises(ValueError, match="Tipo no soportado"):
            plan.execute(target_connection=target)

    def test_execute_runs_normally_when_only_warning_and_info_severities(self) -> None:
        manager = _make_mock_manager()
        plan = MigrationPlanner().plan(manager, "SCHEMA")
        plan.warnings.append(
            MigrationWarning(
                table="USERS",
                column="ID",
                category="TYPE",
                source_type="NUMBER",
                target_type="INT",
                message="Aviso no bloqueante",
                severity="WARNING",
            )
        )
        assert plan.error_count == 0

        target = MagicMock(spec=["execute_custom_one"])  # solo execute_custom_one: vía sentencia a sentencia
        target.execute_custom_one.return_value = None

        plan.execute(target_connection=target)  # No debe lanzar

        assert target.execute_custom_one.called

    def test_execute_has_no_override_flag(self) -> None:
        """No debe existir forma de saltarse el gate: execute() solo acepta target_connection y opciones keyword-only
        que no cambian qué se ejecuta: el destino de auditoría (sesión 2026-10-02c), ``dry_run`` (no ejecuta nada) y
        ``stop_on_error`` (4.3.0)."""
        import inspect

        sig = inspect.signature(MigrationPlan.execute)
        assert list(sig.parameters) == ["self", "target_connection", "audit_sink", "dry_run", "stop_on_error"]
        assert all(sig.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY for name in list(sig.parameters)[2:])


class TestMigrationPlanEmitSyncsFallbackWarnings:
    """MIG-03 (AUDIT_CODE 2026-09-22): los emisores descubren warnings de DEFAULT
    solo durante la emisión (no en fase de transformación, cuando se construye
    plan.warnings). emit_ddl()/emit_statements() deben resincronizar plan.warnings
    con los nuevos warnings que aparezcan en col.warnings tras emitir."""

    @staticmethod
    def _make_plan_with_unrecognized_default() -> MigrationPlan:
        from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
        from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable

        col = CanonicalColumn(
            name="CREATED_AT",
            original_name="CREATED_AT",
            source_type="TIMESTAMP",
            target_type="DATETIME",
            nullable=True,
            default="GETDATE()",  # función SQL Server, no reconocida por el emisor MariaDB
            comment="",
            ordinal=1,
        )
        table = CanonicalTable(
            name="T",
            original_name="T",
            schema="S",
            columns=[col],
            primary_key=[],
            indexes=[],
            foreign_keys=[],
            comment="",
            warnings=[],
        )
        return MigrationPlan(
            tables=[table],
            warnings=[],
            source_schema="S",
            source_engine="sqlserver",
            target_engine="mariadb",
            emitter=MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_unicode_ci"),
        )

    def test_emit_ddl_syncs_new_warning_into_plan_warnings(self) -> None:
        plan = self._make_plan_with_unrecognized_default()
        assert plan.warnings == []

        plan.emit_ddl()

        assert plan.warning_count == 1
        assert "GETDATE()" in plan.warnings[0].message

    def test_emit_statements_syncs_new_warning_into_plan_warnings(self) -> None:
        plan = self._make_plan_with_unrecognized_default()
        assert plan.warnings == []

        plan.emit_statements()

        assert plan.warning_count == 1

    def test_calling_emit_ddl_twice_does_not_duplicate_plan_warnings(self) -> None:
        plan = self._make_plan_with_unrecognized_default()

        plan.emit_ddl()
        plan.emit_ddl()

        assert plan.warning_count == 1

    def test_execute_also_syncs_warnings_via_emit_statements(self) -> None:
        plan = self._make_plan_with_unrecognized_default()
        target = MagicMock(spec=["execute_custom_one"])  # solo execute_custom_one: vía sentencia a sentencia
        target.execute_custom_one.return_value = None

        plan.execute(target_connection=target)

        assert plan.warning_count == 1


class TestMigrationPlannerOracleIdentityMode:
    def test_default_oracle_identity_mode_is_sequence_trigger(self) -> None:
        p = MigrationPlanner()
        assert p._oracle_identity_mode == "sequence_trigger"

    def test_oracle_identity_mode_stored(self) -> None:
        p = MigrationPlanner(oracle_identity_mode="identity_by_default_on_null")
        assert p._oracle_identity_mode == "identity_by_default_on_null"

    def test_invalid_oracle_identity_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="oracle_identity_mode"):
            MigrationPlanner(oracle_identity_mode="always")  # type: ignore[arg-type]

    def test_planner_passes_identity_mode_to_oracle_emitter(self) -> None:
        from unittest.mock import MagicMock, patch

        from util_bbdd.migrate.emitters.oracle import OracleDDLEmitter

        with patch("util_bbdd.migrate.planner.MariaDBSchemaExtractor") as mock_cls:
            mock_extractor = MagicMock()
            mock_extractor.extract.return_value = []
            mock_extractor.extract_views.return_value = []
            mock_extractor.extract_routines.return_value = []
            mock_cls.return_value = mock_extractor

            planner = MigrationPlanner(
                source_engine="mariadb",
                target_engine="oracle",
                oracle_identity_mode="identity_by_default_on_null",
            )
            plan = planner.plan(connection=MagicMock(), schema="TEST")

        assert isinstance(plan.emitter, OracleDDLEmitter)
        assert plan.emitter._identity_mode == "identity_by_default_on_null"


class TestMigrationPlanExecuteOnConnection:
    """A1 (hotfix 2026-09-29): con un manager (``get_sqlalchemy_engine``) o un Engine, el plan se aplica por una
    conexión DB-API con commit tras cada sentencia; antes ``execute_custom_one`` hacía fetch tras el DDL y no hacía
    commit (fallaba en PostgreSQL, SQL Server, MariaDB y Oracle)."""

    @staticmethod
    def _plan(statements: list[str]) -> MigrationPlan:
        emitter = MagicMock()
        emitter.emit_statements.return_value = statements
        return MigrationPlan(
            tables=[], warnings=[], source_schema="S", source_engine="oracle", target_engine="sqlite", emitter=emitter
        )

    @staticmethod
    def _tables(path: str) -> list[str]:
        import sqlite3

        conn = sqlite3.connect(path)
        try:
            return sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"))
        finally:
            conn.close()

    def test_statements_are_committed_and_comment_only_skipped(self, tmp_path: Any) -> None:
        from sqlalchemy import create_engine

        path = str(tmp_path / "destino.db")
        manager = MagicMock()
        manager.get_sqlalchemy_engine.return_value = create_engine(f"sqlite:///{path}")
        plan = self._plan(
            [
                "CREATE TABLE a (x INT)",
                "-- PROCEDURE: p\n-- TODO: body not available",
                "-- NOTE: revisar\nCREATE TABLE b (y INT)",
            ]
        )
        plan.execute(manager)
        assert self._tables(path) == ["a", "b"]  # visibles desde otra conexión: hubo commit
        manager.execute_custom_one.assert_not_called()

    def test_failure_reports_position_and_keeps_previous_statements(self, tmp_path: Any) -> None:
        from sqlalchemy import create_engine

        from util_bbdd._core.exceptions import DatabaseOperationError

        path = str(tmp_path / "destino.db")
        engine = create_engine(f"sqlite:///{path}")
        plan = self._plan(["CREATE TABLE a (x INT)", "-- nota\nCREATE TABLE a (x INT)", "CREATE TABLE c (z INT)"])
        with pytest.raises(DatabaseOperationError, match=r"Sentencia 2/3 .*CREATE TABLE a"):
            plan.execute(engine)
        assert self._tables(path) == ["a"]
        engine.dispose()

    def test_engine_from_manager_is_disposed_but_received_engine_is_not(self) -> None:
        engine = MagicMock()
        manager = MagicMock()
        manager.get_sqlalchemy_engine.return_value = engine
        plan = self._plan(["CREATE TABLE a (x INT)"])
        plan.execute(manager)
        engine.dispose.assert_called_once()
        engine.raw_connection.return_value.commit.assert_called_once()

        received = MagicMock(spec=["raw_connection", "dispose"])
        plan.execute(received)
        received.dispose.assert_not_called()


def test_every_planner_engine_has_a_sqlglot_dialect_for_views() -> None:
    # _transpile_view resuelve SQLGLOT_DIALECT[motor] sin más comprobación: un motor del planner sin dialecto daría
    # KeyError al transpilar sus vistas en lugar del ValueError de MigrationPlanner.
    from util_bbdd.migrate import planner
    from util_bbdd.migrate.views._dialects import SQLGLOT_DIALECT

    assert planner._SUPPORTED_SOURCE <= set(SQLGLOT_DIALECT)
    assert planner._SUPPORTED_TARGET <= set(SQLGLOT_DIALECT)


class TestSupportedEngines:
    """U-M1 (G4 de util_bbdd_web): motores de migración consultables sin leer constantes privadas."""

    def test_match_private_constants(self) -> None:
        from util_bbdd.migrate import planner

        assert set(MigrationPlanner.supported_sources()) == planner._SUPPORTED_SOURCE
        assert set(MigrationPlanner.supported_targets()) == planner._SUPPORTED_TARGET

    def test_sorted_tuples(self) -> None:
        sources = MigrationPlanner.supported_sources()
        targets = MigrationPlanner.supported_targets()
        assert isinstance(sources, tuple) and list(sources) == sorted(sources)
        assert isinstance(targets, tuple) and list(targets) == sorted(targets)

    def test_every_distinct_pair_builds_a_planner(self) -> None:
        for source in MigrationPlanner.supported_sources():
            for target in MigrationPlanner.supported_targets():
                if source != target:
                    MigrationPlanner(source_engine=source, target_engine=target)

    def test_available_on_instances(self) -> None:
        assert MigrationPlanner().supported_targets() == MigrationPlanner.supported_targets()
