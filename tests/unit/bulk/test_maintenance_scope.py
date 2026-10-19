"""Tests para BulkCrud.maintenance_scope y sus helpers privados de motor."""

from __future__ import annotations

import logging

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy import Engine, create_engine

from util_bbdd.bulk._models import MaintenanceScopeResult
from util_bbdd.bulk.crud import BulkCrud
from util_bbdd.metadata.model import CheckMeta, ForeignKeyMeta, Kind, SchemaSnapshot, UniqueMeta

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sqlite_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    return engine


def _make_crud_for_dialect(dialect: str) -> tuple[BulkCrud, MagicMock]:
    """Construye un BulkCrud con dialecto y conexión activa mockeados."""
    crud = BulkCrud(_make_sqlite_engine())

    conn: MagicMock = MagicMock(name="conn")
    crud._session.connection = conn

    mock_engine: MagicMock = MagicMock(name="engine")
    mock_engine.dialect.name = dialect
    mock_engine.dialect.identifier_preparer.format_table.return_value = '"t"'
    crud.engine = mock_engine  # type: ignore[assignment]

    table_mock: MagicMock = MagicMock(name="table")
    table_mock.name = "t"
    table_mock.schema = None
    crud._table_cache["t"] = table_mock  # type: ignore[assignment]

    return crud, conn


_SECONDARY_INDEXES = "util_bbdd.bulk._execution.maintenance.facts.secondary_nonunique_indexes"


def _make_mssql_crud_with_secondary_indexes(names: list[str], *, clustered: int = 0) -> tuple[BulkCrud, MagicMock]:
    """BulkCrud SQL Server con ``clustered`` índices clustered y ``names`` como índices NONCLUSTERED no únicos.

    El parche de ``secondary_nonunique_indexes`` sigue activo hasta el final del test (lo detiene ``_stop_patchers``).
    """
    crud, conn = _make_crud_for_dialect("mssql")
    crud.engine.dialect.identifier_preparer.quote.side_effect = lambda name: f'"{name}"'  # type: ignore[attr-defined]
    conn.execute.return_value.scalar.return_value = clustered
    patcher = patch(_SECONDARY_INDEXES, return_value=[(name, None) for name in names])
    patcher.start()
    _PATCHERS.append(patcher)
    return crud, conn


_PATCHERS: list[Any] = []


@pytest.fixture(autouse=True)
def _stop_patchers() -> Iterator[None]:
    yield
    while _PATCHERS:
        _PATCHERS.pop().stop()


def _sql_calls(conn: MagicMock) -> list[str]:
    """Extrae los textos SQL de las llamadas a conn.execute()."""
    return [str(call.args[0]) for call in conn.execute.call_args_list if call.args]


# ---------------------------------------------------------------------------
# RuntimeError — sin bulk_session activo
# ---------------------------------------------------------------------------


class TestMaintenanceScopeRequiresSession:
    def test_raises_runtime_error_without_active_session(self) -> None:
        crud = BulkCrud(_make_sqlite_engine())
        with pytest.raises(RuntimeError, match="bulk_session"):
            with crud.maintenance_scope("t"):
                pytest.fail("El cuerpo no debería ejecutarse")


# ---------------------------------------------------------------------------
# MySQL / MariaDB
# ---------------------------------------------------------------------------


