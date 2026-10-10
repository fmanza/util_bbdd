"""Tests focalizados para los helpers internos de bulk."""

from __future__ import annotations

import re

from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert

from util_bbdd.bulk._execution.batch import (
    BatchStatementExecutor,
    DeleteBatchExecutor,
    DeleteStrategyResolver,
    GenericDeleteStrategy,
    SqlBasedDeleteStrategy,
)
from util_bbdd.bulk._support.persistence import BulkPersistenceManager
from util_bbdd.bulk._support.sql_helpers import generate_insert_sql
from util_bbdd.bulk._support.validation import build_update_plan, resolve_sql_output_path
from util_bbdd.bulk.audit import AuditManager


def test_resolve_sql_output_path_accepts_str_and_path_only(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path_sql es obligatorio"):
        resolve_sql_output_path(None, table_name="users", operation="insert", generate_name=lambda *_: Path("x.sql"))

    # v1.1.0: un str es una ruta válida; otro tipo sigue siendo ValueError.
    assert (
        resolve_sql_output_path(
            "salida", table_name="users", operation="insert", generate_name=lambda *_: Path("x.sql")
        )
        == Path("salida") / "x.sql"
    )

    with pytest.raises(ValueError, match=r"ruta \(str o Path\)"):
        resolve_sql_output_path(
            cast(Any, 123),
            table_name="users",
            operation="insert",
            generate_name=lambda *_: Path("x.sql"),
        )

    assert (
        resolve_sql_output_path(
            tmp_path,
            table_name="users",
            operation="insert",
            generate_name=lambda *_: Path("generated.sql"),
        )
        == tmp_path / "generated.sql"
    )


def test_build_update_plan_validates_pk_and_updatable_columns() -> None:
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )

    plan = build_update_plan(table, ["id", "name"], "users")

    assert plan.pk_cols == ["id"]
    assert plan.update_cols == ["name"]
    assert plan.pk_param_map == {"id": "pk_id"}

    with pytest.raises(ValueError, match="claves primarias presentes"):
        build_update_plan(table, ["name"], "users")


def test_batch_statement_executor_splits_payload_by_chunk_size() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )
    stmt = insert(table)
    records = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}]

    connection = MagicMock()

    class _BeginContext:
        def __enter__(self):
            return connection

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    cast(Any, engine).begin = MagicMock(return_value=_BeginContext())

    executor = BatchStatementExecutor(engine=engine, chunk_size=2)
    executor.execute(records=records, stmt=stmt)

    assert connection.execute.call_count == 2
    first_payload = connection.execute.call_args_list[0].args[1]
    second_payload = connection.execute.call_args_list[1].args[1]
    assert first_payload == records[:2]
    assert second_payload == records[2:]


def test_delete_strategy_resolver_returns_expected_strategy_by_dialect() -> None:
    resolver = DeleteStrategyResolver()

    assert isinstance(resolver.resolve("mysql"), SqlBasedDeleteStrategy)
    assert isinstance(resolver.resolve("mariadb"), SqlBasedDeleteStrategy)
    assert isinstance(resolver.resolve("sqlite"), GenericDeleteStrategy)


def test_sql_based_delete_strategy_uses_named_params_for_single_pk() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
    )
    batch_df = pd.DataFrame({"id": [10, 20, 30]})

    connection = MagicMock()
    connection.dialect = engine.dialect

    strategy = SqlBasedDeleteStrategy()
    strategy.execute(connection=connection, table=table, batch_df=batch_df, pk_cols=["id"])

    assert connection.execute.call_count == 1
    stmt, params = connection.execute.call_args.args
    assert "DELETE FROM users WHERE id IN" in str(stmt)
    assert params == {"pk_0_0": 10, "pk_1_0": 20, "pk_2_0": 30}


def test_sql_based_delete_strategy_uses_named_params_for_composite_pk() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = Table(
        "orders",
        MetaData(),
        Column("tenant_id", Integer, primary_key=True),
        Column("order_id", Integer, primary_key=True),
    )
    batch_df = pd.DataFrame({"tenant_id": [1, 1], "order_id": [100, 101]})

    connection = MagicMock()
    connection.dialect = engine.dialect

    strategy = SqlBasedDeleteStrategy()
    strategy.execute(
        connection=connection,
        table=table,
        batch_df=batch_df,
        pk_cols=["tenant_id", "order_id"],
    )

    assert connection.execute.call_count == 1
    stmt, params = connection.execute.call_args.args
    assert "DELETE FROM orders WHERE (tenant_id, order_id) IN" in str(stmt)
    assert params == {
        "pk_0_0": 1,
        "pk_0_1": 100,
        "pk_1_0": 1,
        "pk_1_1": 101,
    }


def test_sql_based_delete_strategy_skips_empty_batches() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
    )
    batch_df = pd.DataFrame({"id": []})

    connection = MagicMock()
    connection.dialect = engine.dialect

    strategy = SqlBasedDeleteStrategy()
    strategy.execute(connection=connection, table=table, batch_df=batch_df, pk_cols=["id"])

    connection.execute.assert_not_called()


