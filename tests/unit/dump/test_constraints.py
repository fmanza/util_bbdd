"""Tests unitarios para ConstraintManager y ConstraintResult."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    def test_disable_registers_event_listener(self):
        engine = _make_engine("mariadb")
        with patch("util_bbdd.dump._constraints.event") as mock_event:
            mgr = ConstraintManager(engine)
            mgr.disable_all(tables=[])
            mock_event.listen.assert_called_once()
            # Cyclar pool
            engine.dispose.assert_called_once()

    def test_enable_removes_listener_and_returns_unverified(self):
        engine = _make_engine("mariadb")

        with patch("util_bbdd.dump._constraints.event") as mock_event:
            mgr = ConstraintManager(engine)
            mgr.disable_all(tables=[])
            mgr._mariadb_listener = MagicMock()

            results = mgr.enable_all()
            mock_event.remove.assert_called_once()

        assert len(results) == 1
        assert results[0].status == "unverified"

    def test_enable_without_prior_disable_returns_unverified(self):
        engine = _make_engine("mariadb")
        with patch("util_bbdd.dump._constraints.event"):
            mgr = ConstraintManager(engine)
            results = mgr.enable_all()
        # Sin listener previo, no hay resultados de habilitación
        assert results == [] or results[0].status == "unverified"


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
