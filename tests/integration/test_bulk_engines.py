"""Integración de ``BulkCrud`` (INSERT/UPDATE/DELETE) contra motores reales.

SQLite se ejecuta siempre (fichero temporal). El resto de motores se activan con una URL SQLAlchemy de un servidor de
PRUEBAS en ``UTIL_BBDD_TEST_<MOTOR>_URL`` (``POSTGRESQL``, ``MYSQL``, ``MARIADB``, ``MSSQL``, ``ORACLE``); sin ella se
saltan. La cuenta necesita CREATE TABLE y DROP TABLE::

    UTIL_BBDD_TEST_POSTGRESQL_URL="postgresql+psycopg://usuario:clave@servidor:5432/pruebas" \\
        python -m pytest tests/integration/test_bulk_engines.py

Cada prueba crea una tabla ``zz_util_bbdd_it_<id>`` y la elimina al terminar, incluso si falla.

Regresiones de los hallazgos de .ai/sessions/2026-09-23-performance-audit-bulk/: ``test_insert_and_update_roundtrip``
cubre P-18 (UPDATE con columna DATETIME en SQL Server + pyodbc), los dos tests de DELETE cubren P-05 (más de 2100
parámetros y PK compuesta en SQL Server) ``test_json_column_roundtrip`` cubre P-19 (doble serialización de JSON) y
``test_same_bulkcrud_inserts_into_two_tables_with_same_columns`` cubre P-22 (filas en la tabla equivocada).
``test_update_via_staging_matches_executemany`` verifica P-04 y B-01 (UPDATE por tabla temporal, MySQL/MariaDB y
PostgreSQL) y
``test_binary_column_roundtrip`` cubre P-21 (binarios UTF-8 válidos) y ``test_generated_sql_with_json_column`` cubre
P-20 (``generar_sql`` con columnas JSON) y ``test_generated_sql_keeps_percent_signs`` cubre P-23 (``%`` duplicados).
``test_update_column_named_like_pk_alias`` cubre P-25 (columna ``pk_<PK>``) y los dos tests de DELETE dentro de
``bulk_session`` cubren P-26 (el DELETE fuera de la transacción de la sesión).
Los dos tests de ``commit_every_n_chunks`` cubren P-27 (PostgreSQL perdía las filas del INSERT; en PostgreSQL se
prueban psycopg 3 y psycopg2 si están instalados) y los dos siguientes cubren P-28 (errores del driver sin envolver).
``test_wide_table_insert_and_update`` y ``test_delete_composite_pk_over_parameter_limit`` cubren P-13 (límite de
65.535 parámetros; en MariaDB se prueba también el conector ``mariadb`` si está instalado).
``test_delete_with_text_and_datetime_primary_keys`` cubre P-10 (DELETE por arrays en PostgreSQL).
``test_generated_insert_without_pk_runs_and_keeps_pyformat_text`` cubre P-29 y el Known issue de 0.12.0 (SQL
generado por plantilla, P-06).
``test_generated_sql_binary_column_roundtrip`` cubre C-1 / P-30 (hotfix 2026-09-25: literales binarios por dialecto en
el SQL generado).
"""

from __future__ import annotations

import importlib.util
import os
import uuid

from collections.abc import Iterator
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from sqlalchemy import (
    JSON,
    URL,
    Column,
    DateTime,
    Engine,
    Float,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.parallel_loader import ParallelBulkLoader
from util_bbdd.bulk._support.validation import normalize_identifier
from util_bbdd.bulk.options import AuditOptions, BatchOptions, ExecutionOptions, ParallelOptions

pytestmark = [pytest.mark.integration, pytest.mark.cross_db]

SERVER_ENGINES: tuple[str, ...] = ("postgresql", "mysql", "mariadb", "mssql", "oracle")
#: MariaDB con el conector original (MariaDB Connector/Python), el driver que usa la librería para ``db_type="mariadb"``:
#: mismo servidor y URL que ``mariadb`` (PyMySQL) con ``mariadb+mariadbconnector``. Sesión 2026-10-01w.
MARIADB_CONNECTOR: str = "mariadb_connector"
HAS_MARIADB_CONNECTOR: bool = importlib.util.find_spec("mariadb") is not None
ROWS_OVER_MSSQL_PARAM_LIMIT = 3_000  # > 2100 parámetros por petición de SQL Server


MYSQL_FAMILY: frozenset[str] = frozenset({"mysql", "mariadb", MARIADB_CONNECTOR})  # staging, 65.535 parámetros
NO_JSON: frozenset[str] = frozenset({"mssql", "oracle"})  # SQL Server sin JSON; Oracle refleja JSON como NullType
STAGING_ENGINES: frozenset[str] = MYSQL_FAMILY | {"postgresql"}  # update_via_staging (P-04, B-01)


def _engine_params(*, only: frozenset[str] | None = None, exclude: frozenset[str] = frozenset()) -> list[Any]:
    """Un parámetro por motor; los servidores se saltan si falta su URL.

    ``only``/``exclude`` limitan los motores de un test en lugar de generarlos y saltarlos dentro (así el recuento de
    saltados solo refleja servidores sin URL).
    """
    params: list[Any] = []
    for key in ("sqlite", *SERVER_ENGINES, MARIADB_CONNECTOR):
        if (only is not None and key not in only) or key in exclude:
            continue
        if key == "sqlite":
            params.append(pytest.param(key, id=key))
            continue
        env = _url_env(key)
        skip_reason = f"{env} no definida" if not os.environ.get(env) else ""
        if key == MARIADB_CONNECTOR and not HAS_MARIADB_CONNECTOR:
            skip_reason = "paquete mariadb (MariaDB Connector/Python) no instalado"
        params.append(pytest.param(key, id=key, marks=pytest.mark.skipif(bool(skip_reason), reason=skip_reason)))
    return params


def _url_env(key: str) -> str:
    """Variable de entorno con la URL del motor (el conector de MariaDB usa la de ``mariadb``)."""
    return f"UTIL_BBDD_TEST_{('mariadb' if key == MARIADB_CONNECTOR else key).upper()}_URL"


def _engine_url(key: str) -> URL:
    """URL del servidor ``key``; ``mariadb_connector``: la de MariaDB con el driver ``mariadbconnector``."""
    url = make_url(os.environ[_url_env(key)])
    return url.set(drivername="mariadb+mariadbconnector") if key == MARIADB_CONNECTOR else url


@pytest.fixture(params=_engine_params())
def engine(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Engine]:
    key: str = request.param
    url: str | URL = f"sqlite:///{tmp_path / 'bulk.db'}" if key == "sqlite" else _engine_url(key)
    eng = create_engine(url)
    yield eng
    eng.dispose()


def _name(logical: str, engine: Engine) -> str:
    """Nombre físico según la convención de ``BulkCrud`` (MySQL/MariaDB no se normalizan)."""
    dialect = engine.dialect.name
    return logical if dialect in ("mysql", "mariadb") else normalize_identifier(logical, dialect)


@pytest.fixture
def scratch_table(engine: Engine) -> Iterator[Table]:
    """Tabla temporal con PK simple explícita; se elimina siempre al terminar."""
    n = partial(_name, engine=engine)
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("a"), Integer),
        Column(n("f"), Float),
        Column(n("s"), String(50)),
        Column(n("d"), DateTime),
    )
    table.create(engine)
    try:
        yield table
    finally:
        table.drop(engine, checkfirst=True)


@pytest.fixture
def composite_table(engine: Engine) -> Iterator[Table]:
    """Tabla temporal con PK compuesta; se elimina siempre al terminar."""
    n = partial(_name, engine=engine)
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("k1"), Integer, primary_key=True, autoincrement=False),
        Column(n("k2"), Integer, primary_key=True, autoincrement=False),
        Column(n("v"), String(20)),
    )
    table.create(engine)
    try:
        yield table
    finally:
        table.drop(engine, checkfirst=True)


def _frame(engine: Engine, rows: int) -> pd.DataFrame:
    f = np.arange(rows, dtype=float) / 3
    f[::7] = np.nan
    s = np.array([f" v{i} " for i in range(rows)], dtype=object)
    s[::11] = None
    data = {
        "id": np.arange(1, rows + 1),
        "a": np.arange(rows) % 1000,
        "f": f,
        "s": s,
        "d": pd.date_range("2026-01-01", periods=rows, freq="s"),
    }
    return pd.DataFrame({_name(k, engine): v for k, v in data.items()})


def _count(engine: Engine, table: Table) -> int:
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(table)).scalar_one())


