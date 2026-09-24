"""Columnas binarias en ``BulkCrud`` (hallazgo P-21 del performance-audit de bulk).

``normalize_sql_literal`` decodifica a ``str`` los ``bytes`` que son UTF-8 válido (``b"q"`` → ``"q"``). En una columna
binaria, los parámetros tipados rechazaban ese ``str`` (``TypeError``) en el INSERT de SQLite y SQL Server y en el
UPDATE de PostgreSQL y MySQL/MariaDB (sin staging), y Oracle lo guardaba como NULL. En las columnas binarias los bytes
originales deben llegar intactos; en las de texto se mantiene la decodificación.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, LargeBinary, MetaData, String, Table, create_engine, select

from util_bbdd.bulk import BulkCrud

pytestmark = pytest.mark.unit

VALUES: list[bytes | None] = [b"q", b"\xff\x00", b"a\x08", None, "ñ€".encode()]


@pytest.fixture
def table_and_engine(tmp_path: Path) -> tuple[Table, Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'bin.db'}")
    table = Table(
        "blobs", MetaData(), Column("id", Integer, primary_key=True), Column("b", LargeBinary), Column("s", String(10))
    )
    table.create(engine)
    return table, engine


def _column(engine: Engine, table: Table, name: str) -> list[object]:
    with engine.connect() as conn:
        return list(conn.execute(select(table.c[name]).order_by(table.c.id)).scalars())


def test_insert_keeps_original_bytes_in_binary_columns(table_and_engine: tuple[Table, Engine]) -> None:
    table, engine = table_and_engine
    df = pd.DataFrame({"id": range(1, 6), "b": VALUES, "s": ["x"] * 5})

    BulkCrud(engine).bulk_insert_from_df(df, "blobs", generar_sql=False)

    assert _column(engine, table, "b") == VALUES


def test_update_keeps_original_bytes_in_binary_columns(table_and_engine: tuple[Table, Engine]) -> None:
    table, engine = table_and_engine
    crud = BulkCrud(engine)
    crud.bulk_insert_from_df(pd.DataFrame({"id": range(1, 6), "b": [b"\xff"] * 5, "s": ["x"] * 5}), "blobs", False)

    crud.bulk_update_from_df(pd.DataFrame({"id": range(1, 6), "b": VALUES[::-1], "s": ["y"] * 5}), "blobs", False)

    assert _column(engine, table, "b") == VALUES[::-1]


def test_insert_from_chunks_keeps_original_bytes(table_and_engine: tuple[Table, Engine]) -> None:
    table, engine = table_and_engine
    chunks = [pd.DataFrame({"id": [1], "b": [b"q"], "s": ["x"]}), pd.DataFrame({"id": [2], "b": [b"r"], "s": ["y"]})]

    BulkCrud(engine).bulk_insert_from_chunks(chunks, "blobs")

    assert _column(engine, table, "b") == [b"q", b"r"]


def test_text_columns_still_receive_decoded_strings(table_and_engine: tuple[Table, Engine]) -> None:
    table, engine = table_and_engine
    df = pd.DataFrame({"id": [1], "b": [b"q"], "s": ["ñ".encode()]})

    BulkCrud(engine).bulk_insert_from_df(df, "blobs", generar_sql=False)

    assert _column(engine, table, "s") == ["ñ"]
