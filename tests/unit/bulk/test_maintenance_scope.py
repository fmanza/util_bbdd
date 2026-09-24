"""Tests para BulkCrud.maintenance_scope y sus helpers privados de motor."""

from __future__ import annotations

import logging

from unittest.mock import MagicMock

import pytest

from sqlalchemy import Engine, create_engine

from util_bbdd.bulk.crud import BulkCrud

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
    crud._batch_statement_executor._active_connection = conn

    mock_engine: MagicMock = MagicMock(name="engine")
    mock_engine.dialect.name = dialect
    mock_engine.dialect.identifier_preparer.format_table.return_value = '"t"'
    crud.engine = mock_engine  # type: ignore[assignment]

    table_mock: MagicMock = MagicMock(name="table")
    table_mock.name = "t"
    table_mock.schema = None
    crud._table_cache["t"] = table_mock  # type: ignore[assignment]

    return crud, conn


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
        crud, conn = _make_crud_for_dialect("mssql")
        conn.execute.return_value.scalar.return_value = 0
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER INDEX ALL ON "t" DISABLE' in _sql_calls(conn)

    def test_rebuild_indexes_on_exit_when_disabled(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        conn.execute.return_value.scalar.return_value = 0
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER INDEX ALL ON "t" REBUILD' not in _sql_calls(conn)
        assert 'ALTER INDEX ALL ON "t" REBUILD' in _sql_calls(conn)

    def test_disable_before_rebuild_order(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        conn.execute.return_value.scalar.return_value = 0
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER INDEX ALL ON "t" DISABLE' in _sql_calls(conn)
        sqls = _sql_calls(conn)
        assert sqls.index('ALTER INDEX ALL ON "t" DISABLE') < sqls.index('ALTER INDEX ALL ON "t" REBUILD')

    def test_skip_disable_indexes_when_clustered_exists(self, caplog: pytest.LogCaptureFixture) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        conn.execute.return_value.scalar.return_value = 1
        with caplog.at_level(logging.WARNING):
            with crud.maintenance_scope("t", disable_indexes=True):
                assert 'ALTER INDEX ALL ON "t" DISABLE' not in _sql_calls(conn)
        sqls = _sql_calls(conn)
        assert 'ALTER INDEX ALL ON "t" DISABLE' not in sqls
        assert any("CLUSTERED" in msg for msg in caplog.messages)

    def test_no_rebuild_when_clustered_prevented_disable(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        conn.execute.return_value.scalar.return_value = 1
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER INDEX ALL ON "t" DISABLE' not in _sql_calls(conn)
        assert 'ALTER INDEX ALL ON "t" REBUILD' not in _sql_calls(conn)


# ---------------------------------------------------------------------------
# Orden de restauración: índices antes que constraints
# ---------------------------------------------------------------------------


class TestMaintenanceScopeRestoreOrder:
    def test_indexes_restored_before_constraints_mssql(self) -> None:
        crud, conn = _make_crud_for_dialect("mssql")
        conn.execute.return_value.scalar.return_value = 0
        with crud.maintenance_scope("t", disable_indexes=True):
            assert 'ALTER INDEX ALL ON "t" REBUILD' not in _sql_calls(conn)
        sqls = _sql_calls(conn)
        rebuild_idx = sqls.index('ALTER INDEX ALL ON "t" REBUILD')
        check_idx = sqls.index('ALTER TABLE "t" WITH CHECK CHECK CONSTRAINT ALL')
        assert rebuild_idx < check_idx