def test_insert_and_update_roundtrip(engine: Engine, scratch_table: Table, tmp_path: Path) -> None:
    audit_csv = tmp_path / "audit.csv"
    crud = BulkCrud(engine, batch=BatchOptions(chunk_size=1000), audit=AuditOptions(csv_path=audit_csv))
    df = _frame(engine, ROWS_OVER_MSSQL_PARAM_LIMIT)
    col_a, col_s, col_f, col_id = (_name(c, engine) for c in ("a", "s", "f", "id"))

    crud.bulk_insert_from_df(df, scratch_table.name, generar_sql=False)
    assert _count(engine, scratch_table) == len(df)

    updated = df.copy()
    updated[col_a] = updated[col_a] + 1
    crud.bulk_update_from_df(updated, scratch_table.name, generar_sql=False)

    with engine.connect() as conn:
        total_a = conn.execute(select(func.sum(scratch_table.c[col_a]))).scalar_one()
        null_f = conn.execute(select(func.count()).where(scratch_table.c[col_f].is_(None))).scalar_one()
        null_s = conn.execute(select(func.count()).where(scratch_table.c[col_s].is_(None))).scalar_one()
        s_2 = conn.execute(select(scratch_table.c[col_s]).where(scratch_table.c[col_id] == 2)).scalar_one()
    assert int(total_a) == int(df[col_a].sum()) + len(df)
    assert int(null_f) == int(df[col_f].isna().sum())  # NaN → NULL
    assert int(null_s) == int(df[col_s].isna().sum())  # None → NULL
    assert s_2 == "v1"  # normalize_sql_literal recorta espacios

    # Auditoría integrada: cabecera + INSERT + UPDATE.
    assert len(audit_csv.read_text(encoding="utf-8").splitlines()) == 3


def test_delete_more_rows_than_mssql_parameter_limit(engine: Engine, scratch_table: Table) -> None:
    crud = BulkCrud(engine)  # chunk_size por defecto (5000): un solo lote de 3000 PKs
    df = _frame(engine, ROWS_OVER_MSSQL_PARAM_LIMIT)
    crud.bulk_insert_from_df(df, scratch_table.name, generar_sql=False)

    crud.bulk_delete_from_df(df[[_name("id", engine)]], scratch_table.name, generar_sql=False)

    assert _count(engine, scratch_table) == 0


def test_delete_with_composite_primary_key(engine: Engine, composite_table: Table) -> None:
    k1, k2, v = (_name(c, engine) for c in ("k1", "k2", "v"))
    df = pd.DataFrame({k1: [i // 10 for i in range(50)], k2: [i % 10 for i in range(50)], v: ["x"] * 50})
    crud = BulkCrud(engine)
    crud.bulk_insert_from_df(df, composite_table.name, generar_sql=False)

    crud.bulk_delete_from_df(df[[k1, k2]].iloc[:20], composite_table.name, generar_sql=False)

    assert _count(engine, composite_table) == 30


@pytest.mark.parametrize("engine", _engine_params(exclude=NO_JSON), indirect=True)
def test_json_column_roundtrip(engine: Engine) -> None:
    """P-19: INSERT y UPDATE guardan el objeto JSON una sola vez y ``None`` como NULL SQL."""
    n = partial(_name, engine=engine)
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("j"), JSON().with_variant(postgresql.JSONB(), "postgresql")),
    )
    table.create(engine)
    try:
        col_id, col_j = n("id"), n("j")
        crud = BulkCrud(engine)
        crud.bulk_insert_from_df(
            pd.DataFrame({col_id: [1, 2, 3], col_j: [{"k": 1, "n": "ñ"}, None, [1, "x"]]}), table.name, False
        )
        with engine.connect() as conn:
            inserted = dict(conn.execute(select(table.c[col_id], table.c[col_j]).order_by(table.c[col_id])).all())
            nulls = conn.execute(select(func.count()).where(table.c[col_j].is_(None))).scalar_one()
        assert inserted == {1: {"k": 1, "n": "ñ"}, 2: None, 3: [1, "x"]}
        assert nulls == 1

        crud.bulk_update_from_df(pd.DataFrame({col_id: [1, 3], col_j: [None, {"k": 30}]}), table.name, False)
        with engine.connect() as conn:
            updated = dict(conn.execute(select(table.c[col_id], table.c[col_j]).order_by(table.c[col_id])).all())
            nulls = conn.execute(select(func.count()).where(table.c[col_j].is_(None))).scalar_one()
        assert updated == {1: None, 2: None, 3: {"k": 30}}
        assert nulls == 2
    finally:
        table.drop(engine, checkfirst=True)


def test_same_bulkcrud_inserts_into_two_tables_with_same_columns(engine: Engine) -> None:
    """P-22: una misma ``BulkCrud`` (como en el volcado secuencial) no debe mezclar tablas con las mismas columnas."""
    n = partial(_name, engine=engine)
    metadata = MetaData()
    tables = [
        Table(
            n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
            metadata,
            Column(n("id"), Integer, primary_key=True, autoincrement=False),
            Column(n("v"), String(10)),
        )
        for _ in range(2)
    ]
    metadata.create_all(engine)
    try:
        crud = BulkCrud(engine)
        col_id, col_v = n("id"), n("v")
        crud.bulk_insert_from_df(pd.DataFrame({col_id: [1, 2], col_v: ["a1", "a2"]}), tables[0].name, False)
        crud.bulk_insert_from_df(pd.DataFrame({col_id: [3, 4], col_v: ["b3", "b4"]}), tables[1].name, False)

        with engine.connect() as conn:
            rows = [
                [tuple(r) for r in conn.execute(select(t.c[col_id], t.c[col_v]).order_by(t.c[col_id]))] for t in tables
            ]
        assert rows == [[(1, "a1"), (2, "a2")], [(3, "b3"), (4, "b4")]]
    finally:
        metadata.drop_all(engine)


def _staging_table(engine: Engine) -> Table:
    n = partial(_name, engine=engine)
    return Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("a"), Integer),
        Column(n("f"), Float),
        Column(n("s"), String(20)),
        Column(n("d"), DateTime),
        Column(n("j"), JSON),
        Column(n("keep"), String(10), nullable=False, server_default="k"),
    )


def _update_state(engine: Engine, df_update: pd.DataFrame, *, staging: bool, chunk_size: int) -> list[tuple[Any, ...]]:
    table = _staging_table(engine)
    table.create(engine)
    try:
        seed = pd.DataFrame({"id": [1, 2, 3, 4], "a": [0] * 4, "f": [0.0] * 4, "s": ["s"] * 4, "j": [{"x": 0}] * 4})
        seed["d"] = pd.Timestamp("2020-01-01")
        BulkCrud(engine).bulk_insert_from_df(seed, table.name, False)
        crud = BulkCrud(
            engine, batch=BatchOptions(chunk_size=chunk_size), execution=ExecutionOptions(update_via_staging=staging)
        )
        crud.bulk_update_from_df(df_update, table.name, False)
        with engine.connect() as conn:
            return [tuple(r) for r in conn.execute(select(table).order_by(table.c.id))]
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=STAGING_ENGINES), indirect=True)
@pytest.mark.parametrize("chunk_size", [2, 5000])
def test_update_via_staging_matches_executemany(engine: Engine, chunk_size: int) -> None:
    """P-04/B-01: el UPDATE por tabla temporal deja la tabla igual que el executemany (incluidas PK repetidas y NULL)."""
    df_update = pd.DataFrame(
        {
            "id": [1, 3, 2, 2, 99, 1],  # 2 repetido en el mismo lote, 1 en lotes distintos, 99 no existe
            "a": [10, 30, 20, 21, 99, 11],
            "f": [1.5, None, 2.5, 2.75, 9.0, 1.25],
            "s": [" x ", None, "it's", "%s ?", "no", "fin"],
            "d": [pd.Timestamp("2026-01-01 10:00:00"), pd.NaT, pd.Timestamp("2026-02-01"), pd.NaT, pd.NaT, pd.NaT],
            "j": [{"k": 1}, None, {"k": "first"}, {"k": "last"}, {"k": 9}, [1, "final"]],
        }
    )

    via_executemany = _update_state(engine, df_update, staging=False, chunk_size=chunk_size)
    via_staging = _update_state(engine, df_update, staging=True, chunk_size=chunk_size)

    assert len(via_staging) == 4
    assert via_staging == via_executemany
    assert [r for r in via_staging if r[0] == 2][0][5] == {"k": "last"}


@pytest.mark.parametrize("engine", _engine_params(only=STAGING_ENGINES), indirect=True)
def test_update_via_staging_rolls_back_inside_bulk_session(engine: Engine) -> None:
    """P-04/B-01: las tablas temporales no provocan commit implícito; un fallo en un lote posterior deshace todo."""
    table = _staging_table(engine)
    table.create(engine)
    try:
        seed = pd.DataFrame({"id": [1, 2, 3, 4], "a": [0] * 4, "s": ["s"] * 4})
        BulkCrud(engine).bulk_insert_from_df(seed, table.name, False)
        crud = BulkCrud(engine, batch=BatchOptions(chunk_size=2), execution=ExecutionOptions(update_via_staging=True))
        bad = pd.DataFrame({"id": [1, 2, 3, 4], "s": ["A", "B", "C", "D"], "keep": ["x", "y", None, "w"]})

        with pytest.raises(SQLAlchemyError), crud.bulk_session():
            crud.bulk_update_from_df(bad, table.name, False)

        with engine.connect() as conn:
            assert [r[0] for r in conn.execute(select(table.c.s).order_by(table.c.id))] == ["s"] * 4
            if engine.dialect.name in MYSQL_FAMILY:
                assert conn.execute(text("SHOW TABLES LIKE 'tmp_bulkupd_%'")).all() == []
    finally:
        table.drop(engine, checkfirst=True)


