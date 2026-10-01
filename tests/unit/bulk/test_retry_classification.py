"""Reintentos de ``ParallelBulkLoader`` por código de error y con backoff (B-13 y B-14, performance-audit 2026-10-01).

B-13: antes se reintentaba por clase (``OperationalError``/``TimeoutError``). PyMySQL mapea a esa clase errores
permanentes (1045, 1054, 1292) y oracledb deja fuera el deadlock (ORA-00060 es ``DatabaseError``). Ahora decide el código.
B-14: antes se reintentaba al instante; ahora con backoff exponencial y jitter completo.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.exc import DatabaseError, DBAPIError, IntegrityError, OperationalError

from util_bbdd.bulk import ParallelBulkLoader
from util_bbdd.bulk._support.retry import is_retriable

pytestmark = pytest.mark.unit


def _wrap(orig: BaseException, cls: type[DBAPIError] = OperationalError, **kwargs: Any) -> DBAPIError:
    return cls("SQL", {}, orig, **kwargs)


# ---------------------------------------------------------------------------------------------------------- PyMySQL

pymysql_err = pytest.importorskip("pymysql.err")


@pytest.mark.parametrize(
    ("errno", "expected"),
    [
        (1213, True),  # deadlock
        (1205, True),  # lock wait timeout
        (2006, True),  # MySQL server has gone away
        (2013, True),  # lost connection
        (1045, False),  # acceso denegado (OperationalError en PyMySQL)
        (1142, False),  # comando denegado en la tabla
        (1054, False),  # columna desconocida
        (1292, False),  # valor incorrecto
    ],
)
def test_pymysql_by_errno(errno: int, expected: bool) -> None:
    orig = pymysql_err.OperationalError(errno, "mensaje")
    assert is_retriable(_wrap(orig)) is expected


def test_mariadb_connector_errno_attribute() -> None:
    orig = Exception("deadlock")
    orig.errno = 1213  # type: ignore[attr-defined]
    assert is_retriable(_wrap(orig)) is True


# ---------------------------------------------------------------------------------------------------------- psycopg


def test_psycopg_by_sqlstate() -> None:
    errors = pytest.importorskip("psycopg.errors")
    assert is_retriable(_wrap(errors.DeadlockDetected("x"))) is True
    assert is_retriable(_wrap(errors.SerializationFailure("x"))) is True
    assert is_retriable(_wrap(errors.AdminShutdown("x"))) is True
    assert is_retriable(_wrap(errors.DiskFull("x"))) is False  # OperationalError en psycopg, pero no transitorio
    assert is_retriable(_wrap(errors.UniqueViolation("x"), IntegrityError)) is False
    assert is_retriable(_wrap(errors.InsufficientPrivilege("x"))) is False


def test_psycopg2_pgcode() -> None:
    orig = Exception("deadlock")
    orig.pgcode = "40P01"  # type: ignore[attr-defined]
    assert is_retriable(_wrap(orig)) is True


# ---------------------------------------------------------------------------------------------------------- oracledb


@pytest.mark.parametrize(
    ("code", "full_code", "expected"),
    [
        (60, "ORA-00060", True),
        (3113, "ORA-03113", True),
        (0, "DPY-4011", True),
        (942, "ORA-00942", False),
        (1, "ORA-00001", False),
    ],
)
def test_oracle_by_code(code: int, full_code: str, expected: bool) -> None:
    # Misma forma que oracledb (verificado contra Oracle 23): args[0] es un _Error con code y full_code.
    orig = Exception(SimpleNamespace(code=code, full_code=full_code))
    assert is_retriable(_wrap(orig, DatabaseError)) is expected


# ---------------------------------------------------------------------------------------------------------- SQL Server


@pytest.mark.parametrize(
    ("sqlstate", "message", "expected"),
    [
        ("HYT00", "[HYT00] Query timeout expired (0)", True),
        ("08S01", "[08S01] Communication link failure (10054)", True),
        ("40001", "[40001] Transaction (Process ID 55) was deadlocked ... (1205) (SQLExecDirectW)", True),
        ("42000", "[42000] Transaction was deadlocked ... (1205) (SQLExecDirectW)", True),
        ("23000", "[23000] Violation of PRIMARY KEY constraint (2627)", False),
        ("42S02", "[42S02] Invalid object name 'x'. (208)", False),
    ],
)
def test_pyodbc_by_sqlstate_and_native_error(sqlstate: str, message: str, expected: bool) -> None:
    assert is_retriable(_wrap(Exception(sqlstate, message), DBAPIError)) is expected


def test_pymssql_deadlock_number() -> None:
    assert is_retriable(_wrap(Exception(1205, b"deadlock victim"))) is True
    assert is_retriable(_wrap(Exception(2627, b"duplicate key"), IntegrityError)) is False


# ---------------------------------------------------------------------------------------------------------- generales


def test_timeout_and_invalidated_connection_are_retriable() -> None:
    assert is_retriable(TimeoutError()) is True
    assert is_retriable(_wrap(Exception("sin código"), connection_invalidated=True)) is True


@pytest.mark.parametrize("exc", [ValueError("x"), KeyError("k"), _wrap(Exception("sin código")), _wrap(Exception())])
def test_everything_else_is_permanent(exc: BaseException) -> None:
    assert is_retriable(exc) is False


# ---------------------------------------------------------------------------------------------------------- loader


@pytest.fixture
def engine(tmp_path: Any) -> Any:
    eng = create_engine(f"sqlite:///{tmp_path / 'retry.db'}")
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10))).create(eng)
    return eng


def _reader_failing(times: int, exc_factory: Any) -> Any:
    calls = {"n": 0}

    def reader() -> Any:
        calls["n"] += 1
        if calls["n"] <= times:
            raise exc_factory()
        return iter([pd.DataFrame({"id": [1, 2], "v": ["a", "b"]})])

    reader.calls = calls  # type: ignore[attr-defined]
    return reader


def _deadlock() -> DBAPIError:
    return _wrap(pymysql_err.OperationalError(1213, "Deadlock found"))


def test_loader_retries_transient_error_with_exponential_backoff(engine: Any) -> None:
    loader = ParallelBulkLoader(engine, max_workers=1, max_retries=3, retry_backoff=(0.5, 1.5))
    sleeps: list[float] = []
    loader._sleep = sleeps.append  # type: ignore[method-assign]
    loader._jitter = lambda low, high: high  # type: ignore[method-assign]  # tope de la ventana, sin azar
    reader = _reader_failing(3, _deadlock)

    result = loader.load("items", [reader])

    assert result.partition_errors == []
    assert result.total_rows == 2
    assert sleeps == [0.5, 1.0, 1.5]  # 0,5 · 2**(n−1), acotado a 1,5
    assert result.partition_results[0].retries == 3
    assert result.partition_results[0].retry_wait_seconds == pytest.approx(3.0)


def test_loader_does_not_retry_permanent_pymysql_operational_error(engine: Any) -> None:
    loader = ParallelBulkLoader(engine, max_workers=1, max_retries=3)
    loader._sleep = MagicMock()  # type: ignore[method-assign]
    reader = _reader_failing(1, lambda: _wrap(pymysql_err.OperationalError(1045, "Access denied")))

    result = loader.load("items", [reader])

    assert reader.calls["n"] == 1
    assert result.partition_results[0].retries == 0
    assert len(result.partition_errors) == 1
    loader._sleep.assert_not_called()


def test_zero_backoff_retries_immediately(engine: Any) -> None:
    loader = ParallelBulkLoader(engine, max_workers=1, max_retries=1, retry_backoff=(0, 0))
    loader._sleep = MagicMock()  # type: ignore[method-assign]

    result = loader.load("items", [_reader_failing(1, _deadlock)])

    assert result.partition_errors == []
    loader._sleep.assert_not_called()
    assert result.partition_results[0].retry_wait_seconds == 0.0


def test_custom_retry_on(engine: Any) -> None:
    loader = ParallelBulkLoader(engine, max_workers=1, max_retries=1, retry_backoff=(0, 0), retry_on=lambda e: True)
    result = loader.load("items", [_reader_failing(1, lambda: KeyError("lector"))])
    assert result.partition_errors == []


@pytest.mark.parametrize("backoff", [(-1, 1), (1, float("inf")), (1,), (True, 1), ("1", 2)])
def test_invalid_backoff_is_rejected(engine: Any, backoff: Any) -> None:
    with pytest.raises(ValueError, match="retry_backoff"):
        ParallelBulkLoader(engine, retry_backoff=backoff)


# A2 (audit-code 2026-10-01): los errores reales del conector ``mariadb`` llevan ``sqlstate`` y ``errno``; el lock wait
# timeout (1205) tiene sqlstate HY000 y no se reintentaba porque se decidía por sqlstate antes que por errno.


class _MariaDBError(Exception):
    def __init__(self, message: str, *, errno: int, sqlstate: str) -> None:
        super().__init__(message)
        self.errno = errno
        self.sqlstate = sqlstate


@pytest.mark.parametrize(
    ("errno", "sqlstate", "expected"),
    [
        (1205, "HY000", True),  # lock wait timeout
        (1213, "40001", True),  # deadlock
        (2013, "HY000", True),  # conexión perdida
        (1054, "42S22", False),  # columna desconocida
        (1062, "23000", False),  # clave duplicada
    ],
)
def test_mariadb_connector_decides_by_errno(errno: int, sqlstate: str, expected: bool) -> None:
    assert is_retriable(_wrap(_MariaDBError("x", errno=errno, sqlstate=sqlstate))) is expected
