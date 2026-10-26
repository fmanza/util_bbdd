"""Integración de ``DumpOrchestrator`` contra motores reales: regresiones de los fallos corregidos en v0.16.0.

Origen: un esquema temporal de **PostgreSQL** (``UTIL_BBDD_TEST_POSTGRESQL_URL``), con valores que otros tipos no
representan (BIGINT de 64 bits, DECIMAL(38,10)). Destino: cada servidor con URL de pruebas
(``UTIL_BBDD_TEST_<MOTOR>_URL``) y MariaDB también con MariaDB Connector/Python si está instalado. Las tablas destino se
crean en el esquema por defecto del usuario de pruebas con nombres únicos y se eliminan al terminar; en MySQL, MariaDB y
Oracle ese usuario no puede crear otros esquemas, por eso el origen es siempre PostgreSQL (volcado entre motores).
``target_schema`` se pasa explícito (el esquema por defecto) para recorrer la ruta de nombre lógico ``esquema.tabla``.

Sin URL de PostgreSQL se saltan todos; sin la del destino, el suyo. Hallazgos cubiertos
(``.ai/sessions/2026-09-25b-performance-audit-dump-delta/improvement_roadmap_dump.md``):

- ``test_dump_copies_values_exactly``: PD-05 (datos alterados), PD-10 (DECIMAL de 38 dígitos en SQL Server), PD-01
  (columnas en minúsculas en SQL Server), PF-09 (MariaDB Connector/Python) y PD-13 (DECIMAL con pymssql: la URL de
  pruebas de SQL Server usa pymssql).
- ``test_identity_is_resynced_after_dump``: PD-02 (PK sync con ``target_schema``) y PD-11 (con rangos de PK).
- ``test_redump_with_foreign_keys``: PD-03 (volcado repetido con FK en PostgreSQL).
- ``test_orphan_rows_mark_the_foreign_key_as_failed``: PD-04 (validación real de FK en PostgreSQL).
- ``test_staging_update_with_schema_and_no_default_database``: PD-12 (UPDATE por staging sin BD por defecto).
- ``test_mssql_fk_references_by_schema_match_the_inspector``: Q9 (FK de todo el esquema en una consulta, SQL Server).
"""

from __future__ import annotations