# update_via_staging=True (por defecto) en todos los motores; False solo cambia el UPDATE en MySQL/MariaDB y PostgreSQL.
_BINARY_CASES: list[Any] = [
    *(pytest.param(p.values[0], True, id=f"{p.id}-staging", marks=p.marks) for p in _engine_params()),
    *(
        pytest.param(p.values[0], False, id=f"{p.id}-no-staging", marks=p.marks)
        for p in _engine_params(only=STAGING_ENGINES)
    ),
]


@pytest.mark.parametrize(("engine", "update_via_staging"), _BINARY_CASES, indirect=["engine"])
def test_binary_column_roundtrip(engine: Engine, update_via_staging: bool) -> None:
    """P-21: los bytes llegan intactos aunque sean UTF-8 válido (``normalize_sql_literal`` los decodifica a ``str``).

    Sin valores vacíos: Oracle guarda ``b""`` como NULL por diseño.
    """
    n = partial(_name, engine=engine)
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("b"), LargeBinary),
    )
    table.create(engine)
    try:
        col_id, col_b = n("id"), n("b")
        inserted: list[bytes | None] = [b"q", b"\xff\x00", b"a\x08", None, "ñ€".encode()]
        updated: list[bytes | None] = [None, b"u", b"\xfe\x01", "é".encode(), b"z"]
        crud = BulkCrud(engine, execution=ExecutionOptions(update_via_staging=update_via_staging))

        crud.bulk_insert_from_df(pd.DataFrame({col_id: range(1, 6), col_b: inserted}), table.name, False)
        with engine.connect() as conn:
            got = [
                None if v is None else bytes(v)
                for v in conn.execute(select(table.c[col_b]).order_by(table.c[col_id])).scalars()
            ]
        assert got == inserted

        crud.bulk_update_from_df(pd.DataFrame({col_id: range(1, 6), col_b: updated}), table.name, False)
        with engine.connect() as conn:
            got = [
                None if v is None else bytes(v)
                for v in conn.execute(select(table.c[col_b]).order_by(table.c[col_id])).scalars()
            ]
        assert got == updated
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(exclude=NO_JSON), indirect=True)
def test_generated_sql_with_json_column(engine: Engine, tmp_path: Path) -> None:
    """P-20: el SQL generado con columnas JSON se puede ejecutar y guarda los documentos (sin ``%``: ver P-23)."""
    n = partial(_name, engine=engine)
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("j"), JSON().with_variant(postgresql.JSONB(), "postgresql")),
    )
    table.create(engine)
    backslash = chr(92)
    docs: list[object] = [{"k": 1, "q": "it's", "b": f"a{backslash}b", "dq": 'x"y', "n": "ñ€"}, None, [1, {"z": None}]]
    try:
        col_id, col_j = n("id"), n("j")
        BulkCrud(engine).bulk_insert_from_df(
            pd.DataFrame({col_id: [1, 2, 3], col_j: docs}), table.name, generar_sql=True, path_sql=tmp_path / "sql"
        )
        (sql_file,) = sorted(tmp_path.rglob("*.sql"))
        raw = engine.raw_connection()
        try:
            cursor = raw.cursor()
            for statement in filter(None, (line.strip() for line in sql_file.read_text(encoding="utf-8").splitlines())):
                cursor.execute(statement.rstrip(";"))
            raw.commit()
        finally:
            raw.close()

        with engine.connect() as conn:
            stored = list(conn.execute(select(table.c[col_j]).order_by(table.c[col_id])).scalars())
        assert stored == docs
    finally:
        table.drop(engine, checkfirst=True)


def _execute_generated_sql(engine: Engine, root: Path) -> None:
    """Ejecuta sentencia a sentencia el único ``.sql`` generado bajo ``root`` y lo elimina."""
    (sql_file,) = sorted(root.rglob("*.sql"))
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        for statement in filter(None, (line.strip() for line in sql_file.read_text(encoding="utf-8").splitlines())):
            cursor.execute(statement.rstrip(";"))
        raw.commit()
    finally:
        raw.close()
    sql_file.unlink()


def test_generated_sql_keeps_percent_signs(engine: Engine, tmp_path: Path) -> None:
    """P-23: al ejecutar el SQL generado, los ``%`` de los datos no se duplican (INSERT y UPDATE)."""
    n = partial(_name, engine=engine)
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("s"), String(30)),
    )
    table.create(engine)
    col_id, col_s = n("id"), n("s")
    inserted = ["a%b", "100%", "it's %s", "%%x"]
    updated = ["50% off", "%", "x%%y", "LIKE 'a%'"]
    try:
        crud = BulkCrud(engine)
        crud.bulk_insert_from_df(
            pd.DataFrame({col_id: range(1, 5), col_s: inserted}),
            table.name,
            generar_sql=True,
            path_sql=tmp_path / "sql",
        )
        _execute_generated_sql(engine, tmp_path)
        with engine.connect() as conn:
            assert list(conn.execute(select(table.c[col_s]).order_by(table.c[col_id])).scalars()) == inserted

        crud.bulk_update_from_df(
            pd.DataFrame({col_id: range(1, 5), col_s: updated}), table.name, generar_sql=True, path_sql=tmp_path / "sql"
        )
        _execute_generated_sql(engine, tmp_path)
        with engine.connect() as conn:
            assert list(conn.execute(select(table.c[col_s]).order_by(table.c[col_id])).scalars()) == updated
    finally:
        table.drop(engine, checkfirst=True)


def test_generated_sql_binary_column_roundtrip(engine: Engine, tmp_path: Path) -> None:
    """C-1 / P-30: el SQL generado con columnas binarias se ejecuta y guarda los bytes exactos (INSERT y UPDATE).

    Antes, los bytes UTF-8 se escribían como cadena (TEXT en SQLite, Msg 257 en SQL Server, ``b"abc"`` → ``0x0ABC`` en
    Oracle) y los no UTF-8 como ``0x…`` (inválido en PostgreSQL, Oracle y SQLite). Sin ``b""``: Oracle lo guarda como NULL.
    """
    n = partial(_name, engine=engine)
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("b"), LargeBinary),
    )
    table.create(engine)
    col_id, col_b = n("id"), n("b")
    inserted: list[bytes | None] = [b"abc", b"a'b", b"a\\b", b"\x00\xff", "ñ€".encode(), None]
    updated: list[bytes | None] = [b"\xfe\x01", None, b"%(x)s ?", b"z", bytes(range(256)), b"q"]

    def stored() -> list[bytes | None]:
        with engine.connect() as conn:
            rows = conn.execute(select(table.c[col_b]).order_by(table.c[col_id])).scalars()
            return [None if v is None else bytes(v) for v in rows]

    try:
        crud = BulkCrud(engine)
        crud.bulk_insert_from_df(
            pd.DataFrame({col_id: range(1, 7), col_b: inserted}),
            table.name,
            generar_sql=True,
            path_sql=tmp_path / "sql",
        )
        _execute_generated_sql(engine, tmp_path)
        assert stored() == inserted

        crud.bulk_update_from_df(
            pd.DataFrame({col_id: range(1, 7), col_b: updated}), table.name, generar_sql=True, path_sql=tmp_path / "sql"
        )
        _execute_generated_sql(engine, tmp_path)
        assert stored() == updated
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("update_via_staging", [True, False])
@pytest.mark.parametrize("generar_sql", [False, True])
def test_update_column_named_like_pk_alias(
    engine: Engine, tmp_path: Path, update_via_staging: bool, generar_sql: bool
) -> None:
    """P-25: una columna real llamada ``pk_<PK>`` recibe su valor, no el de la PK."""
    n = partial(_name, engine=engine)
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("pk_id"), Integer),
        Column(n("v"), String(10)),
    )
    table.create(engine)
    col_id, col_pk_id, col_v = n("id"), n("pk_id"), n("v")
    try:
        crud = BulkCrud(engine, execution=ExecutionOptions(update_via_staging=update_via_staging))
        crud.bulk_insert_from_df(
            pd.DataFrame({col_id: [1, 2], col_pk_id: [100, 200], col_v: ["a", "b"]}), table.name, False
        )
        df = pd.DataFrame({col_id: [1, 2], col_pk_id: [111, 222], col_v: ["x", "y"]})
        if generar_sql:
            crud.bulk_update_from_df(df, table.name, generar_sql=True, path_sql=tmp_path / "sql")
            _execute_generated_sql(engine, tmp_path)
        else:
            crud.bulk_update_from_df(df, table.name, False)

        with engine.connect() as conn:
            rows = [tuple(r) for r in conn.execute(select(table).order_by(table.c[col_id]))]
        assert rows == [(1, 111, "x"), (2, 222, "y")]
    finally:
        table.drop(engine, checkfirst=True)


