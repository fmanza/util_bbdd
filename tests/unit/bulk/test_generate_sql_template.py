"""Generación de SQL por plantilla (hallazgo P-06 del performance-audit de bulk).

``generate_insert_sql``/``generate_update_sql``/``generate_delete_sql`` compilan la sentencia una vez con marcadores y
renderizan cada literal con ``render_literal_value`` del compilador. La salida debe ser idéntica, carácter a carácter, a
la del camino anterior (una sentencia compilada por fila con ``literal_binds``) en todos los dialectos y tipos, salvo:

- P-29: el INSERT sin la PK ya no lleva ``RETURNING``/``OUTPUT`` (``inline()``, también en el camino por fila).
- Observación de SQLAlchemy (Known issues de 0.12.0): en dialectos posicionales el compilador convertía en ``?`` un
  texto con forma ``%(nombre)s`` dentro de un literal; ahora se conserva.
"""

from __future__ import annotations

import datetime as dt

from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Identity,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    Time,
    Unicode,
    and_,
    create_engine,
    delete,
    insert,
    update,
)

from util_bbdd.bulk._support.sql_helpers import (
    _json_as_string_literals,
    _override_system_value,
    compile_stmt_with_binary_support,
    generate_delete_sql,
    generate_insert_sql,
    generate_insert_sql_override_identity,
    generate_update_sql,
    restore_binary_values,
)
from util_bbdd.bulk.normalize import dataframe_to_sql_records

pytestmark = pytest.mark.unit

_URLS: list[tuple[str, str]] = [
    ("sqlite://", "sqlite3"),
    ("postgresql+psycopg://", "psycopg"),
    ("postgresql+psycopg2://", "psycopg2"),
    ("mysql+pymysql://", "pymysql"),
    ("mariadb+mariadbconnector://", "mariadb"),
    ("mssql+pyodbc://", "pyodbc"),
    ("mssql+pymssql://", "pymssql"),
    ("oracle+oracledb://", "oracledb"),
]


@pytest.fixture(params=_URLS, ids=[url.split(":")[0] for url, _ in _URLS])
def dialect(request: pytest.FixtureRequest) -> Any:
    url, module = request.param
    pytest.importorskip(module)
    try:
        return create_engine(url).dialect  # no conecta
    except Exception as exc:  # p.ej. el paquete de tests ``tests/integration/metadata/mariadb`` tapa al driver ``mariadb``
        pytest.skip(f"driver {module} no utilizable en esta ejecución: {exc}")


def _tables(with_binary: bool) -> tuple[Table, Table]:
    md = MetaData()
    extra = [Column("bin", LargeBinary)] if with_binary else []
    wide = Table(
        "Wide Tbl",
        md,
        Column("id", Integer, primary_key=True),
        Column("order", String(50)),  # palabra reservada
        Column("Big", BigInteger),
        Column("small", SmallInteger),
        Column("num", Numeric(12, 3)),
        Column("flt", Float),
        Column("txt", Text),
        Column("uni", Unicode(40)),
        Column("flag", Boolean),
        Column("d", Date),
        Column("ts", DateTime),
        Column("tm", Time),
        Column("j", JSON),
        *extra,
        schema="sch",
    )
    composite = Table(
        "comp",
        md,
        Column("k1", Integer, primary_key=True),
        Column("k2", String(20), primary_key=True),
        Column("k3", DateTime, primary_key=True),
        Column("v", String(30)),
    )
    return wide, composite


_TEXTS: list[Any] = [
    "plain",
    "it's",
    "100% 50%% a%b",
    "back\\slash",
    "ñ€漢字",
    "?, :name, $1",
    "line\nbreak",
    "",
    None,
]


