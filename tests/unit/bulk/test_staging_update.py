"""UPDATE por tabla temporal en MySQL/MariaDB (P-04 del performance-audit de bulk), sin servidor.

La equivalencia de resultados con el UPDATE por executemany se verifica contra servidores reales en
``tests/integration/test_bulk_engines.py::test_update_via_staging_matches_executemany``.
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql
from sqlalchemy.exc import DBAPIError
from sqlalchemy.sql.dml import Update
from sqlalchemy.sql.elements import TextClause

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.batch import BatchStatementExecutor, MySQLStagingUpdateStrategy

pytestmark = pytest.mark.unit


def _table() -> Table:
    return Table(
        "t", MetaData(), Column("id", Integer, primary_key=True), Column("a", Integer), Column("s", String(10))
    )


def _connection() -> MagicMock:
    connection = MagicMock()
    connection.dialect = MySQLDialect_pymysql()
    return connection


def _statements(connection: MagicMock) -> list[Any]:
    return [call.args[0] for call in connection.execute.call_args_list]


def test_creates_loads_updates_and_drops_the_staging_table() -> None:
    connection, loader = _connection(), MagicMock()
    strategy = MySQLStagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a", "s"], loader=loader)
    records = [{"id": 1, "a": 10, "s": "x", "pk_id": 1}, {"id": 2, "a": 20, "s": "y", "pk_id": 2}]

    strategy.execute(connection=connection, stmt=None, records=records)

    load_stmt = loader.execute.call_args.kwargs["stmt"]
    assert load_stmt.table.name.startswith("tmp_bulkupd_")
    assert load_stmt.table._prefixes == ["TEMPORARY"]
    # Solo PK + columnas a actualizar; el alias pk_id del WHERE no viaja a la temporal.
    assert loader.execute.call_args.kwargs["records"] == [{"id": 1, "a": 10, "s": "x"}, {"id": 2, "a": 20, "s": "y"}]
    update_stmt, drop_stmt = _statements(connection)
    assert isinstance(update_stmt, Update)
    sql = str(update_stmt.compile(dialect=MySQLDialect_pymysql()))
    assert sql.startswith(f"UPDATE t, {load_stmt.table.name} SET t.a=")
    assert f"WHERE t.id = {load_stmt.table.name}.id" in sql
    assert isinstance(drop_stmt, TextClause)
    assert str(drop_stmt) == f"DROP TEMPORARY TABLE IF EXISTS {load_stmt.table.name}"


def test_last_occurrence_of_a_repeated_pk_wins() -> None:
    loader = MagicMock()
    strategy = MySQLStagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=loader)
    records = [{"id": 1, "a": 1}, {"id": 2, "a": 2}, {"id": 1, "a": 3}]

    strategy.execute(connection=_connection(), stmt=None, records=records)

    assert loader.execute.call_args.kwargs["records"] == [{"id": 1, "a": 3}, {"id": 2, "a": 2}]


def test_staging_table_is_dropped_and_original_error_kept_when_load_fails() -> None:
    connection, loader = _connection(), MagicMock()
    loader.execute.side_effect = RuntimeError("fallo de carga")
    connection.execute.side_effect = lambda stmt, *a: (_ for _ in ()).throw(OSError("drop también falla"))
    strategy = MySQLStagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=loader)

    with pytest.raises(RuntimeError, match="fallo de carga"):
        strategy.execute(connection=connection, stmt=None, records=[{"id": 1, "a": 1}])

    (drop_stmt,) = _statements(connection)
    assert str(drop_stmt).startswith("DROP TEMPORARY TABLE IF EXISTS tmp_bulkupd_")


def test_empty_batch_does_nothing() -> None:
    connection, loader = _connection(), MagicMock()
    MySQLStagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=loader).execute(
        connection=connection, stmt=None, records=[]
    )
    loader.execute.assert_not_called()
    connection.execute.assert_not_called()


def test_executor_uses_the_given_strategy_per_batch() -> None:
    engine = create_engine("sqlite://")
    executor = BatchStatementExecutor(engine=engine, chunk_size=2)
    strategy = MagicMock()

    executor.execute(records=[{"id": i} for i in range(5)], stmt="stmt", strategy=strategy)

    assert [len(call.kwargs["records"]) for call in strategy.execute.call_args_list] == [2, 2, 1]
    assert executor.insert_strategy is not strategy


def test_flag_is_ignored_outside_mysql_family(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    _table().create(engine)
    crud = BulkCrud(engine, update_via_staging=True)
    crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2], "a": [1, 2], "s": ["x", "y"]}), "t", generar_sql=False)

    crud.bulk_update_from_df(pd.DataFrame({"id": [1, 2], "a": [10, 20], "s": ["X", "Y"]}), "t", generar_sql=False)

    with engine.connect() as conn:
        assert [tuple(r) for r in conn.execute(text("SELECT id, a, s FROM t ORDER BY id"))] == [
            (1, 10, "X"),
            (2, 20, "Y"),
        ]


class _FakeDriverError(Exception):
    """Excepción del driver con el errno en ``args[0]`` (como PyMySQL)."""


def _denied(errno: int) -> DBAPIError:
    return DBAPIError("CREATE TEMPORARY TABLE ...", {}, _FakeDriverError(errno, "Access denied"))


def test_denied_temporary_table_falls_back_to_row_update_and_logs_once(caplog: pytest.LogCaptureFixture) -> None:
    connection, loader = _connection(), MagicMock()
    connection._run_ddl_visitor.side_effect = _denied(1044)
    strategy = MySQLStagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=loader)
    update_stmt = MagicMock(name="update_stmt")
    batch_1, batch_2 = [{"id": 1, "a": 1, "pk_id": 1}], [{"id": 2, "a": 2, "pk_id": 2}]

    with caplog.at_level(logging.WARNING, logger="util_bbdd.bulk._execution.batch"):
        strategy.execute(connection=connection, stmt=update_stmt, records=batch_1)
        strategy.execute(connection=connection, stmt=update_stmt, records=batch_2)

    assert strategy.staging_denied is True
    loader.execute.assert_not_called()
    assert connection._run_ddl_visitor.call_count == 1  # el segundo lote no reintenta la temporal
    assert [call.args for call in connection.execute.call_args_list] == [(update_stmt, batch_1), (update_stmt, batch_2)]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "CREATE TEMPORARY TABLES" in warnings[0].getMessage()
    assert "update_via_staging=False" in warnings[0].getMessage()


@pytest.mark.parametrize("errno", [1142, 1227])
def test_other_privilege_errnos_also_fall_back(errno: int) -> None:
    connection = _connection()
    connection._run_ddl_visitor.side_effect = _denied(errno)
    strategy = MySQLStagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=MagicMock())

    strategy.execute(connection=connection, stmt="update_stmt", records=[{"id": 1, "a": 1}])

    assert strategy.staging_denied is True


def test_errno_attribute_is_recognised_as_in_mariadb_connector() -> None:
    orig = _FakeDriverError("Access denied")
    orig.errno = 1044  # type: ignore[attr-defined]
    connection = _connection()
    connection._run_ddl_visitor.side_effect = DBAPIError("CREATE ...", {}, orig)
    strategy = MySQLStagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=MagicMock())

    strategy.execute(connection=connection, stmt="update_stmt", records=[{"id": 1, "a": 1}])

    assert strategy.staging_denied is True


def test_other_create_errors_are_not_hidden() -> None:
    connection = _connection()
    connection._run_ddl_visitor.side_effect = _denied(1064)  # error de sintaxis, no de privilegio
    strategy = MySQLStagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=MagicMock())

    with pytest.raises(DBAPIError):
        strategy.execute(connection=connection, stmt="update_stmt", records=[{"id": 1, "a": 1}])
    assert strategy.staging_denied is False
    connection.execute.assert_not_called()
