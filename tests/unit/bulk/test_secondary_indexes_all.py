"""Tests del modo ``disable_indexes="all"`` de la estrategia común de índices (v3.3.0) y de ``fk_orphans``."""

from __future__ import annotations

import logging

from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk._support.fk_orphans import orphan_check_sql
from util_bbdd.bulk._support.secondary_indexes import (
    IndexDdlRunner,
    IndexStep,
    SecondaryIndexPlanner,
    duplicates_sql,
    rebuild_error,
    resolve_index_mode,
    restore_batches,
)
from util_bbdd.exceptions import IndexRebuildError
from util_bbdd.metadata import facts

pytestmark = pytest.mark.unit

_LOG = logging.getLogger("test_secondary_indexes_all")
_UNIQUE = facts.UniqueIndexFact
_INBOUND = facts.InboundForeignKeyFact


def _prep() -> MagicMock:
    prep = MagicMock()
    prep.quote.side_effect = lambda name: f"`{name}`"
    prep.quote_identifier.side_effect = lambda name: f"`{name}`"
    return prep


def _plan_all(
    dialect: str, uniques: list[object], inbound: list[object], secondary: list[tuple[str, str | None]]
) -> list[IndexStep]:
    with (
        patch.object(facts, "unique_indexes", return_value=uniques),
        patch.object(facts, "inbound_foreign_keys", return_value=inbound),
        patch.object(facts, "secondary_nonunique_indexes", return_value=secondary),
        patch.object(facts, "storage_engine", return_value="InnoDB"),
    ):
        return SecondaryIndexPlanner(dialect, _prep()).plan(
            MagicMock(), table="t", schema=None, quoted_table="`t`", mode="all"
        )


def _restore_sql(steps: list[IndexStep]) -> list[str]:
    return [sql for sql, _ in restore_batches(steps)]


def test_resolve_index_mode_accepts_all() -> None:
    assert resolve_index_mode("all", "x") == "all"


def test_mssql_all_disables_unique_and_reenables_inbound_fks_after_rebuild() -> None:
    steps = _plan_all(
        "mssql",
        [_UNIQUE("uq_code", "unique_constraint", ("code",))],
        [
            _INBOUND("uq_code", "dbo", "child", "fk_ok", True, True),
            _INBOUND("uq_code", "dbo", "child", "fk_untrusted", True, False),
            _INBOUND("uq_code", "dbo", "child", "fk_off", False, False),  # ya deshabilitada: se queda así
            _INBOUND("pk_clustered", "dbo", "child", "fk_pk", True, True),  # su índice no se toca
        ],
        [("ix_a", None)],
    )
    assert [(s.index_name, s.disable_sql) for s in steps] == [
        ("uq_code", "ALTER INDEX `uq_code` ON `t` DISABLE"),
        ("fk_ok", ""),
        ("fk_untrusted", ""),
        ("ix_a", "ALTER INDEX `ix_a` ON `t` DISABLE"),
    ]
    assert _restore_sql(steps) == [
        "ALTER INDEX `uq_code` ON `t` REBUILD",
        "ALTER INDEX `ix_a` ON `t` REBUILD",
        "ALTER TABLE `dbo`.`child` WITH CHECK CHECK CONSTRAINT `fk_ok`",
        "ALTER TABLE `dbo`.`child` CHECK CONSTRAINT `fk_untrusted`",
    ]


def test_oracle_all_disables_constraints_cascade_and_reenables_children() -> None:
    steps = _plan_all(
        "oracle",
        [_UNIQUE("PK_T", "pk", ("ID",))],
        [_INBOUND("PK_T", "HR", "CHILD", "FK_C", True, True)],
        [],
    )
    assert steps[0].disable_sql == "ALTER TABLE `t` DISABLE CONSTRAINT `PK_T` CASCADE"
    assert _restore_sql(steps) == [
        "ALTER TABLE `t` ENABLE VALIDATE CONSTRAINT `PK_T`",
        "ALTER TABLE `HR`.`CHILD` ENABLE VALIDATE CONSTRAINT `FK_C`",
    ]


