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
    _binary_or_value,
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
    return create_engine(url).dialect  # no conecta


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


# Camino anterior (una sentencia compilada por fila), con inline() en el INSERT (P-29) y los binarios con el literal
# hexadecimal del dialecto (C-1).
def _bin(table: Table, column: str, value: Any, dialect: Any) -> Any:
    return _binary_or_value(table.c[column].type, value, dialect) if column in table.c else value


def _ref_insert(table: Table, records: list[dict[str, Any]], dialect: Any, override: bool = False) -> list[str]:
    lines = []
    for record in records:
        values = {k: _bin(table, k, v, dialect) for k, v in _json_as_string_literals(table, record).items()}
        sql = compile_stmt_with_binary_support(insert(table).inline().values(values), dialect)
        lines.append(_override_system_value(sql) if override else sql)
    return lines


def _ref_update(table: Table, records: list[dict[str, Any]], dialect: Any, pk: list[str], cols: list[str]) -> list[str]:
    lines = []
    for record in records:
        values = {
            k: _bin(table, k, v, dialect)
            for k, v in _json_as_string_literals(table, {c: record[c] for c in cols}).items()
        }
        stmt = (
            update(table)
            .where(and_(*(table.c[c] == _bin(table, c, record[f"pk_{c}"], dialect) for c in pk)))
            .values(values)
        )
        lines.append(compile_stmt_with_binary_support(stmt, dialect))
    return lines


def _ref_delete(table: Table, records: list[dict[str, Any]], dialect: Any, pk: list[str]) -> list[str]:
    return [
        compile_stmt_with_binary_support(
            delete(table).where(and_(*(table.c[c] == _bin(table, c, r[c], dialect) for c in pk))), dialect
        )
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


def test_block_mixing_template_and_per_row_rows_keeps_order(dialect: Any) -> None:
    """P-31: con el render por columnas, las filas que caen al camino anterior salen en su sitio y con el mismo SQL."""
    _, comp = _tables(False)
    ts = dt.datetime(2026, 1, 1)
    table = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10)))
    inserts = [{"id": 1, "v": "a"}, {"id": 2}, {"id": 3, "v": None}, {"id": 4, "v": "d%"}, {"v": "e", "id": 5}]
    deletes = [
        {"k1": 1, "k2": None, "k3": ts},
        {"k1": 2, "k2": "b", "k3": ts},
        {"k1": 3, "k2": "c", "k3": None},
        {"k1": 4, "k2": "d", "k3": ts},
    ]

    assert generate_insert_sql(insert(table), inserts, dialect) == _ref_insert(table, inserts, dialect)
    pk = ["k1", "k2", "k3"]
    assert generate_delete_sql(records=deletes, table=comp, pk_cols=pk, dialect=dialect) == _ref_delete(
        comp, deletes, dialect, pk
    )


def test_direct_literal_processor_only_where_compiler_does_not_override(dialect: Any) -> None:
    """P-32: el literal_processor directo solo se usa si el compilador no redefine render_literal_value."""
    from sqlalchemy.sql.compiler import SQLCompiler

    from util_bbdd.bulk._support.sql_helpers import _LiteralTemplate, _markers, _Slot

    table = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10)))
    slots = [_Slot("id", table.c.id.type), _Slot("v", table.c.v.type)]
    stmt = insert(table).inline().values(dict(zip(["id", "v"], _markers(2), strict=True)))
    template = _LiteralTemplate(stmt, slots, dialect, exact_keys=True)

    overrides = (
        type(dialect.statement_compiler(dialect, None)).render_literal_value is not SQLCompiler.render_literal_value
    )
    assert overrides == (dialect.name in ("postgresql", "mysql", "mariadb"))
    assert all((processor is None) == overrides for processor in template._processors)


_HEX_LITERALS: dict[str, str] = {
    "sqlite": "X'{}'",
    "postgresql": "decode('{}', 'hex')",
    "mysql": "X'{}'",
    "mariadb": "X'{}'",
    "mssql": "0x{}",
    "oracle": "HEXTORAW('{}')",
}


def test_binary_values_use_the_dialect_hex_literal(dialect: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-1 / P-30 (hotfix 2026-09-25): los binarios se escriben con el literal hexadecimal del dialecto, sin compilar
    la fila por el camino anterior. Antes: ``'abc'`` para bytes UTF-8 (TEXT en SQLite, Msg 257 en SQL Server,
    ``0x0ABC`` en Oracle) y ``0x…`` por el camino anterior para los no UTF-8 (inválido en PostgreSQL, Oracle y SQLite).
    """
    import util_bbdd.bulk._support.sql_helpers as helpers

    calls: list[object] = []
    original = helpers.compile_stmt_with_binary_support
    monkeypatch.setattr(
        helpers, "compile_stmt_with_binary_support", lambda *a, **k: calls.append(a) or original(*a, **k)
    )
    table = Table("t", MetaData(), Column("id", Integer, primary_key=True), Column("b", LargeBinary))
    literal = _HEX_LITERALS[dialect.name].format
    values = [b"abc", b"\x00\xff", bytearray(b"a'b"), b"", None]
    records = [{"id": i, "b": v} for i, v in enumerate(values, start=1)]
    expected = [literal("616263"), literal("00FF"), literal("612762"), literal(""), "NULL"]

    inserted = generate_insert_sql(insert(table), records, dialect)
    updated = generate_update_sql(
        table=table,
        records=[{**r, "pk_id": r["id"]} for r in records],
        update_cols=["b"],
        pk_param_map={"id": "pk_id"},
        pk_cols=["id"],
        dialect=dialect,
    )

    assert [line.split("VALUES (", 1)[1].split(", ", 1)[1].removesuffix(");") for line in inserted] == expected
    assert [line.split(" SET ", 1)[1].split(" WHERE ")[0].split("=", 1)[1] for line in updated] == expected
    assert calls == []


def test_binary_primary_key_in_where_uses_hex_literal(dialect: Any) -> None:
    """C-1: también en el WHERE (DELETE/UPDATE por PK binaria), por plantilla y por el camino anterior (PK ``None``)."""
    table = Table("t", MetaData(), Column("k", LargeBinary(16), primary_key=True), Column("v", String(10)))
    literal = _HEX_LITERALS[dialect.name].format

    lines = generate_delete_sql(records=[{"k": b"\x00\xff"}, {"k": None}], table=table, pk_cols=["k"], dialect=dialect)

    assert literal("00FF") in lines[0]
    assert lines == _ref_delete(table, [{"k": b"\x00\xff"}, {"k": None}], dialect, ["k"])
