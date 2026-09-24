"""``ParallelBulkLoader._hoist_constraints_for_workers`` en PostgreSQL (auditoría de ``bulk`` del 2026-09-24, hallazgo 3).

Sin privilegios para ``DISABLE TRIGGER``, el contexto cedía el control (``yield False``) dentro del
``with engine.begin()`` de la comprobación: esa conexión quedaba fuera del pool, con una transacción abierta, durante
toda la carga de los workers. Ahora la conexión se devuelve antes de ceder el control, con y sin privilegios.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.bulk import ParallelBulkLoader

pytestmark = pytest.mark.unit


def _engine(can_disable: bool, events: list[str]) -> MagicMock:
    conn = MagicMock()

    def _execute(stmt: Any, *args: Any, **kwargs: Any) -> MagicMock:
        sql = str(stmt)
        events.append("DISABLE" if "DISABLE TRIGGER" in sql else "ENABLE" if "ENABLE TRIGGER" in sql else "SELECT")
        result = MagicMock()
        result.scalar.return_value = can_disable
        return result

    conn.execute.side_effect = _execute

    class _Begin:
        def __enter__(self) -> MagicMock:
            events.append("begin")
            return conn

        def __exit__(self, *exc: object) -> bool:
            events.append("end")
            return False

    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.begin.side_effect = _Begin
    return engine


def test_without_privileges_releases_connection_before_workers() -> None:
    events: list[str] = []
    loader = ParallelBulkLoader(_engine(False, events), max_workers=2)

    with loader._hoist_constraints_for_workers("public.orders") as hoisted:
        events.append("workers")

    assert hoisted is False
    assert events == ["begin", "SELECT", "end", "workers"]


def test_with_privileges_disables_in_short_transaction_and_restores_after() -> None:
    events: list[str] = []
    loader = ParallelBulkLoader(_engine(True, events), max_workers=2)

    with loader._hoist_constraints_for_workers("orders") as hoisted:
        events.append("workers")

    assert hoisted is True
    assert events == ["begin", "SELECT", "DISABLE", "end", "workers", "begin", "ENABLE", "end"]