class TestMaintenanceScopeMySQL:
    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_disable_constraints_sets_fk_checks_off(self, dialect: str) -> None:
        crud, conn = _make_crud_for_dialect(dialect)
        with crud.maintenance_scope("t"):
            assert "SET SESSION FOREIGN_KEY_CHECKS=0" in _sql_calls(conn)

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_restore_fk_checks_on_normal_exit(self, dialect: str) -> None:
        crud, conn = _make_crud_for_dialect(dialect)
        with crud.maintenance_scope("t"):
            assert "SET SESSION FOREIGN_KEY_CHECKS=1" not in _sql_calls(conn)
        sqls = _sql_calls(conn)
        assert "SET SESSION FOREIGN_KEY_CHECKS=1" in sqls
        assert sqls.index("SET SESSION FOREIGN_KEY_CHECKS=0") < sqls.index("SET SESSION FOREIGN_KEY_CHECKS=1")

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_restore_fk_checks_on_exception(self, dialect: str) -> None:
        crud, conn = _make_crud_for_dialect(dialect)
        with pytest.raises(ValueError):
            with crud.maintenance_scope("t"):
                raise ValueError("boom")
        assert "SET SESSION FOREIGN_KEY_CHECKS=1" in _sql_calls(conn)

    # DISABLE KEYS solo tiene efecto en MyISAM/Aria; en InnoDB el servidor lo ignora pero, como DDL, provoca un commit
    # implícito que rompía la atomicidad de la sesión (hallazgo 8 de la auditoría de bulk, 2026-09-24).
    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    @pytest.mark.parametrize("storage_engine", ["MyISAM", "Aria"])
    def test_disable_indexes_issues_disable_keys_for_myisam_and_aria(self, dialect: str, storage_engine: str) -> None:
        crud, conn = _make_crud_for_dialect(dialect)
        conn.execute.return_value.scalar.return_value = storage_engine
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER TABLE "t" DISABLE KEYS' in _sql_calls(conn)
            assert 'ALTER TABLE "t" ENABLE KEYS' not in _sql_calls(conn)
        assert 'ALTER TABLE "t" ENABLE KEYS' in _sql_calls(conn)

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_disable_indexes_skips_ddl_for_innodb(self, dialect: str, caplog: pytest.LogCaptureFixture) -> None:
        crud, conn = _make_crud_for_dialect(dialect)
        conn.execute.return_value.scalar.return_value = "InnoDB"
        with caplog.at_level(logging.INFO), crud.maintenance_scope("t", disable_indexes=True):
            pass
        assert not any("KEYS" in sql for sql in _sql_calls(conn))
        assert any("InnoDB" in msg and "commit implícito" in msg for msg in caplog.messages)

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_enable_keys_restored_on_exception(self, dialect: str) -> None:
        crud, conn = _make_crud_for_dialect(dialect)
        conn.execute.return_value.scalar.return_value = "MyISAM"
        with pytest.raises(RuntimeError):
            with crud.maintenance_scope("t", disable_indexes=True):
                raise RuntimeError("fail")
        assert 'ALTER TABLE "t" ENABLE KEYS' in _sql_calls(conn)


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


