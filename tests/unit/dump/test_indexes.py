"""Tests unitarios para IndexManager (adaptador de la estrategia común de bulk desde 3.2.0)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk._support.secondary_indexes import IndexStep
from util_bbdd.dump._indexes import IndexManager
from util_bbdd.dump._models import IndexActionResult

_FACTS = "util_bbdd.bulk._support.secondary_indexes.facts"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_engine(dialect_name: str) -> tuple[MagicMock, MagicMock]:
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


def _step(table: str, name: str, dialect_sql: tuple[str, str], action: str = "rebuilt", **kw: object) -> IndexStep:
    return IndexStep(table, f"[{table}]", name, dialect_sql[0], dialect_sql[1], action, **kw)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Dialectos no soportados
# ---------------------------------------------------------------------------


class TestIndexManagerUnsupported:
    def test_sqlite_disable_is_noop(self, caplog: pytest.LogCaptureFixture) -> None:
        engine, conn = _make_engine("sqlite")
        mgr = IndexManager(engine)
        with caplog.at_level("WARNING"):
            mgr.disable_all(tables=["t1"])
        assert "no soportado" in caplog.text.lower()
        conn.execute.assert_not_called()

    def test_sqlite_rebuild_returns_empty(self) -> None:
        engine, _ = _make_engine("sqlite")
        mgr = IndexManager(engine)
        assert mgr.rebuild_all() == []


# ---------------------------------------------------------------------------
# SQL Server
# ---------------------------------------------------------------------------


class TestIndexManagerSqlServer:
    def test_disable_discovers_and_disables_nonclustered(self) -> None:
        engine, conn = _make_engine("mssql")
        # 1ª llamada execute = discovery (fetchall), siguientes = ALTER DISABLE
        conn.execute.return_value.fetchall.return_value = [("ix_a",), ("ix_b",)]
        mgr = IndexManager(engine, schema="dbo")
        mgr.disable_all(tables=["orders"])

        sql = _executed_sql(conn)
        assert any("NONCLUSTERED" in s and "is_primary_key = 0" in s for s in sql)
        assert any("ALTER INDEX [ix_a] ON [dbo].[orders] DISABLE" in s for s in sql)
        assert any("ALTER INDEX [ix_b] ON [dbo].[orders] DISABLE" in s for s in sql)
        assert [(s.table, s.index_name) for s in mgr._disabled] == [("orders", "ix_a"), ("orders", "ix_b")]
        assert conn.commit.call_count == 2  # una transacción por índice

    def test_rebuild_emits_rebuild_and_returns_rebuilt(self) -> None:
        engine, conn = _make_engine("mssql")
        mgr = IndexManager(engine, schema="dbo")
        mgr._disabled = [_step("orders", "ix_a", ("…", "ALTER INDEX [ix_a] ON [dbo].[orders] REBUILD"))]

        results = mgr.rebuild_all()
        sql = _executed_sql(conn)
        assert any("ALTER INDEX [ix_a] ON [dbo].[orders] REBUILD" in s for s in sql)
        assert results == [IndexActionResult("orders", "ix_a", "mssql", "rebuilt")]

    def test_rebuild_failure_returns_failed(self) -> None:
        engine, conn = _make_engine("mssql")
        conn.execute.side_effect = SQLAlchemyError("rebuild boom")
        mgr = IndexManager(engine)
        mgr._disabled = [_step("orders", "ix_a", ("…", "ALTER INDEX [ix_a] ON [orders] REBUILD"))]

        results = mgr.rebuild_all()
        assert results[0].action == "failed"
        assert "rebuild boom" in results[0].error_msg
        conn.rollback.assert_called_once()

    def test_disable_failure_skips_the_index_and_continues(self) -> None:
        engine, conn = _make_engine("mssql")
        discovery = MagicMock()
        discovery.fetchall.return_value = [("ix_a",), ("ix_b",)]
        conn.execute.side_effect = [discovery, SQLAlchemyError("locked"), MagicMock()]
        mgr = IndexManager(engine, schema="dbo")
        mgr.disable_all(tables=["orders"])
        assert [s.index_name for s in mgr._disabled] == ["ix_b"]


# ---------------------------------------------------------------------------
# Oracle
# ---------------------------------------------------------------------------


class TestIndexManagerOracle:
    def test_disable_marks_unusable(self) -> None:
        engine, conn = _make_engine("oracle")
        conn.execute.return_value.fetchall.return_value = [("IX_NORMAL",)]
        mgr = IndexManager(engine, schema="HR")
        mgr.disable_all(tables=["EMP"])

        sql = _executed_sql(conn)
        assert any("all_indexes" in s and "NONUNIQUE" in s for s in sql)
        assert any("ALTER INDEX [HR].[IX_NORMAL] UNUSABLE" in s for s in sql)
        assert [(s.table, s.index_name) for s in mgr._disabled] == [("EMP", "IX_NORMAL")]

    def test_disable_without_schema_uses_user_indexes(self) -> None:
        engine, conn = _make_engine("oracle")
        conn.execute.return_value.fetchall.return_value = []
        mgr = IndexManager(engine)
        mgr.disable_all(tables=["EMP"])

        sql = _executed_sql(conn)
        assert any("user_indexes" in s for s in sql)

    def test_rebuild_emits_rebuild(self) -> None:
        engine, conn = _make_engine("oracle")
        conn.execute.return_value.fetchall.return_value = [("IX_NORMAL",)]
        mgr = IndexManager(engine, schema="HR")
        mgr.disable_all(tables=["EMP"])

        results = mgr.rebuild_all()
        sql = _executed_sql(conn)
        assert any("ALTER INDEX [HR].[IX_NORMAL] REBUILD" in s for s in sql)
        assert results[0].action == "rebuilt"


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


class TestIndexManagerPostgreSQL:
    DDL = "CREATE INDEX idx_orders_cust ON public.orders USING btree (cust_id)"

    def test_disable_logs_ddl_before_drop(self, caplog: pytest.LogCaptureFixture) -> None:
        engine, conn = _make_engine("postgresql")
        conn.execute.return_value.fetchall.return_value = [("idx_orders_cust", self.DDL)]
        mgr = IndexManager(engine, schema="public")
        with caplog.at_level("WARNING"):
            mgr.disable_all(tables=["orders"])

        # El DDL se loguea ANTES del DROP (recuperable si el proceso cae)
        assert self.DDL in caplog.text
        sql = _executed_sql(conn)
        assert any("pg_get_indexdef" in s and "NOT i.indisunique" in s for s in sql)
        assert any("DROP INDEX [public].[idx_orders_cust]" in s for s in sql)
        assert [(s.index_name, s.recovery_ddl) for s in mgr._disabled] == [("idx_orders_cust", self.DDL)]

    def test_recreate_executes_saved_ddl_with_if_not_exists(self) -> None:
        engine, conn = _make_engine("postgresql")
        conn.execute.return_value.fetchall.return_value = [("idx_orders_cust", self.DDL)]
        mgr = IndexManager(engine, schema="public")
        mgr.disable_all(tables=["orders"])

        results = mgr.rebuild_all()
        sql = _executed_sql(conn)
        assert "CREATE INDEX IF NOT EXISTS idx_orders_cust ON public.orders USING btree (cust_id)" in sql
        assert results == [IndexActionResult("orders", "idx_orders_cust", "postgresql", "recreated")]


# ---------------------------------------------------------------------------
# MariaDB / MySQL (desde 3.2.0)
# ---------------------------------------------------------------------------


class TestIndexManagerMariaDB:
    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_innodb_drops_and_recreates_in_one_alter(self, dialect: str, caplog: pytest.LogCaptureFixture) -> None:
        engine, conn = _make_engine(dialect)
        with patch(_FACTS) as facts:
            facts.storage_engine.return_value = "InnoDB"
            facts.secondary_nonunique_indexes.return_value = [
                ("ix_a", "INDEX [ix_a] ([a])"),
                ("ix_b", "INDEX [ix_b] ([b])"),
            ]
            mgr = IndexManager(engine)
            with caplog.at_level("WARNING"):
                mgr.disable_all(tables=["orders"])
            results = mgr.rebuild_all()

        sql = _executed_sql(conn)
        assert sql == [
            "ALTER TABLE [orders] DROP INDEX [ix_a]",
            "ALTER TABLE [orders] DROP INDEX [ix_b]",
            "ALTER TABLE [orders] ADD INDEX [ix_a] ([a]), ADD INDEX [ix_b] ([b])",
        ]
        assert "ALTER TABLE [orders] ADD INDEX [ix_a] ([a])" in caplog.text  # DDL de recuperación antes del DROP
        assert [(r.index_name, r.action) for r in results] == [("ix_a", "recreated"), ("ix_b", "recreated")]

    def test_myisam_uses_disable_keys(self) -> None:
        engine, conn = _make_engine("mariadb")
        with patch(_FACTS) as facts:
            facts.storage_engine.return_value = "Aria"
            mgr = IndexManager(engine)
            mgr.disable_all(tables=["orders"])
            results = mgr.rebuild_all()

        assert _executed_sql(conn) == ["ALTER TABLE [orders] DISABLE KEYS", "ALTER TABLE [orders] ENABLE KEYS"]
        assert results == [IndexActionResult("orders", "*", "mariadb", "rebuilt")]

    def test_failed_group_marks_every_index(self) -> None:
        engine, conn = _make_engine("mysql")
        with patch(_FACTS) as facts:
            facts.storage_engine.return_value = "InnoDB"
            facts.secondary_nonunique_indexes.return_value = [
                ("ix_a", "INDEX [ix_a] ([a])"),
                ("ix_b", "INDEX [ix_b] ([b])"),
            ]
            mgr = IndexManager(engine)
            mgr.disable_all(tables=["orders"])
            conn.execute.side_effect = SQLAlchemyError("add boom")
            results = mgr.rebuild_all()

        assert [(r.index_name, r.action) for r in results] == [("ix_a", "failed"), ("ix_b", "failed")]


# ---------------------------------------------------------------------------
# Context manager — rebuild garantizado en __exit__
# ---------------------------------------------------------------------------


class TestIndexManagerContextManager:
    def test_exit_populates_index_results(self) -> None:
        engine, _ = _make_engine("mssql")
        mgr = IndexManager(engine)
        mgr._disabled = [_step("orders", "ix_a", ("…", "ALTER INDEX [ix_a] ON [orders] REBUILD"))]

        with mgr:
            pass

        assert isinstance(mgr.index_results, list)
        assert mgr.index_results[0].action == "rebuilt"

    def test_exit_rebuilds_even_when_body_raises(self) -> None:
        engine, _ = _make_engine("mssql")
        mgr = IndexManager(engine)
        mgr._disabled = [_step("orders", "ix_a", ("…", "ALTER INDEX [ix_a] ON [orders] REBUILD"))]

        with pytest.raises(RuntimeError):
            with mgr:
                raise RuntimeError("load failed")

        # rebuild se ejecutó pese a la excepción del cuerpo
        assert mgr.index_results[0].action == "rebuilt"


def test_index_action_result_is_the_bulk_class() -> None:
    from util_bbdd.bulk._models import IndexActionResult as BulkIndexActionResult
    from util_bbdd.dump import IndexActionResult as PublicIndexActionResult

    assert IndexActionResult is BulkIndexActionResult is PublicIndexActionResult
