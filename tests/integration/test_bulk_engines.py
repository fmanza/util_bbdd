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
``test_update_via_staging_matches_executemany`` verifica P-04 (UPDATE por tabla temporal, solo MySQL/MariaDB) y
``test_binary_column_roundtrip`` cubre P-21 (binarios UTF-8 válidos) y ``test_generated_sql_with_json_column`` cubre
P-20 (``generar_sql`` con columnas JSON) y ``test_generated_sql_keeps_percent_signs`` cubre P-23 (``%`` duplicados).
``test_update_column_named_like_pk_alias`` cubre P-25 (columna ``pk_<PK>``) y los dos tests de DELETE dentro de
``bulk_session`` cubren P-26 (el DELETE fuera de la transacción de la sesión).
Los dos tests de ``commit_every_n_chunks`` cubren P-27 (PostgreSQL perdía las filas del INSERT; en PostgreSQL se
prueban psycopg 3 y psycopg2 si están instalados) y los dos siguientes cubren P-28 (errores del driver sin envolver).
``test_wide_table_insert_and_update`` y ``test_delete_composite_pk_over_parameter_limit`` cubren P-13 (límite de
65.535 parámetros; en MariaDB se prueba también el conector ``mariadb`` si está instalado).
``test_delete_with_text_and_datetime_primary_keys`` cubre P-10 (DELETE por arrays en PostgreSQL).
"""

from __future__ import annotations

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
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.parallel_loader import ParallelBulkLoader
from util_bbdd.bulk._support.validation import normalize_identifier

pytestmark = [pytest.mark.integration, pytest.mark.cross_db]

SERVER_ENGINES: tuple[str, ...] = ("postgresql", "mysql", "mariadb", "mssql", "oracle")
ROWS_OVER_MSSQL_PARAM_LIMIT = 3_000  # > 2100 parámetros por petición de SQL Server


def _engine_params() -> list[object]:
    params: list[object] = [pytest.param("sqlite", id="sqlite")]
    for key in SERVER_ENGINES:
        env = f"UTIL_BBDD_TEST_{key.upper()}_URL"
        params.append(
            pytest.param(key, id=key, marks=pytest.mark.skipif(not os.environ.get(env), reason=f"{env} no definida"))
        )
    return params


@pytest.fixture(params=_engine_params())
def engine(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Engine]:
    key: str = request.param
    url = f"sqlite:///{tmp_path / 'bulk.db'}" if key == "sqlite" else os.environ[f"UTIL_BBDD_TEST_{key.upper()}_URL"]
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
    crud = BulkCrud(engine, chunk_size=1000, audit_csv_path=audit_csv)
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


def test_json_column_roundtrip(engine: Engine) -> None:
    """P-19: INSERT y UPDATE guardan el objeto JSON una sola vez y ``None`` como NULL SQL."""
    if engine.dialect.name in ("mssql", "oracle"):
        pytest.skip("SQL Server no tiene tipo JSON; Oracle refleja la columna como NullType (sin procesador)")
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
        crud = BulkCrud(engine, chunk_size=chunk_size, update_via_staging=staging)
        crud.bulk_update_from_df(df_update, table.name, False)
        with engine.connect() as conn:
            return [tuple(r) for r in conn.execute(select(table).order_by(table.c.id))]
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("chunk_size", [2, 5000])
def test_update_via_staging_matches_executemany(engine: Engine, chunk_size: int) -> None:
    """P-04: el UPDATE por tabla temporal deja la tabla igual que el executemany (incluidas PK repetidas y NULL)."""
    if engine.dialect.name not in ("mysql", "mariadb"):
        pytest.skip("update_via_staging solo aplica a MySQL/MariaDB")
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


def test_update_via_staging_rolls_back_inside_bulk_session(engine: Engine) -> None:
    """P-04: las tablas temporales no provocan commit implícito; un fallo en un lote posterior deshace todo."""
    if engine.dialect.name not in ("mysql", "mariadb"):
        pytest.skip("update_via_staging solo aplica a MySQL/MariaDB")
    table = _staging_table(engine)
    table.create(engine)
    try:
        seed = pd.DataFrame({"id": [1, 2, 3, 4], "a": [0] * 4, "s": ["s"] * 4})
        BulkCrud(engine).bulk_insert_from_df(seed, table.name, False)
        crud = BulkCrud(engine, chunk_size=2, update_via_staging=True)
        bad = pd.DataFrame({"id": [1, 2, 3, 4], "s": ["A", "B", "C", "D"], "keep": ["x", "y", None, "w"]})

        with pytest.raises(SQLAlchemyError), crud.bulk_session():
            crud.bulk_update_from_df(bad, table.name, False)

        with engine.connect() as conn:
            assert [r[0] for r in conn.execute(select(table.c.s).order_by(table.c.id))] == ["s"] * 4
            assert conn.execute(text("SHOW TABLES LIKE 'tmp_bulkupd_%'")).all() == []
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("update_via_staging", [True, False])
def test_binary_column_roundtrip(engine: Engine, update_via_staging: bool) -> None:
    """P-21: los bytes llegan intactos aunque sean UTF-8 válido (``normalize_sql_literal`` los decodifica a ``str``).

    Sin valores vacíos: Oracle guarda ``b""`` como NULL por diseño.
    """
    if not update_via_staging and engine.dialect.name not in ("mysql", "mariadb"):
        pytest.skip("update_via_staging solo cambia el UPDATE en MySQL/MariaDB")
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
        crud = BulkCrud(engine, update_via_staging=update_via_staging)

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


def test_generated_sql_with_json_column(engine: Engine, tmp_path: Path) -> None:
    """P-20: el SQL generado con columnas JSON se puede ejecutar y guarda los documentos (sin ``%``: ver P-23)."""
    if engine.dialect.name in ("mssql", "oracle"):
        pytest.skip("SQL Server no tiene tipo JSON; Oracle refleja la columna como NullType")
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
        crud = BulkCrud(engine, update_via_staging=update_via_staging)
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
    crud = BulkCrud(engine, commit_every_n_chunks=commit_every_n_chunks)

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
        crud = BulkCrud(eng, chunk_size=2, commit_every_n_chunks=commit_every_n_chunks)
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
        crud = BulkCrud(eng, chunk_size=2, commit_every_n_chunks=1)
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
        result = ParallelBulkLoader(eng, max_workers=1).load(scratch_table.name, readers)

        assert (result.total_rows, len(result.partition_errors)) == (3, 1), eng.dialect.driver
        assert _count(eng, scratch_table) == 4, eng.dialect.driver


def _mysql_driver_engines(engine: Engine) -> Iterator[Engine]:
    """El engine de la prueba y, en MariaDB, el mismo servidor con el conector ``mariadb`` (prepara en el servidor)."""
    yield engine
    if engine.dialect.name != "mariadb" or engine.dialect.driver == "mariadbconnector":
        return
    try:
        __import__("mariadb")
    except ImportError:
        return
    alt = create_engine(engine.url.set(drivername="mariadb+mariadbconnector"))
    try:
        yield alt
    finally:
        alt.dispose()


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
        for eng in _mysql_driver_engines(engine):
            with eng.begin() as conn:
                conn.execute(table.delete())
            data = {n("id"): np.arange(1, rows + 1), **{n(f"c{i}"): np.arange(rows) + i for i in range(ncols)}}
            df = pd.DataFrame(data)
            crud = BulkCrud(eng)
            crud.bulk_insert_from_df(df, table.name, False)
            updated = df.assign(**{n(f"c{i}"): df[n(f"c{i}")] * 2 for i in range(ncols)})
            crud.bulk_update_from_df(updated, table.name, False)

            with eng.connect() as conn:
                stored = pd.DataFrame(conn.execute(select(table).order_by(table.c[n("id")])).all(), columns=df.columns)
            pd.testing.assert_frame_equal(stored, updated, check_dtype=False, obj=eng.dialect.driver)
    finally:
        table.drop(engine, checkfirst=True)


def test_delete_composite_pk_over_parameter_limit(engine: Engine, composite_table: Table) -> None:
    """P-13: un lote de 34.000 PK compuestas (68.000 parámetros) supera el límite del conector ``mariadb``."""
    if engine.dialect.name not in ("mysql", "mariadb"):
        pytest.skip("límite de 65.535 parámetros de MySQL/MariaDB")
    k1, k2, v = (_name(c, engine) for c in ("k1", "k2", "v"))
    rows = 34_000
    df = pd.DataFrame({k1: np.arange(rows) // 10, k2: np.arange(rows) % 10, v: "x"})
    for eng in _mysql_driver_engines(engine):
        crud = BulkCrud(eng, chunk_size=rows)
        crud.bulk_insert_from_df(df, composite_table.name, False)

        crud.bulk_delete_from_df(df[[k1, k2]], composite_table.name, False)

        assert _count(eng, composite_table) == 0, eng.dialect.driver


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