def test_delete_inside_bulk_session_rolls_back_with_it(engine: Engine, scratch_table: Table) -> None:
    """P-26: el DELETE usa la transacción de ``bulk_session``; si la sesión falla, no se borra nada."""
    crud = BulkCrud(engine)
    col_id = _name("id", engine)
    crud.bulk_insert_from_df(_frame(engine, 4), scratch_table.name, False)

    with pytest.raises(RuntimeError), crud.bulk_session():
        crud.bulk_delete_from_df(pd.DataFrame({col_id: [1, 2]}), scratch_table.name, False)
        raise RuntimeError("fallo posterior al DELETE")

    assert _count(engine, scratch_table) == 4


@pytest.mark.parametrize("commit_every_n_chunks", [None, 1])
def test_delete_inside_bulk_session_commits_with_it(
    engine: Engine, scratch_table: Table, commit_every_n_chunks: int | None
) -> None:
    """P-26: INSERT y DELETE de la misma sesión quedan aplicados al salir de ella."""
    col_id = _name("id", engine)
    BulkCrud(engine).bulk_insert_from_df(_frame(engine, 4), scratch_table.name, False)
    crud = BulkCrud(engine, batch=BatchOptions(commit_every_n_chunks=commit_every_n_chunks))

    with crud.bulk_session():
        crud.bulk_insert_from_df(_frame(engine, 6).iloc[4:], scratch_table.name, False)
        crud.bulk_delete_from_df(pd.DataFrame({col_id: [1, 2]}), scratch_table.name, False)

    with engine.connect() as conn:
        ids = list(conn.execute(select(scratch_table.c[col_id]).order_by(scratch_table.c[col_id])).scalars())
    assert ids == [3, 4, 5, 6]


def _pg_driver_engines(engine: Engine) -> Iterator[Engine]:
    """El engine de la prueba y, en PostgreSQL, el mismo servidor con el otro driver (psycopg 3 / psycopg2)."""
    yield engine
    if engine.dialect.name != "postgresql":
        return
    other = "psycopg2" if engine.dialect.driver == "psycopg" else "psycopg"
    try:
        __import__(other)
    except ImportError:
        return
    alt = create_engine(engine.url.set(drivername=f"postgresql+{other}"))
    try:
        yield alt
    finally:
        alt.dispose()


@pytest.mark.parametrize("in_session", [False, True])
@pytest.mark.parametrize("commit_every_n_chunks", [1, 2])
def test_commit_every_n_chunks_persists_inserts(
    engine: Engine, scratch_table: Table, commit_every_n_chunks: int, in_session: bool
) -> None:
    """P-27: con ``commit_every_n_chunks`` las filas del INSERT quedan guardadas (en PostgreSQL se perdían todas)."""
    col_id = _name("id", engine)
    for eng in _pg_driver_engines(engine):
        with eng.begin() as conn:
            conn.execute(scratch_table.delete())
        crud = BulkCrud(eng, batch=BatchOptions(chunk_size=2, commit_every_n_chunks=commit_every_n_chunks))
        df = _frame(eng, 5)
        if in_session:
            with crud.bulk_session():
                crud.bulk_insert_from_df(df, scratch_table.name, False)
                crud.bulk_insert_from_df(df.assign(**{col_id: df[col_id] + 10}), scratch_table.name, False)
        else:
            crud.bulk_insert_from_df(df, scratch_table.name, False)
            crud.bulk_insert_from_chunks([df.assign(**{col_id: df[col_id] + 10})], scratch_table.name)

        assert (_count(eng, scratch_table), crud.rows_committed) == (10, 10), eng.dialect.driver


def test_commit_every_n_chunks_keeps_committed_chunks_on_failure(engine: Engine, scratch_table: Table) -> None:
    """P-27: si un lote falla, los lotes ya confirmados permanecen y ``rows_committed`` los cuenta."""
    col_id = _name("id", engine)
    for eng in _pg_driver_engines(engine):
        with eng.begin() as conn:
            conn.execute(scratch_table.delete())
        crud = BulkCrud(eng, batch=BatchOptions(chunk_size=2, commit_every_n_chunks=1))
        df = _frame(eng, 5)
        df.loc[4, col_id] = 1  # el tercer lote repite la PK 1, ya confirmada

        with pytest.raises(SQLAlchemyError):
            crud.bulk_insert_from_df(df, scratch_table.name, False)

        assert (_count(eng, scratch_table), crud.rows_committed) == (4, 4), eng.dialect.driver


def test_insert_duplicate_key_raises_sqlalchemy_integrity_error(engine: Engine, scratch_table: Table) -> None:
    """P-28: el error del INSERT es ``sqlalchemy.exc.IntegrityError`` en todos los motores (PostgreSQL lo daba sin
    envolver, como excepción del driver)."""
    for eng in _pg_driver_engines(engine):
        with eng.begin() as conn:
            conn.execute(scratch_table.delete())
        crud = BulkCrud(eng)
        crud.bulk_insert_from_df(_frame(eng, 2), scratch_table.name, False)

        with pytest.raises(IntegrityError):
            crud.bulk_insert_from_df(_frame(eng, 3), scratch_table.name, False)

        assert _count(eng, scratch_table) == 2, eng.dialect.driver


def test_parallel_loader_reports_partition_error(engine: Engine, scratch_table: Table) -> None:
    """P-28: un error de datos en una partición queda en ``partition_errors`` sin abortar la carga."""
    col_id = _name("id", engine)
    for eng in _pg_driver_engines(engine):
        with eng.begin() as conn:
            conn.execute(scratch_table.delete())
        BulkCrud(eng).bulk_insert_from_df(_frame(eng, 1), scratch_table.name, False)
        ok = _frame(eng, 13).iloc[10:]  # ids 11-13
        clash = _frame(eng, 2).assign(**{col_id: [1, 20]})  # la PK 1 ya existe

        readers = [lambda frame=frame: [frame] for frame in (ok, clash)]
        result = ParallelBulkLoader(eng, parallel=ParallelOptions(max_workers=1)).load(scratch_table.name, readers)

        assert (result.total_rows, len(result.partition_errors)) == (3, 1), eng.dialect.driver
        assert _count(eng, scratch_table) == 4, eng.dialect.driver


