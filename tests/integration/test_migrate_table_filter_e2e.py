"""``MigrationPlanner.plan(table_filter=...)`` aplicado en motores reales (5.9.0, G56 de util_bbdd_web).

Origen PostgreSQL hacia los otros cuatro motores y MariaDB hacia PostgreSQL. En el origen: ``zzvw_ft_padre``,
``zzvw_ft_hijo`` (FK a la padre), ``zzvw_ft_otra`` y la vista ``zzvw_ft_v_hijo``. Primero se migra solo la padre;
después, con el filtro ``zzvw_ft_hijo, zzvw_ft_v_*``, la hija y la vista: la FK hacia la padre (fuera del filtro) se
emite con ``ALTER TABLE`` al final y se crea en el destino porque la padre ya existe. ``zzvw_ft_otra`` no se migra.

Usa las conexiones y los espacios de nombres de ``test_migrate_views_e2e`` (y su limpieza de ``ZZVW*`` en Oracle).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from sqlalchemy import inspect

from util_bbdd.metadata import TableFilter

from .test_migrate_views_e2e import (
    DST,
    SRC,
    MigrationPlanner,
    _create_namespace,
    _drop_namespace,
    _engine,
    _manager,
    _run,
    _source_schema,
    pytestmark,  # noqa: F401  (integration + skip sin URLs)
)

PAIRS = [("postgresql", t) for t in ("mysql", "mariadb", "sqlserver", "oracle")] + [("mariadb", "postgresql")]

SOURCE = [
    "CREATE TABLE zzvw_ft_padre (id INT PRIMARY KEY)",
    "CREATE TABLE zzvw_ft_hijo (id INT PRIMARY KEY, padre_id INT, "
    "CONSTRAINT fk_zzvw_ft_hijo FOREIGN KEY (padre_id) REFERENCES zzvw_ft_padre (id))",
    "CREATE TABLE zzvw_ft_otra (id INT PRIMARY KEY)",
    "CREATE VIEW zzvw_ft_v_hijo AS SELECT id FROM zzvw_ft_hijo",
]


@pytest.fixture
def pair(request: pytest.FixtureRequest) -> Iterator[tuple[str, str]]:
    source, target = request.param
    _create_namespace(source, SRC)
    _create_namespace(target, DST)
    try:
        _run(source, SRC, SOURCE)
        yield source, target
    finally:
        _drop_namespace(source, SRC)
        _drop_namespace(target, DST)


def _plan(source: str, target: str, include: str) -> object:
    manager = _manager(source)
    try:
        return MigrationPlanner(
            source_engine=source, target_engine=target, pg_schema=DST if target == "postgresql" else None
        ).plan(manager, _source_schema(source), table_filter=TableFilter.from_patterns(include=include.split(",")))
    finally:
        manager.close()


def _execute(plan: object, target: str) -> None:
    manager = _manager(target, DST)
    try:
        plan.execute(manager)  # type: ignore[attr-defined]
    finally:
        manager.close()


@pytest.mark.parametrize("pair", PAIRS, indirect=True, ids=[f"{s}-{t}" for s, t in PAIRS])
def test_filtered_plan_defers_the_fk_to_a_table_already_in_the_target(pair: tuple[str, str]) -> None:
    source, target = pair

    _execute(_plan(source, target, "zzvw_ft_padre"), target)

    plan = _plan(source, target, "zzvw_ft_hijo, zzvw_ft_v_*")
    assert [t.original_name.lower() for t in plan.tables] == ["zzvw_ft_hijo"]  # type: ignore[attr-defined]
    assert [v.original_name.lower() for v in plan.views] == ["zzvw_ft_v_hijo"]  # type: ignore[attr-defined]
    assert [name.lower() for name in plan.frontier] == ["zzvw_ft_padre"]  # type: ignore[attr-defined]
    outside = [w for w in plan.warnings if w.code == "FK_OUTSIDE_FILTER"]  # type: ignore[attr-defined]
    assert [w.target_type.lower() for w in outside] == ["zzvw_ft_padre"]
    assert plan.error_count == 0  # type: ignore[attr-defined]
    _execute(plan, target)

    engine = _engine(target, DST)
    try:
        inspector = inspect(engine)
        schema = DST if target == "postgresql" else None
        tables = sorted(n.lower() for n in inspector.get_table_names(schema=schema) if n.lower().startswith("zzvw_ft"))
        assert tables == ["zzvw_ft_hijo", "zzvw_ft_padre"]
        views = [n.lower() for n in inspector.get_view_names(schema=schema) if n.lower().startswith("zzvw_ft")]
        assert views == ["zzvw_ft_v_hijo"]
        fks = inspector.get_foreign_keys("zzvw_ft_hijo" if target != "oracle" else "ZZVW_FT_HIJO", schema=schema)
        assert [fk["referred_table"].lower() for fk in fks] == ["zzvw_ft_padre"]
    finally:
        engine.dispose()
