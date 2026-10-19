"""Tests de la estrategia común de índices secundarios (``bulk/_support/secondary_indexes.py``, 3.2.0)."""

from __future__ import annotations

import logging

from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk._support.secondary_indexes import (
    IndexDdlRunner,
    IndexStep,
    SecondaryIndexPlanner,
    _if_not_exists,
    resolve_index_mode,
    restore_batches,
)
from util_bbdd.metadata import facts

pytestmark = pytest.mark.unit

_LOG = logging.getLogger("test_secondary_indexes")


def _prep() -> MagicMock:
    prep = MagicMock()
    prep.quote.side_effect = lambda name: f"`{name}`"
    return prep


@pytest.mark.parametrize(
    ("value", "expected"), [(False, None), (None, None), (True, "secondary"), ("secondary", "secondary")]
)
def test_resolve_index_mode(value: object, expected: object) -> None:
    assert resolve_index_mode(value, "x") == expected  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["all", "SECONDARY", 1, 0])
def test_resolve_index_mode_rejects_other_values(value: object) -> None:
    with pytest.raises(ValueError, match="campo"):
        resolve_index_mode(value, "campo")  # type: ignore[arg-type]


def test_if_not_exists_is_idempotent() -> None:
    assert _if_not_exists("CREATE INDEX ix ON t (a)") == "CREATE INDEX IF NOT EXISTS ix ON t (a)"
    assert _if_not_exists("CREATE INDEX IF NOT EXISTS ix ON t (a)") == "CREATE INDEX IF NOT EXISTS ix ON t (a)"
    assert _if_not_exists("ALTER INDEX x REBUILD") == "ALTER INDEX x REBUILD"


def test_restore_batches_groups_innodb_per_table_and_keeps_order() -> None:
    steps = [
        IndexStep("a", "`a`", "ix1", "…", "ADD INDEX `ix1` (`c`)", "recreated", grouped=True),
        IndexStep("b", "`b`", "ix2", "…", "ALTER INDEX ix2 REBUILD", "rebuilt"),
        IndexStep("a", "`a`", "ix3", "…", "ADD INDEX `ix3` (`d`)", "recreated", grouped=True),
    ]
    batches = restore_batches(steps)
    assert [sql for sql, _ in batches] == [
        "ALTER TABLE `a` ADD INDEX `ix1` (`c`), ADD INDEX `ix3` (`d`)",
        "ALTER INDEX ix2 REBUILD",
    ]
    assert [[s.index_name for s in members] for _, members in batches] == [["ix1", "ix3"], ["ix2"]]


def test_planner_skips_postgresql_indexes_without_ddl() -> None:
    planner = SecondaryIndexPlanner("postgresql", _prep())
    with patch.object(
        facts, "secondary_nonunique_indexes", return_value=[("ix_a", None), ("ix_b", "CREATE INDEX ix_b ON t (b)")]
    ):
        steps = planner.plan(MagicMock(), table="t", schema="public", quoted_table="public.t")
    assert [(s.index_name, s.disable_sql, s.restore_sql) for s in steps] == [
        ("ix_b", "DROP INDEX `public`.`ix_b`", "CREATE INDEX IF NOT EXISTS ix_b ON t (b)")
    ]


def test_planner_returns_nothing_for_unsupported_dialects() -> None:
    assert SecondaryIndexPlanner("sqlite", _prep()).plan(MagicMock(), table="t", schema=None, quoted_table="t") == []


def test_runner_uses_savepoint_without_commit_in_session_mode() -> None:
    conn = MagicMock()
    step = IndexStep("t", "t", "ix", "ALTER INDEX ix ON t DISABLE", "ALTER INDEX ix ON t REBUILD", "rebuilt")
    runner = IndexDdlRunner("mssql", _LOG, commit=False, savepoint=True)
    assert runner.disable(conn, [step]) == [step]
    assert conn.begin_nested.call_count == 1
    conn.commit.assert_not_called()


def test_runner_commits_and_rolls_back_in_autonomous_mode() -> None:
    conn = MagicMock()
    conn.execute.side_effect = [MagicMock(), SQLAlchemyError("boom")]
    steps = [
        IndexStep("t", "t", "ix1", "DISABLE 1", "REBUILD 1", "rebuilt"),
        IndexStep("t", "t", "ix2", "DISABLE 2", "REBUILD 2", "rebuilt"),
    ]
    runner = IndexDdlRunner("oracle", _LOG, commit=True, savepoint=False)
    assert [s.index_name for s in runner.disable(conn, steps)] == ["ix1"]
    conn.commit.assert_called_once()
    conn.rollback.assert_called_once()
    conn.begin_nested.assert_not_called()


def _stats_row(name: str, column: str | None, **extra: object) -> MagicMock:
    row = MagicMock()
    row._mapping = {"INDEX_NAME": name, "COLUMN_NAME": column, "INDEX_TYPE": "BTREE", "COLLATION": "A", **extra}
    return row


def test_mysql_facts_filter_and_build_add_clauses() -> None:
    """Fuera: prefijo, DESC, comentario, invisible (MySQL), ignorado (MariaDB), funcional, no BTREE y los de FK."""
    conn = MagicMock()
    conn.dialect.identifier_preparer.quote.side_effect = lambda name: f"`{name}`"
    stats = [
        _stats_row("ix_ab", "a"),
        _stats_row("ix_ab", "b"),
        _stats_row("ix_pref", "s", SUB_PART=10),
        _stats_row("ix_desc", "c", COLLATION="D"),
        _stats_row("ix_comment", "a", INDEX_COMMENT="x"),
        _stats_row("ix_invisible", "a", IS_VISIBLE="NO"),
        _stats_row("ix_ignored", "a", IGNORED="YES"),
        _stats_row("ix_func", None, EXPRESSION="(a + 1)"),
        _stats_row("ix_ft", "s", INDEX_TYPE="FULLTEXT"),
        _stats_row("ix_fk", "p"),
        _stats_row("ix_fk_wide", "p"),
        _stats_row("ix_fk_wide", "a"),
        _stats_row("ix_ref", "r"),
    ]
    fks = [
        ("db", "t", "fk_p", "p", "db", "parent", "id", 1, 1),  # la tabla es la hija: ix_fk y ix_fk_wide empiezan por p
        ("db", "child", "fk_r", "zr", "db", "t", "r", 1, 1),  # otra tabla la referencia por r
    ]
    conn.execute.side_effect = [iter(stats), iter(fks)]
    assert facts.secondary_nonunique_indexes(conn, None, "t", "mysql") == [("ix_ab", "INDEX `ix_ab` (`a`, `b`)")]
