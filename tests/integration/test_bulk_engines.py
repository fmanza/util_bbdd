"""Integración de ``BulkCrud`` (INSERT/UPDATE/DELETE) contra motores reales.

SQLite se ejecuta siempre (fichero temporal). El resto de motores se activan con una URL SQLAlchemy de un servidor de
PRUEBAS en ``UTIL_BBDD_TEST_<MOTOR>_URL`` (``POSTGRESQL``, ``MYSQL``, ``MARIADB``, ``MSSQL``, ``ORACLE``); sin ella se
saltan. La cuenta necesita CREATE TABLE y DROP TABLE::

    UTIL_BBDD_TEST_POSTGRESQL_URL="postgresql+psycopg://usuario:clave@servidor:5432/pruebas" \\
        python -m pytest tests/integration/test_bulk_engines.py

Cada prueba crea una tabla ``zz_util_bbdd_it_<id>`` y la elimina al terminar, incluso si falla.

Fallos conocidos marcados ``xfail(strict=True)`` (hallazgos de .ai/sessions/2026-09-23-performance-audit-bulk/): los
DELETE en SQL Server (P-05). Cuando se corrijan, las pruebas pasarán y ``strict`` obligará a retirar la marca.
``test_insert_and_update_roundtrip`` es la regresión de P-18 (UPDATE con columna DATETIME en SQL Server + pyodbc).
"""

from __future__ import annotations

import os
import uuid

from collections.abc import Iterator
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sqlalchemy import Column, DateTime, Engine, Float, Integer, MetaData, String, Table, create_engine, func, select

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._support.validation import normalize_identifier

pytestmark = [pytest.mark.integration, pytest.mark.cross_db]

SERVER_ENGINES: tuple[str, ...] = ("postgresql", "mysql", "mariadb", "mssql", "oracle")
ROWS_OVER_MSSQL_PARAM_LIMIT = 3_000  # > 2100 parámetros por petición de SQL Server

_P05_PARAMS = "P-05: SqlBasedDeleteStrategy supera el límite de 2100 parámetros de SQL Server (pyodbc)"
_P05_COMPOSITE = "P-05: SQL Server no admite '(a, b) IN ((..), (..))' en SqlBasedDeleteStrategy"


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


def _xfail_if_mssql(request: pytest.FixtureRequest, engine: Engine, reason: str, *, pyodbc_only: bool) -> None:
    if engine.dialect.name != "mssql":
        return
    if pyodbc_only and engine.dialect.driver != "pyodbc":
        return
    request.applymarker(pytest.mark.xfail(strict=True, reason=reason))


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


def test_delete_more_rows_than_mssql_parameter_limit(
    request: pytest.FixtureRequest, engine: Engine, scratch_table: Table
) -> None:
    _xfail_if_mssql(request, engine, _P05_PARAMS, pyodbc_only=True)
    crud = BulkCrud(engine)  # chunk_size por defecto (5000): un solo lote de 3000 PKs
    df = _frame(engine, ROWS_OVER_MSSQL_PARAM_LIMIT)
    crud.bulk_insert_from_df(df, scratch_table.name, generar_sql=False)

    crud.bulk_delete_from_df(df[[_name("id", engine)]], scratch_table.name, generar_sql=False)

    assert _count(engine, scratch_table) == 0


def test_delete_with_composite_primary_key(
    request: pytest.FixtureRequest, engine: Engine, composite_table: Table
) -> None:
    _xfail_if_mssql(request, engine, _P05_COMPOSITE, pyodbc_only=False)
    k1, k2, v = (_name(c, engine) for c in ("k1", "k2", "v"))
    df = pd.DataFrame({k1: [i // 10 for i in range(50)], k2: [i % 10 for i in range(50)], v: ["x"] * 50})
    crud = BulkCrud(engine)
    crud.bulk_insert_from_df(df, composite_table.name, generar_sql=False)

    crud.bulk_delete_from_df(df[[k1, k2]].iloc[:20], composite_table.name, generar_sql=False)

    assert _count(engine, composite_table) == 30
