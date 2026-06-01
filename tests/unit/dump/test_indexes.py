"""Tests unitarios para IndexManager."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.dump._indexes import IndexManager
from util_bbdd.dump._models import IndexActionResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_engine(dialect_name: str) -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = dialect_name
    engine.dialect.identifier_preparer.quote.side_effect = lambda name: f"[{name}]"
    conn = MagicMock()
    conn_ctx = MagicMock()
    conn_ctx.__enter__ = MagicMock(return_value=conn)
    conn_ctx.__exit__ = MagicMock(return_value=False)
    engine.connect.return_value = conn_ctx
    return engine, conn


def _executed_sql(conn: MagicMock) -> list[str]:
    return [str(call.args[0]) for call in conn.execute.call_args_list]


# ---------------------------------------------------------------------------
# Dialectos no soportados
# ---------------------------------------------------------------------------


class TestIndexManagerUnsupported:
    def test_mariadb_disable_is_noop_with_warning(self, caplog):
        engine, conn = _make_engine("mariadb")
        mgr = IndexManager(engine)
        with caplog.at_level("WARNING"):
            mgr.disable_all(tables=["t1"])
        assert "no soporta" in caplog.text.lower()
        conn.execute.assert_not_called()

    def test_mariadb_rebuild_returns_unsupported(self):
        engine, _ = _make_engine("mysql")
        mgr = IndexManager(engine)
        results = mgr.rebuild_all()
        assert len(results) == 1
        assert results[0].action == "unsupported"

    def test_sqlite_disable_is_noop(self, caplog):
        engine, conn = _make_engine("sqlite")
        mgr = IndexManager(engine)
        with caplog.at_level("WARNING"):
            mgr.disable_all(tables=["t1"])
        assert "no soportado" in caplog.text.lower()
        conn.execute.assert_not_called()

    def test_sqlite_rebuild_returns_empty(self):
        engine, _ = _make_engine("sqlite")
        mgr = IndexManager(engine)
        assert mgr.rebuild_all() == []


# ---------------------------------------------------------------------------
# SQL Server
# ---------------------------------------------------------------------------


class TestIndexManagerSqlServer:
    def test_disable_discovers_and_disables_nonclustered(self):
        engine, conn = _make_engine("mssql")
        # 1ª llamada execute = discovery (fetchall), siguientes = ALTER DISABLE
        conn.execute.return_value.fetchall.return_value = [("ix_a",), ("ix_b",)]
        mgr = IndexManager(engine, schema="dbo")
        mgr.disable_all(tables=["orders"])

        sql = _executed_sql(conn)
        assert any("NONCLUSTERED" in s and "is_primary_key = 0" in s for s in sql)
        assert any("ALTER INDEX [ix_a] ON [dbo].[orders] DISABLE" in s for s in sql)
        assert any("ALTER INDEX [ix_b] ON [dbo].[orders] DISABLE" in s for s in sql)
        assert mgr._disabled == [("orders", "ix_a"), ("orders", "ix_b")]

    def test_rebuild_emits_rebuild_and_returns_rebuilt(self):
        engine, conn = _make_engine("mssql")
        mgr = IndexManager(engine, schema="dbo")
        mgr._disabled = [("orders", "ix_a")]

        results = mgr.rebuild_all()
        sql = _executed_sql(conn)
        assert any("ALTER INDEX [ix_a] ON [dbo].[orders] REBUILD" in s for s in sql)
        assert results == [IndexActionResult("orders", "ix_a", "mssql", "rebuilt")]

    def test_rebuild_failure_returns_failed(self):
        from sqlalchemy.exc import SQLAlchemyError

        engine, conn = _make_engine("mssql")
        conn.execute.side_effect = SQLAlchemyError("rebuild boom")
        mgr = IndexManager(engine)
        mgr._disabled = [("orders", "ix_a")]

        results = mgr.rebuild_all()
        assert results[0].action == "failed"
        assert "rebuild boom" in results[0].error_msg


# ---------------------------------------------------------------------------
# Oracle
# ---------------------------------------------------------------------------


class TestIndexManagerOracle:
    def test_disable_marks_unusable(self):
        engine, conn = _make_engine("oracle")
        conn.execute.return_value.fetchall.return_value = [("IX_NORMAL",)]
        mgr = IndexManager(engine, schema="HR")
        mgr.disable_all(tables=["EMP"])

        sql = _executed_sql(conn)
        assert any("all_indexes" in s and "NONUNIQUE" in s for s in sql)
        assert any("ALTER INDEX [HR].[IX_NORMAL] UNUSABLE" in s for s in sql)
        assert mgr._disabled == [("EMP", "IX_NORMAL")]

    def test_disable_without_schema_uses_user_indexes(self):
        engine, conn = _make_engine("oracle")
        conn.execute.return_value.fetchall.return_value = []
        mgr = IndexManager(engine)
        mgr.disable_all(tables=["EMP"])

        sql = _executed_sql(conn)
        assert any("user_indexes" in s for s in sql)

    def test_rebuild_emits_rebuild(self):
        engine, conn = _make_engine("oracle")
        mgr = IndexManager(engine, schema="HR")
        mgr._disabled = [("EMP", "IX_NORMAL")]

        results = mgr.rebuild_all()
        sql = _executed_sql(conn)
        assert any("ALTER INDEX [HR].[IX_NORMAL] REBUILD" in s for s in sql)
        assert results[0].action == "rebuilt"


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


class TestIndexManagerPostgreSQL:
    def test_disable_logs_ddl_before_drop(self, caplog):
        engine, conn = _make_engine("postgresql")
        conn.execute.return_value.fetchall.return_value = [
            ("idx_orders_cust", "CREATE INDEX idx_orders_cust ON public.orders (cust_id)"),
        ]
        mgr = IndexManager(engine, schema="public")
        with caplog.at_level("WARNING"):
            mgr.disable_all(tables=["orders"])

        # El DDL se loguea ANTES del DROP (recuperable si el proceso cae)
        assert "CREATE INDEX idx_orders_cust" in caplog.text
        sql = _executed_sql(conn)
        assert any("pg_get_indexdef" in s and "NOT i.indisunique" in s for s in sql)
        assert any("DROP INDEX [public].[idx_orders_cust]" in s for s in sql)
        assert mgr._dropped_pg == [
            ("orders", "idx_orders_cust", "CREATE INDEX idx_orders_cust ON public.orders (cust_id)")
        ]

    def test_recreate_executes_saved_ddl(self):
        engine, conn = _make_engine("postgresql")
        ddl = "CREATE INDEX idx_orders_cust ON public.orders (cust_id)"
        mgr = IndexManager(engine, schema="public")
        mgr._dropped_pg = [("orders", "idx_orders_cust", ddl)]

        results = mgr.rebuild_all()
        sql = _executed_sql(conn)
        assert ddl in sql
        assert results == [IndexActionResult("orders", "idx_orders_cust", "postgresql", "recreated")]


# ---------------------------------------------------------------------------
# Context manager — rebuild garantizado en __exit__
# ---------------------------------------------------------------------------


class TestIndexManagerContextManager:
    def test_exit_populates_index_results(self):
        engine, conn = _make_engine("mssql")
        mgr = IndexManager(engine)
        mgr._disabled = [("orders", "ix_a")]

        with mgr:
            pass

        assert isinstance(mgr.index_results, list)
        assert mgr.index_results[0].action == "rebuilt"

    def test_exit_rebuilds_even_when_body_raises(self):
        import pytest

        engine, conn = _make_engine("mssql")
        mgr = IndexManager(engine)
        mgr._disabled = [("orders", "ix_a")]

        with pytest.raises(RuntimeError):
            with mgr:
                raise RuntimeError("load failed")

        # rebuild se ejecutó pese a la excepción del cuerpo
        assert mgr.index_results[0].action == "rebuilt"