def _wide_frame(with_binary: bool) -> pd.DataFrame:
    rows = len(_TEXTS)
    data: dict[str, Any] = {
        "id": range(1, rows + 1),
        "order": _TEXTS,
        "Big": [2**40 + i for i in range(rows)],
        "small": [(-1) ** i * i for i in range(rows)],
        "num": [Decimal("12345.678"), Decimal("-0.001"), None, *[Decimal(i) for i in range(rows - 3)]],
        "flt": [0.1, -2.5e-8, float("nan"), 1e20, *[i / 3 for i in range(rows - 4)]],
        "txt": list(reversed(_TEXTS)),
        "uni": _TEXTS,
        "flag": [True, False, None, *[bool(i % 2) for i in range(rows - 3)]],
        "d": [dt.date(2026, 1, 1 + i) for i in range(rows)],
        "ts": [dt.datetime(2026, 9, 24, 10, 0, i, 123456) for i in range(rows)],
        "tm": [dt.time(23, 59, i) for i in range(rows)],
        "j": [{"k": "v'%", "n": [1, None]}, None, [1, "x"], *[{"i": i} for i in range(rows - 3)]],
    }
    if with_binary:
        data["bin"] = [b"\x00\xff", b"q", None, *[bytes([i]) for i in range(rows - 3)]]
    return pd.DataFrame(data)


def _records(df: pd.DataFrame, table: Table) -> list[dict[str, Any]]:
    records = dataframe_to_sql_records(df)
    restore_binary_values(records, table)
    return records


# Camino anterior (una sentencia compilada por fila), con inline() en el INSERT (P-29).
def _ref_insert(table: Table, records: list[dict[str, Any]], dialect: Any, override: bool = False) -> list[str]:
    lines = []
    for record in records:
        sql = compile_stmt_with_binary_support(
            insert(table).inline().values(_json_as_string_literals(table, record)), dialect
        )
        lines.append(_override_system_value(sql) if override else sql)
    return lines


def _ref_update(table: Table, records: list[dict[str, Any]], dialect: Any, pk: list[str], cols: list[str]) -> list[str]:
    lines = []
    for record in records:
        stmt = (
            update(table)
            .where(and_(*(table.c[c] == record[f"pk_{c}"] for c in pk)))
            .values(_json_as_string_literals(table, {c: record[c] for c in cols}))
        )
        lines.append(compile_stmt_with_binary_support(stmt, dialect))
    return lines


def _ref_delete(table: Table, records: list[dict[str, Any]], dialect: Any, pk: list[str]) -> list[str]:
    return [
        compile_stmt_with_binary_support(delete(table).where(and_(*(table.c[c] == r[c] for c in pk))), dialect)
        for r in records
    ]


@pytest.mark.parametrize("with_binary", [False, True])
def test_insert_matches_per_row_compilation(dialect: Any, with_binary: bool) -> None:
    wide, _ = _tables(with_binary)
    records = _records(_wide_frame(with_binary), wide)

    assert generate_insert_sql(insert(wide), records, dialect) == _ref_insert(wide, records, dialect)


def test_insert_override_identity_matches_per_row_compilation(dialect: Any) -> None:
    wide, _ = _tables(False)
    records = _records(_wide_frame(False), wide)

    expected = _ref_insert(wide, records, dialect, override=True)
    assert generate_insert_sql_override_identity(insert(wide), records, dialect) == expected


@pytest.mark.parametrize("with_binary", [False, True])
def test_update_matches_per_row_compilation(dialect: Any, with_binary: bool) -> None:
    wide, _ = _tables(with_binary)
    records = _records(_wide_frame(with_binary), wide)
    cols = [c.name for c in wide.columns if c.name != "id"]
    for record in records:
        record["pk_id"] = record["id"]

    lines = generate_update_sql(
        table=wide, records=records, update_cols=cols, pk_param_map={"id": "pk_id"}, pk_cols=["id"], dialect=dialect
    )

    assert lines == _ref_update(wide, records, dialect, ["id"], cols)


