"""Hallazgo P-28 del performance-audit de bulk: errores del INSERT de PostgreSQL por el cursor del driver.

Lo que se ejecuta por ``connection.connection.cursor()`` no pasa por SQLAlchemy, que es quien envuelve los errores
del driver. Una clave duplicada en el COPY llegaba como ``psycopg.errors.UniqueViolation`` y quien captura
``SQLAlchemyError`` (``ParallelBulkLoader``, ``dump``, el log de ``BulkCrud``) no la veía. Ahora se envuelve como
haría SQLAlchemy: ``IntegrityError``, ``OperationalError``…, e invalidando la conexión si es una desconexión.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert
from sqlalchemy.exc import IntegrityError, OperationalError

from util_bbdd.bulk._execution.batch import PostgresCopyStrategy, PostgreSQLExecuteValuesStrategy

pytestmark = pytest.mark.unit

_TABLE = Table("t", MetaData(), Column("id", Integer, primary_key=True))


def _connection(driver: str, *, closed: bool = False) -> MagicMock:
    conn = MagicMock()
    conn.dialect = create_engine(f"postgresql+{driver}://u:p@localhost/db").dialect  # no conecta
    conn.in_transaction.return_value = True
    dbapi_conn = conn.connection.dbapi_connection
    dbapi_conn.closed = closed
    dbapi_conn.broken = False
    return conn


def _copy_raising(conn: MagicMock, exc: Exception) -> None:
    conn.connection.cursor.return_value.copy.side_effect = exc


def test_copy_unique_violation_becomes_integrity_error() -> None:
    errors = pytest.importorskip("psycopg.errors")
    conn = _connection("psycopg")
    original = errors.UniqueViolation("duplicate key value violates unique constraint")
    _copy_raising(conn, original)

    with pytest.raises(IntegrityError) as info:
        PostgresCopyStrategy().execute(connection=conn, stmt=insert(_TABLE), records=[{"id": 1}])

    assert info.value.orig is original
    assert "COPY" in str(info.value.statement)
    assert info.value.params is None
    conn.invalidate.assert_not_called()


def test_copy_disconnect_becomes_operational_error_and_invalidates() -> None:
    psycopg = pytest.importorskip("psycopg")
    conn = _connection("psycopg", closed=True)
    original = psycopg.OperationalError("server closed the connection unexpectedly")
    _copy_raising(conn, original)

    with pytest.raises(OperationalError) as info:
        PostgresCopyStrategy().execute(connection=conn, stmt=insert(_TABLE), records=[{"id": 1}])

    assert info.value.connection_invalidated
    conn.invalidate.assert_called_once_with(original)


def test_copy_non_driver_error_is_not_wrapped() -> None:
    pytest.importorskip("psycopg")
    conn = _connection("psycopg")
    _copy_raising(conn, KeyError("id"))

    with pytest.raises(KeyError):
        PostgresCopyStrategy().execute(connection=conn, stmt=insert(_TABLE), records=[{"id": 1}])


def test_execute_values_unique_violation_becomes_integrity_error(monkeypatch: pytest.MonkeyPatch) -> None:
    extras = pytest.importorskip("psycopg2.extras")
    errors = pytest.importorskip("psycopg2.errors")
    original = errors.UniqueViolation("duplicate key value violates unique constraint")

    def _raise(*args: Any, **kwargs: Any) -> None:
        raise original

    monkeypatch.setattr(extras, "execute_values", _raise)
    conn = _connection("psycopg2")

    with pytest.raises(IntegrityError) as info:
        PostgreSQLExecuteValuesStrategy().execute(connection=conn, stmt=insert(_TABLE), records=[{"id": 1}])

    assert info.value.orig is original
    assert "INSERT INTO" in str(info.value.statement)
