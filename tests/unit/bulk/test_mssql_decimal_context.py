"""PD-10 (performance-audit de dump 2026-09-26): precisión de ``Decimal`` con ``fast_executemany`` en SQL Server.

pyodbc convierte cada ``Decimal`` con el contexto ``decimal`` del hilo (28 dígitos por defecto): un DECIMAL(38,s) de más
de 28 dígitos significativos se redondeaba. El ejecutor sube la precisión a 38 solo alrededor de la llamada al driver.
"""

from __future__ import annotations

import decimal

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.bulk._execution.batch import BatchStatementExecutor, _driver_decimal_context

pytestmark = pytest.mark.unit


def _engine(dialect: str, *, fast: bool) -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = dialect
    engine.dialect.fast_executemany = fast
    engine.url.drivername = "mssql+pyodbc" if dialect == "mssql" else dialect
    return engine


@pytest.mark.parametrize(
    ("dialect", "fast", "expected"),
    [("mssql", True, 38), ("mssql", False, 28), ("postgresql", True, 28), ("oracle", False, 28)],
)
def test_precision_inside_the_driver_context(dialect: str, fast: bool, expected: int) -> None:
    with decimal.localcontext() as ctx:
        ctx.prec = 28
        with _driver_decimal_context(_engine(dialect, fast=fast)):
            assert decimal.getcontext().prec == expected
        assert decimal.getcontext().prec == 28  # se restaura


def test_higher_user_precision_is_kept() -> None:
    with decimal.localcontext() as ctx:
        ctx.prec = 60
        with _driver_decimal_context(_engine("mssql", fast=True)):
            assert decimal.getcontext().prec == 60


def test_executor_calls_the_strategy_with_raised_precision() -> None:
    seen: list[int] = []

    class _Strategy:
        def execute(self, *, connection: Any, stmt: Any, records: Any) -> None:
            seen.append(decimal.getcontext().prec)

    engine = _engine("mssql", fast=True)
    executor = BatchStatementExecutor(engine=engine, chunk_size=2, enable_fast_executemany=False)
    executor.execute(records=[{"a": 1}] * 5, stmt=MagicMock(), strategy=_Strategy())

    assert seen == [38, 38, 38]
    assert decimal.getcontext().prec == 28
