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


_ORA_DDL = """CREATE UNIQUE INDEX "HR"."UX_T" ON "HR"."T" (TO_CHAR("DT",'HH24:MI'), "ID") TABLESPACE "USERS\""""


def test_oracle_all_drops_unique_index_without_constraint_and_recreates_it_from_its_ddl() -> None:
    steps = _plan_all(
        "oracle",
        [
            _UNIQUE("PK_T", "pk", ("ID",)),
            _UNIQUE(
                "UX_T", "unique_index", ("SYS_NC00005$", "ID"), _ORA_DDL, key_sql=("TO_CHAR(\"DT\",'HH24:MI')", '"ID"')
            ),
        ],
        [],
        [],
    )
    ux = next(s for s in steps if s.index_name == "UX_T")
    assert (ux.disable_sql, ux.action, ux.recovery_ddl) == ("DROP INDEX `UX_T`", "recreated", _ORA_DDL)
    assert ux.unique_columns == ("TO_CHAR(\"DT\",'HH24:MI')", '"ID"')
    assert ux.unique
    assert _restore_sql(steps)[0] == _ORA_DDL  # antes que la PK, como el resto de únicos; ':' escapado al ejecutar


def test_oracle_unique_index_without_ddl_is_kept_and_reported_as_skipped() -> None:
    steps = _plan_all("oracle", [_UNIQUE("UX_T", "unique_index", ("C",), ddl_error="ORA-31603: no encontrado")], [], [])
    conn = MagicMock()
    runner = IndexDdlRunner("oracle", _LOG, commit=True, savepoint=False)
    done = runner.disable(conn, steps)
    results = runner.restore(conn, done)
    conn.execute.assert_not_called()
    assert [(r.index_name, r.action, r.error_msg) for r in results] == [("UX_T", "skipped", "ORA-31603: no encontrado")]
    assert rebuild_error(runner, results, "carga") is None


def test_failed_recreation_of_a_dropped_unique_index_carries_its_ddl() -> None:
    conn = MagicMock()
    conn.execute.side_effect = [SQLAlchemyError("ORA-01452"), SQLAlchemyError("sin diagnóstico")]
    step = IndexStep(
        "t", "t", "UX_T", "DROP INDEX UX_T", "CREATE …", "recreated", _ORA_DDL, unique_columns=("C",), unique=True
    )
    runner = IndexDdlRunner("oracle", _LOG, commit=True, savepoint=False)
    results = runner.restore(conn, [step])
    assert results[0].action == "failed"
    assert f"DDL para recrearlo: {_ORA_DDL}" in results[0].error_msg
    error = rebuild_error(runner, results, "carga")
    assert isinstance(error, IndexRebuildError)
    assert error.recovery_ddl == {"t.UX_T": _ORA_DDL}
    assert _ORA_DDL in str(error)


def test_rebuilt_unique_failure_has_no_recovery_ddl() -> None:
    """Un índice desactivado (no borrado) sigue existiendo: no hay DDL que recuperar."""
    conn = MagicMock()
    conn.execute.side_effect = [SQLAlchemyError("dup"), SQLAlchemyError("sin diagnóstico")]
    step = IndexStep("t", "t", "uq", "ALTER INDEX uq DISABLE", "REBUILD", "rebuilt", unique_columns=("c",), unique=True)
    runner = IndexDdlRunner("mssql", _LOG, commit=True, savepoint=False)
    runner.restore(conn, [step])
    assert runner.recovery_ddl == {}


def _oracle_conn(
    constraints: list[tuple[str, str, str]], index_rows: list[tuple[str, str, str | None]], ddl: dict[str, object]
) -> MagicMock:
    def execute(statement: object, params: dict[str, object]) -> MagicMock:
        sql = str(statement)
        result = MagicMock()
        if "DBMS_METADATA" in sql:
            value = ddl[str(params["name"])]
            if isinstance(value, Exception):
                raise value
            result.scalar.return_value = value
        elif "all_ind_columns" in sql:
            result.__iter__.return_value = iter(index_rows)
        else:
            result.__iter__.return_value = iter(constraints)
        return result

    conn = MagicMock()
    conn.execute.side_effect = execute
    return conn


