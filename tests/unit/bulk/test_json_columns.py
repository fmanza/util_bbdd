"""Columnas JSON en ``BulkCrud`` (hallazgo P-19 del performance-audit de bulk).

``normalize_sql_literal`` ya serializa dict/list a texto JSON. Las sentencias construidas a partir de la tabla
reflejada aplicaban además el procesador del tipo ``JSON`` de SQLAlchemy: el objeto se guardaba como un *string* JSON
(doble serialización) y ``None`` como el literal JSON ``null`` en lugar de ``NULL`` SQL. En SQLite fallaban INSERT y
UPDATE; en MySQL y PostgreSQL, el UPDATE.
"""

from __future__ import annotations

import json

from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import JSON, Column, Engine, Integer, MetaData, String, Table, create_engine, func, select, text
from sqlalchemy.dialects import postgresql

from util_bbdd.bulk import BulkCrud

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'json.db'}")
    Table(
        "docs", MetaData(), Column("id", Integer, primary_key=True), Column("j", JSON), Column("s", String(10))
    ).create(eng)
    return eng


def _raw(engine: Engine) -> list[tuple[int, str | None, str | None]]:
    with engine.connect() as conn:
        return [(r[0], r[1], r[2]) for r in conn.execute(text("SELECT id, j, s FROM docs ORDER BY id"))]


def _null_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM docs WHERE j IS NULL")).scalar_one())


def test_insert_stores_json_object_once_and_none_as_sql_null(engine: Engine) -> None:
    df = pd.DataFrame({"id": [1, 2, 3], "j": [{"k": 1, "n": "ñ"}, None, [1, "x"]], "s": ["a", "b", "c"]})

    BulkCrud(engine).bulk_insert_from_df(df, "docs", generar_sql=False)

    rows = _raw(engine)
    assert json.loads(rows[0][1] or "") == {"k": 1, "n": "ñ"}
    assert rows[1][1] is None
    assert json.loads(rows[2][1] or "") == [1, "x"]
    assert _null_count(engine) == 1
    assert [r[2] for r in rows] == ["a", "b", "c"]


def test_update_stores_json_object_once_and_none_as_sql_null(engine: Engine) -> None:
    crud = BulkCrud(engine)
    crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2], "j": [{"k": 1}, {"k": 2}], "s": ["a", "b"]}), "docs", False)

    crud.bulk_update_from_df(pd.DataFrame({"id": [1, 2], "j": [{"k": 10}, None], "s": ["x", "y"]}), "docs", False)

    rows = _raw(engine)
    assert json.loads(rows[0][1] or "") == {"k": 10}
    assert rows[1][1] is None
    assert _null_count(engine) == 1
    assert [r[2] for r in rows] == ["x", "y"]


def test_insert_from_chunks_stores_json_object_once(engine: Engine) -> None:
    chunks = [
        pd.DataFrame({"id": [1], "j": [{"k": 1}], "s": ["a"]}),
        pd.DataFrame({"id": [2], "j": [None], "s": ["b"]}),
    ]

    BulkCrud(engine).bulk_insert_from_chunks(chunks, "docs")

    rows = _raw(engine)
    assert json.loads(rows[0][1] or "") == {"k": 1}
    assert rows[1][1] is None


def test_json_values_can_be_read_back_as_objects(engine: Engine) -> None:
    BulkCrud(engine).bulk_insert_from_df(pd.DataFrame({"id": [1], "j": [{"k": [1, 2]}], "s": ["a"]}), "docs", False)

    table = Table("docs", MetaData(), autoload_with=engine)
    with engine.connect() as conn:
        assert conn.execute(select(table.c.j)).scalar_one() == {"k": [1, 2]}
        assert conn.execute(select(func.json_type(table.c.j))).scalar_one() == "object"


def test_postgresql_update_keeps_jsonb_cast() -> None:
    # En PostgreSQL el parámetro debe seguir llevando el cast de la columna (::JSONB) para asignarse a jsonb.
    from sqlalchemy import bindparam, update

    from util_bbdd.bulk._support.sql_helpers import json_passthrough_binds

    table = Table("docs", MetaData(), Column("id", Integer, primary_key=True), Column("j", postgresql.JSONB))
    binds = json_passthrough_binds(table, ["id", "j"])
    assert list(binds) == ["j"]
    stmt = update(table).where(table.c.id == bindparam("pk_id")).values(binds)
    sql = str(stmt.compile(dialect=postgresql.psycopg.dialect()))
    assert "j=%(j)s::JSONB" in sql