def test_update_and_delete_with_composite_pk_match(dialect: Any) -> None:
    _, comp = _tables(False)
    df = pd.DataFrame(
        {
            "k1": [1, 2, 3],
            "k2": ["a'b", "50%", "?"],
            "k3": [dt.datetime(2026, 1, 1, 0, 0, 0, 5), dt.datetime(2026, 1, 2), dt.datetime(2026, 1, 3)],
            "v": ["x", None, "z"],
        }
    )
    records = _records(df, comp)
    for record in records:
        for c in ("k1", "k2", "k3"):
            record[f"pk_{c}"] = record[c]
    pk = ["k1", "k2", "k3"]
    pk_map = {c: f"pk_{c}" for c in pk}

    updated = generate_update_sql(
        table=comp, records=records, update_cols=["v"], pk_param_map=pk_map, pk_cols=pk, dialect=dialect
    )
    assert updated == _ref_update(comp, records, dialect, pk, ["v"])

    # DELETE: registros de df.to_dict (tipos numpy/pandas), como en BulkCrud.
    delete_records = [{str(k): v for k, v in r.items()} for r in df[pk].to_dict(orient="records")]
    assert generate_delete_sql(records=delete_records, table=comp, pk_cols=pk, dialect=dialect) == _ref_delete(
        comp, delete_records, dialect, pk
    )


def test_none_in_where_keeps_is_null(dialect: Any) -> None:
    _, comp = _tables(False)
    records = [
        {"k1": 1, "k2": None, "k3": dt.datetime(2026, 1, 1)},
        {"k1": 2, "k2": "b", "k3": dt.datetime(2026, 1, 1)},
    ]

    lines = generate_delete_sql(records=records, table=comp, pk_cols=["k1", "k2", "k3"], dialect=dialect)

    assert lines == _ref_delete(comp, records, dialect, ["k1", "k2", "k3"])
    assert "IS NULL" in lines[0]


def test_insert_without_pk_has_no_returning(dialect: Any) -> None:
    """P-29: el INSERT sin la PK no debe devolver la clave (RETURNING/OUTPUT); en Oracle dejaba ``:ret_0`` sin valor."""
    table = Table("t", MetaData(), Column("id", Integer, Identity(), primary_key=True), Column("v", String(10)))

    (line,) = generate_insert_sql(insert(table), [{"v": "a"}], dialect)

    assert "RETURNING" not in line.upper()
    assert "OUTPUT" not in line.upper()
    assert ":ret_" not in line


@pytest.mark.parametrize("value", ["%(name)s", "a %(x)s b", "%s ? %%(y)s"])
def test_pyformat_like_text_is_preserved(dialect: Any, value: str) -> None:
    """Known issue de 0.12.0: en dialectos posicionales, ``'%(name)s'`` se generaba como ``'?'``."""
    table = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(30)))
    escaped = value.replace("'", "''")

    (ins,) = generate_insert_sql(insert(table), [{"id": 1, "v": value}], dialect)
    (upd,) = generate_update_sql(
        table=table,
        records=[{"id": 1, "v": value, "pk_id": 1}],
        update_cols=["v"],
        pk_param_map={"id": "pk_id"},
        pk_cols=["id"],
        dialect=dialect,
    )
    (dele,) = generate_delete_sql(records=[{"id": value}], table=table, pk_cols=["id"], dialect=dialect)

    assert f"'{escaped}'" in ins
    assert f"'{escaped}'" in upd
    assert value in dele


def test_record_with_other_keys_uses_per_row_path(dialect: Any) -> None:
    table = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10)))
    records = [{"id": 1, "v": "a"}, {"id": 2}]  # el segundo registro no trae "v"

    assert generate_insert_sql(insert(table), records, dialect) == _ref_insert(table, records, dialect)


def test_template_path_is_used_without_per_row_compilation(dialect: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin binarios, ninguna fila debe compilarse por el camino anterior (si no, P-06 no aporta nada)."""
    import util_bbdd.bulk._support.sql_helpers as helpers

    calls: list[object] = []
    original = helpers.compile_stmt_with_binary_support
    monkeypatch.setattr(
        helpers, "compile_stmt_with_binary_support", lambda *a, **k: calls.append(a) or original(*a, **k)
    )
    wide, _ = _tables(False)
    records = _records(_wide_frame(False), wide)
    cols = [c.name for c in wide.columns if c.name != "id"]

    generate_insert_sql(insert(wide), records, dialect)
    for record in records:
        record["pk_id"] = record["id"]
    generate_update_sql(
        table=wide, records=records, update_cols=cols, pk_param_map={"id": "pk_id"}, pk_cols=["id"], dialect=dialect
    )
    generate_delete_sql(records=records, table=wide, pk_cols=["id"], dialect=dialect)

    assert calls == []
