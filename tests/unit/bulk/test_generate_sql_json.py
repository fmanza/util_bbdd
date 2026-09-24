"""``generar_sql=True`` con columnas JSON (hallazgo P-20 del performance-audit de bulk).

La generación compila con ``literal_binds=True`` y el tipo ``JSON`` de SQLAlchemy no tiene ``literal_processor``:
fallaba con ``CompileError``. El valor ya llega serializado por ``normalize_sql_literal``, así que debe escribirse
como literal de cadena (sin volver a serializar). Se verifica ejecutando el SQL generado.
"""

from __future__ import annotations

import json

from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import JSON, Column, Engine, Integer, MetaData, Table, create_engine, select

from util_bbdd.bulk import BulkCrud

pytestmark = pytest.mark.unit

DOCS: list[object] = [{"k": 1, "q": "it's", "b": "a\\b", "n": "ñ€😀"}, None, [1, "x", {"z": None}]]


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Table("docs", MetaData(), Column("id", Integer, primary_key=True), Column("j", JSON)).create(eng)
    return eng


def _run_generated_sql(engine: Engine, folder: Path) -> None:
    # En SQLite el nombre generado incluye la ruta absoluta de la BD, que prevalece sobre path_sql: el fichero queda
    # junto a la BD (comportamiento previo, ajeno a P-20). Se busca en todo tmp_path.
    (sql_file,) = sorted(folder.parent.rglob("*.sql"))
    raw = engine.raw_connection()
    try:
        raw.driver_connection.executescript(sql_file.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        raw.commit()
    finally:
        raw.close()


def _stored(engine: Engine) -> list[object]:
    with engine.connect() as conn:
        return [
            None if v is None else json.loads(v)
            for v in conn.exec_driver_sql("SELECT j FROM docs ORDER BY id").scalars()
        ]


def test_generated_insert_sql_stores_the_json_documents(engine: Engine, tmp_path: Path) -> None:
    out = tmp_path / "sql"
    BulkCrud(engine).bulk_insert_from_df(
        pd.DataFrame({"id": [1, 2, 3], "j": DOCS}), "docs", generar_sql=True, path_sql=out
    )

    _run_generated_sql(engine, out)

    assert _stored(engine) == DOCS


def test_generated_update_sql_stores_the_json_documents(engine: Engine, tmp_path: Path) -> None:
    crud = BulkCrud(engine)
    crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2, 3], "j": [{"old": 1}] * 3}), "docs", generar_sql=False)
    out = tmp_path / "sql"
    crud.bulk_update_from_df(pd.DataFrame({"id": [1, 2, 3], "j": DOCS}), "docs", generar_sql=True, path_sql=out)

    _run_generated_sql(engine, out)

    assert _stored(engine) == DOCS
    with engine.connect() as conn:
        table = Table("docs", MetaData(), autoload_with=engine)
        assert conn.execute(select(table.c.j).where(table.c.id == 2)).scalar_one() is None  # NULL SQL, no 'null'