import importlib.util
import os
import uuid

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from sqlalchemy import (
    URL,
    BigInteger,
    Column,
    Engine,
    ForeignKey,
    Identity,
    Inspector,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.schema import CreateSchema, DropSchema

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk.options import AuditOptions
from util_bbdd.dump import DumpConfig, DumpOrchestrator

pytestmark = [pytest.mark.integration, pytest.mark.cross_db]

PG_URL_ENV = "UTIL_BBDD_TEST_POSTGRESQL_URL"
SERVER_TARGETS: tuple[str, ...] = ("postgresql", "mysql", "mariadb", "mssql", "oracle")
MYSQL_FAMILY = frozenset({"mysql", "mariadb", "mariadb_connector"})
HAS_MARIADB_CONNECTOR = importlib.util.find_spec("mariadb") is not None

VALUES: list[tuple[Any, ...]] = [
    (1, 9_007_199_254_740_993, Decimal("1234567890123456789012345678.9012345678"), "  padded  "),
    (2, None, None, None),
    (3, 9_223_372_036_854_775_807, Decimal("-0.0000000001"), " x"),
    (4, -9_223_372_036_854_775_807, Decimal("12345678901234567.8900000000"), "y "),
]


def _url_env(key: str) -> str:
    return f"UTIL_BBDD_TEST_{('mariadb' if key == 'mariadb_connector' else key).upper()}_URL"


def _target_params(*, only: frozenset[str] | None = None) -> list[Any]:
    keys = [*SERVER_TARGETS, *(["mariadb_connector"] if HAS_MARIADB_CONNECTOR else [])]
    params = []
    for key in keys:
        if only is not None and key not in only:
            continue
        missing = [env for env in (PG_URL_ENV, _url_env(key)) if not os.environ.get(env)]
        params.append(
            pytest.param(
                key, id=key, marks=pytest.mark.skipif(bool(missing), reason=f"{', '.join(missing)} no definida")
            )
        )
    return params


def _make_target_engine(key: str) -> Engine:
    url = os.environ[_url_env(key)]
    if key == "mariadb_connector":
        url = url.replace("mariadb+pymysql://", "mariadb+mariadbconnector://", 1)
    return create_engine(url)


@dataclass
class Setup:
    source: Engine
    target: Engine
    source_schema: str
    target_schema: str
    prefix: str
    tmp: Path

    def name(self, suffix: str) -> str:
        return f"{self.prefix}_{suffix}"

    def run(self, tables: list[str], **cfg: Any) -> Any:
        return DumpOrchestrator(
            DumpConfig(
                source_engine=self.source,
                target_engine=self.target,
                source_schema=self.source_schema,
                target_schema=self.target_schema,
                tables=[self.name(t) for t in tables],
                output_dir=self.tmp,
                **cfg,
            )
        ).run()


@pytest.fixture
def setup(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Setup]:
    """Esquema origen temporal en PostgreSQL + engine destino; borra el esquema y las tablas destino al terminar."""
    key: str = request.param
    source = create_engine(os.environ[PG_URL_ENV])
    target = _make_target_engine(key)
    source_schema = f"zz_it_dump_{uuid.uuid4().hex[:8]}"
    with source.begin() as conn:
        conn.execute(CreateSchema(source_schema))
    target_schema = inspect(target).default_schema_name
    assert target_schema, "el engine destino no tiene esquema por defecto"
    data = Setup(source, target, source_schema, target_schema, f"zzd{uuid.uuid4().hex[:6]}", tmp_path)
    created: list[Table] = []
    request.node.created_tables = created
    try:
        yield data
    finally:
        for table in reversed(created):
            table.drop(target, checkfirst=True)
        with source.begin() as conn:
            conn.execute(DropSchema(source_schema, cascade=True))
        source.dispose()
        target.dispose()


def _create(request: pytest.FixtureRequest, engine: Engine, table: Table) -> Table:
    """Crea ``table`` en el destino y la registra para borrarla al terminar (en orden inverso)."""
    table.create(engine)
    request.node.created_tables.append(table)
    return table


def _pk(engine: Engine) -> Column[Any]:
    """PK entera con identidad en el destino (AUTO_INCREMENT en MySQL/MariaDB)."""
    if engine.dialect.name in ("mysql", "mariadb"):
        return Column("id", Integer, primary_key=True, autoincrement=True)
    return Column("id", Integer, Identity(), primary_key=True)


def _values_table(name: str, *, schema: str | None = None) -> Table:
    return Table(
        name,
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("big", BigInteger),
        Column("amount", Numeric(38, 10)),
        Column("s", String(30)),
        schema=schema,
    )


@pytest.mark.parametrize("setup", _target_params(), indirect=True)
def test_dump_copies_values_exactly(setup: Setup, request: pytest.FixtureRequest) -> None:
    source_table = _values_table(setup.name("vals"), schema=setup.source_schema)
    source_table.create(setup.source)
    with setup.source.begin() as conn:
        conn.execute(
            source_table.insert(), [dict(zip(("id", "big", "amount", "s"), row, strict=True)) for row in VALUES]
        )
    target_table = _create(request, setup.target, _values_table(setup.name("vals")))

    result = setup.run(["vals"])

    assert [r.status for r in result.table_results] == ["success"], [r.error_msg for r in result.table_results]
    with setup.target.connect() as conn:
        got = [tuple(r) for r in conn.execute(select(target_table).order_by(target_table.c.id))]
    assert got == VALUES


@pytest.mark.parametrize("mode", [True, "all"])
@pytest.mark.parametrize("setup", _target_params(), indirect=True)
def test_manage_indexes_restores_indexes(setup: Setup, request: pytest.FixtureRequest, mode: bool | str) -> None:
    """3.2.0: estrategia común con ``BulkCrud``; MariaDB/MySQL (InnoDB) pasa de «unsupported» a recrear sus índices.

    3.3.0, ``"all"``: también el índice único ``big`` y la PK (salvo clustered de SQL Server y PK de InnoDB)."""
    from sqlalchemy import Index

    source_table = _values_table(setup.name("ix"), schema=setup.source_schema)
    source_table.create(setup.source)
    with setup.source.begin() as conn:
        conn.execute(
            source_table.insert(), [dict(zip(("id", "big", "amount", "s"), row, strict=True)) for row in VALUES]
        )
    target_table = _values_table(setup.name("ix"))
    Index(f"{setup.prefix}_ix_s", target_table.c.s)
    Index(f"{setup.prefix}_ux_big", target_table.c.big, unique=True)
    _create(request, setup.target, target_table)

    def state() -> tuple[Any, ...]:
        insp = inspect(setup.target)
        pk = insp.get_pk_constraint(target_table.name).get("constrained_columns")
        names = sorted((str(i["name"]).lower(), bool(i["unique"])) for i in insp.get_indexes(target_table.name))
        return tuple(pk or ()), tuple(names)

    before = state()
    result = setup.run(["ix"], manage_indexes=mode)

    assert [r.status for r in result.table_results] == ["success"], [r.error_msg for r in result.table_results]
    assert state() == before
    assert result.index_results is not None
    touched = {r.index_name.lower() for r in result.index_results}
    assert f"{setup.prefix}_ix_s" in touched
    # "all" también toca los índices únicos sin constraint (ux_big); en Oracle, desde 4.0.0 (DROP + GET_DDL).
    assert (f"{setup.prefix}_ux_big" in touched) is (mode == "all")
    assert {r.action for r in result.index_results} <= {"rebuilt", "recreated"}, result.index_results


def _parent_child(
    engine: Engine, prefix: str, *, schema: str | None = None, identity: bool = True
) -> tuple[Table, Table]:
    md = MetaData(schema=schema)

    def pk() -> Column[Any]:
        return _pk(engine) if identity else Column("id", Integer, primary_key=True, autoincrement=False)

    parent = Table(f"{prefix}_parent", md, pk(), Column("v", String(10)))
    child_pk = pk()
    fk_target = f"{schema}.{prefix}_parent.id" if schema else f"{prefix}_parent.id"
    child = Table(
        f"{prefix}_child", md, child_pk, Column("parent_id", Integer, ForeignKey(fk_target)), Column("v", String(10))
    )
    return parent, child


def _load_source(setup: Setup, *, orphan: bool = False, with_fk: bool = True) -> None:
    parent, child = _parent_child(setup.source, setup.prefix, schema=setup.source_schema, identity=False)
    if not with_fk:
        child = Table(
            child.name,
            MetaData(schema=setup.source_schema),
            Column("id", Integer, primary_key=True, autoincrement=False),
            Column("parent_id", Integer),
            Column("v", String(10)),
        )
    parent.create(setup.source)
    child.create(setup.source)
    with setup.source.begin() as conn:
        conn.execute(parent.insert(), [{"id": i, "v": "p"} for i in (1, 2, 3)])
        conn.execute(
            child.insert(), [{"id": i, "parent_id": 99 if orphan and i == 3 else i, "v": "c"} for i in (1, 2, 3)]
        )


@pytest.mark.parametrize("ranges", [1, 2], ids=["tabla_entera", "rangos"])
@pytest.mark.parametrize("setup", _target_params(), indirect=True)
def test_identity_is_resynced_after_dump(setup: Setup, request: pytest.FixtureRequest, ranges: int) -> None:
    _load_source(setup)
    parent, child = _parent_child(setup.target, setup.prefix)
    _create(request, setup.target, parent)
    _create(request, setup.target, child)

    result = setup.run(["parent", "child"], parallel_pk_ranges=ranges)

    assert {r.status for r in result.table_results} == {"success"}, [r.error_msg for r in result.table_results]
    assert result.pk_sync_results, "la resincronización de PK no se ejecutó"
    with setup.target.begin() as conn:  # INSERT sin PK: no debe chocar con las filas volcadas (1..3)
        conn.execute(parent.insert(), [{"v": "nuevo"}])
        new_id = conn.execute(select(parent.c.id).where(parent.c.v == "nuevo")).scalar_one()
    assert new_id > 3


@pytest.mark.parametrize("setup", _target_params(), indirect=True)
def test_redump_with_foreign_keys(setup: Setup, request: pytest.FixtureRequest) -> None:
    _load_source(setup)
    parent, child = _parent_child(setup.target, setup.prefix, identity=False)
    _create(request, setup.target, parent)
    _create(request, setup.target, child)

    first = setup.run(["parent", "child"])
    second = setup.run(["parent", "child"])

    for result in (first, second):
        assert {r.status for r in result.table_results} == {"success"}, [r.error_msg for r in result.table_results]
    with setup.target.connect() as conn:
        assert conn.execute(select(child.c.id).order_by(child.c.id)).scalars().all() == [1, 2, 3]


@pytest.mark.parametrize("setup", _target_params(only=frozenset({"postgresql"})), indirect=True)
def test_orphan_rows_mark_the_foreign_key_as_failed(setup: Setup, request: pytest.FixtureRequest) -> None:
    _load_source(setup, orphan=True, with_fk=False)  # el origen no tiene FK y trae una fila huérfana
    parent, child = _parent_child(setup.target, setup.prefix, identity=False)
    _create(request, setup.target, parent)
    _create(request, setup.target, child)

    result = setup.run(["parent", "child"])

    fk_results = [c for c in result.constraint_results if c.table_name == child.name]
    assert fk_results and all(c.status == "failed" for c in fk_results), result.constraint_results


@pytest.mark.parametrize("key", [p.values[0] for p in _target_params(only=MYSQL_FAMILY)])
def test_staging_update_with_schema_and_no_default_database(key: str) -> None:
    env = _url_env(key)
    if not os.environ.get(env):
        pytest.skip(f"{env} no definida")
    engine = _make_target_engine(key)
    schema = engine.url.database
    url = engine.url  # URL.set(database=None) no cambia nada: set() ignora los None
    no_default_db = create_engine(
        URL.create(url.drivername, url.username, url.password, url.host, url.port, database=None, query=url.query)
    )
    assert no_default_db.url.database is None
    table = Table(
        f"zzd{uuid.uuid4().hex[:6]}_upd",
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("v", String(10)),
        schema=schema,
    )
    table.create(engine)
    try:
        with engine.begin() as conn:
            conn.execute(table.insert(), [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}])

        BulkCrud(no_default_db, audit=AuditOptions(warn_if_disabled=False)).bulk_update_from_df(
            pd.DataFrame({"id": [1, 2], "v": ["A", "B"]}), f"{schema}.{table.name}", generar_sql=False
        )

        with engine.connect() as conn:
            assert conn.execute(select(table.c.v).order_by(table.c.id)).scalars().all() == ["A", "B"]
    finally:
        table.drop(engine, checkfirst=True)
        no_default_db.dispose()
        engine.dispose()


