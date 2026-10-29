"""U-9.1 (G44 de util_bbdd_web): ``NUMBER`` de Oracle sin pasar por ``float`` en las consultas, con dobles."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest

from util_bbdd.executors._oracle_numbers import oracle_output_type_handler, prepare_query_cursor
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor

oracledb = pytest.importorskip("oracledb")

pytestmark = pytest.mark.unit


@dataclass
class _FetchInfo:
    """Como ``oracledb.FetchInfo``: tipo, precisión y escala de la columna."""

    type_code: Any
    precision: int | None
    scale: int | None


class _Cursor:
    arraysize = 100

    def __init__(self) -> None:
        self.outputtypehandler: Any = None
        self.description = (("X", None, None, None, None, None, None),)
        self.vars: list[tuple[Any, int, Any]] = []

    def var(self, type_code: Any, arraysize: int, outconverter: Any) -> tuple[Any, int, Any]:
        self.vars.append((type_code, arraysize, outconverter))
        return self.vars[-1]

    def execute(self, *args: Any) -> None:
        pass

    def fetchall(self) -> list[tuple[int]]:
        return [(1,)]

    def fetchone(self) -> tuple[int]:
        return (1,)

    def close(self) -> None:
        pass


class _Connection:
    def __init__(self, module: str = "oracledb.connection", handler: Any = None) -> None:
        # el driver se detecta por el módulo de la clase (``oracledb.connection`` en la real)
        self.__class__ = type("Connection", (_Connection,), {"__module__": module})
        self.outputtypehandler = handler
        self.cursors: list[_Cursor] = []

    def cursor(self) -> _Cursor:
        self.cursors.append(_Cursor())
        return self.cursors[-1]

    def rollback(self) -> None:
        pass


def _converter(precision: int | None, scale: int | None) -> Any:
    cursor = _Cursor()
    result = oracle_output_type_handler(cursor, _FetchInfo(oracledb.DB_TYPE_NUMBER, precision, scale))
    if result is None:
        return None
    type_code, arraysize, converter = result
    assert (type_code, arraysize) == (oracledb.DB_TYPE_VARCHAR, cursor.arraysize)
    return converter


def test_number_with_scale_is_decimal() -> None:
    converter = _converter(38, 3)
    assert converter("12345678901234567.891") == Decimal("12345678901234567.891")
    assert type(converter("7")) is Decimal  # con escala, siempre Decimal (como PostgreSQL con numeric(p,s))


@pytest.mark.parametrize("scale", [0, -127, None])
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.5", Decimal("1.5")),
        ("-.5", Decimal("-0.5")),
        ("7", 7),
        ("-7", -7),
        ("1000000000000000000000000000000", 10**30),
        ("1E+30", 10**30),
        ("123456789012345678901234567890", 123456789012345678901234567890),
    ],
)
def test_unconstrained_number_is_int_or_decimal(scale: int | None, text: str, expected: int | Decimal) -> None:
    value = _converter(0, scale)(text)
    assert value == expected
    assert type(value) is type(expected)


def test_precision_none_counts_as_unconstrained() -> None:
    assert _converter(None, None)("2") == 2


@pytest.mark.parametrize(("precision", "scale"), [(10, 0), (38, 0), (10, -2), (126, -127), (63, -127)])
def test_integers_and_float_are_left_to_the_driver(precision: int, scale: int) -> None:
    """``NUMBER(p)`` y ``NUMBER(p, s<0)`` ya son ``int``; ``FLOAT`` (p > 0, s = -127) sigue siendo ``float``."""
    assert _converter(precision, scale) is None


@pytest.mark.parametrize("type_name", ["DB_TYPE_BINARY_DOUBLE", "DB_TYPE_BINARY_FLOAT", "DB_TYPE_VARCHAR"])
def test_other_types_are_left_to_the_driver(type_name: str) -> None:
    info = _FetchInfo(getattr(oracledb, type_name), 0, -127)
    assert oracle_output_type_handler(_Cursor(), info) is None


def test_prepare_only_oracledb_cursors() -> None:
    oracle_cursor, other_cursor = _Cursor(), _Cursor()
    prepare_query_cursor(_Connection(), oracle_cursor)
    prepare_query_cursor(_Connection("psycopg"), other_cursor)

    assert oracle_cursor.outputtypehandler is oracle_output_type_handler
    assert other_cursor.outputtypehandler is None


def test_prepare_keeps_the_connection_handler() -> None:
    """Si la conexión ya tiene un ``outputtypehandler`` propio, manda el del usuario (el cursor lo hereda)."""
    cursor = _Cursor()
    prepare_query_cursor(_Connection(handler=lambda cursor, metadata: None), cursor)
    assert cursor.outputtypehandler is None


def test_real_oracledb_connection_module() -> None:
    assert oracledb.Connection.__module__.startswith("oracledb")
    assert oracledb.AsyncConnection.__module__.startswith("oracledb")


@pytest.mark.parametrize("module", ["oracledb.connection", "psycopg"])
def test_sync_executor_prepares_query_cursors(module: str) -> None:
    conn = _Connection(module)
    executor = SyncQueryExecutor(lambda: conn, lambda _conn: None)
    executor.execute_custom_many("SELECT 1 FROM dual")
    executor.execute_custom_result("SELECT 1 FROM dual", read_only=True, db_type="oracle")

    prepared = [c for c in conn.cursors if c.outputtypehandler is oracle_output_type_handler]
    # solo los de las dos consultas, no los del prólogo de solo lectura
    assert len(prepared) == (2 if module.startswith("oracledb") else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("module", ["oracledb.connection", "aiomysql.connection"])
async def test_async_executor_prepares_query_cursors(module: str) -> None:
    conn = _Connection(module)

    async def provide() -> Any:
        return conn

    async def release(_conn: Any) -> None:
        pass

    executor = AsyncQueryExecutor(provide, release)
    await executor.execute_custom_many("SELECT 1 FROM dual")
    await executor.execute_custom_result("SELECT 1 FROM dual", read_only=True, db_type="oracle")

    prepared = [c for c in conn.cursors if c.outputtypehandler is oracle_output_type_handler]
    assert len(prepared) == (2 if module.startswith("oracledb") else 0)