def test_wide_table_insert_and_update(engine: Engine) -> None:
    """P-13: 1000 filas × 71 columnas superan los 65.535 parámetros de una sentencia preparada (conector ``mariadb``)."""
    n = partial(_name, engine=engine)
    ncols = 70
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        *(Column(n(f"c{i}"), Integer) for i in range(ncols)),
    )
    table.create(engine)
    rows = 1000
    try:
        with engine.begin() as conn:
            conn.execute(table.delete())
        data = {n("id"): np.arange(1, rows + 1), **{n(f"c{i}"): np.arange(rows) + i for i in range(ncols)}}
        df = pd.DataFrame(data)
        crud = BulkCrud(engine)
        crud.bulk_insert_from_df(df, table.name, False)
        updated = df.assign(**{n(f"c{i}"): df[n(f"c{i}")] * 2 for i in range(ncols)})
        crud.bulk_update_from_df(updated, table.name, False)

        with engine.connect() as conn:
            stored = pd.DataFrame(conn.execute(select(table).order_by(table.c[n("id")])).all(), columns=df.columns)
        pd.testing.assert_frame_equal(stored, updated, check_dtype=False, obj=engine.dialect.driver)
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=MYSQL_FAMILY), indirect=True)
def test_delete_composite_pk_over_parameter_limit(engine: Engine, composite_table: Table) -> None:
    """P-13: un lote de 34.000 PK compuestas (68.000 parámetros) supera el límite del conector ``mariadb``."""
    k1, k2, v = (_name(c, engine) for c in ("k1", "k2", "v"))
    rows = 34_000
    df = pd.DataFrame({k1: np.arange(rows) // 10, k2: np.arange(rows) % 10, v: "x"})
    crud = BulkCrud(engine, batch=BatchOptions(chunk_size=rows))
    crud.bulk_insert_from_df(df, composite_table.name, False)

    crud.bulk_delete_from_df(df[[k1, k2]], composite_table.name, False)

    assert _count(engine, composite_table) == 0, engine.dialect.driver


@pytest.mark.parametrize("composite", [False, True])
def test_delete_with_text_and_datetime_primary_keys(engine: Engine, composite: bool) -> None:
    """P-10: el DELETE por arrays de PostgreSQL (``ANY`` / ``unnest``) con PK de texto y de fecha; resto de motores igual."""
    n = partial(_name, engine=engine)
    pk = [Column(n("code"), String(20), primary_key=True)]
    if composite:
        pk.append(Column(n("at"), DateTime, primary_key=True))
    table = Table(n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"), MetaData(), *pk, Column(n("v"), Integer))
    table.create(engine)
    rows = 3_000
    data: dict[str, Any] = {n("code"): [f"c'{i}%" for i in range(rows)], n("v"): range(rows)}
    if composite:
        data[n("at")] = pd.date_range("2026-01-01", periods=rows, freq="min")
    df = pd.DataFrame(data)
    pk_cols = [c.name for c in pk]
    try:
        for eng in _pg_driver_engines(engine):
            with eng.begin() as conn:
                conn.execute(table.delete())
            crud = BulkCrud(eng)
            crud.bulk_insert_from_df(df, table.name, False)

            crud.bulk_delete_from_df(df[pk_cols].iloc[::2], table.name, False)

            with eng.connect() as conn:
                left = sorted(conn.execute(select(table.c[n("v")])).scalars())
            assert left == list(range(1, rows, 2)), eng.dialect.driver
    finally:
        table.drop(engine, checkfirst=True)


def test_generated_insert_without_pk_runs_and_keeps_pyformat_text(engine: Engine, tmp_path: Path) -> None:
    """P-29: el INSERT generado sin la PK no lleva RETURNING/OUTPUT (en Oracle no se ejecutaba: ``:ret_0``).
    Known issue de 0.12.0: ``%(x)s`` dentro de un texto se generaba como ``?`` en SQLite y SQL Server + pyodbc."""
    from sqlalchemy import Identity

    n = partial(_name, engine=engine)
    auto: list[Any] = [] if engine.dialect.name in ("sqlite", "mysql", "mariadb") else [Identity()]
    table = Table(
        n(f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, *auto, primary_key=True),
        Column(n("s"), String(40)),
    )
    table.create(engine)
    values = ["a %(x)s b", "it's 100%", "? :name"]
    try:
        BulkCrud(engine).bulk_insert_from_df(
            pd.DataFrame({n("s"): values}), table.name, generar_sql=True, path_sql=tmp_path / "sql"
        )
        (sql_file,) = sorted(tmp_path.rglob("*.sql"))
        text_sql = sql_file.read_text(encoding="utf-8").upper()
        assert "RETURNING" not in text_sql
        assert "OUTPUT" not in text_sql
        _execute_generated_sql(engine, tmp_path)

        with engine.connect() as conn:
            stored = sorted(conn.execute(select(table.c[n("s")])).scalars())
        assert stored == sorted(values)
    finally:
        table.drop(engine, checkfirst=True)


def _fk_disabled_count(engine: Engine, child: Table) -> int:
    """Restricciones de ``child`` que siguen deshabilitadas (PostgreSQL: triggers de la FK; SQL Server: FK no fiable)."""
    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            return int(
                conn.execute(
                    text("SELECT count(*) FROM pg_trigger WHERE tgrelid = to_regclass(:t) AND tgenabled = 'D'"),
                    {"t": child.name},
                ).scalar_one()
            )
        if engine.dialect.name == "mssql":
            return int(
                conn.execute(
                    text(
                        "SELECT count(*) FROM sys.foreign_keys WHERE parent_object_id = OBJECT_ID(:t) "
                        "AND (is_disabled = 1 OR is_not_trusted = 1)"
                    ),
                    {"t": child.name},
                ).scalar_one()
            )
        if engine.dialect.name == "oracle":
            return int(
                conn.execute(
                    text(
                        "SELECT count(*) FROM user_constraints WHERE table_name = :t AND constraint_type = 'R' "
                        "AND status = 'DISABLED'"
                    ),
                    {"t": child.name.upper()},
                ).scalar_one()
            )
    return 0


def _indexed_table(engine: Engine) -> tuple[MetaData, Table]:
    """Tabla con PK y dos índices secundarios no únicos (``a`` y ``s``); nombres según la convención de ``BulkCrud``."""
    from sqlalchemy import Index

    n = partial(_name, engine=engine)
    suffix = uuid.uuid4().hex[:8]
    metadata = MetaData()
    table = Table(
        n(f"zz_util_bbdd_it_ix{suffix}"),
        metadata,
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("a"), Integer),
        Column(n("s"), String(30)),
        Index(f"ix_zz_a_{suffix}", n("a")),
        Index(f"ix_zz_s_{suffix}", n("s")),
    )
    metadata.create_all(engine)
    return metadata, table


def _index_state(engine: Engine, table: Table) -> tuple[list[str], int]:
    """Nombres (en minúsculas) de los índices no únicos de ``table`` y cuántos están deshabilitados o no válidos."""
    from sqlalchemy import inspect

    names = sorted(str(i["name"]).lower() for i in inspect(engine).get_indexes(table.name) if not i["unique"])
    dialect = engine.dialect.name
    queries = {
        "mssql": ("SELECT count(*) FROM sys.indexes WHERE object_id = OBJECT_ID(:t) AND is_disabled = 1", table.name),
        "oracle": (
            "SELECT count(*) FROM user_indexes WHERE table_name = :t AND status NOT IN ('VALID', 'N/A')",
            table.name.upper(),
        ),
        "postgresql": (
            "SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid WHERE c.relname = :t "
            "AND NOT i.indisvalid",
            table.name,
        ),
    }
    if dialect not in queries:
        return names, 0
    sql, name = queries[dialect]
    with engine.connect() as conn:
        return names, int(conn.execute(text(sql), {"t": name}).scalar_one())


def _indexed_frame(engine: Engine, rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            _name("id", engine): np.arange(1, rows + 1),
            _name("a", engine): np.arange(rows) % 50,
            _name("s", engine): [f"v{i}" for i in range(rows)],
        }
    )


@pytest.mark.parametrize("engine", _engine_params(exclude=frozenset({"sqlite"})), indirect=True)
def test_maintenance_scope_disable_indexes_restores_them(engine: Engine) -> None:
    """3.2.0: estrategia común con dump. En InnoDB, con la sesión atómica, se omite (su DDL confirmaría lo pendiente)."""
    metadata, table = _indexed_table(engine)
    try:
        before = _index_state(engine, table)
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
        with (
            crud.bulk_session(),
            crud.maintenance_scope(table.name, disable_constraints=False, disable_indexes=True) as ms,
        ):
            crud.bulk_insert_from_df(_indexed_frame(engine, 500), table.name, generar_sql=False)
        assert _count(engine, table) == 500
        assert _index_state(engine, table) == before
        if engine.dialect.name in ("mysql", "mariadb"):
            assert ms.index_results == []
        else:
            assert {r.action for r in ms.index_results} == (
                {"recreated"} if engine.dialect.name == "postgresql" else {"rebuilt"}
            )
            assert len(ms.index_results) == 2
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=MYSQL_FAMILY - {MARIADB_CONNECTOR}), indirect=True)
def test_maintenance_scope_innodb_recreates_indexes_with_commit_cadence(engine: Engine) -> None:
    metadata, table = _indexed_table(engine)
    try:
        before = _index_state(engine, table)
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False), batch=BatchOptions(commit_every_n_chunks=1))
        with (
            crud.bulk_session(),
            crud.maintenance_scope(table.name, disable_constraints=False, disable_indexes=True) as ms,
        ):
            assert _index_state(engine, table)[0] == []  # borrados durante la carga
            crud.bulk_insert_from_df(_indexed_frame(engine, 500), table.name, generar_sql=False)
        assert _count(engine, table) == 500
        assert _index_state(engine, table) == before
        assert [r.action for r in ms.index_results] == ["recreated", "recreated"]
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"postgresql", "mssql"})), indirect=True)
def test_maintenance_scope_disable_indexes_rolls_back_with_the_session(engine: Engine) -> None:
    """PostgreSQL y SQL Server: el DDL va en la transacción; si la carga falla, el rollback devuelve los índices."""
    metadata, table = _indexed_table(engine)
    try:
        before = _index_state(engine, table)
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
        with pytest.raises(RuntimeError, match="fallo"), crud.bulk_session():
            with crud.maintenance_scope(table.name, disable_constraints=False, disable_indexes=True):
                crud.bulk_insert_from_df(_indexed_frame(engine, 100), table.name, generar_sql=False)
                raise RuntimeError("fallo posterior")
        assert _count(engine, table) == 0
        assert _index_state(engine, table) == before
    finally:
        metadata.drop_all(engine)