@pytest.mark.parametrize("key", [p.values[0] for p in _target_params(only=frozenset({"mssql"}))])
def test_mssql_fk_references_by_schema_match_the_inspector(key: str) -> None:
    """Q9: en SQL Server, las FK de todo el esquema en una consulta dan lo mismo que ``get_foreign_keys`` por tabla.

    Cubre dos FK a la misma tabla, una FK a sí misma, una FK hacia otro esquema, ``schema=None`` y nombres con otro case.
    """
    env = _url_env(key)
    if not os.environ.get(env):
        pytest.skip(f"{env} no definida")
    engine = _make_target_engine(key)
    default = inspect(engine).default_schema_name
    other = f"zz_it_q9_{uuid.uuid4().hex[:6]}"
    prefix = f"zzq{uuid.uuid4().hex[:6]}"
    md = MetaData()
    parent = Table(f"{prefix}_p", md, Column("id", Integer, primary_key=True, autoincrement=False))
    child = Table(
        f"{prefix}_c",
        md,
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("p1", Integer, ForeignKey(parent.c.id)),
        Column("p2", Integer, ForeignKey(parent.c.id)),
        Column("self_id", Integer, ForeignKey(f"{prefix}_c.id")),
    )
    cross = Table(
        f"{prefix}_x",
        md,
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("p", Integer, ForeignKey(parent.c.id)),
        schema=other,
    )
    with engine.begin() as conn:
        conn.execute(CreateSchema(other))
    try:
        md.create_all(engine)
        for schema in (None, default, other):
            insp = inspect(engine)
            tables = [t for t in insp.get_table_names(schema=schema) if t.startswith(prefix)]
            expected = {
                t: sorted(fk["referred_table"] for fk in insp.get_foreign_keys(t, schema=schema)) for t in tables
            }
            with patch.object(Inspector, "get_foreign_keys", side_effect=AssertionError("vía tabla a tabla")):
                got = DumpOrchestrator._referred_tables(tables, inspect(engine), schema)
            assert {t: sorted(refs) for t, refs in got.items()} == expected
        assert expected == {cross.name: [parent.name]}

        upper = [parent.name.upper(), child.name.upper()]
        got_upper = DumpOrchestrator._referred_tables(upper, inspect(engine), default)
        assert sorted(got_upper[child.name.upper()]) == sorted([parent.name, parent.name, child.name])
        assert got_upper[parent.name.upper()] == []
    finally:
        md.drop_all(engine, checkfirst=True)
        with engine.begin() as conn:
            conn.execute(DropSchema(other))
        engine.dispose()