def test_postgresql_all_drops_inbound_fks_first_and_validates_them_last() -> None:
    steps = _plan_all(
        "postgresql",
        [
            _UNIQUE("t_pkey", "pk", ("id",), "PRIMARY KEY (id)", "t_pkey"),
            _UNIQUE("ux_alt", "unique_index", ("alt",), "CREATE UNIQUE INDEX ux_alt ON public.t USING btree (alt)"),
        ],
        [_INBOUND("", "public", "child", "fk_c", True, True, "FOREIGN KEY (pid) REFERENCES t(id)")],
        [("ix_a", "CREATE INDEX ix_a ON public.t USING btree (a)")],
    )
    assert [s.disable_sql for s in steps if s.disable_sql] == [
        "ALTER TABLE `public`.`child` DROP CONSTRAINT `fk_c`",
        "ALTER TABLE `t` DROP CONSTRAINT `t_pkey`",
        "DROP INDEX `ux_alt`",
        "DROP INDEX `ix_a`",
    ]
    assert _restore_sql(steps) == [
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_alt ON public.t USING btree (alt)",
        "CREATE INDEX IF NOT EXISTS ix_a ON public.t USING btree (a)",
        "ALTER TABLE `t` ADD CONSTRAINT `t_pkey` PRIMARY KEY (id)",
        "ALTER TABLE `public`.`child` ADD CONSTRAINT `fk_c` FOREIGN KEY (pid) REFERENCES t(id) NOT VALID",
        "ALTER TABLE `public`.`child` VALIDATE CONSTRAINT `fk_c`",
    ]


def test_postgresql_not_valid_fk_is_recreated_without_validation() -> None:
    steps = _plan_all(
        "postgresql",
        [_UNIQUE("t_pkey", "pk", ("id",), "PRIMARY KEY (id)", "t_pkey")],
        [_INBOUND("", "public", "child", "fk_c", True, False, "FOREIGN KEY (pid) REFERENCES t(id) NOT VALID")],
        [],
    )
    assert not [s for s in steps if "VALIDATE CONSTRAINT" in s.restore_sql]


def test_mysql_all_adds_unique_and_secondary_in_one_alter() -> None:
    steps = _plan_all(
        "mysql",
        [_UNIQUE("uq_code", "unique_index", ("code",), "UNIQUE INDEX `uq_code` (`code`)")],
        [],
        [("ix_a", "INDEX `ix_a` (`a`)")],
    )
    assert _restore_sql(steps) == ["ALTER TABLE `t` ADD UNIQUE INDEX `uq_code` (`code`), ADD INDEX `ix_a` (`a`)"]


def test_secondary_mode_ignores_uniques() -> None:
    with (
        patch.object(facts, "unique_indexes") as uniques,
        patch.object(facts, "secondary_nonunique_indexes", return_value=[]),
    ):
        SecondaryIndexPlanner("mssql", _prep()).plan(MagicMock(), table="t", schema=None, quoted_table="`t`")
    uniques.assert_not_called()


def test_runner_skips_dependent_steps_and_does_not_execute_restore_only_ones() -> None:
    steps = [
        IndexStep("t", "t", "uq", "DISABLE uq", "REBUILD uq", "rebuilt", priority=0),
        IndexStep("c", "c", "fk", "", "CHECK fk", "rebuilt", step_id="fk:c.fk", depends_on="t.uq"),
    ]
    failing = MagicMock()
    failing.execute.side_effect = SQLAlchemyError("locked")
    assert IndexDdlRunner("mssql", _LOG, commit=False, savepoint=False).disable(failing, steps) == []
    conn = MagicMock()
    done = IndexDdlRunner("mssql", _LOG, commit=False, savepoint=False).disable(conn, steps)
    assert [s.index_name for s in done] == ["uq", "fk"]
    assert [str(c.args[0]) for c in conn.execute.call_args_list] == ["DISABLE uq"]  # la FK la deshabilita el motor


