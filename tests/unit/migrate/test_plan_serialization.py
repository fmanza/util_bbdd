"""U-M3 (G26 de util_bbdd_web): ``MigrationPlan.to_dict``/``from_dict`` y ejecución de un plan reconstruido."""

from __future__ import annotations

import copy
import hashlib
import json

from dataclasses import fields
from typing import Any

import pytest

from util_bbdd.exceptions import MigrationPlanValidationError, ValidationError
from util_bbdd.migrate import MigrationPlan, MigrationPlanner
from util_bbdd.migrate.ir.models import _has_sql

from ._snapshot_source import col, fake_manager, fk, index, pk, routine, table, view

ENGINES = ["oracle", "mariadb", "mysql", "sqlserver", "postgresql"]


def _source(engine: str) -> Any:
    """Esquema con PK, FK, índice, comentario largo, vista y rutina, con tipos comunes a los cinco motores."""
    if engine == "oracle":
        number, text = ("NUMBER(10)", "NUMBER"), ("VARCHAR2(50)", "VARCHAR2")
    elif engine in {"mariadb", "mysql"}:
        number, text = ("int(11)", "int"), ("varchar(50)", "varchar")
    elif engine == "sqlserver":
        number, text = ("int", "int"), ("varchar", "varchar")
    else:
        number, text = ("integer", "integer"), ("character varying", "character varying")
    num = {"precision": 10, "scale": 0} if engine == "oracle" else {}
    return fake_manager(
        engine,
        table("PADRE", "Tabla padre " + "x" * 3000),
        col("PADRE", "ID", 1, number[0], number[1], nullable=False, **num),
        col("PADRE", "NOMBRE", 2, text[0], text[1], length=50, comment="Nombre"),
        pk("PADRE", "ID"),
        index("PADRE", "IX_PADRE_NOMBRE", "NOMBRE"),
        table("HIJO"),
        col("HIJO", "ID", 1, number[0], number[1], nullable=False, **num),
        col("HIJO", "PADRE_ID", 2, number[0], number[1], **num),
        pk("HIJO", "ID"),
        fk("HIJO", "FK_HIJO_PADRE", ("PADRE_ID",), "PADRE", ("ID",), ref_schema="S"),
        view("V_PADRE", "SELECT ID, NOMBRE FROM PADRE"),
        routine("P_NADA", "PROCEDURE", "BEGIN NULL; END;"),
    )


def _plans() -> list[tuple[str, str, MigrationPlan]]:
    plans = []
    for source in ENGINES:
        for target in ENGINES:
            if source != target:
                planner = MigrationPlanner(source_engine=source, target_engine=target, view_strategy="passthrough")
                plans.append((source, target, planner.plan(_source(source), "S")))
    return plans


@pytest.mark.parametrize(("source", "target", "plan"), _plans(), ids=lambda v: v if isinstance(v, str) else "")
def test_round_trip_through_json(source: str, target: str, plan: MigrationPlan) -> None:
    data = plan.to_dict()
    restored = MigrationPlan.from_dict(json.loads(json.dumps(data)))

    assert restored.emit_statements() == plan.emit_statements()
    assert restored.emit_ddl() == plan.emit_ddl()
    assert restored.to_dict() == data
    for f in fields(MigrationPlan):
        if f.name != "emitter":
            assert getattr(restored, f.name) == getattr(plan, f.name), f.name
    assert type(restored.emitter) is type(plan.emitter)
    assert data["format"] == "util_bbdd.migration_plan" and data["format_version"] == 1
    assert data["statements_sha256"] == plan.statements_sha256()


def test_statements_sha256_is_nul_separated_sha256() -> None:
    plan = MigrationPlanner().plan(_source("oracle"), "S")
    expected = hashlib.sha256("\x00".join(plan.emit_statements()).encode("utf-8")).hexdigest()
    assert plan.statements_sha256() == expected


