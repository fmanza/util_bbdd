"""UPDATE por tabla temporal en PostgreSQL (B-01 del performance-audit de bulk 2026-10-01), sin servidor.

El UPDATE fila a fila de PostgreSQL era 4,4 veces más lento que su INSERT (1M filas: 24,9 s); por tabla temporal + COPY
+ ``UPDATE … FROM``, 10,6 s. La equivalencia de resultados con el UPDATE por executemany se verifica contra el servidor
en ``tests/integration/test_bulk_audit_20261001.py``.
"""

from __future__ import annotations

import logging

from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table
from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg
from sqlalchemy.sql.dml import Update

from util_bbdd.bulk._execution.batch import STAGING_UPDATE_DIALECTS, MySQLStagingUpdateStrategy, StagingUpdateStrategy

pytestmark = pytest.mark.unit


def _table(schema: str | None = "ventas") -> Table:
    return Table(
        "t",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("a", Integer),
        Column("s", String(10)),
        schema=schema,
    )


def _connection(can_create_temp: bool = True) -> MagicMock:
    connection = MagicMock()
    connection.dialect = PGDialect_psycopg()
    connection.execute.return_value.scalar.return_value = can_create_temp
    return connection


def _sql(connection: MagicMock) -> list[str]:
    return [
        str(call.args[0].compile(dialect=PGDialect_psycopg()))
        if isinstance(call.args[0], Update)
        else str(call.args[0])
        for call in connection.execute.call_args_list
    ]


def _records() -> list[dict[str, Any]]:
    return [
        {"id": 1, "a": 10, "s": "x", "pk_id": 1},
        {"id": 1, "a": 11, "s": "y", "pk_id": 1},
        {"id": 2, "a": 20, "s": "z", "pk_id": 2},
    ]


def test_postgresql_is_a_staging_dialect() -> None:
    assert {"postgresql", "mysql", "mariadb"} <= STAGING_UPDATE_DIALECTS
    assert MySQLStagingUpdateStrategy is StagingUpdateStrategy  # alias anterior a B-01


def test_postgresql_copies_types_loads_updates_from_and_drops() -> None:
    connection, loader = _connection(), MagicMock()
    strategy = StagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a", "s"], loader=loader)

    strategy.execute(connection=connection, stmt=None, records=_records())

    privilege, create, update_sql, drop = _sql(connection)
    assert privilege == "SELECT has_database_privilege(current_database(), 'TEMP')"
    tmp = loader.execute.call_args.kwargs["stmt"].table
    assert tmp.schema is None  # PostgreSQL no admite esquema en una temporal
    assert create == f"CREATE TEMPORARY TABLE {tmp.name} AS SELECT id, a, s FROM ventas.t WITH NO DATA"
    assert update_sql.startswith(f"UPDATE ventas.t SET a={tmp.name}.a, s={tmp.name}.s FROM {tmp.name} WHERE")
    assert drop == f"DROP TABLE IF EXISTS {tmp.name}"
    # Última aparición por PK; el alias pk_id del WHERE no viaja a la temporal.
    assert loader.execute.call_args.kwargs["records"] == [{"id": 1, "a": 11, "s": "y"}, {"id": 2, "a": 20, "s": "z"}]
    connection._run_ddl_visitor.assert_not_called()  # sin Table.create: no se intentan crear tipos (ENUM)


def test_privilege_is_checked_once() -> None:
    connection = _connection()
    strategy = StagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=MagicMock())

    for _ in range(3):
        strategy.execute(connection=connection, stmt=None, records=[{"id": 1, "a": 1}])

    assert sum("has_database_privilege" in sql for sql in _sql(connection)) == 1


def test_without_temp_privilege_falls_back_to_row_update(caplog: pytest.LogCaptureFixture) -> None:
    connection, loader = _connection(can_create_temp=False), MagicMock()
    strategy = StagingUpdateStrategy(table=_table(), pk_cols=["id"], update_cols=["a"], loader=loader)
    update_stmt = MagicMock(name="update_stmt")
    batch_1, batch_2 = [{"id": 1, "a": 1, "pk_id": 1}], [{"id": 2, "a": 2, "pk_id": 2}]

    with caplog.at_level(logging.WARNING, logger="util_bbdd.bulk._execution.batch"):
        strategy.execute(connection=connection, stmt=update_stmt, records=batch_1)
        strategy.execute(connection=connection, stmt=update_stmt, records=batch_2)

    assert strategy.staging_denied is True
    loader.execute.assert_not_called()
    assert [call.args for call in connection.execute.call_args_list[1:]] == [
        (update_stmt, batch_1),
        (update_stmt, batch_2),
    ]
    assert not any("CREATE TEMPORARY" in sql for sql in _sql(connection)[1:] if isinstance(sql, str))
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "TEMP" in warnings[0]
    assert "update_via_staging=False" in warnings[0]


def test_error_during_load_drops_the_staging_table_and_reraises() -> None:
    connection, loader = _connection(), MagicMock()
    loader.execute.side_effect = RuntimeError("fallo de COPY")
    strategy = StagingUpdateStrategy(table=_table(None), pk_cols=["id"], update_cols=["a"], loader=loader)

    with pytest.raises(RuntimeError, match="fallo de COPY"):
        strategy.execute(connection=connection, stmt=None, records=[{"id": 1, "a": 1}])

    assert _sql(connection)[-1].startswith("DROP TABLE IF EXISTS tmp_bulkupd_")