def _unique_parent_child(engine: Engine, *, child_fk: bool = True) -> tuple[MetaData, Table, Table]:
    """Padre con PK, UNIQUE ``code`` e índice no único ``a``; hija con FK hacia ``code`` (v3.3.0, ``"all"``).

    ``child_fk=False``: la hija sin FK (en MariaDB/MySQL un índice referenciado por una FK no se toca nunca)."""
    from sqlalchemy import ForeignKeyConstraint, Index, UniqueConstraint

    n = partial(_name, engine=engine)
    suffix = uuid.uuid4().hex[:8]
    metadata = MetaData()
    parent = Table(
        n(f"zz_util_bbdd_it_up{suffix}"),
        metadata,
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("code"), String(20), nullable=False),
        Column(n("a"), Integer),
        UniqueConstraint(n("code"), name=f"uq_zz_up_{suffix}"),
        Index(f"ix_zz_up_{suffix}", n("a")),
    )
    child = Table(
        n(f"zz_util_bbdd_it_uc{suffix}"),
        metadata,
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("code"), String(20)),
        *([ForeignKeyConstraint([n("code")], [parent.c[n("code")]], name=f"fk_zz_uc_{suffix}")] if child_fk else []),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(parent.insert(), [{n("id"): 1, n("code"): "c1", n("a"): 1}])
        conn.execute(child.insert(), [{n("id"): 1, n("code"): "c1"}])
    return metadata, parent, child


