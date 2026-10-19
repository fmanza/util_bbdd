"""T1 (2026-10-18): ``elapsed_ms`` se mide con un reloj monotónico, no con la hora de pared (``time.time()``).

Si el reloj del sistema retrocede (ajuste de NTP, cambio de hora) durante una consulta, ``time.time()`` daba una
duración negativa en ``QueryResolver.resolve`` y en los logs de los ejecutores sync/async.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from util_bbdd.models import QueryDefinition
from util_bbdd.query import QueryResolver

pytestmark = pytest.mark.unit


def test_resolver_elapsed_ms_is_not_negative_when_the_wall_clock_goes_back() -> None:
    registry = MagicMock()
    registry.get_query_definition.return_value = QueryDefinition(
        name="q", db_type="mariadb", sql_template="SELECT 1", required_params=[]
    )
    resolver = QueryResolver(registry=registry, db_type="mariadb")
    with patch("time.time", side_effect=[1_000.0, 990.0, 990.0, 990.0]):  # la hora de pared retrocede 10 s
        resolved = resolver.resolve("q", {})
    assert resolved.metadata["elapsed_ms"] >= 0


@pytest.mark.parametrize(
    "module",
    [
        "util_bbdd.executors.sync_query_executor",
        "util_bbdd.executors.async_query_executor",
        "util_bbdd.query.resolver",
    ],
)
def test_executors_do_not_measure_with_the_wall_clock(module: str) -> None:
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(module))
    assert "time.time()" not in source