def test_failed_unique_rebuild_reports_duplicates_and_builds_the_error() -> None:
    conn = MagicMock()
    duplicates = MagicMock()
    duplicates.fetchall.return_value = [("A1", 2), ("B7", 3)]
    conn.execute.side_effect = [SQLAlchemyError("duplicate key"), duplicates, MagicMock()]
    steps = [
        IndexStep("t", "t", "uq", "…", "REBUILD uq", "rebuilt", priority=0, unique_columns=("code",)),
        IndexStep("t", "t", "ix", "…", "REBUILD ix", "rebuilt"),
    ]
    runner = IndexDdlRunner("postgresql", _LOG, commit=False, savepoint=False)
    results = runner.restore(conn, steps)
    assert [(r.index_name, r.action) for r in results] == [("uq", "failed"), ("ix", "rebuilt")]
    assert "A1 → 2" in results[0].error_msg
    assert str(conn.execute.call_args_list[1].args[0]) == (
        "SELECT code, COUNT(*) FROM t GROUP BY code HAVING COUNT(*) > 1 LIMIT 5"
    )
    error = rebuild_error(runner, results, "carga")
    assert isinstance(error, IndexRebuildError)
    assert error.duplicates == {"t.uq": ["A1 → 2", "B7 → 3"]}
    assert error.results == results


def test_rebuild_error_is_none_without_unique_failures() -> None:
    assert rebuild_error(IndexDdlRunner("mssql", _LOG, commit=False, savepoint=False), [], "carga") is None


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        ("mssql", "SELECT TOP 5 a, b, COUNT(*) FROM t GROUP BY a, b HAVING COUNT(*) > 1"),
        ("oracle", "SELECT a, b, COUNT(*) FROM t GROUP BY a, b HAVING COUNT(*) > 1 FETCH FIRST 5 ROWS ONLY"),
        ("mysql", "SELECT a, b, COUNT(*) FROM t GROUP BY a, b HAVING COUNT(*) > 1 LIMIT 5"),
    ],
)
def test_duplicates_sql_per_dialect(dialect: str, expected: str) -> None:
    assert duplicates_sql(dialect, "t", ["a", "b"]) == expected


@pytest.mark.parametrize(
    ("dialect", "prefix", "suffix"),
    [
        ("mssql", "SELECT TOP 1 1 ", ""),
        ("oracle", "SELECT 1 ", " FETCH FIRST 1 ROWS ONLY"),
        ("mysql", "SELECT 1 ", " LIMIT 1"),
    ],
)
def test_orphan_check_sql_per_dialect(dialect: str, prefix: str, suffix: str) -> None:
    fk = {"constrained_columns": ["pid"], "referred_schema": None, "referred_table": "p", "referred_columns": ["id"]}
    assert orphan_check_sql(dialect, _prep(), "`c`", fk) == (
        f"{prefix}FROM `c` c WHERE c.`pid` IS NOT NULL AND NOT EXISTS (SELECT 1 FROM `p` p WHERE p.`id` = c.`pid`){suffix}"
    )
    assert orphan_check_sql(dialect, _prep(), "`c`", {**fk, "referred_columns": []}) is None


# ---------------------------------------------------------------------------
# Validaciones de las opciones (D1, F2, F3 del AUDIT_PLAN)
# ---------------------------------------------------------------------------


def test_parallel_all_requires_disable_constraints() -> None:
    from util_bbdd.bulk.options import ParallelOptions

    with pytest.raises(ValueError, match="disable_constraints"):
        ParallelOptions(disable_indexes="all")
    ParallelOptions(disable_indexes="all", disable_constraints=True)


def test_parallel_all_rejects_isolate() -> None:
    from util_bbdd.bulk.options import BulkOptions, ParallelOptions, RejectOptions

    parallel = ParallelOptions(disable_indexes="all", disable_constraints=True)
    with pytest.raises(ValueError, match="isolate"):
        BulkOptions.of(parallel=parallel, rejects=RejectOptions(on_error="isolate", csv_path="r.csv"))


def test_dump_all_requires_truncate_target_and_rejects_isolate(tmp_path: object) -> None:
    from util_bbdd.dump import DumpConfig

    engine = MagicMock()
    with pytest.raises(ValueError, match="truncate_target"):
        DumpConfig(source_engine=engine, target_engine=engine, manage_indexes="all", truncate_target=False)
    with pytest.raises(ValueError, match="isolate"):
        DumpConfig(
            source_engine=engine,
            target_engine=engine,
            manage_indexes="all",
            on_error="isolate",
            rejects_csv_path="r.csv",
        )
    DumpConfig(source_engine=engine, target_engine=engine, manage_indexes="all")