def _full_index_state(engine: Engine, parent: Table, child: Table) -> tuple[Any, ...]:
    """PK, índices (únicos o no) y FK de la hija, más objetos deshabilitados, no válidos o FK no validadas."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    pk = tuple(sorted(str(c).lower() for c in insp.get_pk_constraint(parent.name).get("constrained_columns") or []))
    indexes = sorted((str(i["name"]).lower(), bool(i["unique"])) for i in insp.get_indexes(parent.name))
    fks = sorted(str(f["name"]).lower() for f in insp.get_foreign_keys(child.name))
    bad = _index_state(engine, parent)[1] + _fk_disabled_count(engine, child)
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            bad += int(
                conn.execute(
                    text("SELECT count(*) FROM pg_constraint WHERE conrelid = to_regclass(:t) AND NOT convalidated"),
                    {"t": child.name},
                ).scalar_one()
            )
    return pk, tuple(indexes), tuple(fks), bad


def _unique_frame(engine: Engine, rows: int, *, duplicate: bool = False) -> pd.DataFrame:
    codes = [f"k{i}" for i in range(rows)]
    if duplicate:
        codes[-1] = codes[0]
    return pd.DataFrame(
        {_name("id", engine): np.arange(2, rows + 2), _name("code", engine): codes, _name("a", engine): np.arange(rows)}
    )


@pytest.mark.parametrize("engine", _engine_params(exclude=frozenset({"sqlite", MARIADB_CONNECTOR})), indirect=True)
def test_maintenance_scope_all_restores_uniques_and_inbound_fks(engine: Engine) -> None:
    """v3.3.0: con ``"all"`` se desactivan también UNIQUE/PK (no el clustered) y se restaura todo, FK entrantes incluidas.

    Con ``commit_every_n_chunks`` para que InnoDB también lo aplique (en la sesión atómica se omite)."""
    metadata, parent, child = _unique_parent_child(engine)
    try:
        before = _full_index_state(engine, parent, child)
        assert before[-1] == 0
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False), batch=BatchOptions(commit_every_n_chunks=1))
        with crud.bulk_session(), crud.maintenance_scope(parent.name, disable_indexes="all") as ms:
            crud.bulk_insert_from_df(_unique_frame(engine, 500), parent.name, generar_sql=False)
        assert _count(engine, parent) == 501
        assert _full_index_state(engine, parent, child) == before
        assert ms.index_results
        assert all(r.action in ("rebuilt", "recreated") for r in ms.index_results), ms.index_results
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"postgresql", "mssql"})), indirect=True)
def test_maintenance_scope_all_duplicates_raise_and_roll_back(engine: Engine) -> None:
    """PostgreSQL y SQL Server: los duplicados hacen fallar la reconstrucción; la sesión deshace carga y DDL.

    En SQL Server el propio servidor deshace la transacción al fallar el ``REBUILD`` (las filas ya no existen), así que
    no se pueden listar las claves duplicadas; en PostgreSQL el savepoint lo permite."""
    from util_bbdd.exceptions import IndexRebuildError

    metadata, parent, child = _unique_parent_child(engine)
    try:
        before = _full_index_state(engine, parent, child)
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
        with pytest.raises(IndexRebuildError) as info, crud.bulk_session():
            with crud.maintenance_scope(parent.name, disable_indexes="all"):
                crud.bulk_insert_from_df(_unique_frame(engine, 50, duplicate=True), parent.name, generar_sql=False)
        if engine.dialect.name == "postgresql":
            assert any("k0" in dup for dups in info.value.duplicates.values() for dup in dups)
        assert info.value.results
        assert _count(engine, parent) == 1
        assert _full_index_state(engine, parent, child) == before
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"postgresql"})), indirect=True)
def test_maintenance_scope_all_error_before_first_commit_restores_without_false_failures(
    engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    """Con ``commit_every_n_chunks`` y un fallo antes del primer commit periódico, el rollback ya devuelve PK/UNIQUE y FK;
    la restauración no debe intentar recrearlas y avisar de un fallo que no lo es («ya existe»)."""
    import logging

    metadata, parent, child = _unique_parent_child(engine)
    try:
        before = _full_index_state(engine, parent, child)
        crud = BulkCrud(
            engine, audit=AuditOptions(warn_if_disabled=False), batch=BatchOptions(commit_every_n_chunks=1_000)
        )
        with caplog.at_level(logging.WARNING), pytest.raises(RuntimeError, match="fallo"), crud.bulk_session():
            with crud.maintenance_scope(parent.name, disable_indexes="all"):
                crud.bulk_insert_from_df(_unique_frame(engine, 50), parent.name, generar_sql=False)
                raise RuntimeError("fallo posterior")
        assert _count(engine, parent) == 1
        assert _full_index_state(engine, parent, child) == before
        assert not [m for m in caplog.messages if "Error al restaurar" in m or "No se pudieron restaurar" in m]
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"oracle", "mysql", "mariadb"})), indirect=True)
def test_maintenance_scope_all_duplicates_raise_with_keys_when_ddl_committed(engine: Engine) -> None:
    """Oracle y MariaDB/MySQL: el DDL ya confirmó la carga; ``IndexRebuildError`` lista las claves y las filas quedan."""
    from util_bbdd.exceptions import IndexRebuildError

    metadata, parent, child = _unique_parent_child(engine, child_fk=engine.dialect.name == "oracle")
    try:
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False), batch=BatchOptions(commit_every_n_chunks=1))
        with pytest.raises(IndexRebuildError) as info, crud.bulk_session():
            with crud.maintenance_scope(parent.name, disable_indexes="all"):
                crud.bulk_insert_from_df(_unique_frame(engine, 50, duplicate=True), parent.name, generar_sql=False)
        assert any("k0" in dup for dups in info.value.duplicates.values() for dup in dups), info.value.duplicates
        assert _count(engine, parent) == 51
    finally:
        with engine.begin() as conn:
            conn.execute(child.delete())
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql", "oracle", "postgresql"})), indirect=True)
def test_parallel_all_restores_uniques_and_inbound_fks(engine: Engine) -> None:
    metadata, parent, child = _unique_parent_child(engine)
    try:
        before = _full_index_state(engine, parent, child)
        loader = ParallelBulkLoader(
            engine,
            audit=AuditOptions(warn_if_disabled=False),
            parallel=ParallelOptions(mode="manual", max_workers=2, disable_constraints=True, disable_indexes="all"),
        )
        frame = _unique_frame(engine, 2_000)
        result = loader.load(parent.name, [lambda: iter([frame.iloc[:1000]]), lambda: iter([frame.iloc[1000:]])])
        assert result.partition_errors == []
        assert _count(engine, parent) == 2_001
        assert _full_index_state(engine, parent, child) == before
        assert all(r.action in ("rebuilt", "recreated") for r in result.index_results), result.index_results
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=MYSQL_FAMILY - {MARIADB_CONNECTOR}), indirect=True)
def test_maintenance_scope_validate_fks_after_detects_orphans(engine: Engine) -> None:
    """v3.3.0: con FOREIGN_KEY_CHECKS=0 entra un huérfano; ``validate_fks_after`` lo detecta al reactivarlas."""
    metadata, parent, child = _unique_parent_child(engine)
    try:
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
        orphan = pd.DataFrame({_name("id", engine): [2], _name("code", engine): ["no-existe"]})
        with crud.bulk_session(), crud.maintenance_scope(child.name, validate_fks_after=True) as ms:
            crud.bulk_insert_from_df(orphan, child.name, generar_sql=False)
        assert [(r.constraint_name.lower(), r.status) for r in ms.constraint_results] == [
            (f"fk_zz_uc_{child.name[-8:]}", "failed")
        ]
    finally:
        with engine.begin() as conn:
            conn.execute(child.delete())
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(exclude=frozenset({"sqlite"})), indirect=True)
def test_parallel_disable_indexes_restores_them(engine: Engine) -> None:
    metadata, table = _indexed_table(engine)
    try:
        before = _index_state(engine, table)
        loader = ParallelBulkLoader(
            engine,
            audit=AuditOptions(warn_if_disabled=False),
            parallel=ParallelOptions(mode="manual", max_workers=2, disable_indexes=True),
        )
        frame = _indexed_frame(engine, 2_000)
        result = loader.load(table.name, [lambda: iter([frame.iloc[:1000]]), lambda: iter([frame.iloc[1000:]])])
        assert result.partition_errors == []
        assert _count(engine, table) == 2_000
        assert _index_state(engine, table) == before
        assert len(result.index_results) == 2
        assert all(r.action in ("rebuilt", "recreated") for r in result.index_results)
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"oracle"})), indirect=True)
def test_oracle_parallel_disable_constraints_reenables_unique(engine: Engine) -> None:
    """Hotfix 2026-10-19: con ``ParallelOptions(disable_constraints=True)`` cada worker desactivaba y reactivaba las
    constraints en su ``maintenance_scope``; con otro worker insertando, DISABLE y ENABLE VALIDATE fallaban con ORA-00054
    y la UNIQUE quedaba DISABLED y sin índice (G0 de la sesión 2026-10-18b, 4 de 6 tandas)."""
    from sqlalchemy import UniqueConstraint

    suffix = uuid.uuid4().hex[:8]
    metadata = MetaData()
    table = Table(
        f"zz_util_bbdd_it_pu{suffix}",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("s", String(30)),
        UniqueConstraint("s", name=f"uq_zz_pu_{suffix}"),
    )
    metadata.create_all(engine)
    try:
        rows = 200_000  # con menos filas los workers apenas coinciden y la carrera no siempre se daba
        frame = pd.DataFrame({"id": np.arange(1, rows + 1), "s": [f"v{i}" for i in range(rows)]})
        crud = BulkCrud(
            engine,
            audit=AuditOptions(warn_if_disabled=False),
            parallel=ParallelOptions(mode="manual", max_workers=4, disable_constraints=True),
        )
        crud.bulk_insert_from_df(frame, table.name, generar_sql=False)
        with engine.connect() as conn:
            states = conn.execute(
                text("SELECT constraint_name, status, validated FROM user_constraints WHERE table_name = :t"),
                {"t": table.name.upper()},
            ).all()
        assert _count(engine, table) == rows
        assert {(str(status), str(validated)) for _, status, validated in states} == {("ENABLED", "VALIDATED")}
    finally:
        metadata.drop_all(engine)


def test_oracle_maintenance_scope_really_disables_foreign_keys(engine: Engine) -> None:
    """H-31 (C5): en Oracle los nombres de constraint llegaban en minúsculas (normalizados por SQLAlchemy) y
    ``ALTER TABLE … DISABLE CONSTRAINT "fk_x"`` fallaba en silencio: la optimización no se aplicaba nunca. Ahora salen
    del catálogo como los guarda Oracle."""
    if engine.dialect.name != "oracle":
        pytest.skip("solo Oracle")
    from sqlalchemy import ForeignKey

    suffix = uuid.uuid4().hex[:8]
    metadata = MetaData()
    parent = Table(f"zz_util_bbdd_op{suffix}", metadata, Column("id", Integer, primary_key=True, autoincrement=False))
    child = Table(
        f"zz_util_bbdd_oc{suffix}",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("pid", Integer, ForeignKey(parent.c.id)),
    )
    metadata.create_all(engine)
    try:
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
        with crud.bulk_session(), crud.maintenance_scope(child.name) as ms:
            assert _fk_disabled_count(engine, child) == 1
        assert ms.optimization_applied
        assert _fk_disabled_count(engine, child) == 0
        assert {r.status for r in ms.constraint_results} == {"enabled"}
    finally:
        metadata.drop_all(engine)


def _mssql_heap_with_incoming_fk(engine: Engine) -> tuple[MetaData, Table, Table, str]:
    """Heap con PK NONCLUSTERED y un índice no único, y una tabla hija con FK hacia él (con una fila cada una)."""
    from sqlalchemy import ForeignKey, Index, PrimaryKeyConstraint

    n = partial(_name, engine=engine)
    suffix = uuid.uuid4().hex[:8]
    metadata = MetaData()
    index_name = f"ix_zz_heap_{suffix}"
    parent = Table(
        n(f"zz_util_bbdd_it_h{suffix}"),
        metadata,
        Column(n("id"), Integer, autoincrement=False, nullable=False),
        Column(n("a"), Integer),
        PrimaryKeyConstraint(n("id"), mssql_clustered=False),
        Index(index_name, n("a")),
    )
    child = Table(
        n(f"zz_util_bbdd_it_hc{suffix}"),
        metadata,
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("pid"), Integer, ForeignKey(parent.c[n("id")])),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(parent.insert(), [{n("id"): 1, n("a"): 1}])
        conn.execute(child.insert(), [{n("id"): 1, n("pid"): 1}])
    return metadata, parent, child, index_name


def _mssql_index_disabled(conn: Any, table: Table) -> dict[str, bool]:
    """Índices NONCLUSTERED de ``table`` y si están deshabilitados.

    Dentro de ``maintenance_scope`` hay que pasar la conexión de la sesión: ``ALTER INDEX … DISABLE`` retiene un bloqueo
    de esquema hasta el commit y la consulta desde otra conexión esperaría a que acabe la sesión (que la espera a ella).
    """
    rows = conn.execute(
        text("SELECT name, is_primary_key, is_disabled FROM sys.indexes WHERE object_id = OBJECT_ID(:t) AND type = 2"),
        {"t": table.name},
    ).all()
    return {("PK" if r[1] else str(r[0])): bool(r[2]) for r in rows}


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
def test_mssql_disable_indexes_on_heap_keeps_pk_and_incoming_foreign_keys(engine: Engine) -> None:
    """Hotfix 2026-10-19: ``ALTER INDEX ALL … DISABLE`` en un heap deshabilitaba también la PK NONCLUSTERED; SQL Server
    deshabilitaba con ella las FK entrantes y el ``REBUILD`` no las reactivaba (quedaban ``is_not_trusted = 1``)."""
    metadata, parent, child, index_name = _mssql_heap_with_incoming_fk(engine)
    try:
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
        frame = pd.DataFrame({_name("id", engine): [2, 3], _name("a", engine): [2, 3]})
        with crud.bulk_session(), crud.maintenance_scope(parent.name, disable_constraints=False, disable_indexes=True):
            assert _mssql_index_disabled(crud._session.connection, parent) == {"PK": False, index_name: True}
            crud.bulk_insert_from_df(frame, parent.name, generar_sql=False)
        with engine.connect() as conn:
            assert _mssql_index_disabled(conn, parent) == {"PK": False, index_name: False}
        assert _fk_disabled_count(engine, child) == 0
        assert _count(engine, parent) == 3
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
def test_mssql_disable_indexes_on_heap_still_rejects_duplicate_pk(engine: Engine) -> None:
    """Hotfix 2026-10-19: con la PK deshabilitada se aceptaban filas con PK duplicada durante la carga."""
    metadata, parent, _, _ = _mssql_heap_with_incoming_fk(engine)
    try:
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
        duplicate = pd.DataFrame({_name("id", engine): [1], _name("a", engine): [9]})
        with pytest.raises(IntegrityError), crud.bulk_session():
            with crud.maintenance_scope(parent.name, disable_constraints=False, disable_indexes=True):
                crud.bulk_insert_from_df(duplicate, parent.name, generar_sql=False)
        assert _count(engine, parent) == 1
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("commit_every_n_chunks", [None, 1])
def test_maintenance_scope_error_keeps_original_exception_and_restores(
    engine: Engine, commit_every_n_chunks: int | None
) -> None:
    """Auditoría de bulk 2026-09-24: un error dentro de ``maintenance_scope`` llega tal cual (en PostgreSQL llegaba
    ``InFailedSqlTransaction``) y las restricciones quedan activas, también si un commit periódico confirmó su
    desactivación."""
    from sqlalchemy import ForeignKey

    n = partial(_name, engine=engine)
    suffix = uuid.uuid4().hex[:8]
    metadata = MetaData()
    parent = Table(
        n(f"zz_util_bbdd_it_p{suffix}"), metadata, Column(n("id"), Integer, primary_key=True, autoincrement=False)
    )
    child = Table(
        n(f"zz_util_bbdd_it_c{suffix}"),
        metadata,
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("pid"), Integer, ForeignKey(parent.c[n("id")])),
    )
    metadata.create_all(engine)
    col_id, col_pid = n("id"), n("pid")
    try:
        with engine.begin() as conn:
            conn.execute(parent.insert(), [{col_id: 1}])
            conn.execute(child.insert(), [{col_id: 1, col_pid: 1}])
        crud = BulkCrud(engine, batch=BatchOptions(chunk_size=1, commit_every_n_chunks=commit_every_n_chunks))

        with pytest.raises(IntegrityError), crud.bulk_session(), crud.maintenance_scope(child.name):
            crud.bulk_insert_from_df(pd.DataFrame({col_id: [2], col_pid: [1]}), child.name, False)
            crud.bulk_insert_from_df(pd.DataFrame({col_id: [1], col_pid: [1]}), child.name, False)  # PK repetida

        assert _fk_disabled_count(engine, child) == 0
        with engine.connect() as conn:
            ids = sorted(conn.execute(select(child.c[col_id])).scalars())
        assert ids == ([1] if commit_every_n_chunks is None else [1, 2])
    finally:
        metadata.drop_all(engine)


@pytest.mark.parametrize("engine", _engine_params(exclude=MYSQL_FAMILY), indirect=True)
def test_parallel_loader_disable_constraints_with_differently_cased_name(engine: Engine, scratch_table: Table) -> None:
    """Auditoría de bulk 2026-09-24 (hallazgo 4): con ``disable_constraints=True`` el loader citaba el nombre recibido
    tal cual. En PostgreSQL, con otras mayúsculas, la comprobación de propietario fallaba en silencio o el
    ``ALTER TABLE "NOMBRE"`` daba error; ahora usa la tabla reflejada, como ``BulkCrud``. (MySQL/MariaDB no normalizan
    nombres: su sensibilidad a mayúsculas depende de ``lower_case_table_names``.)"""
    name = scratch_table.name
    other_case = name.upper() if name == name.lower() else name.lower()
    df = _frame(engine, 6)
    readers = [lambda part=part: [part] for part in (df.iloc[:3], df.iloc[3:])]

    result = ParallelBulkLoader(engine, parallel=ParallelOptions(max_workers=1, disable_constraints=True)).load(
        other_case, readers
    )

    assert (result.total_rows, result.partition_errors) == (6, [])
    assert _count(engine, scratch_table) == 6


def test_sync_pk_sequences_with_name_that_needs_quoting(engine: Engine) -> None:
    """Auditoría de bulk 2026-09-24 (hallazgo 5): en PostgreSQL ``pg_get_serial_sequence`` recibía el nombre sin comillas
    (lo analiza como identificador) y Oracle buscaba ``UPPER(nombre)`` en el catálogo: con nombres que exigen comillas
    (aquí, un guion) la sincronización terminaba en ``error``/``unsupported`` y el contador quedaba atrasado."""
    from sqlalchemy import Identity

    n = partial(_name, engine=engine)
    auto: list[Any] = [] if engine.dialect.name in ("sqlite", "mysql", "mariadb") else [Identity()]
    table = Table(
        n(f"zz_util_bbdd_it-{uuid.uuid4().hex[:8]}"),
        MetaData(),
        Column(n("id"), Integer, *auto, primary_key=True),
        Column(n("v"), String(10)),
    )
    table.create(engine)
    col_id, col_v = n("id"), n("v")
    quoted = engine.dialect.identifier_preparer.format_table(table)
    try:
        with engine.begin() as conn:
            if engine.dialect.name == "mssql":
                conn.exec_driver_sql(f"SET IDENTITY_INSERT {quoted} ON")
            conn.execute(table.insert(), [{col_id: i, col_v: "x"} for i in (1, 2, 3)])
            if engine.dialect.name == "mssql":
                conn.exec_driver_sql(f"SET IDENTITY_INSERT {quoted} OFF")

        results = BulkCrud(engine).sync_pk_sequences([table.name])

        if engine.dialect.name == "sqlite":
            assert results == []  # SQLite: sin columna identity que sincronizar
            return
        (result,) = results
        assert (result.status, result.max_value) == ("synced", 3), result.error_msg
        with engine.begin() as conn:
            conn.execute(table.insert(), [{col_v: "nuevo"}])
            new_id = conn.execute(select(table.c[col_id]).where(table.c[col_v] == "nuevo")).scalar_one()
        assert new_id == 4
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"postgresql"})), indirect=True)
def test_sync_pk_sequences_in_mixed_case_schema(engine: Engine) -> None:
    """Hallazgo 5 en PostgreSQL: ``BulkCrud`` normaliza la tabla a minúsculas pero no el esquema; con un esquema con
    mayúsculas, ``pg_get_serial_sequence('Esquema.tabla')`` sin comillas buscaba ``esquema`` y fallaba."""
    from sqlalchemy import Identity
    from sqlalchemy.schema import CreateSchema, DropSchema

    schema = f"ZzUtilBbdd_{uuid.uuid4().hex[:6]}"
    table = Table(
        "t", MetaData(), Column("id", Integer, Identity(), primary_key=True), Column("v", String(5)), schema=schema
    )
    with engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        table.create(engine)
        with engine.begin() as conn:
            conn.execute(table.insert(), [{"id": i, "v": "x"} for i in (1, 2, 3)])

        (result,) = BulkCrud(engine).sync_pk_sequences([f"{schema}.t"])

        assert (result.status, result.max_value) == ("synced", 3), result.error_msg
        with engine.begin() as conn:
            conn.execute(table.insert(), [{"v": "nuevo"}])
            assert conn.execute(select(table.c.id).where(table.c.v == "nuevo")).scalar_one() == 4
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))


@pytest.mark.parametrize("engine", _engine_params(only=MYSQL_FAMILY), indirect=True)
def test_maintenance_scope_disable_indexes_keeps_session_atomic_on_innodb(engine: Engine, scratch_table: Table) -> None:
    """Auditoría de bulk 2026-09-24 (hallazgo 8): ``DISABLE KEYS``/``ENABLE KEYS`` no tienen efecto en InnoDB pero, como
    DDL, provocaban un commit implícito: al fallar la sesión quedaban confirmadas las filas insertadas antes."""
    crud = BulkCrud(engine)

    with pytest.raises(RuntimeError), crud.bulk_session():
        crud.bulk_insert_from_df(_frame(engine, 2), scratch_table.name, False)
        with crud.maintenance_scope(scratch_table.name, disable_constraints=False, disable_indexes=True):
            crud.bulk_insert_from_df(_frame(engine, 4).iloc[2:], scratch_table.name, False)
            raise RuntimeError("fallo posterior")

    assert _count(engine, scratch_table) == 0


def _reflection_signature(table: Table) -> dict[str, Any]:
    """Lo que ``BulkCrud`` usa de la ``Table`` reflejada (columnas, tipos, PK, identidad, defaults) e índices."""
    return {
        "columns": [
            (
                c.name,
                repr(c.type),
                c.nullable,
                c.primary_key,
                c.autoincrement,
                repr(c.identity),
                str(getattr(c.server_default, "arg", c.server_default)),
            )
            for c in table.columns
        ],
        "pk": [c.name for c in table.primary_key.columns],
        "indexes": sorted((i.name or "", tuple(c.name for c in i.columns)) for i in table.indexes),
    }


def test_reflect_without_foreign_keys_matches_default_reflection(engine: Engine) -> None:
    """Q9: ``reflect_foreign_keys=False`` da la misma tabla que la reflexión por defecto, salvo las FK."""
    from sqlalchemy import ForeignKey, Identity, Index, Numeric

    n = partial(_name, engine=engine)
    suffix = uuid.uuid4().hex[:8]
    md = MetaData()
    identity: list[Any] = [] if engine.dialect.name in ("mysql", "mariadb", "sqlite") else [Identity()]
    parent = Table(n(f"zz_util_bbdd_rp_{suffix}"), md, Column(n("id"), Integer, *identity, primary_key=True))
    child = Table(
        n(f"zz_util_bbdd_rc_{suffix}"),
        md,
        Column(n("id"), Integer, *identity, primary_key=True),
        Column(n("parent_id"), Integer, ForeignKey(parent.c[n("id")]), nullable=False),
        Column(n("amount"), Numeric(18, 4)),
        Column(n("s"), String(30), server_default="x"),
        Column(n("d"), DateTime),
        Index(n(f"ix_rc_{suffix}"), n("d")),
    )
    md.create_all(engine)
    try:
        default = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False)).reflect_table(child.name)
        without_fk = BulkCrud(
            engine, audit=AuditOptions(warn_if_disabled=False), execution=ExecutionOptions(reflect_foreign_keys=False)
        ).reflect_table(child.name)

        assert _reflection_signature(without_fk) == _reflection_signature(default)
        assert len(default.foreign_keys) == 1
        assert not without_fk.foreign_keys
        assert set(without_fk.metadata.tables) == {without_fk.key}
    finally:
        md.drop_all(engine, checkfirst=True)