def test_facts_oracle_unique_indexes_include_indexes_without_constraint() -> None:
    error = SQLAlchemyError("x")
    error.orig = Exception('ORA-31603: object "UX_B" of type INDEX not found in schema "HR"\nmás detalle')  # type: ignore[attr-defined]
    conn = _oracle_conn(
        [("PK_T", "P", "ID")],
        [
            ("UX_A", "C", None),
            ("UX_A", "SYS_NC00005$", 'CASE  WHEN "D"=\'S\' THEN "C" END '),
            ("UX_B", "E", None),
            ("UX_C", "F", None),
        ],
        {"UX_A": '\n  CREATE UNIQUE INDEX "HR"."UX_A" ON "HR"."T" ("C") ', "UX_B": error, "UX_C": "ALTER SESSION …"},
    )
    out = {f.name: f for f in facts.unique_indexes(conn, "HR", "T", "oracle")}
    assert out["PK_T"].kind == "pk"
    assert out["UX_A"] == _UNIQUE(
        "UX_A",
        "unique_index",
        ("C", "SYS_NC00005$"),
        'CREATE UNIQUE INDEX "HR"."UX_A" ON "HR"."T" ("C")',
        key_sql=('"C"', 'CASE  WHEN "D"=\'S\' THEN "C" END'),
    )
    assert out["UX_B"].ddl is None
    assert (
        out["UX_B"].ddl_error
        == 'DBMS_METADATA.GET_DDL falló: ORA-31603: object "UX_B" of type INDEX not found in schema "HR"'
    )
    assert out["UX_C"].ddl is None
    assert "no devolvió un CREATE UNIQUE INDEX" in str(out["UX_C"].ddl_error)


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
        IndexStep("t", "t", "uq", "…", "REBUILD uq", "rebuilt", priority=0, unique_columns=("code",), unique=True),
        IndexStep("t", "t", "ix", "…", "REBUILD ix", "rebuilt"),
    ]
    runner = IndexDdlRunner("postgresql", _LOG, commit=False, savepoint=False)
    results = runner.restore(conn, steps)
    assert [(r.index_name, r.action) for r in results] == [("uq", "failed"), ("ix", "rebuilt")]
    assert "A1 → 2" in results[0].error_msg
    assert str(conn.execute.call_args_list[1].args[0]) == (
        "SELECT code, COUNT(*) FROM t WHERE code IS NOT NULL GROUP BY code HAVING COUNT(*) > 1 LIMIT 5"
    )
    error = rebuild_error(runner, results, "carga")
    assert isinstance(error, IndexRebuildError)
    assert error.duplicates == {"t.uq": ["A1 → 2", "B7 → 3"]}
    assert error.results == results


def test_restore_skips_constraints_that_already_exist() -> None:
    """Un rollback de la sesión devolvió la PK/UNIQUE o FK borrada: no se recrea (no habría fallo, sino «ya existe»)."""
    conn = MagicMock()
    conn.execute.return_value.first.side_effect = [MagicMock(name="ya existe"), None]
    check = ("pk", "t")
    steps = [
        IndexStep("t", "t", "pk", "DROP pk", "ADD pk", "recreated", priority=2, exists_check=check),
        IndexStep("c", "c", "fk", "DROP fk", "ADD fk", "recreated", priority=3, exists_check=check),
    ]
    results = IndexDdlRunner("postgresql", _LOG, commit=False, savepoint=False).restore(conn, steps)
    assert [(r.index_name, r.action) for r in results] == [("pk", "recreated"), ("fk", "recreated")]
    executed = [str(c.args[0]) for c in conn.execute.call_args_list]
    assert "ADD pk" not in executed
    assert "ADD fk" in executed