def test_delete_batch_executor_uses_generic_strategy_for_sqlite_dialect() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
    )
    batch_df = pd.DataFrame({"id": [1, 2, 3]})

    class _SpyStrategy:
        def __init__(self) -> None:
            self.calls: int = 0

        def execute(
            self,
            *,
            connection: Any,
            table: Table,
            batch_df: pd.DataFrame,
            pk_cols: Sequence[str],
        ) -> None:
            del connection, table, batch_df, pk_cols
            self.calls += 1

    sql_spy = _SpyStrategy()
    generic_spy = _SpyStrategy()
    resolver = DeleteStrategyResolver(
        sql_based_dialects=frozenset({"mysql", "mariadb", "mssql", "hsqldb"}),
        sql_based_strategy=sql_spy,
        generic_strategy=generic_spy,
    )
    executor = DeleteBatchExecutor(engine=engine, chunk_size=2, resolver=resolver)

    executor.execute(table=table, df=batch_df, pk_cols=["id"])

    assert sql_spy.calls == 0
    assert generic_spy.calls == 2


def test_generate_insert_sql_returns_literal_statements() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )
    sql_lines = generate_insert_sql(
        insert(table),
        [{"id": 1, "name": "Alice"}],
        engine.dialect,
    )

    assert len(sql_lines) == 1
    assert "INSERT INTO users" in sql_lines[0]
    assert "Alice" in sql_lines[0]


def test_bulk_persistence_manager_builds_sql_path_with_dynamic_name(tmp_path: Path) -> None:
    persistence = BulkPersistenceManager(
        engine_url="sqlite:///mydb.db",
        logger=MagicMock(),
        audit_manager=MagicMock(spec=AuditManager),
        db_info="SQLITE",
    )

    sql_path = persistence.resolve_sql_output_path(tmp_path, "users", "insert")

    assert sql_path.parent == tmp_path
    assert re.fullmatch(r"mydb\.db-users-insert_\d{8}_\d{6}\.sql", sql_path.name)


def test_bulk_persistence_manager_persists_sql_file(tmp_path: Path) -> None:
    logger = MagicMock()
    persistence = BulkPersistenceManager(
        engine_url="sqlite:///mydb.db",
        logger=logger,
        audit_manager=MagicMock(spec=AuditManager),
        db_info="SQLITE",
    )
    sql_file = tmp_path / "bulk" / "users.sql"

    persistence.persist_sql(["SELECT 1;", "SELECT 2;"], sql_file)

    assert sql_file.read_text(encoding="utf-8") == "SELECT 1;\nSELECT 2;"
    logger.info.assert_called_with(f"💾 SQL guardada en: {sql_file}")


def test_bulk_persistence_manager_registers_operations_in_audit() -> None:
    audit_manager = MagicMock(spec=AuditManager)
    persistence = BulkPersistenceManager(
        engine_url="sqlite:///mydb.db",
        logger=MagicMock(),
        audit_manager=audit_manager,
        db_info="SQLITE",
    )

    persistence.register_operation(
        table_name="users",
        operation="INSERT",
        rowcount=3,
        elapsed=1.25,
        generated_sql=True,
    )

    audit_manager.registrar_operacion.assert_called_once_with("users", "SQLITE", "INSERT", 3, 1.25, True)


# ---------------------------------------------------------------------------
# Propuesta A — caché reflect_table (Identity Map)
# ---------------------------------------------------------------------------


def test_reflect_table_caches_result() -> None:
    """Segunda llamada con la misma tabla devuelve el mismo objeto (sin autoload_with extra)."""
    from util_bbdd.bulk.crud import BulkCrud

    engine = create_engine("sqlite:///:memory:")
    Table("items", MetaData(), Column("id", Integer, primary_key=True)).create(bind=engine)

    crud = BulkCrud(engine=engine)
    table_a = crud.reflect_table("items")
    table_b = crud.reflect_table("items")

    assert table_a is table_b


def test_reflect_table_cache_isolated_per_instance() -> None:
    """El caché no se comparte entre distintas instancias de BulkCrud."""
    from util_bbdd.bulk.crud import BulkCrud

    engine = create_engine("sqlite:///:memory:")
    Table("items", MetaData(), Column("id", Integer, primary_key=True)).create(bind=engine)

    crud_1 = BulkCrud(engine=engine)
    crud_2 = BulkCrud(engine=engine)
    table_1 = crud_1.reflect_table("items")
    table_2 = crud_2.reflect_table("items")

    assert table_1 is not table_2
    assert crud_1._table_cache is not crud_2._table_cache


# ---------------------------------------------------------------------------
# Propuesta B — BatchStatementExecutor con conexión inyectada
# ---------------------------------------------------------------------------


def test_batch_executor_uses_injected_connection() -> None:
    """Si _active_connection está inyectado, engine.begin() no debe llamarse."""
    engine = MagicMock()
    executor = BatchStatementExecutor(engine=engine, chunk_size=10)

    conn = MagicMock()
    executor.session.connection = conn

    executor.execute(records=[{"id": 1}], stmt=MagicMock())

    engine.begin.assert_not_called()
    conn.execute.assert_called_once()
