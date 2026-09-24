"""Hallazgo P-27 del performance-audit de bulk: INSERT de PostgreSQL por el cursor del driver.

``PostgresCopyStrategy`` (psycopg 3) y ``PostgreSQLExecuteValuesStrategy`` (psycopg2) escriben por
``connection.connection.cursor()``, que SQLAlchemy no ve. Con ``commit_every_n_chunks`` la conexión es
commit-as-you-go: sin transacción iniciada, ``commit()`` no hacía nada y todas las filas se perdían. Las estrategias
inician ahora la transacción antes de usar el cursor.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, text
from sqlalchemy.dialects import postgresql

from util_bbdd.bulk._execution.batch import (
    PostgresCopyStrategy,
    PostgreSQLExecuteValuesStrategy,
    _begin_if_needed,
)

pytestmark = pytest.mark.unit

_TABLE = Table("t", MetaData(), Column("id", Integer, primary_key=True))


def _connection(in_transaction: bool, calls: list[str]) -> MagicMock:
    conn = MagicMock()
    conn.dialect = postgresql.dialect()
    conn.in_transaction.return_value = in_transaction
    conn.begin.side_effect = lambda: calls.append("begin")

    def _cursor() -> MagicMock:
        calls.append("cursor")
        return MagicMock()

    conn.connection.cursor.side_effect = _cursor
    return conn


@pytest.mark.parametrize(("in_transaction", "expected"), [(False, ["begin", "cursor"]), (True, ["cursor"])])
def test_copy_begins_transaction_before_raw_cursor(in_transaction: bool, expected: list[str]) -> None:
    calls: list[str] = []
    conn = _connection(in_transaction, calls)

    PostgresCopyStrategy().execute(connection=conn, stmt=insert(_TABLE), records=[{"id": 1}])

    assert calls == expected


@pytest.mark.parametrize(("in_transaction", "expected"), [(False, ["begin", "cursor"]), (True, ["cursor"])])
def test_execute_values_begins_transaction_before_raw_cursor(
    in_transaction: bool, expected: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    extras = pytest.importorskip("psycopg2.extras")
    monkeypatch.setattr(extras, "execute_values", lambda *args, **kwargs: None)
    calls: list[str] = []
    conn = _connection(in_transaction, calls)

    PostgreSQLExecuteValuesStrategy().execute(connection=conn, stmt=insert(_TABLE), records=[{"id": 1}])

    assert calls == expected


def test_begin_if_needed_makes_commit_effective_in_commit_as_you_go(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'tx.db'}")
    _TABLE.create(engine)

    with engine.connect() as conn:
        _begin_if_needed(conn)
        assert conn.in_transaction()
        conn.connection.cursor().execute("INSERT INTO t (id) VALUES (1)")  # cursor del driver, como COPY
        conn.commit()

    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM t")).scalar_one() == 1


def test_begin_if_needed_keeps_existing_transaction(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'tx.db'}")

    with engine.begin() as conn:
        transaction = conn.get_transaction()
        _begin_if_needed(conn)
        assert conn.get_transaction() is transaction