# ------------------------------------------------------------- Fase 4: DumpConfig(on_error="isolate") (2026-10-01u)


def _isolate_tables(setup: Setup, request: pytest.FixtureRequest, *, s_length: int) -> None:
    """Origen con 10 filas (``req`` nulo en 3 y 8; ``s`` de 9 caracteres en 4 y 9); destino más estricto."""
    source = Table(
        setup.name("iso"),
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("s", String(30)),
        Column("req", String(5)),
        schema=setup.source_schema,
    )
    source.create(setup.source)
    rows = [
        {"id": i, "s": "largo9xyz" if i in (4, 9) else "ok", "req": None if i in (3, 8) else "r"} for i in range(1, 11)
    ]
    with setup.source.begin() as conn:
        conn.execute(source.insert(), rows)
    target = Table(
        setup.name("iso"),
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("s", String(s_length)),
        Column("req", String(5), nullable=False),
    )
    _create(request, setup.target, target)


def _ids(setup: Setup) -> list[int]:
    with setup.target.connect() as conn:
        return [r[0] for r in conn.execute(text(f"SELECT id FROM {setup.name('iso')} ORDER BY id"))]


@pytest.mark.parametrize("ranges", [1, 2], ids=["tabla_entera", "rangos"])
@pytest.mark.parametrize("setup", _target_params(), indirect=True)
def test_dump_isolate_not_null(setup: Setup, request: pytest.FixtureRequest, ranges: int) -> None:
    _isolate_tables(setup, request, s_length=30)

    result = setup.run(
        ["iso"], parallel_pk_ranges=ranges, on_error="isolate", rejects_csv_path=setup.tmp / "rechazos.csv"
    )

    assert [(r.status, r.rows_rejected) for r in result.table_results] == [("success", 2)], [
        r.error_msg for r in result.table_results
    ]
    assert _ids(setup) == [1, 2, 4, 5, 6, 7, 9, 10]
    rejects = pd.read_csv(setup.tmp / "rechazos.csv", sep="\t", keep_default_na=False)
    if ranges == 1:
        assert rejects["fila"].tolist() == [2, 7] and set(rejects["particion"]) == {""}
    else:  # rangos 1–5 y 6–10: la posición es la del rango
        assert sorted(zip(rejects["particion"].astype(int), rejects["fila"], strict=True)) == [(0, 2), (1, 2)]