class TestMaintenanceScopePostgreSQL:
    def test_disable_triggers_when_privileged(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = True
        with crud.maintenance_scope("t"):
            assert 'ALTER TABLE "t" DISABLE TRIGGER ALL' in _sql_calls(conn)

    def test_enable_triggers_on_exit(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = True
        with crud.maintenance_scope("t"):
            assert 'ALTER TABLE "t" ENABLE TRIGGER ALL' not in _sql_calls(conn)
        assert 'ALTER TABLE "t" ENABLE TRIGGER ALL' in _sql_calls(conn)

    def test_disable_before_enable_order(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = True
        with crud.maintenance_scope("t"):
            assert 'ALTER TABLE "t" DISABLE TRIGGER ALL' in _sql_calls(conn)
        sqls = _sql_calls(conn)
        assert sqls.index('ALTER TABLE "t" DISABLE TRIGGER ALL') < sqls.index('ALTER TABLE "t" ENABLE TRIGGER ALL')

    def test_warning_and_no_ddl_when_not_privileged(self, caplog: pytest.LogCaptureFixture) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = False
        with caplog.at_level(logging.WARNING):
            with crud.maintenance_scope("t"):
                assert 'ALTER TABLE "t" DISABLE TRIGGER ALL' not in _sql_calls(conn)
        sqls = _sql_calls(conn)
        assert 'ALTER TABLE "t" DISABLE TRIGGER ALL' not in sqls
        assert 'ALTER TABLE "t" ENABLE TRIGGER ALL' not in sqls
        assert any("privilegios" in msg for msg in caplog.messages)

    def test_enable_trigger_on_exception_when_previously_disabled(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = True
        with pytest.raises(ValueError):
            with crud.maintenance_scope("t"):
                raise ValueError("boom")
        assert 'ALTER TABLE "t" ENABLE TRIGGER ALL' in _sql_calls(conn)

    def test_no_enable_trigger_on_exception_when_not_privileged(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = False
        with pytest.raises(ValueError):
            with crud.maintenance_scope("t"):
                raise ValueError("boom")
        assert 'ALTER TABLE "t" ENABLE TRIGGER ALL' not in _sql_calls(conn)


# ---------------------------------------------------------------------------
# SQL Server
# ---------------------------------------------------------------------------


class TestMaintenanceScopeSQLServer:
    def test_disable_constraints_nocheck(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        with crud.maintenance_scope("t"):
            assert 'ALTER TABLE "t" NOCHECK CONSTRAINT ALL' in _sql_calls(conn)

    def test_restore_check_constraint_on_exit(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        with crud.maintenance_scope("t"):
            assert 'ALTER TABLE "t" WITH CHECK CHECK CONSTRAINT ALL' not in _sql_calls(conn)
        assert 'ALTER TABLE "t" WITH CHECK CHECK CONSTRAINT ALL' in _sql_calls(conn)

    def test_nocheck_before_check_order(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        with crud.maintenance_scope("t"):
            assert 'ALTER TABLE "t" NOCHECK CONSTRAINT ALL' in _sql_calls(conn)
        sqls = _sql_calls(conn)
        assert sqls.index('ALTER TABLE "t" NOCHECK CONSTRAINT ALL') < sqls.index(
            'ALTER TABLE "t" WITH CHECK CHECK CONSTRAINT ALL'
        )

    def test_restore_check_constraint_on_exception(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        with pytest.raises(RuntimeError):
            with crud.maintenance_scope("t"):
                raise RuntimeError("fail")
        assert 'ALTER TABLE "t" WITH CHECK CHECK CONSTRAINT ALL' in _sql_calls(conn)

    def test_disable_indexes_when_no_clustered(self) -> None:
        crud, conn = _make_mssql_crud_with_secondary_indexes(["ix_a", "ix_b"])
        with crud.maintenance_scope("t", disable_indexes=True):
            sqls = _sql_calls(conn)
            assert 'ALTER INDEX "ix_a" ON "t" DISABLE' in sqls
            assert 'ALTER INDEX "ix_b" ON "t" DISABLE' in sqls

    def test_disable_indexes_never_uses_all_on_heap(self) -> None:
        """Hotfix 2026-10-19: ``ALTER INDEX ALL … DISABLE`` en un heap desactivaba también la PK/UNIQUE NONCLUSTERED.

        Sin ellas se aceptaban duplicados y SQL Server deshabilitaba las FK entrantes, que el ``REBUILD`` no reactiva.
        """
        crud, conn = _make_mssql_crud_with_secondary_indexes(["ix_a"])
        with crud.maintenance_scope("t", disable_indexes=True):
            pass
        assert not [sql for sql in _sql_calls(conn) if "ALTER INDEX ALL" in sql]

    def test_only_non_unique_nonclustered_indexes_are_requested(self) -> None:
        crud, _ = _make_mssql_crud_with_secondary_indexes(["ix_a"])
        with patch(_SECONDARY_INDEXES, return_value=[("ix_a", None)]) as discover:
            with crud.maintenance_scope("t", disable_indexes=True):
                pass
        discover.assert_called_once()
        assert discover.call_args.args[1:] == (None, "t", "mssql")

    def test_no_disable_when_heap_has_no_secondary_indexes(self) -> None:
        crud, conn = _make_mssql_crud_with_secondary_indexes([])
        with crud.maintenance_scope("t", disable_indexes=True):
            pass
        assert not [sql for sql in _sql_calls(conn) if sql.startswith("ALTER INDEX")]

    def test_rebuild_indexes_on_exit_when_disabled(self) -> None:
        crud, conn = _make_mssql_crud_with_secondary_indexes(["ix_a", "ix_b"])
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER INDEX "ix_a" ON "t" REBUILD' not in _sql_calls(conn)
        sqls = _sql_calls(conn)
        assert 'ALTER INDEX "ix_a" ON "t" REBUILD' in sqls
        assert 'ALTER INDEX "ix_b" ON "t" REBUILD' in sqls

    def test_disable_before_rebuild_order(self) -> None:
        crud, conn = _make_mssql_crud_with_secondary_indexes(["ix_a"])
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER INDEX "ix_a" ON "t" DISABLE' in _sql_calls(conn)
        sqls = _sql_calls(conn)
        assert sqls.index('ALTER INDEX "ix_a" ON "t" DISABLE') < sqls.index('ALTER INDEX "ix_a" ON "t" REBUILD')

    def test_tables_with_clustered_index_also_disable_secondary_indexes(self) -> None:
        """3.2.0: estrategia común con dump; la condición de «solo heaps» de 3.1.x desaparece (el clustered no se toca)."""
        crud, conn = _make_mssql_crud_with_secondary_indexes(["ix_a"], clustered=1)
        with crud.maintenance_scope("t", disable_indexes=True) as ms:
            assert 'ALTER INDEX "ix_a" ON "t" DISABLE' in _sql_calls(conn)
        assert 'ALTER INDEX "ix_a" ON "t" REBUILD' in _sql_calls(conn)
        assert [(r.index_name, r.action) for r in ms.index_results] == [("ix_a", "rebuilt")]

    def test_each_index_ddl_runs_in_a_savepoint(self) -> None:
        crud, conn = _make_mssql_crud_with_secondary_indexes(["ix_a", "ix_b"])
        with crud.maintenance_scope("t", disable_constraints=False, disable_indexes=True):
            pass
        assert conn.begin_nested.call_count == 4  # 2 DISABLE + 2 REBUILD
        conn.commit.assert_not_called()  # la sesión confirma al salir, no cada sentencia


# ---------------------------------------------------------------------------
# Índices: estrategia común con dump (3.2.0)
# ---------------------------------------------------------------------------


class TestMaintenanceScopeIndexStrategy:
    def test_postgresql_drops_and_recreates_with_if_not_exists(self, caplog: pytest.LogCaptureFixture) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        crud.engine.dialect.identifier_preparer.quote.side_effect = lambda name: f'"{name}"'  # type: ignore[attr-defined]
        ddl = "CREATE INDEX ix_a ON public.t USING btree (a)"
        with (
            patch(_SECONDARY_INDEXES, return_value=[("ix_a", ddl)]),
            caplog.at_level(logging.WARNING),
            crud.maintenance_scope("t", disable_constraints=False, disable_indexes="secondary") as ms,
        ):
            assert 'DROP INDEX "ix_a"' in _sql_calls(conn)
        assert "CREATE INDEX IF NOT EXISTS ix_a ON public.t USING btree (a)" in _sql_calls(conn)
        assert ddl in caplog.text  # DDL de recuperación antes del DROP
        assert [(r.index_name, r.action) for r in ms.index_results] == [("ix_a", "recreated")]

    def test_oracle_marks_unusable_and_rebuilds_without_savepoint(self) -> None:
        crud, conn = _make_crud_for_dialect("oracle")
        crud.engine.dialect.identifier_preparer.quote.side_effect = lambda name: name  # type: ignore[attr-defined]
        with (
            patch(_SECONDARY_INDEXES, return_value=[("IX_A", None)]),
            crud.maintenance_scope("t", disable_constraints=False, disable_indexes=True),
        ):
            assert "ALTER INDEX IX_A UNUSABLE" in _sql_calls(conn)
        assert "ALTER INDEX IX_A REBUILD" in _sql_calls(conn)
        conn.begin_nested.assert_not_called()

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_innodb_with_commit_cadence_drops_and_adds_in_one_alter(self, dialect: str) -> None:
        crud, conn = _make_crud_for_dialect(dialect)
        crud.engine.dialect.identifier_preparer.quote.side_effect = lambda name: f"`{name}`"  # type: ignore[attr-defined]
        crud._batch_statement_executor.cadence.every = 10
        with (
            patch("util_bbdd.metadata.facts.storage_engine", return_value="InnoDB"),
            patch(_SECONDARY_INDEXES, return_value=[("ix_a", "INDEX `ix_a` (`a`)"), ("ix_b", "INDEX `ix_b` (`b`)")]),
            crud.maintenance_scope("t", disable_constraints=False, disable_indexes=True) as ms,
        ):
            pass
        assert [sql for sql in _sql_calls(conn) if sql.startswith("ALTER TABLE")] == [
            'ALTER TABLE "t" DROP INDEX `ix_a`',
            'ALTER TABLE "t" DROP INDEX `ix_b`',
            'ALTER TABLE "t" ADD INDEX `ix_a` (`a`), ADD INDEX `ix_b` (`b`)',
        ]
        assert [r.action for r in ms.index_results] == ["recreated", "recreated"]

    def test_unknown_index_mode_is_rejected(self) -> None:
        crud, _ = _make_crud_for_dialect("postgresql")
        with pytest.raises(ValueError, match="disable_indexes"):
            with crud.maintenance_scope("t", disable_indexes="todos"):  # type: ignore[arg-type]
                pass

    def test_failed_disable_is_skipped_and_not_restored(self, caplog: pytest.LogCaptureFixture) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        crud, conn = _make_mssql_crud_with_secondary_indexes(["ix_a", "ix_b"])

        def execute(stmt: object, *args: object, **kwargs: object) -> MagicMock:
            if 'ALTER INDEX "ix_a" ON "t" DISABLE' in str(stmt):
                raise SQLAlchemyError("locked")
            return MagicMock()

        conn.execute.side_effect = execute
        with caplog.at_level(logging.WARNING):
            with crud.maintenance_scope("t", disable_constraints=False, disable_indexes=True) as ms:
                pass
        assert 'ALTER INDEX "ix_a" ON "t" REBUILD' not in _sql_calls(conn)
        assert [r.index_name for r in ms.index_results] == ["ix_b"]
        assert any("ix_a" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# Orden de restauración: índices antes que constraints
# ---------------------------------------------------------------------------


class TestMaintenanceScopeRestoreOrder:
    def test_indexes_restored_before_constraints_mssql(self) -> None:
        crud, conn = _make_mssql_crud_with_secondary_indexes(["ix_a"])
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER INDEX "ix_a" ON "t" REBUILD' not in _sql_calls(conn)
        sqls = _sql_calls(conn)
        rebuild_idx = sqls.index('ALTER INDEX "ix_a" ON "t" REBUILD')
        check_idx = sqls.index('ALTER TABLE "t" WITH CHECK CHECK CONSTRAINT ALL')
        assert rebuild_idx < check_idx


# ---------------------------------------------------------------------------
# MaintenanceScopeResult — yield + optimization_applied + constraint_results
# ---------------------------------------------------------------------------


class TestMaintenanceScopeResult:
    def test_yields_maintenance_scope_result(self) -> None:
        crud, conn = _make_crud_for_dialect("mysql")
        with crud.maintenance_scope("t") as ms:
            assert isinstance(ms, MaintenanceScopeResult)

    def test_optimization_applied_true_for_mysql(self) -> None:
        crud, conn = _make_crud_for_dialect("mysql")
        with crud.maintenance_scope("t") as ms:
            pass
        assert ms.optimization_applied is True

    def test_optimization_applied_false_for_sqlite(self) -> None:
        crud, conn = _make_crud_for_dialect("sqlite")
        with crud.maintenance_scope("t") as ms:
            pass
        assert ms.optimization_applied is False

    def test_optimization_applied_true_mssql(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        with crud.maintenance_scope("t") as ms:
            pass
        assert ms.optimization_applied is True

    def test_optimization_applied_true_postgresql_when_privileged(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = True
        with crud.maintenance_scope("t") as ms:
            pass
        assert ms.optimization_applied is True

    def test_optimization_applied_false_postgresql_when_not_privileged(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = False
        with crud.maintenance_scope("t") as ms:
            pass
        assert ms.optimization_applied is False

    def test_constraint_results_populated_mysql(self) -> None:
        crud, conn = _make_crud_for_dialect("mysql")
        with crud.maintenance_scope("t", validate_fks_after=False) as ms:
            pass
        assert len(ms.constraint_results) == 1
        assert ms.constraint_results[0].constraint_name == "FOREIGN_KEY_CHECKS"
        assert ms.constraint_results[0].status == "unverified"

    def test_constraint_results_populated_mssql(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        with crud.maintenance_scope("t") as ms:
            pass
        assert len(ms.constraint_results) == 1
        assert ms.constraint_results[0].constraint_name == "ALL"
        assert ms.constraint_results[0].status == "enabled"

    def test_constraint_results_empty_when_no_constraints(self) -> None:
        crud, conn = _make_crud_for_dialect("sqlite")
        with crud.maintenance_scope("t") as ms:
            pass
        assert ms.constraint_results == []


# ---------------------------------------------------------------------------
# require_optimization
# ---------------------------------------------------------------------------


class TestMaintenanceScopeRequireOptimization:
    def test_raises_when_pg_not_privileged_and_required(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = False  # no privileges
        with pytest.raises(RuntimeError, match="privilegios"):
            with crud.maintenance_scope("t", require_optimization=True):
                pass

    def test_raises_does_not_log_warning_when_required(self, caplog: pytest.LogCaptureFixture) -> None:
        # A-01: solo log si NO se lanza; sin duplicado warning + exception
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = False
        with caplog.at_level(logging.WARNING):
            with pytest.raises(RuntimeError):
                with crud.maintenance_scope("t", require_optimization=True):
                    pass
        assert not any("privilegios" in msg for msg in caplog.messages)

    def test_not_required_logs_warning_instead_of_raising(self, caplog: pytest.LogCaptureFixture) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = False
        with caplog.at_level(logging.WARNING):
            with crud.maintenance_scope("t", require_optimization=False):
                pass
        assert any("privilegios" in msg for msg in caplog.messages)

    def test_no_raise_when_pg_privileged_and_required(self) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = True
        with crud.maintenance_scope("t", require_optimization=True):
            pass  # must not raise

    def test_no_raise_for_sqlite_without_require(self) -> None:
        crud, conn = _make_crud_for_dialect("sqlite")
        with crud.maintenance_scope("t", require_optimization=False):
            pass  # must not raise

    def test_raises_for_unsupported_dialect_when_required(self) -> None:
        # A-05: dialecto no soportado (sqlite) con require_optimization=True
        crud, conn = _make_crud_for_dialect("sqlite")
        with pytest.raises(RuntimeError, match="sqlite"):
            with crud.maintenance_scope("t", require_optimization=True):
                pass

    def test_no_raise_for_mysql_required(self) -> None:
        crud, conn = _make_crud_for_dialect("mysql")
        with crud.maintenance_scope("t", require_optimization=True):
            pass  # MySQL always applies FK_CHECKS optimization


# ---------------------------------------------------------------------------
# Oracle
# ---------------------------------------------------------------------------


def _snapshot(fks: list[dict] | None = None, checks: list[str] = (), uniques: list[str] = ()) -> SchemaSnapshot:  # type: ignore[assignment]
    """Snapshot de la tabla ``t`` como lo devuelve ``BulkCrud._table_snapshot`` (catálogo de metadata/, C5)."""
    return SchemaSnapshot(
        "test",
        "s",
        {
            Kind.FOREIGN_KEYS: tuple(
                ForeignKeyMeta(
                    "t",
                    fk["name"],
                    tuple(fk.get("constrained_columns", ["c"])),
                    fk.get("referred_schema") or "s",
                    fk.get("referred_table", "p"),
                    tuple(fk.get("referred_columns", ["id"])),
                )
                for fk in fks or []
            ),
            Kind.CHECKS: tuple(CheckMeta("t", n, "x > 0") for n in checks),
            Kind.UNIQUES: tuple(UniqueMeta("t", n, ("c",)) for n in uniques),
        },
    )


def _make_oracle_crud(
    fk_names: list[str] | None = None,
    check_names: list[str] | None = None,
    unique_names: list[str] | None = None,
) -> tuple[BulkCrud, MagicMock, SchemaSnapshot]:
    """Construye un BulkCrud para Oracle con el snapshot de la tabla simulado."""
    crud, conn = _make_crud_for_dialect("oracle")
    snapshot = _snapshot([{"name": n} for n in fk_names or []], check_names or [], unique_names or [])
    crud.engine.dialect.identifier_preparer.quote_identifier.side_effect = lambda x: f'"{x}"'
    return crud, conn, snapshot


class TestMaintenanceScopeOracle:
    def test_disable_fk_constraint(self) -> None:
        crud, conn, mock_insp = _make_oracle_crud(fk_names=["fk_user"])
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with crud.maintenance_scope("t"):
                assert 'ALTER TABLE "t" DISABLE CONSTRAINT "fk_user"' in _sql_calls(conn)

    def test_enable_validate_constraint_on_exit(self) -> None:
        crud, conn, mock_insp = _make_oracle_crud(fk_names=["fk_user"])
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with crud.maintenance_scope("t"):
                pass
        assert 'ALTER TABLE "t" ENABLE VALIDATE CONSTRAINT "fk_user"' in _sql_calls(conn)

    def test_disable_before_enable_order(self) -> None:
        crud, conn, mock_insp = _make_oracle_crud(fk_names=["fk_user"])
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with crud.maintenance_scope("t"):
                pass
        sqls = _sql_calls(conn)
        assert sqls.index('ALTER TABLE "t" DISABLE CONSTRAINT "fk_user"') < sqls.index(
            'ALTER TABLE "t" ENABLE VALIDATE CONSTRAINT "fk_user"'
        )

    def test_multiple_constraints_disabled_and_reenabled(self) -> None:
        crud, conn, mock_insp = _make_oracle_crud(
            fk_names=["fk_user"],
            check_names=["chk_status"],
            unique_names=["uk_email"],
        )
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with crud.maintenance_scope("t"):
                pass
        sqls = _sql_calls(conn)
        for name in ("fk_user", "chk_status", "uk_email"):
            assert f'ALTER TABLE "t" DISABLE CONSTRAINT "{name}"' in sqls
            assert f'ALTER TABLE "t" ENABLE VALIDATE CONSTRAINT "{name}"' in sqls

    def test_sys_c_check_constraints_skipped(self) -> None:
        crud, conn, mock_insp = _make_oracle_crud(check_names=["SYS_C0012345", "chk_visible"])
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with crud.maintenance_scope("t"):
                pass
        sqls = _sql_calls(conn)
        assert not any("SYS_C0012345" in s for s in sqls)
        assert any("chk_visible" in s for s in sqls)

    def test_no_oracle_sql_when_no_constraints(self) -> None:
        crud, conn, mock_insp = _make_oracle_crud()
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with crud.maintenance_scope("t"):
                pass
        sqls = _sql_calls(conn)
        assert not any("DISABLE CONSTRAINT" in s for s in sqls)
        assert not any("ENABLE VALIDATE" in s for s in sqls)

    def test_enable_constraint_on_exception_after_the_session_rollback(self) -> None:
        """H-31: el DDL de Oracle confirmaría lo pendiente; se reactiva al terminar la sesión, en otra conexión."""
        crud, conn, mock_insp = _make_oracle_crud(fk_names=["fk_user"])
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with pytest.raises(RuntimeError):
                with crud.maintenance_scope("t"):
                    raise RuntimeError("fail")
        enable = 'ALTER TABLE "t" ENABLE VALIDATE CONSTRAINT "fk_user"'
        assert enable not in _sql_calls(conn)  # no en la transacción de la sesión
        assert len(crud._session.after_end) == 1
        assert crud._session.run_after_end() == []
        fresh = crud.engine.connect.return_value.__enter__.return_value
        assert enable in _sql_calls(fresh)
        fresh.commit.assert_called_once()

    def test_warning_on_disable_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        crud, conn, mock_insp = _make_oracle_crud(fk_names=["fk_bad"])
        conn.execute.side_effect = SQLAlchemyError("permission denied")
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with caplog.at_level(logging.WARNING):
                with crud.maintenance_scope("t"):
                    pass
        assert any("fk_bad" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# PostgreSQL — orphan check (audit H-01, 2026-09-27)
# ---------------------------------------------------------------------------


def _make_pg_inspector_mock(
    fks: list[dict] | None = None,
    orphan_found: bool = False,
) -> SchemaSnapshot:
    return _snapshot(fks)


class TestMaintenanceScopePostgreSQLOrphanCheck:
    def _make_pg_crud_with_fk(self) -> tuple[BulkCrud, MagicMock]:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = True  # can_disable_pg_triggers
        crud.engine.dialect.identifier_preparer.quote.side_effect = lambda x: f'"{x}"'
        crud.engine.dialect.identifier_preparer.quote_identifier.side_effect = lambda x: f'"{x}"'
        return crud, conn

    def test_orphan_check_warns_when_orphan_found(self, caplog: pytest.LogCaptureFixture) -> None:
        crud, conn = self._make_pg_crud_with_fk()
        mock_insp = _make_pg_inspector_mock(
            fks=[
                {
                    "name": "fk_user",
                    "constrained_columns": ["user_id"],
                    "referred_table": "users",
                    "referred_columns": ["id"],
                    "referred_schema": None,
                }
            ]
        )
        conn.execute.return_value.first.return_value = MagicMock(name="orphan_row")
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with caplog.at_level(logging.WARNING):
                with crud.maintenance_scope("t"):
                    pass
        assert any("fk_user" in msg and "violaciones" in msg for msg in caplog.messages)

    def test_orphan_check_no_warning_when_no_orphans(self, caplog: pytest.LogCaptureFixture) -> None:
        crud, conn = self._make_pg_crud_with_fk()
        mock_insp = _make_pg_inspector_mock(
            fks=[
                {
                    "name": "fk_user",
                    "constrained_columns": ["user_id"],
                    "referred_table": "users",
                    "referred_columns": ["id"],
                    "referred_schema": None,
                }
            ]
        )
        conn.execute.return_value.first.return_value = None
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with caplog.at_level(logging.WARNING):
                with crud.maintenance_scope("t"):
                    pass
        assert not any("violaciones" in msg for msg in caplog.messages)

    def test_orphan_check_skipped_when_not_privileged(self, caplog: pytest.LogCaptureFixture) -> None:
        crud, conn = _make_crud_for_dialect("postgresql")
        conn.execute.return_value.scalar.return_value = False  # no privileges → triggers not disabled
        mock_insp = _make_pg_inspector_mock(
            fks=[
                {
                    "name": "fk_user",
                    "constrained_columns": ["user_id"],
                    "referred_table": "users",
                    "referred_columns": ["id"],
                    "referred_schema": None,
                }
            ]
        )
        conn.execute.return_value.first.return_value = MagicMock(name="orphan")
        with patch.object(BulkCrud, "_table_snapshot", return_value=mock_insp):
            with caplog.at_level(logging.WARNING):
                with crud.maintenance_scope("t"):
                    pass
        assert not any("violaciones" in msg for msg in caplog.messages)

    def test_orphan_check_silently_skipped_when_inspect_raises(self, caplog: pytest.LogCaptureFixture) -> None:
        """Sin catálogo para el engine: sin WARNING, constraint_results retorna unverified (A-06)."""
        crud, conn = self._make_pg_crud_with_fk()
        with patch.object(BulkCrud, "_table_snapshot", side_effect=LookupError("sin catálogo")):
            with caplog.at_level(logging.WARNING):
                with crud.maintenance_scope("t") as ms:
                    pass
        assert not any("violaciones" in msg for msg in caplog.messages)
        assert len(ms.constraint_results) == 1
        assert ms.constraint_results[0].status == "unverified"
        assert ms.constraint_results[0].constraint_name == "*"


# ---------------------------------------------------------------------------
# v3.3.0: disable_indexes="all" y validate_fks_after
# ---------------------------------------------------------------------------

_FK_USER = {
    "name": "fk_user",
    "constrained_columns": ["user_id"],
    "referred_table": "users",
    "referred_columns": ["id"],
    "referred_schema": None,
}


class TestMaintenanceScopeAllMode:
    def test_all_requires_disable_constraints(self) -> None:
        crud, _ = _make_crud_for_dialect("mssql")
        with pytest.raises(ValueError, match="disable_constraints"):
            with crud.maintenance_scope("t", disable_constraints=False, disable_indexes="all"):
                pass

    def test_all_rejects_isolate(self, tmp_path: Any) -> None:
        from util_bbdd.bulk.options import RejectOptions

        crud = BulkCrud(_make_sqlite_engine(), rejects=RejectOptions(on_error="isolate", csv_path=tmp_path / "r.csv"))
        with pytest.raises(ValueError, match="isolate"):
            with crud.maintenance_scope("t", disable_indexes="all"):
                pass

    def test_failed_unique_rebuild_raises_after_restoring_constraints(self, caplog: pytest.LogCaptureFixture) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        from util_bbdd.exceptions import IndexRebuildError
        from util_bbdd.metadata import facts

        crud, conn = _make_mssql_crud_with_secondary_indexes([])
        duplicates = MagicMock()
        duplicates.fetchall.return_value = [("X", 2)]

        def execute(stmt: object, *args: object, **kwargs: object) -> MagicMock:
            sql = str(stmt)
            if 'ALTER INDEX "uq_code" ON "t" REBUILD' in sql:
                raise SQLAlchemyError("duplicate key")
            return duplicates if sql.startswith("SELECT TOP 5") else MagicMock()

        conn.execute.side_effect = execute
        with (
            patch.object(
                facts, "unique_indexes", return_value=[facts.UniqueIndexFact("uq_code", "unique_constraint", ("code",))]
            ),
            patch.object(facts, "inbound_foreign_keys", return_value=[]),
            pytest.raises(IndexRebuildError) as info,
        ):
            with caplog.at_level(logging.WARNING), crud.maintenance_scope("t", disable_indexes="all") as ms:
                pass
        sqls = _sql_calls(conn)
        assert 'ALTER TABLE "t" WITH CHECK CHECK CONSTRAINT ALL' in sqls  # constraints restauradas antes del error
        assert info.value.duplicates == {"t.uq_code": ["X → 2"]}
        assert [r.action for r in ms.index_results] == ["failed"]
        assert any("disable_indexes='all'" in msg for msg in caplog.messages)


class TestMaintenanceScopeValidateFksAfter:
    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_reports_each_fk_instead_of_unverified(self, dialect: str) -> None:
        crud, conn = _make_crud_for_dialect(dialect)
        crud.engine.dialect.identifier_preparer.quote.side_effect = lambda x: f"`{x}`"
        crud.engine.dialect.identifier_preparer.quote_identifier.side_effect = lambda x: f"`{x}`"
        conn.execute.return_value.first.return_value = MagicMock(name="orphan")
        with patch.object(BulkCrud, "_table_snapshot", return_value=_make_pg_inspector_mock(fks=[_FK_USER])):
            with crud.maintenance_scope("t", validate_fks_after=True) as ms:
                pass
        assert [(r.constraint_name, r.status) for r in ms.constraint_results] == [("fk_user", "failed")]
        assert any("LIMIT 1" in sql and "NOT EXISTS" in sql for sql in _sql_calls(conn))

    def test_false_keeps_the_single_unverified_row(self) -> None:
        crud, _ = _make_crud_for_dialect("mysql")
        with crud.maintenance_scope("t", validate_fks_after=False) as ms:
            pass
        assert [(r.constraint_name, r.status) for r in ms.constraint_results] == [("FOREIGN_KEY_CHECKS", "unverified")]

    def test_validation_is_on_by_default(self) -> None:
        """v3.4.0: ``validate_fks_after=True`` por defecto (≈1 % de la carga medido en G0)."""
        crud, conn = _make_crud_for_dialect("mysql")
        crud.engine.dialect.identifier_preparer.quote.side_effect = lambda x: f"`{x}`"
        crud.engine.dialect.identifier_preparer.quote_identifier.side_effect = lambda x: f"`{x}`"
        conn.execute.return_value.first.return_value = None
        with patch.object(BulkCrud, "_table_snapshot", return_value=_make_pg_inspector_mock(fks=[_FK_USER])):
            with crud.maintenance_scope("t") as ms:
                pass
        assert [(r.constraint_name, r.status) for r in ms.constraint_results] == [("fk_user", "enabled")]
