"""Nombre del fichero de ``generar_sql`` (hallazgo P-24 del performance-audit de bulk).

``generate_sql_filename`` usaba ``url.database`` en crudo como prefijo:
- sin base de datos en la URL (p.ej. Oracle por ``?service_name=``) lanzaba ``ValueError``, y como ``generar_sql=True``
  es el valor por defecto, ``bulk_insert_from_df(df, tabla)`` fallaba;
- en SQLite con ruta absoluta, ``path_sql / nombre`` tomaba esa ruta y el fichero quedaba junto a la BD, no en
  ``path_sql``; con ``:memory:`` el nombre no era válido en Windows.
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from util_bbdd.bulk._support.sql_helpers import generate_sql_filename

pytestmark = pytest.mark.unit

_SUFFIX = r"-users-insert_\d{8}_\d{6}\.sql"


def _name(url: str) -> str:
    return str(generate_sql_filename(engine_url=url, table="users", operation="INSERT"))


@pytest.mark.parametrize(
    ("url", "prefix"),
    [
        ("postgresql+psycopg://u:p@h:5432/bench", "bench"),  # sin cambios
        ("sqlite:///mydb.db", "mydb.db"),  # sin cambios (relativa)
        ("oracle+oracledb://u:p@h:1521/?service_name=FREEPDB1", "FREEPDB1"),
        ("oracle+oracledb://u:p@h:1521/?sid=XE", "XE"),
        ("mssql+pyodbc://u:p@h:1433", "mssql"),  # sin BD ni service_name: nombre del motor
        ("sqlite:///:memory:", "_memory_"),
    ],
)
def test_prefix_is_derived_from_the_url(url: str, prefix: str) -> None:
    assert re.fullmatch(re.escape(prefix) + _SUFFIX, _name(url))


def test_sqlite_absolute_path_keeps_only_the_file_name(tmp_path: Path) -> None:
    name = generate_sql_filename(
        engine_url=f"sqlite:///{tmp_path / 'data' / 'bench.db'}", table="users", operation="INSERT"
    )

    assert re.fullmatch(r"bench\.db" + _SUFFIX, str(name))
    assert (tmp_path / "out" / name).parent == tmp_path / "out"  # queda dentro de path_sql


def test_generated_file_lands_in_path_sql_for_absolute_sqlite(tmp_path: Path) -> None:
    import pandas as pd

    from sqlalchemy import Column, Integer, MetaData, Table, create_engine

    from util_bbdd.bulk import BulkCrud

    engine = create_engine(f"sqlite:///{tmp_path / 'db' / 'bench.db'}")
    (tmp_path / "db").mkdir()
    Table("t", MetaData(), Column("id", Integer, primary_key=True)).create(engine)
    out = tmp_path / "sql"

    BulkCrud(engine).bulk_insert_from_df(pd.DataFrame({"id": [1]}), "t", generar_sql=True, path_sql=out)

    assert len(list(out.glob("*.sql"))) == 1
    assert list((tmp_path / "db").glob("*.sql")) == []