@pytest.mark.parametrize(
    "setup",
    _target_params(only=frozenset({"postgresql", "mysql", "mariadb", "mariadb_connector", "oracle"})),
    indirect=True,
)
def test_dump_isolate_narrower_target_column(setup: Setup, request: pytest.FixtureRequest) -> None:
    """Destino con ``s`` más estrecho que el origen: los valores demasiado largos se apartan (SQL Server no: R-1)."""
    _isolate_tables(setup, request, s_length=5)

    result = setup.run(["iso"], on_error="isolate", rejects_csv_path=setup.tmp / "rechazos.csv")

    assert [(r.status, r.rows_rejected) for r in result.table_results] == [("success", 4)], [
        r.error_msg for r in result.table_results
    ]
    assert _ids(setup) == [1, 2, 5, 6, 7, 10]


@pytest.mark.parametrize("setup", _target_params(), indirect=True)
def test_dump_isolate_single_duplicated_row(setup: Setup, request: pytest.FixtureRequest) -> None:
    """G32 (4.4.0): añadir una única fila con la PK ya presente la aparta en todos los motores (Oracle fallaba)."""
    source = Table(
        setup.name("dup"),
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("s", String(10)),
        schema=setup.source_schema,
    )
    source.create(setup.source)
    with setup.source.begin() as conn:
        conn.execute(source.insert(), [{"id": 1, "s": "origen"}])
    target = _create(
        request,
        setup.target,
        Table(
            setup.name("dup"),
            MetaData(),
            Column("id", Integer, primary_key=True, autoincrement=False),
            Column("s", String(10)),
        ),
    )
    with setup.target.begin() as conn:
        conn.execute(target.insert(), [{"id": 1, "s": "destino"}])

    result = setup.run(["dup"], truncate_target=False, on_error="isolate", rejects_csv_path=setup.tmp / "rechazos.csv")

    assert [(r.status, r.rows_rejected) for r in result.table_results] == [("success", 1)], [
        r.error_msg for r in result.table_results
    ]
    with setup.target.connect() as conn:
        assert conn.execute(select(target.c.s)).scalars().all() == ["destino"]