def test_emitter_options_survive() -> None:
    planners = {
        "mariadb": MigrationPlanner(target_engine="mariadb", charset="latin1", collation="latin1_swedish_ci"),
        "sqlserver": MigrationPlanner(target_engine="sqlserver", sql_server_collation="Latin1_General_CI_AS"),
        "postgresql": MigrationPlanner(target_engine="postgresql", pg_schema="destino"),
    }
    for target, planner in planners.items():
        plan = planner.plan(_source("oracle"), "S")
        restored = MigrationPlan.from_dict(plan.to_dict())
        assert restored.emit_ddl() == plan.emit_ddl(), target
    oracle = MigrationPlanner(
        source_engine="mariadb", target_engine="oracle", oracle_identity_mode="identity_by_default_on_null"
    ).plan(_source("mariadb"), "S")
    assert MigrationPlan.from_dict(oracle.to_dict()).to_dict()["emitter"] == {
        "oracle_identity_mode": "identity_by_default_on_null"
    }


def test_restored_plan_executes() -> None:
    plan = MigrationPlanner(target_engine="postgresql").plan(_source("oracle"), "S")
    restored = MigrationPlan.from_dict(json.loads(json.dumps(plan.to_dict())))
    sent: list[str] = []

    class Target:
        def execute_custom_one(self, sql: str, params: dict[str, Any]) -> None:
            sent.append(sql)

    restored.execute(Target())
    assert sent == [s.strip() for s in plan.emit_statements() if _has_sql(s)]


@pytest.fixture
def data() -> dict[str, Any]:
    return MigrationPlanner().plan(_source("oracle"), "S").to_dict()


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (lambda d: d.update(format="otro"), "No es un MigrationPlan"),
        (lambda d: d.update(format_version=2), "format_version 2"),
        (lambda d: d.pop("statements_sha256"), "statements_sha256"),
        (lambda d: d.update(target_engine="db2"), "target_engine"),
        (lambda d: d.update(emitter={"charset": "utf8mb4"}), "emitter"),
        (lambda d: d["emitter"].update(engine="no valido;"), "emitter"),
        (lambda d: d.pop("tables"), "tables"),
        (lambda d: d["tables"][1]["columns"][0].update(nullable="no"), r"tables\[1\]\.columns\[0\]\.nullable"),
        (lambda d: d["tables"][0]["columns"][0].pop("name"), "campo obligatorio ausente"),
        (lambda d: d["warnings"][0].update(severity="FATAL"), r"warnings\[0\]\.severity"),
        (lambda d: d["tables"][0]["columns"][0].update(target_type="SMALLINT"), "no emite las mismas sentencias"),
    ],
)
def test_invalid_data_is_rejected(data: dict[str, Any], change: Any, match: str) -> None:
    bad = copy.deepcopy(data)
    change(bad)
    with pytest.raises(MigrationPlanValidationError, match=match):
        MigrationPlan.from_dict(bad)


def test_not_a_dict_and_error_hierarchy() -> None:
    with pytest.raises(MigrationPlanValidationError, match="espera un dict"):
        MigrationPlan.from_dict([])  # type: ignore[arg-type]
    assert issubclass(MigrationPlanValidationError, ValidationError)
    assert issubclass(MigrationPlanValidationError, ValueError)


def test_unknown_keys_are_ignored(data: dict[str, Any]) -> None:
    data["campo_futuro"] = 1
    data["tables"][0]["campo_futuro"] = 1
    MigrationPlan.from_dict(data)


def test_foreign_emitter_is_not_serializable() -> None:
    plan = MigrationPlanner().plan(_source("oracle"), "S")
    plan.emitter = object()  # type: ignore[assignment]
    with pytest.raises(TypeError, match="emitter"):
        plan.to_dict()


def test_format_is_a_class_constant_not_a_field() -> None:
    assert "FORMAT" not in {f.name for f in fields(MigrationPlan)}
