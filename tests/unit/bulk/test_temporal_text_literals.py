"""Fechas en texto en el SQL del modo seco (G48 de util_bbdd_web, U-10.1, 5.2.0).

Un ``str`` en una columna ``Date``/``DateTime``/``Time`` (las fechas de un CSV que pandas deja como texto) daba
``CompileError`` al generar el SQL en todos los dialectos; con ``dry_run=False`` el mismo ``DataFrame`` se cargaba.
Ahora se escribe como literal de cadena, decidido por valor, sin convertir ni interpretar el formato. Los objetos fecha
siguen el literal de su tipo (``TO_DATE`` en Oracle).
"""

from __future__ import annotations

import datetime as dt

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Date, DateTime, Engine, MetaData, String, Table, Time, create_engine, insert, text
from sqlalchemy.dialects import mssql, mysql, oracle, postgresql, sqlite

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._support.sql_helpers import generate_delete_sql, generate_insert_sql, generate_update_sql
from util_bbdd.bulk.options import AuditOptions

pytestmark = pytest.mark.unit

DIALECTS: dict[str, Any] = {
    "sqlite": sqlite.dialect(),
    "postgresql": postgresql.dialect(),
    "mssql": mssql.dialect(),
    "oracle": oracle.dialect(),
    "mysql": mysql.dialect(),
}

TABLE = Table(
    "t",
    MetaData(),
    Column("id", Date, primary_key=True),
    Column("d", Date),
    Column("ts", DateTime),
    Column("tm", Time),
    Column("s", String(20)),
)

TEXT = {"id": "2026-10-01", "d": "2026-10-18", "ts": "18/10/2026 12:30", "tm": "12:30:00", "s": "x"}
OBJECTS = {
    "id": dt.date(2026, 10, 1),
    "d": dt.date(2026, 10, 18),
    "ts": dt.datetime(2026, 10, 18, 12, 30),
    "tm": dt.time(12, 30),
    "s": "x",
}


def _update(records: list[dict[str, Any]], dialect: Any) -> list[str]:
    return generate_update_sql(
        table=TABLE,
        records=[{**record, "pk_id": record["id"]} for record in records],
        update_cols=["d", "ts", "tm"],
        pk_param_map={"id": "pk_id"},
        pk_cols=["id"],
        dialect=dialect,
    )


@pytest.mark.parametrize("name", DIALECTS)
def test_text_dates_are_written_as_given(name: str) -> None:
    dialect = DIALECTS[name]

    [insert_sql] = generate_insert_sql(insert(TABLE), [TEXT], dialect)
    [update_sql] = _update([TEXT], dialect)
    [delete_sql] = generate_delete_sql(records=[TEXT], table=TABLE, pk_cols=["id"], dialect=dialect)

    assert insert_sql.endswith("VALUES ('2026-10-01', '2026-10-18', '18/10/2026 12:30', '12:30:00', 'x');")
    assert "d='2026-10-18', ts='18/10/2026 12:30', tm='12:30:00' WHERE " in update_sql
    assert update_sql.endswith("t.id = '2026-10-01';")
    assert delete_sql.endswith("WHERE t.id = '2026-10-01';")


@pytest.mark.parametrize("name", DIALECTS)
def test_date_objects_keep_the_literal_of_their_type(name: str) -> None:
    dialect = DIALECTS[name]

    [insert_sql] = generate_insert_sql(insert(TABLE), [OBJECTS], dialect)

    expected = str(
        insert(TABLE).values(OBJECTS).compile(dialect=dialect, compile_kwargs={"literal_binds": True})
    ).replace("%%", "%")
    assert insert_sql == f"{expected};"
    if name == "oracle":
        assert "TO_DATE('2026-10-18', 'YYYY-MM-DD')" in insert_sql


@pytest.mark.parametrize("name", DIALECTS)
def test_text_and_objects_mixed_in_the_same_column(name: str) -> None:
    dialect = DIALECTS[name]

    lines = generate_insert_sql(insert(TABLE), [TEXT, OBJECTS, {**TEXT, "d": None}], dialect)

    assert "'18/10/2026 12:30'" in lines[0]
    assert "'18/10/2026 12:30'" not in lines[1]
    assert ", NULL, " in lines[2]


@pytest.mark.parametrize("name", DIALECTS)
def test_per_row_path_writes_text_dates(name: str) -> None:
    # Claves distintas de las de la plantilla: la segunda fila va por el camino anterior (por fila).
    records = [TEXT, {key: value for key, value in TEXT.items() if key != "s"}]

    lines = generate_insert_sql(insert(TABLE), records, DIALECTS[name])

    assert lines[1].endswith("VALUES ('2026-10-01', '2026-10-18', '18/10/2026 12:30', '12:30:00');")


@pytest.mark.parametrize("name", DIALECTS)
def test_quotes_in_text_dates_are_escaped(name: str) -> None:
    [insert_sql] = generate_insert_sql(insert(TABLE), [{**TEXT, "d": "18 o'clock"}], DIALECTS[name])

    assert "'18 o''clock'" in insert_sql


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE ev (id INTEGER PRIMARY KEY, d DATE, ts DATETIME)"))
    yield engine
    engine.dispose()


def test_bulk_crud_dry_run_with_text_dates(engine: Engine, tmp_path: Path) -> None:
    crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
    df = pd.DataFrame({"id": [1, 2], "d": ["2026-10-18", None], "ts": ["2026-10-18 12:30:00", "2026-10-19 08:00:00"]})
    out = tmp_path / "sql"
    out.mkdir()

    crud.bulk_insert_from_df(df, "ev", path_sql=out, dry_run=True)
    crud.bulk_update_from_df(df, "ev", path_sql=out, dry_run=True)

    content = "\n".join(path.read_text(encoding="utf-8") for path in sorted(out.glob("*.sql")))
    assert "VALUES (1, '2026-10-18', '2026-10-18 12:30:00');" in content
    assert "VALUES (2, NULL, '2026-10-19 08:00:00');" in content
    assert "SET d='2026-10-18', ts='2026-10-18 12:30:00' WHERE ev.id = 1;" in content


def test_bulk_crud_execution_with_text_dates_is_unchanged(engine: Engine) -> None:
    # La ejecución no cambia: en SQLite el tipo Date de SQLAlchemy rechaza el texto al enlazar el parámetro, como
    # antes (en MariaDB, el caso de G48, el driver lo acepta). Solo cambia cómo se escribe el SQL del modo seco.
    crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
    df = pd.DataFrame({"id": [1], "d": ["2026-10-18"], "ts": ["2026-10-18 12:30:00"]})

    with pytest.raises(Exception, match="SQLite Date type only accepts Python date objects"):
        crud.bulk_insert_from_df(df, "ev", dry_run=False)