# ------------------------------------------------------- U-V3: diario de constraints (G31 de util_bbdd_web, 4.4.0)


def _fk_enabled(engine: Engine, table: str) -> bool:
    """``True`` si la FK de ``table`` está activa en el catálogo del destino."""
    sql = {
        "mssql": "SELECT is_disabled FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID(:t)",
        "oracle": "SELECT status FROM user_constraints WHERE table_name = UPPER(:t) AND constraint_type = 'R'",
        "postgresql": "SELECT tgenabled FROM pg_trigger WHERE tgrelid = CAST(:t AS regclass) AND tgisinternal",
    }[engine.dialect.name]
    with engine.connect() as conn:
        states = [row[0] for row in conn.execute(text(sql), {"t": table})]
    assert states, f"sin FK en {table}"
    enabled = {"mssql": lambda s: not s, "oracle": lambda s: s == "ENABLED", "postgresql": lambda s: s == "O"}
    return all(enabled[engine.dialect.name](s) for s in states)


@pytest.mark.parametrize("setup", _target_params(only=frozenset({"postgresql", "mssql", "oracle"})), indirect=True)
def test_restore_constraints_after_an_interrupted_dump(setup: Setup, request: pytest.FixtureRequest) -> None:
    """Proceso interrumpido simulado: se desactiva con diario y no se reactiva; ``restore_constraints`` lo deja todo."""
    from util_bbdd.dump import ConstraintManager, restore_constraints

    parent, child = _parent_child(setup.target, setup.prefix, identity=False)
    _create(request, setup.target, parent)
    _create(request, setup.target, child)
    journal = setup.tmp / "constraints_journal.json"

    ConstraintManager(setup.target, setup.target_schema, journal_path=journal).disable_all([parent.name, child.name])

    assert journal.exists()
    assert not _fk_enabled(setup.target, child.name)

    results = restore_constraints(create_engine(setup.target.url), journal)  # otro proceso, otro engine

    assert results and all(r.status == "enabled" for r in results), results
    assert _fk_enabled(setup.target, child.name)
    assert not journal.exists()
    assert restore_constraints(setup.target, journal) == []
