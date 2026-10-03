"""``metadata.facts`` y ``metadata.reflection.reflect_table``: lo que ``bulk`` consulta del catálogo (C5, ADR-003)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import MetaData, Table, create_engine

from util_bbdd.metadata import facts
from util_bbdd.metadata.reflection import reflect_table


def _conn(value: Any) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value.scalar.return_value = value
    conn.execute.return_value.fetchone.return_value = value
    return conn


def _sql(conn: MagicMock) -> str:
    return str(conn.execute.call_args.args[0])


def test_serial_sequence_passes_the_quoted_table() -> None:
    conn = _conn("public.t_id_seq")
    assert facts.serial_sequence(conn, '"Esquema"."T"', "id") == "public.t_id_seq"
    assert "pg_get_serial_sequence" in _sql(conn)
    assert conn.execute.call_args.args[1] == {"tbl": '"Esquema"."T"', "col": "id"}
    assert facts.serial_sequence(_conn(None), "t", "id") is None


@pytest.mark.parametrize(("owner", "view"), [("HR", "all_tab_identity_cols"), (None, "user_tab_identity_cols")])
def test_identity_generation_with_and_without_owner(owner: str | None, view: str) -> None:
    conn = _conn(("BY DEFAULT", "YES"))
    assert facts.identity_generation(conn, "T", "ID", owner) == ("BY DEFAULT", "YES")
    assert view in _sql(conn)
    assert ("owner" in conn.execute.call_args.args[1]) is bool(owner)
    assert facts.identity_generation(_conn(None), "T", "ID") is None


def test_server_and_table_facts() -> None:
    assert facts.storage_engine(_conn("MyISAM"), None, "t") == "MyISAM"
    assert facts.storage_engine(_conn(None), None, "t") is None
    assert facts.clustered_index_count(_conn(1), "dbo.t") == 1
    assert facts.clustered_index_count(_conn(None), "dbo.t") == 0
    assert facts.compatibility_level(_conn(160)) == 160
    assert facts.can_create_temp_tables(_conn(True)) is True
    assert facts.can_disable_triggers(_conn(0), "s", "t") is False


def test_reflect_table_with_and_without_foreign_keys(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'r.db').as_posix()}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE p (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("CREATE TABLE c (id INTEGER PRIMARY KEY, pid INTEGER REFERENCES p(id), x TEXT)")
    try:
        with_fk = Table("c", MetaData())
        reflect_table(engine, with_fk)
        without_fk = Table("c", MetaData())
        reflect_table(engine, without_fk, foreign_keys=False)
        assert [c.name for c in without_fk.columns] == [c.name for c in with_fk.columns] == ["id", "pid", "x"]
        assert len(with_fk.foreign_keys) == 1 and not without_fk.foreign_keys
        assert set(with_fk.metadata.tables) == {"c"}  # resolve_fks=False: no refleja la tabla referenciada
    finally:
        engine.dispose()