def test_postgresql_constraint_steps_carry_an_existence_check() -> None:
    steps = _plan_all(
        "postgresql",
        [_UNIQUE("t_pkey", "pk", ("id",), "PRIMARY KEY (id)", "t_pkey")],
        [_INBOUND("", "public", "child", "fk_c", True, True, "FOREIGN KEY (pid) REFERENCES t(id)")],
        [],
    )
    checks = {s.index_name: s.exists_check for s in steps if s.exists_check is not None}
    assert checks == {"t_pkey": ("t_pkey", "`t`"), "fk_c": ("fk_c", "`public`.`child`")}


def test_rebuild_error_is_none_without_unique_failures() -> None:
    assert rebuild_error(IndexDdlRunner("mssql", _LOG, commit=False, savepoint=False), [], "carga") is None


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [
        ("mssql", "SELECT TOP 5 a, b, COUNT(*) FROM t GROUP BY a, b HAVING COUNT(*) > 1"),
        (
            "oracle",
            "SELECT * FROM (SELECT a, b, COUNT(*) FROM t WHERE NOT (a IS NULL AND b IS NULL) GROUP BY a, b "
            "HAVING COUNT(*) > 1) WHERE ROWNUM <= 5",
        ),
        (
            "mysql",
            "SELECT a, b, COUNT(*) FROM t WHERE a IS NOT NULL AND b IS NOT NULL GROUP BY a, b HAVING COUNT(*) > 1 "
            "LIMIT 5",
        ),
        (
            "postgresql",
            "SELECT a, b, COUNT(*) FROM t WHERE a IS NOT NULL AND b IS NOT NULL GROUP BY a, b HAVING COUNT(*) > 1 "
            "LIMIT 5",
        ),
    ],
)
def test_duplicates_sql_per_dialect(dialect: str, expected: str) -> None:
    assert duplicates_sql(dialect, "t", ["a", "b"]) == expected


