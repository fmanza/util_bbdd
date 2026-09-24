"""fast_executemany en SQL Server + pyodbc (hallazgos P-01 y P-18 del performance-audit de bulk).

``BulkCrud(enable_fast_executemany=True)`` debe configurar el dialecto igual que
``create_engine(..., fast_executemany=True)``. Si solo se activa ``cursor.fast_executemany`` a espaldas de
SQLAlchemy, el dialecto sigue llamando a ``cursor.setinputsizes()`` en los executemany (pyodbc falla con
``HY104 Invalid precision value`` en columnas DATETIME: P-18) y mantiene insertmanyvalues, de modo que el INSERT nunca
usa fast_executemany (P-01).

Los engines se crean con un DBAPI simulado: no hace falta pyodbc ni servidor.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sqlalchemy import Column, DateTime, Engine, Integer, MetaData, Table, create_engine, event, insert
from sqlalchemy.dialects.mssql.pyodbc import MSDialect_pyodbc

from util_bbdd.bulk._execution.batch import BatchStatementExecutor

pytestmark = pytest.mark.unit


def _engine(url: str) -> Engine:
    paramstyle = "pyformat" if "pymssql" in url else "qmark"
    return create_engine(url, module=MagicMock(version="5.3.0", paramstyle=paramstyle))


@pytest.fixture
def pyodbc_engine() -> Engine:
    return _engine("mssql+pyodbc://u:p@servidor/db?driver=ODBC+Driver+18+for+SQL+Server")


def _insert_uses_insertmanyvalues(engine: Engine) -> bool:
    table = Table("t", MetaData(), Column("id", Integer, primary_key=True, autoincrement=False), Column("d", DateTime))
    compiled = insert(table).compile(dialect=engine.dialect, column_keys=["id", "d"], for_executemany=True)
    return compiled._insertmanyvalues is not None


def test_pyodbc_dialect_is_configured_like_create_engine_fast_executemany(pyodbc_engine: Engine) -> None:
    assert _insert_uses_insertmanyvalues(pyodbc_engine)  # estado de partida del dialecto

    BatchStatementExecutor(engine=pyodbc_engine, chunk_size=10, enable_fast_executemany=True)

    reference_fast = MSDialect_pyodbc(fast_executemany=True)  # lo que fija create_engine(fast_executemany=True)
    dialect = pyodbc_engine.dialect
    # P-18: con fast_executemany en el dialecto, SQLAlchemy deja de llamar a setinputsizes() en los executemany.
    assert dialect.fast_executemany is reference_fast.fast_executemany is True  # type: ignore[attr-defined]
    # P-01: sin insertmanyvalues, el INSERT llega al cursor como executemany y usa fast_executemany.
    assert dialect.use_insertmanyvalues_wo_returning is reference_fast.use_insertmanyvalues_wo_returning is False
    assert not _insert_uses_insertmanyvalues(pyodbc_engine)


def test_no_cursor_listener_is_registered(pyodbc_engine: Engine) -> None:
    BatchStatementExecutor(engine=pyodbc_engine, chunk_size=10, enable_fast_executemany=True)

    assert not pyodbc_engine.dispatch.before_cursor_execute
    assert not event.contains(pyodbc_engine, "before_cursor_execute", lambda *a: None)


def test_disabled_flag_leaves_dialect_untouched(pyodbc_engine: Engine) -> None:
    BatchStatementExecutor(engine=pyodbc_engine, chunk_size=10, enable_fast_executemany=False)

    assert pyodbc_engine.dialect.fast_executemany is False  # type: ignore[attr-defined]
    assert _insert_uses_insertmanyvalues(pyodbc_engine)


def test_pymssql_engine_is_not_modified() -> None:
    engine = _engine("mssql+pymssql://u:p@servidor/db")

    BatchStatementExecutor(engine=engine, chunk_size=10, enable_fast_executemany=True)

    assert not hasattr(engine.dialect, "fast_executemany")
    assert _insert_uses_insertmanyvalues(engine)


def test_registration_is_idempotent(pyodbc_engine: Engine) -> None:
    BatchStatementExecutor(engine=pyodbc_engine, chunk_size=10, enable_fast_executemany=True)
    BatchStatementExecutor(engine=pyodbc_engine, chunk_size=10, enable_fast_executemany=True)

    assert pyodbc_engine.dialect.fast_executemany is True  # type: ignore[attr-defined]
    assert not pyodbc_engine.dispatch.before_cursor_execute
