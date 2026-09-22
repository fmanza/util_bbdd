"""Tests unitarios para ConstraintManager y ConstraintResult."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.exc import SQLAlchemyError

from util_bbdd._core.exceptions import DumpConstraintError
from util_bbdd.dump._constraints import ConstraintManager, ConstraintResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_engine(dialect_name: str) -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = dialect_name
    engine.dialect.identifier_preparer.quote.side_effect = lambda name: name
    conn_ctx = MagicMock()
    conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
    conn_ctx.__exit__ = MagicMock(return_value=False)
    engine.connect.return_value = conn_ctx
    engine.begin.return_value = conn_ctx
    return engine


# ---------------------------------------------------------------------------
# ConstraintResult
# ---------------------------------------------------------------------------


class TestConstraintResult:
    def test_fields_defaults(self):
        cr = ConstraintResult(
            table_name="orders",
            constraint_name="fk_orders_customers",
            dialect="mssql",
            status="enabled",
        )
        assert cr.error_msg == ""
        assert cr.status == "enabled"

    def test_failed_status(self):
        cr = ConstraintResult(
            table_name="t",
            constraint_name="c",
            dialect="oracle",
            status="failed",
            error_msg="ORA-02298",
        )
        assert cr.status == "failed"
        assert "ORA-02298" in cr.error_msg


# ---------------------------------------------------------------------------
# ConstraintManager — dialectos no soportados
# ---------------------------------------------------------------------------


class TestConstraintManagerUnsupportedDialect:
    def test_disable_unsupported_dialect_is_noop(self, caplog):
        engine = _make_engine("sqlite")
        mgr = ConstraintManager(engine)
        with caplog.at_level("WARNING"):
            mgr.disable_all(tables=["t1", "t2"])
        assert "no soportado" in caplog.text.lower()

    def test_enable_unsupported_dialect_returns_empty(self):
        engine = _make_engine("sqlite")
        mgr = ConstraintManager(engine)
        results = mgr.enable_all()
        assert results == []


# ---------------------------------------------------------------------------
# ConstraintManager — SQL Server
# ---------------------------------------------------------------------------


class TestConstraintManagerSqlServer:
    def test_disable_executes_nocheck_per_table(self):
        engine = _make_engine("mssql")
        mgr = ConstraintManager(engine)
        mgr.disable_all(tables=["orders", "items"])

        executed_sql = [str(call_args[0][0]) for call_args in engine.begin.return_value.execute.call_args_list]
        assert any("NOCHECK CONSTRAINT ALL" in s for s in executed_sql)

    def test_disable_empty_tables_skips_sql(self):
        engine = _make_engine("mssql")
        mgr = ConstraintManager(engine)
        mgr.disable_all(tables=[])
        engine.begin.return_value.execute.assert_not_called()

    def test_enable_returns_enabled_on_success(self):
        engine = _make_engine("mssql")
        mgr = ConstraintManager(engine)
        mgr._nocheck_tables = ["orders"]

        results = mgr.enable_all()

        assert len(results) == 1
        assert results[0].status == "enabled"
        assert results[0].table_name == "orders"

    def test_enable_returns_failed_on_sqlalchemy_error(self):
        from sqlalchemy.exc import SQLAlchemyError

        engine = _make_engine("mssql")
        engine.connect.return_value.__enter__.return_value.execute.side_effect = SQLAlchemyError("FK violation")
        mgr = ConstraintManager(engine)
        mgr._nocheck_tables = ["orders"]

        results = mgr.enable_all()

        assert results[0].status == "failed"
        assert "FK violation" in results[0].error_msg

    def test_context_manager_calls_enable_on_exit(self):
        engine = _make_engine("mssql")
        mgr = ConstraintManager(engine)
        mgr._nocheck_tables = ["t1"]

        with mgr:
            pass  # no disable called inside; testing __exit__ only

        assert isinstance(mgr.constraint_results, list)


# ---------------------------------------------------------------------------
# ConstraintManager — MariaDB
# ---------------------------------------------------------------------------


class TestConstraintManagerMariaDB:
    def test_disable_registers_checkout_and_checkin_without_dispose(self):
        engine = _make_engine("mariadb")
        with patch("util_bbdd.dump._constraints.event") as mock_event:
            mgr = ConstraintManager(engine)
            mgr.disable_all(tables=[])
            # Se registran listeners checkout (FK=0) y checkin (FK=1)
            assert mock_event.listen.call_count == 2
            registered_events = {call.args[1] for call in mock_event.listen.call_args_list}
            assert registered_events == {"checkout", "checkin"}
            # No se cicla el pool: dispose() ya no se usa (seguro bajo concurrencia)
            engine.dispose.assert_not_called()

    def test_disable_sets_fk_off_on_checkout_and_fk_on_on_checkin(self):
        """Los listeners ejecutan SET SESSION FOREIGN_KEY_CHECKS sobre la conexión DBAPI."""
        engine = _make_engine("mariadb")
        captured: dict[str, Callable[..., None]] = {}

        def _capture(_engine: object, event_name: str, fn: Callable[..., None]) -> None:
            captured[event_name] = fn

        with patch("util_bbdd.dump._constraints.event") as mock_event:
            mock_event.listen.side_effect = _capture
            mgr = ConstraintManager(engine)
            mgr.disable_all(tables=[])

        dbapi_conn = MagicMock()
        cursor = dbapi_conn.cursor.return_value
        captured["checkout"](dbapi_conn, MagicMock(), MagicMock())
        cursor.execute.assert_called_with("SET SESSION FOREIGN_KEY_CHECKS = 0")

        dbapi_conn2 = MagicMock()
        cursor2 = dbapi_conn2.cursor.return_value
        captured["checkin"](dbapi_conn2, MagicMock())
        cursor2.execute.assert_called_with("SET SESSION FOREIGN_KEY_CHECKS = 1")

    def test_enable_removes_both_listeners_and_returns_unverified(self):
        engine = _make_engine("mariadb")

        with patch("util_bbdd.dump._constraints.event") as mock_event:
            mgr = ConstraintManager(engine)
            mgr.disable_all(tables=[])

            results = mgr.enable_all()
            assert mock_event.remove.call_count == 2
            # No se cicla el pool al reactivar
            engine.dispose.assert_not_called()

        assert len(results) == 1
        assert results[0].status == "unverified"

    def test_enable_without_prior_disable_returns_empty(self):
        engine = _make_engine("mariadb")
        with patch("util_bbdd.dump._constraints.event"):
            mgr = ConstraintManager(engine)
            results = mgr.enable_all()
        # Sin listener previo, no hay resultados de habilitación
        assert results == []


# ---------------------------------------------------------------------------
# ConstraintManager — Oracle (filtrado SYS_C)
# ---------------------------------------------------------------------------


class TestConstraintManagerOracle:
    def _make_oracle_engine_with_inspector(self, constraints: list[dict]) -> tuple[MagicMock, MagicMock]:
        engine = _make_engine("oracle")
        insp = MagicMock()
        insp.get_foreign_keys.return_value = constraints
        insp.get_check_constraints.return_value = []
        insp.get_unique_constraints.return_value = []
        return engine, insp

    def test_disable_skips_sys_c_constraints(self):
        # SYS_C* son nombres auto-generados por Oracle en check constraints, no en FKs
        engine, _ = self._make_oracle_engine_with_inspector([{"name": "FK_ORDERS_CUST"}])
        insp = MagicMock()
        insp.get_foreign_keys.return_value = [{"name": "FK_ORDERS_CUST"}]
        insp.get_check_constraints.return_value = [{"name": "SYS_C0012345"}, {"name": "CK_STATUS"}]
        insp.get_unique_constraints.return_value = []
        with patch("util_bbdd.dump._constraints.inspect", return_value=insp):
            mgr = ConstraintManager(engine)
            mgr._disable_oracle(tables=["orders"])

        # SYS_C0012345 filtrado; FK_ORDERS_CUST y CK_STATUS sí deshabilitados
        names = {c[1] for c in mgr._disabled}
        assert "SYS_C0012345" not in names
        assert {"FK_ORDERS_CUST", "CK_STATUS"} == names

    def test_disable_registers_all_non_system_constraints(self):
        engine, insp = self._make_oracle_engine_with_inspector(
            [
                {"name": "FK_A"},
                {"name": "FK_B"},
            ],
        )
        with patch("util_bbdd.dump._constraints.inspect", return_value=insp):
            mgr = ConstraintManager(engine)
            mgr._disable_oracle(tables=["t1"])

        assert {c[1] for c in mgr._disabled} == {"FK_A", "FK_B"}


# ---------------------------------------------------------------------------
# ConstraintManager — PostgreSQL
# ---------------------------------------------------------------------------


class TestConstraintManagerPostgreSQL:
    def test_disable_stores_disabled_pg_list(self):
        engine = _make_engine("postgresql")
        mgr = ConstraintManager(engine)
        mgr.disable_all(tables=["orders", "items"])

        assert "orders" in mgr._disabled_pg
        assert "items" in mgr._disabled_pg

    def test_disable_with_permission_error_skips_table(self):
        from sqlalchemy.exc import SQLAlchemyError

        engine = _make_engine("postgresql")
        engine.connect.return_value.__enter__.return_value.execute.side_effect = SQLAlchemyError("permission denied")
        mgr = ConstraintManager(engine)
        mgr.disable_all(tables=["orders"])

        assert "orders" not in mgr._disabled_pg

    def test_enable_only_reenables_disabled_tables(self):
        engine = _make_engine("postgresql")
        insp = MagicMock()
        insp.get_foreign_keys.return_value = []
        with patch("util_bbdd.dump._constraints.inspect", return_value=insp):
            mgr = ConstraintManager(engine)
            mgr._disabled_pg = ["orders"]
            results = mgr.enable_all()

        assert results == []

    def test_enable_empty_disabled_list_returns_empty(self):
        engine = _make_engine("postgresql")
        insp = MagicMock()
        insp.get_foreign_keys.return_value = []
        with patch("util_bbdd.dump._constraints.inspect", return_value=insp):
            mgr = ConstraintManager(engine)
            results = mgr.enable_all()

        assert results == []

    def test_enable_validates_fk_constraints(self):
        engine = _make_engine("postgresql")
        insp = MagicMock()
        insp.get_foreign_keys.return_value = [{"name": "fk_orders_cust"}]
        with patch("util_bbdd.dump._constraints.inspect", return_value=insp):
            mgr = ConstraintManager(engine)
            mgr._disabled_pg = ["orders"]
            results = mgr.enable_all()

        assert len(results) == 1
        assert results[0].constraint_name == "fk_orders_cust"
        assert results[0].status == "enabled"

    def test_enable_fk_failure_returns_failed_status(self):
        from sqlalchemy.exc import SQLAlchemyError

        engine = _make_engine("postgresql")
        conn_mock = engine.connect.return_value.__enter__.return_value

        # Forzar fallo solo en VALIDATE CONSTRAINT, no en SAVEPOINT ni ROLLBACK
        def _selective_fail(sql: object, *args: object, **kwargs: object) -> None:
            if "VALIDATE CONSTRAINT" in str(sql):
                raise SQLAlchemyError("fk violation")

        conn_mock.execute.side_effect = _selective_fail
        insp = MagicMock()
        insp.get_foreign_keys.return_value = [{"name": "fk_orders_cust"}]
        with patch("util_bbdd.dump._constraints.inspect", return_value=insp):
            mgr = ConstraintManager(engine)
            mgr._disabled_pg = ["orders"]
            results = mgr.enable_all()

        assert len(results) == 1
        assert results[0].status == "failed"
        assert "fk violation" in results[0].error_msg

    def test_enable_trigger_failure_skips_fk_validation(self):
        """C3: si ENABLE TRIGGER falla, no se intenta VALIDATE CONSTRAINT."""
        from sqlalchemy.exc import SQLAlchemyError

        engine = _make_engine("postgresql")
        conn_mock = engine.connect.return_value.__enter__.return_value

        def _trigger_fail(sql: object, *args: object, **kwargs: object) -> None:
            if "ENABLE TRIGGER" in str(sql):
                raise SQLAlchemyError("permission denied")

        conn_mock.execute.side_effect = _trigger_fail
        insp = MagicMock()
        insp.get_foreign_keys.return_value = [{"name": "fk_orders_cust"}]
        with patch("util_bbdd.dump._constraints.inspect", return_value=insp):
            mgr = ConstraintManager(engine)
            mgr._disabled_pg = ["orders"]
            results = mgr.enable_all()

        # FK validation skipped → no results
        assert results == []
        # Inspector no consultado para FK (tabla excluida)
        insp.get_foreign_keys.assert_not_called()

    def test_enable_without_prior_disable_returns_empty(self):
        engine = _make_engine("postgresql")
        insp = MagicMock()
        insp.get_foreign_keys.return_value = []
        with patch("util_bbdd.dump._constraints.inspect", return_value=insp):
            mgr = ConstraintManager(engine)
            results = mgr.enable_all()

        assert results == []
        insp.get_foreign_keys.assert_not_called()


# ---------------------------------------------------------------------------
# ConstraintManager — quoting helpers
# ---------------------------------------------------------------------------


class TestConstraintManagerQuoting:
    def test_qt_without_schema(self):
        engine = _make_engine("mssql")
        engine.dialect.identifier_preparer.quote.side_effect = lambda n: f"[{n}]"
        mgr = ConstraintManager(engine)
        assert mgr._qt("my_table") == "[my_table]"

    def test_qt_with_schema(self):
        engine = _make_engine("mssql")
        engine.dialect.identifier_preparer.quote.side_effect = lambda n: f"[{n}]"
        mgr = ConstraintManager(engine, schema="dbo")
        assert mgr._qt("orders") == "[dbo].[orders]"

    def test_qi_delegates_to_preparer(self):
        engine = _make_engine("postgresql")
        engine.dialect.identifier_preparer.quote.side_effect = lambda n: f'"{n}"'
        mgr = ConstraintManager(engine)
        assert mgr._qi("order") == '"order"'


# ---------------------------------------------------------------------------
# ConstraintManager — __exit__ silencia enable_all() pero propaga excepción original
# ---------------------------------------------------------------------------


class TestConstraintManagerExitBehavior:
    def test_exit_propagates_original_exception_when_enable_all_raises(self):
        """TC6: si enable_all() lanza dentro de __exit__, la excepción original del bloque with
        sigue propagándose; la excepción de enable_all() solo se loguea."""
        engine = _make_engine("mssql")
        mgr = ConstraintManager(engine)

        # Forzar que enable_all() falle
        mgr.enable_all = MagicMock(side_effect=RuntimeError("enable_all broken"))

        with pytest.raises(ValueError, match="original error"):
            with mgr:
                raise ValueError("original error")

    def test_exit_constraint_results_accessible_even_when_body_raises(self):
        """__exit__ asigna constraint_results aunque el bloque with lance excepción."""
        engine = _make_engine("mssql")
        mgr = ConstraintManager(engine)
        mgr._nocheck_tables = ["orders"]

        with pytest.raises(RuntimeError):
            with mgr:
                raise RuntimeError("body error")

        assert isinstance(mgr.constraint_results, list)


# ---------------------------------------------------------------------------
# ConstraintManager — FND-03/FND-04: fallos no recuperables → DumpConstraintError
# ---------------------------------------------------------------------------


class TestConstraintManagerDumpConstraintError:
    """FND-03/FND-04 (AUDIT_CODE 2026-09-22, decisión confirmada por el usuario):
    un fallo real (no por-constraint) desactivando/reactivando constraints debe
    surgir como DumpConstraintError, no como SQLAlchemyError crudo."""

    def test_disable_all_wraps_sqlalchemy_error_in_dump_constraint_error(self):
        engine = _make_engine("mssql")
        engine.begin.return_value.execute.side_effect = SQLAlchemyError("connection lost")
        mgr = ConstraintManager(engine)

        with pytest.raises(DumpConstraintError, match="connection lost"):
            mgr.disable_all(tables=["orders"])

    def test_disable_all_dump_constraint_error_preserves_cause(self):
        engine = _make_engine("mssql")
        original = SQLAlchemyError("connection lost")
        engine.begin.return_value.execute.side_effect = original
        mgr = ConstraintManager(engine)

        with pytest.raises(DumpConstraintError) as exc_info:
            mgr.disable_all(tables=["orders"])

        assert exc_info.value.__cause__ is original

    def test_enable_all_wraps_sqlalchemy_error_in_dump_constraint_error(self):
        engine = _make_engine("mssql")
        mgr = ConstraintManager(engine)
        mgr._nocheck_tables = ["orders"]
        engine.connect.return_value.execute.side_effect = SQLAlchemyError("connection lost")
        # No debe entrar en el except SQLAlchemyError por-tabla ya existente: forzamos
        # el fallo directamente en el dispatcher simulando un error inesperado.
        mgr._enable_sqlserver = MagicMock(side_effect=SQLAlchemyError("connection lost"))  # type: ignore[method-assign]

        with pytest.raises(DumpConstraintError, match="connection lost"):
            mgr.enable_all()

    def test_disable_all_non_sqlalchemy_error_propagates_unwrapped(self):
        """Solo SQLAlchemyError se envuelve; otros errores (p.ej. bugs) se propagan tal cual."""
        engine = _make_engine("mssql")
        engine.begin.return_value.execute.side_effect = RuntimeError("unexpected bug")
        mgr = ConstraintManager(engine)

        with pytest.raises(RuntimeError, match="unexpected bug"):
            mgr.disable_all(tables=["orders"])
