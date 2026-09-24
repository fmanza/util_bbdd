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
P-20 (``generar_sql`` con columnas JSON).
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
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.bulk import BulkCrud
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
        # En SQLite el fichero queda junto a la BD (el nombre incluye su ruta absoluta): se busca en todo tmp_path.
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
