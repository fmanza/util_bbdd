"""A9 (fix 2026-09-29): ``engine`` (MariaDB/MySQL) se interpolaba sin validar en ``ENGINE=...``.

Un valor como ``"InnoDB; DROP TABLE x"`` acababa en el DDL. Se acepta cualquier identificador simple (InnoDB, Aria,
MyISAM, ColumnStore, RocksDB...), no una lista cerrada.
"""

from __future__ import annotations

import pytest

from util_bbdd.migrate import MigrationPlanner
from util_bbdd.migrate.charset import validate_storage_engine
from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
from util_bbdd.migrate.emitters.mysql import MySQLDDLEmitter


@pytest.mark.parametrize("engine", ["InnoDB", "Aria", "MyISAM", "ColumnStore", "RocksDB", " innodb "])
def test_simple_identifiers_are_accepted(engine: str) -> None:
    assert validate_storage_engine(engine) == engine.strip()


@pytest.mark.parametrize("engine", ["", "InnoDB; DROP TABLE x", "Inno DB", "InnoDB -- x", "`InnoDB`", "1nno"])
def test_anything_else_is_rejected(engine: str) -> None:
    with pytest.raises(ValueError, match="engine"):
        validate_storage_engine(engine)


@pytest.mark.parametrize("target", ["mariadb", "mysql"])
def test_planner_rejects_invalid_engine_for_mysql_family(target: str) -> None:
    with pytest.raises(ValueError, match="engine"):
        MigrationPlanner(source_engine="oracle", target_engine=target, engine="InnoDB; DROP TABLE x")


def test_planner_ignores_engine_for_other_targets() -> None:
    MigrationPlanner(source_engine="oracle", target_engine="postgresql", engine="no aplica")


@pytest.mark.parametrize("emitter_cls", [MariaDBDDLEmitter, MySQLDDLEmitter])
def test_emitters_validate_engine(emitter_cls: type[MariaDBDDLEmitter]) -> None:
    with pytest.raises(ValueError, match="engine"):
        emitter_cls(charset="utf8mb4", collation="utf8mb4_bin", engine="InnoDB; DROP TABLE x")
    assert emitter_cls(charset="utf8mb4", collation="utf8mb4_bin", engine="Aria")._engine == "Aria"
