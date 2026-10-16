"""``ParallelBulkLoader._hoist_constraints_for_workers`` en PostgreSQL (auditoría de ``bulk`` del 2026-09-24, hallazgo 3).

Sin privilegios para ``DISABLE TRIGGER``, el contexto cedía el control (``yield False``) dentro del
``with engine.begin()`` de la comprobación: esa conexión quedaba fuera del pool, con una transacción abierta, durante
toda la carga de los workers. Ahora la conexión se devuelve antes de ceder el control, con y sin privilegios.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import MetaData, Table

from util_bbdd.bulk import ParallelBulkLoader
from util_bbdd.bulk.options import ParallelOptions

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


def _loader(can_disable: bool, events: list[str], monkeypatch: pytest.MonkeyPatch) -> ParallelBulkLoader:
    loader = ParallelBulkLoader(_engine(can_disable, events), parallel=ParallelOptions(max_workers=2))
    # La tabla se refleja como en BulkCrud (hallazgo 4); aquí basta una Table fija.
    monkeypatch.setattr(loader, "_resolve_table", lambda name: Table("orders", MetaData(), schema="public"))
    return loader


def test_without_privileges_releases_connection_before_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    loader = _loader(False, events, monkeypatch)

    with loader._hoist_constraints_for_workers("public.orders") as hoisted:
        events.append("workers")

    assert hoisted is False
    assert events == ["begin", "SELECT", "end", "workers"]


def test_with_privileges_disables_in_short_transaction_and_restores_after(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    loader = _loader(True, events, monkeypatch)

    with loader._hoist_constraints_for_workers("public.orders") as hoisted:
        events.append("workers")

    assert hoisted is True
    assert events == ["begin", "SELECT", "DISABLE", "end", "workers", "begin", "ENABLE", "end"]


def test_privilege_check_and_ddl_use_the_reflected_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hallazgo 4: el nombre sale de la tabla reflejada (como en BulkCrud), no del texto recibido."""
    from sqlalchemy.dialects import postgresql

    events: list[str] = []
    engine = _engine(True, events)
    engine.dialect = postgresql.dialect()
    loader = ParallelBulkLoader(engine, parallel=ParallelOptions(max_workers=2))
    monkeypatch.setattr(loader, "_resolve_table", lambda name: Table("usuarios", MetaData(), schema="ventas"))
    conn = engine.begin().__enter__()

    with loader._hoist_constraints_for_workers("Ventas.Usuarios"):
        pass

    select_call, disable_call = conn.execute.call_args_list[:2]
    assert select_call.args[1] == {"schema": "ventas", "tbl": "usuarios"}
    assert str(disable_call.args[0]) == "ALTER TABLE ventas.usuarios DISABLE TRIGGER ALL"
