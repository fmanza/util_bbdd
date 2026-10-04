"""``mysql`` en metadatos y consumidores: delegación del adapter, estrategias y paridad con ``mariadb``.

MySQL comparte con MariaDB el catálogo de queries y la forma de sus filas, así que cada consumidor debe tratar
``mysql`` exactamente igual que ``mariadb``.
"""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from util_bbdd.doc.infrastructure.renderers.shared.generator_shared import GeneratorTabularRuntime
from util_bbdd.doc.infrastructure.runtime.headers_runtime import DocumentationHeadersRuntime
from util_bbdd.doc.infrastructure.storage.runtime import StorageInventoryRuntime

HEADERS_FILE = Path(__file__).resolve().parents[2] / "src/util_bbdd/doc/data/headers_config.json"


class TestMysqlFollowsMariaDBInConsumers:
    def test_headers_match_mariadb(self) -> None:
        runtime = DocumentationHeadersRuntime()
        config: Any = json.loads(HEADERS_FILE.read_text(encoding="utf-8"))
        assert runtime.build_headers(config, "mysql") == runtime.build_headers(config, "mariadb")

    def test_tabular_runtime_does_not_depend_on_the_engine(self) -> None:
        """D1: las filas de la documentación son neutras (``catalog_rows``); los helpers ya no reciben el motor."""
        indices = [("ix", "col", "No", "BTREE")]
        fks = [("fk", "col", "parent", "id", "NO ACTION", "NO ACTION")]
        assert GeneratorTabularRuntime.process_indices_data(indices) == [["ix", "col", "No", "BTREE"]]
        assert GeneratorTabularRuntime.map_foreign_keys_by_column(foreign_keys=fks, arrow="->") == {
            "col": "fk -> parent(id)"
        }
        assert GeneratorTabularRuntime.map_indices_by_column(indices=indices) == {"col": ["ix"]}

    def test_storage_runtime_has_dedicated_mysql_strategy(self) -> None:
        manager = MagicMock()
        runtime = StorageInventoryRuntime(
            db_manager=manager, logger=MagicMock(), db_type="mysql", database="db1", print_config={}
        )
        assert runtime._uses_generic_storage_fallback() is False
        assert [name for name, _ in runtime._build_storage_query_specs()] == [
            "ficheros_fisicos",
            "temp_tablespaces",
            "temp_storage_variables",
        ]
        assert runtime._get_storage_headers_by_query("ficheros_fisicos")[0] == "DB"
