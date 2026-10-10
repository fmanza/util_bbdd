"""F5 (v0.41.3): ``clear_cache(table=…)`` descarta el schema del manager aunque su nombre no esté normalizado."""

from __future__ import annotations

import logging

from typing import Any

import pytest

from util_bbdd.managers._manager_shared_mixin import DatabaseManagerSharedMixin
from util_bbdd.metadata.model import Kind


class _Manager(DatabaseManagerSharedMixin):
    def __init__(self, db_type: str, user: str) -> None:
        self.logger = logging.getLogger(__name__)
        self.db_type = db_type
        self.database = ""
        self.conn_params: dict[str, Any] = {"user": user, "host": "h", "port": 1521}


def _cached(manager: _Manager) -> bool:
    cache = manager._catalog_cache()
    key = (manager._catalog_source_id(), manager._catalog_default_schema(), Kind.TABLES, None)
    return cache.get(key) is not None


@pytest.mark.parametrize(
    ("db_type", "user"),
    [("oracle", '"zz_f5"'), ("oracle", "bench"), ("hsqldb", '"zz_f5"')],
    ids=["oracle-entrecomillado-minusculas", "oracle-normal", "hsqldb-entrecomillado"],
)
def test_targeted_clear_cache_drops_the_manager_schema(db_type: str, user: str) -> None:
    manager = _Manager(db_type, user)
    cache = manager._catalog_cache()
    # La clave con que get_schema_metadata() sin schema guarda lo leído: el contexto del manager tal cual
    key = (manager._catalog_source_id(), manager._catalog_default_schema(), Kind.TABLES, None)
    cache.get_or_load(key, lambda: ("tabla",))
    assert _cached(manager)

    manager.clear_cache(table="cualquiera")

    assert not _cached(manager)