@pytest.mark.parametrize(
    ("dialect", "prefix", "suffix"),
    [
        ("mssql", "SELECT TOP 1 1 ", ""),
        ("oracle", "SELECT 1 ", " AND ROWNUM = 1"),
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
# Auditoría v3.0.3..HEAD (2026-10-19): H1, H2 y H3
# ---------------------------------------------------------------------------


class _FailingConn:
    """Conexión falsa: falla la sentencia que contiene ``fail_on`` y apunta lo que se ejecuta (con sus parámetros)."""

    def __init__(self, fail_on: str) -> None:
        self.fail_on = fail_on
        self.executed: list[str] = []
        self.binds: list[list[str]] = []

    def execute(self, statement: object, *args: object, **kwargs: object) -> MagicMock:
        sql = str(statement)
        self.executed.append(sql)
        self.binds.append(list(getattr(statement, "_bindparams", {})))
        if self.fail_on in sql:
            raise SQLAlchemyError("duplicate key")
        return MagicMock()

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def test_postgresql_expression_unique_index_that_fails_raises_index_rebuild_error() -> None:
    """H1: un único de expresión no tiene columnas (``attnum`` 0); su fallo tiene que dar ``IndexRebuildError``."""
    ddl = "CREATE UNIQUE INDEX ux_email ON public.t USING btree (lower((email)::text))"
    steps = _plan_all(
        "postgresql", [_UNIQUE("ux_email", "unique_index", (), ddl, key_sql=("lower((email)::text)",))], [], []
    )
    assert steps[0].unique
    assert steps[0].unique_columns == ("lower((email)::text)",)
    conn = _FailingConn("CREATE UNIQUE INDEX")
    runner = IndexDdlRunner("postgresql", _LOG, commit=True, savepoint=False)
    results = runner.restore(conn, runner.disable(conn, steps))
    assert [(r.index_name, r.action) for r in results] == [("ux_email", "failed")]
    error = rebuild_error(runner, results, "carga")
    assert isinstance(error, IndexRebuildError)
    assert error.recovery_ddl == {"t.ux_email": ddl}
    assert "GROUP BY lower((email)::text)" in conn.executed[-1]  # diagnóstico de duplicados sobre la expresión


def test_unique_step_without_known_key_still_counts_as_failed_unique() -> None:
    """H1: sin ``unique_columns`` no hay diagnóstico de duplicados, pero el fallo sigue contando."""
    step = IndexStep("t", "t", "ux", "DROP INDEX ux", "CREATE UNIQUE INDEX ux …", "recreated", "CREATE …", unique=True)
    conn = _FailingConn("CREATE UNIQUE INDEX")
    runner = IndexDdlRunner("postgresql", _LOG, commit=True, savepoint=False)
    results = runner.restore(conn, [step])
    assert runner.failed_unique == ["t.ux"]
    assert conn.executed == ["CREATE UNIQUE INDEX ux …"]  # sin SELECT de duplicados
    assert isinstance(rebuild_error(runner, results, "carga"), IndexRebuildError)


def test_facts_postgresql_unique_indexes_carry_key_sql() -> None:
    row = ("ux_email", None, None, "CREATE UNIQUE INDEX ux_email …", None, [], ["lower((email)::text)"])
    pk = ("t_pkey", "t_pkey", "p", "CREATE UNIQUE INDEX t_pkey …", "PRIMARY KEY (id)", ["id"], ["id"])
    conn = MagicMock()
    conn.execute.return_value = iter([row, pk])
    out = {f.name: f for f in facts.unique_indexes(conn, "public", "t", "postgresql")}
    assert out["ux_email"].key_sql == ("lower((email)::text)",)
    assert out["ux_email"].columns == ()
    assert (out["t_pkey"].kind, out["t_pkey"].constraint, out["t_pkey"].key_sql) == ("pk", "t_pkey", ("id",))


def test_failed_grouped_innodb_restore_retries_each_index_on_its_own() -> None:
    """H2: el único con duplicados no deja sin recrear al secundario del mismo ``ALTER TABLE``."""
    steps = _plan_all(
        "mysql",
        [_UNIQUE("ux_a", "unique_index", ("a",), "UNIQUE INDEX `ux_a` (`a`)")],
        [],
        [("ix_b", "INDEX `ix_b` (`b`)")],
    )
    conn = _FailingConn("ADD UNIQUE INDEX")
    runner = IndexDdlRunner("mysql", _LOG, commit=True, savepoint=False)
    results = runner.restore(conn, runner.disable(conn, steps))
    assert [(r.index_name, r.action) for r in results] == [("ux_a", "failed"), ("ix_b", "recreated")]
    assert "ALTER TABLE `t` ADD INDEX `ix_b` (`b`)" in conn.executed
    error = rebuild_error(runner, results, "carga")
    assert isinstance(error, IndexRebuildError)
    assert error.recovery_ddl == {"t.ux_a": "ALTER TABLE `t` ADD UNIQUE INDEX `ux_a` (`a`)"}


def test_dropped_secondary_index_that_fails_carries_its_ddl() -> None:
    """H2: un secundario borrado que no se recrea también deja su DDL en el resultado y en ``recovery_ddl``."""
    step = IndexStep("t", "t", "ix", "DROP INDEX ix", "CREATE INDEX ix …", "recreated", "CREATE INDEX ix …")
    runner = IndexDdlRunner("postgresql", _LOG, commit=True, savepoint=False)
    results = runner.restore(_FailingConn("CREATE INDEX"), [step])
    assert "DDL para recrearlo: CREATE INDEX ix …" in results[0].error_msg
    assert runner.recovery_ddl == {"t.ix": "CREATE INDEX ix …"}
    assert rebuild_error(runner, results, "carga") is None  # no es único: no hay IndexRebuildError


def test_colons_in_postgresql_ddl_are_not_bind_parameters() -> None:
    """H3: ``' :x'`` en el predicado de un índice parcial no es un parámetro de ``text()``."""
    ddl = "CREATE INDEX ix_p ON public.t USING btree (a) WHERE (code <> ' :x'::text)"
    steps = _plan_all("postgresql", [], [], [("ix_p", ddl)])
    conn = _FailingConn("never")
    runner = IndexDdlRunner("postgresql", _LOG, commit=True, savepoint=False)
    results = runner.restore(conn, runner.disable(conn, steps))
    assert [r.action for r in results] == ["recreated"]
    assert conn.binds == [[], []]
    assert "' :x'::text" in conn.executed[-1]


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
