"""Integración de las mejoras del performance-audit de bulk 2026-10-01 (sesión 2026-10-01h).

- B-02: DELETE de SQL Server con OPENJSON, por tipo de PK, dentro y fuera de ``bulk_session`` y con cadencia.
- B-03: INSERT por columnas (COPY, ``execute_values``, ``executemany`` de PyMySQL) con los mismos valores que antes.
- B-01: UPDATE de PostgreSQL por tabla temporal con el mismo estado final que el UPDATE fila a fila.
- B-15a: nota con el lote fallido en un error real del servidor.

Mismas URLs que ``test_bulk_engines.py`` (``UTIL_BBDD_TEST_<MOTOR>_URL``); sin ellas, los servidores se saltan.
"""

from __future__ import annotations

import decimal
import uuid

from collections.abc import Iterator
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import (
    BigInteger,
    Column,
    Engine,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    Unicode,
    Uuid,
    event,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DatabaseError, DataError, IntegrityError

from util_bbdd.bulk import BulkCrud

from .test_bulk_engines import _engine_params, _name, engine  # noqa: F401  (fixture reutilizada)

pytestmark = [pytest.mark.integration, pytest.mark.cross_db]


def _table_name() -> str:
    return f"zz_util_bbdd_it_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def statements(engine: Engine) -> Iterator[list[str]]:  # noqa: F811
    """Sentencias enviadas al driver durante el test."""
    seen: list[str] = []

    def _capture(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _capture)


# --------------------------------------------------------------------------------------------------------- B-02

_MSSQL_PK_CASES: list[Any] = [
    pytest.param(Integer, [1, 2, 3, 4, 5, 6], id="int"),
    pytest.param(BigInteger, [2**40 + i for i in range(6)], id="bigint"),
    pytest.param(String(30), ["a", "o'brien", "ñandú", "x y", "%z", "tail "], id="varchar"),
    pytest.param(Unicode(30), ["α", "β'", "漢字", "d", "e", "f"], id="nvarchar"),
    pytest.param(Uuid, [uuid.UUID(int=i) for i in range(1, 7)], id="uniqueidentifier"),
    pytest.param(Numeric(12, 2), [decimal.Decimal(f"{i}.25") for i in range(6)], id="decimal"),
]


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
@pytest.mark.parametrize(("pk_type", "keys"), _MSSQL_PK_CASES)
@pytest.mark.parametrize("mode", ["plain", "session", "cadence"])
def test_mssql_delete_openjson_by_pk_type(
    engine: Engine,  # noqa: F811
    statements: list[str],
    pk_type: Any,
    keys: list[Any],
    mode: str,
) -> None:
    table = Table(
        _table_name(), MetaData(), Column("k", pk_type, primary_key=True, autoincrement=False), Column("v", Integer)
    )
    table.create(engine)
    try:
        BulkCrud(engine).bulk_insert_from_df(pd.DataFrame({"k": keys, "v": range(len(keys))}), table.name, False)
        doomed = pd.DataFrame({"k": keys[::2]})
        crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=1 if mode == "cadence" else None)
        statements.clear()
        if mode == "plain":
            crud.bulk_delete_from_df(doomed, table.name, False)
        else:
            with crud.bulk_session():
                crud.bulk_delete_from_df(doomed, table.name, False)

        with engine.connect() as conn:
            remaining = sorted(r[0] for r in conn.execute(select(table.c.k)))
        # El INSERT recorta los espacios de los extremos (strip_strings=True por defecto).
        assert remaining == sorted(k.strip() if isinstance(k, str) else k for k in keys[1::2])
        assert any("OPENJSON" in s for s in statements)
    finally:
        table.drop(engine, checkfirst=True)


_MSSQL_COMPOSITE_CASES: list[Any] = [
    pytest.param(Integer, String(20), [(1, "a"), (1, "o'b"), (2, "a"), (2, "ñ"), (3, "x"), (3, "%")], id="int-varchar"),
    pytest.param(Integer, Uuid, [(i % 2, uuid.UUID(int=i)) for i in range(6)], id="int-uniqueidentifier"),
    pytest.param(
        Numeric(8, 2), BigInteger, [(decimal.Decimal(f"{i}.50"), 2**40 + i) for i in range(6)], id="decimal-bigint"
    ),
]


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
@pytest.mark.parametrize(("type_a", "type_b", "keys"), _MSSQL_COMPOSITE_CASES)
def test_mssql_delete_openjson_composite_pk(
    engine: Engine,  # noqa: F811
    statements: list[str],
    type_a: Any,
    type_b: Any,
    keys: list[tuple[Any, Any]],
) -> None:
    table = Table(
        _table_name(),
        MetaData(),
        Column("a", type_a, primary_key=True, autoincrement=False),
        Column("b", type_b, primary_key=True, autoincrement=False),
    )
    table.create(engine)
    try:
        frame = pd.DataFrame(keys, columns=["a", "b"])
        BulkCrud(engine).bulk_insert_from_df(frame, table.name, False)
        statements.clear()
        BulkCrud(engine, chunk_size=2).bulk_delete_from_df(frame.iloc[::2], table.name, False)

        with engine.connect() as conn:
            remaining = sorted(tuple(r) for r in conn.execute(select(table.c.a, table.c.b)))
        assert remaining == sorted(keys[1::2])
        assert any("OPENJSON" in s for s in statements)
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
def test_mssql_delete_rolls_back_with_session(engine: Engine) -> None:  # noqa: F811
    table = Table(_table_name(), MetaData(), Column("k", Integer, primary_key=True, autoincrement=False))
    table.create(engine)
    try:
        crud = BulkCrud(engine, chunk_size=2)
        crud.bulk_insert_from_df(pd.DataFrame({"k": range(10)}), table.name, False)
        with pytest.raises(RuntimeError), crud.bulk_session():
            crud.bulk_delete_from_df(pd.DataFrame({"k": range(10)}), table.name, False)
            raise RuntimeError("rollback")
        with engine.connect() as conn:
            assert len(conn.execute(select(table.c.k)).all()) == 10
    finally:
        table.drop(engine, checkfirst=True)


# --------------------------------------------------------------------------------------------------------- B-01


def _pg_update_state(db: Engine, statements: list[str], *, staging: bool, cadence: int | None) -> list[tuple[Any, ...]]:
    enum_name = f"zz_mood_{uuid.uuid4().hex[:8]}"
    mood = postgresql.ENUM("ok", "ko", name=enum_name, create_type=False)
    table = Table(
        _table_name(),
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("m", mood),
        Column("j", postgresql.JSONB),
        Column("b", LargeBinary),
        Column("s", String(20)),
        schema="public",
    )
    with db.begin() as conn:
        conn.execute(text(f"CREATE TYPE {enum_name} AS ENUM ('ok', 'ko')"))
    table.create(db)
    try:
        seed = pd.DataFrame({"id": [1, 2, 3, 4], "m": ["ok"] * 4, "j": [{"x": 0}] * 4, "b": [b"0"] * 4, "s": ["s"] * 4})
        BulkCrud(db).bulk_insert_from_df(seed, f"public.{table.name}", False)
        update = pd.DataFrame(
            {
                "id": [1, 2, 2, 99, 3],  # 2 repetido (gana el último), 99 no existe
                "m": ["ko", "ko", "ok", "ko", None],
                "j": [{"k": [1, 2]}, None, {"k": "last"}, {}, {"q": "it's"}],
                "b": [b"\xff", None, b"q", b"z", b""],
                "s": [" x ", "%s", "fin", "no", None],
            }
        )
        crud = BulkCrud(db, chunk_size=2, update_via_staging=staging, commit_every_n_chunks=cadence)
        statements.clear()
        crud.bulk_update_from_df(update, f"public.{table.name}", False)
        used_staging = any("CREATE TEMPORARY TABLE" in s and "WITH NO DATA" in s for s in statements)
        assert used_staging is staging
        with db.connect() as conn:
            return [
                (r.id, r.m, r.j, bytes(r.b) if r.b is not None else None, r.s)
                for r in conn.execute(select(table).order_by(table.c.id))
            ]
    finally:
        table.drop(db, checkfirst=True)
        with db.begin() as conn:
            conn.execute(text(f"DROP TYPE IF EXISTS {enum_name}"))


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"postgresql"})), indirect=True)
@pytest.mark.parametrize("cadence", [None, 1])
def test_postgresql_staging_update_matches_row_update(
    engine: Engine,  # noqa: F811
    statements: list[str],
    cadence: int | None,
) -> None:
    via_rows = _pg_update_state(engine, statements, staging=False, cadence=cadence)
    via_staging = _pg_update_state(engine, statements, staging=True, cadence=cadence)

    assert via_staging == via_rows
    assert via_staging[1] == (2, "ok", {"k": "last"}, b"q", "fin")


# --------------------------------------------------------------------------------------------------------- B-03


def test_insert_values_roundtrip_with_columns_path(engine: Engine) -> None:  # noqa: F811
    """Mismos valores con la vía por columnas (PG, MySQL, MariaDB) que con la de registros (resto)."""
    n = lambda logical: _name(logical, engine)  # noqa: E731
    table = Table(
        n(_table_name()),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("s"), String(20)),
        Column(n("amount"), Numeric(12, 2)),
        Column(n("blob"), LargeBinary),
    )
    table.create(engine)
    try:
        df = pd.DataFrame(
            {
                n("id"): [1, 2, 3, 4, 5],
                n("s"): [" a ", None, "o'b", "%x", "ñ"],
                n("amount"): [decimal.Decimal("1.10"), None, decimal.Decimal("-3.00"), decimal.Decimal("0"), None],
                n("blob"): [b"q", b"\xff\x00", None, b"", b"z"],
            }
        )
        BulkCrud(engine, chunk_size=2).bulk_insert_from_df(df, table.name, False)
        with engine.connect() as conn:
            rows = [tuple(r) for r in conn.execute(select(table).order_by(table.c[n("id")]))]
        blobs = [bytes(r[3]) if r[3] is not None else None for r in rows]
        # Oracle guarda b"" como NULL (cadena vacía = NULL); el resto lo conserva.
        empty = None if engine.dialect.name == "oracle" else b""
        assert [r[1] for r in rows] == ["a", None, "o'b", "%x", "ñ"]
        assert [r[2] for r in rows] == [
            decimal.Decimal("1.10"),
            None,
            decimal.Decimal("-3.00"),
            decimal.Decimal("0"),
            None,
        ]
        assert blobs == [b"q", b"\xff\x00", None, empty, b"z"]
    finally:
        table.drop(engine, checkfirst=True)


# --------------------------------------------------------------------------------------------------------- B-15a


def test_error_note_points_to_failing_batch(engine: Engine) -> None:  # noqa: F811
    n = lambda logical: _name(logical, engine)  # noqa: E731
    table = Table(n(_table_name()), MetaData(), Column(n("id"), Integer, primary_key=True, autoincrement=False))
    table.create(engine)
    try:
        crud = BulkCrud(engine, chunk_size=3)
        crud.bulk_insert_from_df(pd.DataFrame({n("id"): [7]}), table.name, False)
        with pytest.raises(IntegrityError) as info:
            crud.bulk_insert_from_df(pd.DataFrame({n("id"): list(range(1, 10))}), table.name, False)
        notes = getattr(info.value, "__notes__", [])
        assert any("falló el lote 2 (filas 6–8 de la entrada, base 0)" in note for note in notes)
    finally:
        table.drop(engine, checkfirst=True)


# --------------------------------------------------------------------------------------------- Fase 2: B-08, B-11, B-05


def _seed_table(db: Engine, rows: int) -> Table:
    n = lambda logical: _name(logical, db)  # noqa: E731
    table = Table(
        n(_table_name()),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("v"), String(20)),
    )
    table.create(db)
    BulkCrud(db).bulk_insert_from_df(
        pd.DataFrame({n("id"): range(1, rows + 1), n("v"): ["v"] * rows}), table.name, False
    )
    return table


def _state(db: Engine, table: Table) -> list[tuple[Any, ...]]:
    with db.connect() as conn:
        return [tuple(r) for r in conn.execute(select(table).order_by(table.c[_name("id", db)]))]


def test_from_chunks_match_from_df(engine: Engine) -> None:  # noqa: F811
    n = lambda logical: _name(logical, engine)  # noqa: E731
    update = pd.DataFrame({n("id"): [1, 3, 3, 9, 40], n("v"): ["a", "b", "c", "d", "e"]})
    doomed = pd.DataFrame({n("id"): [2, 4, 6, 8]})
    streamed, direct = _seed_table(engine, 12), _seed_table(engine, 12)
    try:
        crud = BulkCrud(engine, chunk_size=2, commit_every_n_chunks=1)
        crud.bulk_update_from_chunks(iter([update.iloc[:2], update.iloc[2:4], update.iloc[4:]]), streamed.name)
        crud.bulk_delete_from_chunks(iter([doomed.iloc[:1], doomed.iloc[1:]]), streamed.name)
        other = BulkCrud(engine, chunk_size=2)
        other.bulk_update_from_df(update, direct.name, False)
        other.bulk_delete_from_df(doomed, direct.name, False)
        assert _state(engine, streamed) == _state(engine, direct)
    finally:
        streamed.drop(engine, checkfirst=True)
        direct.drop(engine, checkfirst=True)


def test_parallel_retry_resumes_without_duplicates(engine: Engine) -> None:  # noqa: F811
    from sqlalchemy.exc import OperationalError

    from util_bbdd.bulk import ParallelBulkLoader

    n = lambda logical: _name(logical, engine)  # noqa: E731
    table = Table(n(_table_name()), MetaData(), Column(n("id"), Integer, primary_key=True, autoincrement=False))
    table.create(engine)
    try:
        frames = [pd.DataFrame({n("id"): range(start, start + 100)}) for start in range(1, 1001, 100)]
        calls = {"n": 0}

        def reader() -> Iterator[pd.DataFrame]:
            calls["n"] += 1
            for index, frame in enumerate(frames):
                if calls["n"] == 1 and index == 6:
                    raise OperationalError("INSERT", {}, Exception("conexión perdida"), connection_invalidated=True)
                yield frame

        loader = ParallelBulkLoader(
            engine, chunk_size=100, max_workers=1, commit_every_n_chunks=2, max_retries=1, retry_backoff=(0, 0)
        )
        result = loader.load(table.name, [reader])

        assert result.partition_errors == []
        assert result.total_rows == 1000
        with engine.connect() as conn:
            ids = [r[0] for r in conn.execute(select(table.c[n("id")]).order_by(table.c[n("id")]))]
        assert ids == list(range(1, 1001))
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(exclude=frozenset({"sqlite"})), indirect=True)
def test_parallel_update_and_delete(engine: Engine) -> None:  # noqa: F811
    from util_bbdd.bulk import ParallelBulkLoader

    n = lambda logical: _name(logical, engine)  # noqa: E731
    table = _seed_table(engine, 400)
    try:
        loader = ParallelBulkLoader(engine, chunk_size=50, max_workers=2)
        parts = [pd.DataFrame({n("id"): range(lo, lo + 200), n("v"): ["u"] * 200}) for lo in (1, 201)]
        updated = loader.update(
            table.name, [lambda p=p: iter([p]) for p in parts], partition_ranges=[(1, 200), (201, 400)]
        )
        assert (updated.total_rows, updated.partition_errors) == (400, [])
        assert {r[1] for r in _state(engine, table)} == {"u"}

        doomed = [pd.DataFrame({n("id"): range(lo, lo + 100)}) for lo in (1, 301)]
        deleted = loader.delete(table.name, [lambda d=d: iter([d]) for d in doomed])
        assert (deleted.total_rows, deleted.partition_errors) == (200, [])
        assert [r[0] for r in _state(engine, table)] == list(range(101, 301))
    finally:
        table.drop(engine, checkfirst=True)


# ------------------------------------------------------------------- hotfix A1/A2 (audit-code 2026-10-01)

_A1_CASES: list[Any] = [
    pytest.param(String(5), ["abcde", "zz"], ["abcdeXYZ"], id="varchar-truncado"),
    pytest.param(
        Numeric(8, 2),
        [decimal.Decimal("1.11"), decimal.Decimal("2.00")],
        [decimal.Decimal("1.105")],
        id="numeric-redondeo",
    ),
    pytest.param(String(5), ["?", "a"], ["α"], id="varchar-code-page"),
    pytest.param(Integer, [1, 2], [2**40], id="int-fuera-de-rango"),
]


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
@pytest.mark.parametrize(("pk_type", "rows", "doomed"), _A1_CASES)
def test_mssql_delete_never_deletes_keys_that_do_not_fit_the_pk(
    engine: Engine,  # noqa: F811
    pk_type: Any,
    rows: list[Any],
    doomed: list[Any],
) -> None:
    """A1: OPENJSON convertía la clave al tipo de la PK (trunca/redondea/best fit) y borraba otras filas."""
    table = Table(_table_name(), MetaData(), Column("k", pk_type, primary_key=True, autoincrement=False))
    table.create(engine)
    try:
        BulkCrud(engine, strip_strings=False).bulk_insert_from_df(
            pd.DataFrame({"k": rows}, dtype=object), table.name, False
        )
        BulkCrud(engine).bulk_delete_from_df(pd.DataFrame({"k": doomed}, dtype=object), table.name, False)
        with engine.connect() as conn:
            remaining = sorted(str(r[0]) for r in conn.execute(select(table.c.k)))
        assert remaining == sorted(str(r) for r in rows)
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
def test_mssql_composite_delete_never_deletes_keys_that_do_not_fit(engine: Engine) -> None:  # noqa: F811
    table = Table(
        _table_name(),
        MetaData(),
        Column("a", Integer, primary_key=True, autoincrement=False),
        Column("b", String(5), primary_key=True),
    )
    table.create(engine)
    try:
        BulkCrud(engine).bulk_insert_from_df(pd.DataFrame({"a": [1, 1], "b": ["abcde", "zz"]}), table.name, False)
        BulkCrud(engine).bulk_delete_from_df(pd.DataFrame({"a": [1], "b": ["abcdeXYZ"]}), table.name, False)
        with engine.connect() as conn:
            assert sorted(tuple(r) for r in conn.execute(select(table.c.a, table.c.b))) == [(1, "abcde"), (1, "zz")]
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mariadb"})), indirect=True)
def test_mariadb_connector_lock_wait_timeout_is_retriable(engine: Engine) -> None:  # noqa: F811
    """A2: con el conector ``mariadb`` el lock wait timeout (1205, sqlstate HY000) no se reintentaba."""
    pytest.importorskip("mariadb")
    from sqlalchemy import create_engine
    from sqlalchemy.exc import DBAPIError

    from util_bbdd.bulk._support.retry import is_retriable

    url = engine.url.set(drivername="mariadb+mariadbconnector")
    connector = create_engine(url)
    table = Table(_table_name(), MetaData(), Column("id", Integer, primary_key=True, autoincrement=False))
    table.create(connector)
    first, second = connector.connect(), connector.connect()
    try:
        with connector.begin() as conn:
            conn.execute(table.insert(), [{"id": 1}])
        for conn in (first, second):
            conn.exec_driver_sql("SET SESSION innodb_lock_wait_timeout = 1")
        first.execute(table.update().values(id=1))
        with pytest.raises(DBAPIError) as info:
            second.execute(table.update().values(id=1))
        assert info.value.orig.errno == 1205
        assert is_retriable(info.value) is True
    finally:
        second.rollback()
        first.rollback()
        first.close()
        second.close()
        table.drop(connector, checkfirst=True)
        connector.dispose()


# ------------------------------------------------------------------- prefetch_blocks (S-4, sesión 2026-10-01m)


def test_prefetch_blocks_gives_the_same_result(engine: Engine) -> None:  # noqa: F811
    n = lambda logical: _name(logical, engine)  # noqa: E731
    states = []
    for prefetch in (False, True):
        table = _seed_table(engine, 0)
        try:
            crud = BulkCrud(engine, chunk_size=7, prefetch_blocks=prefetch)
            crud.bulk_insert_from_df(pd.DataFrame({n("id"): range(1, 51), n("v"): ["v"] * 50}), table.name, False)
            crud.bulk_update_from_df(pd.DataFrame({n("id"): range(1, 51, 3), n("v"): ["u"] * 17}), table.name, False)
            crud.bulk_insert_from_chunks(iter([pd.DataFrame({n("id"): range(51, 70), n("v"): ["c"] * 19})]), table.name)
            states.append(_state(engine, table))
        finally:
            table.drop(engine, checkfirst=True)
    assert states[0] == states[1]
    assert len(states[0]) == 69


# --------------------------------------------------------------------------------- S-2: BulkCrud(on_error="isolate")


def _isolate_table(db: Engine) -> Table:
    n = lambda logical: _name(logical, db)  # noqa: E731
    table = Table(
        n(_table_name()),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("v"), String(5)),
    )
    table.create(db)
    BulkCrud(db).bulk_insert_from_df(pd.DataFrame({n("id"): range(1, 21), n("v"): ["v"] * 20}), table.name, False)
    return table


def _rejected_rows(path: Any) -> list[tuple[str, int]]:
    frame = pd.read_csv(path, sep="\t")
    return list(zip(frame["operacion"], frame["fila"], strict=True))


@pytest.mark.parametrize("cadence", [None, 2])
def test_isolate_insert_rejects_duplicate_keys(engine: Engine, cadence: int | None, tmp_path: Any) -> None:  # noqa: F811
    n = lambda logical: _name(logical, engine)  # noqa: E731
    table = _isolate_table(engine)
    try:
        crud = BulkCrud(
            engine,
            chunk_size=4,
            commit_every_n_chunks=cadence,
            on_error="isolate",
            rejects_csv_path=tmp_path / "rejects.csv",
        )
        crud.bulk_insert_from_df(pd.DataFrame({n("id"): range(15, 31), n("v"): ["i"] * 16}), table.name, False)

        state = _state(engine, table)
        assert [row[0] for row in state] == list(range(1, 31))
        assert [row[1] for row in state] == ["v"] * 20 + ["i"] * 10
        assert _rejected_rows(tmp_path / "rejects.csv") == [("INSERT", i) for i in range(6)]
        assert crud.rows_rejected == 6
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize(
    "engine", _engine_params(only=frozenset({"postgresql", "mysql", "mariadb", "oracle"})), indirect=True
)
@pytest.mark.parametrize("staging", [True, False])
def test_isolate_update_rejects_values_too_long(engine: Engine, staging: bool, tmp_path: Any) -> None:  # noqa: F811
    """Valor demasiado largo en el UPDATE por staging y fila a fila (``DataError``); en Oracle, con batcherrors (S-5)."""
    n = lambda logical: _name(logical, engine)  # noqa: E731
    table = _isolate_table(engine)
    try:
        crud = BulkCrud(
            engine, chunk_size=4, update_via_staging=staging, on_error="isolate", rejects_csv_path=tmp_path / "r.csv"
        )
        values = ["u" if i not in (3, 11) else "demasiado" for i in range(1, 13)]
        crud.bulk_update_from_df(pd.DataFrame({n("id"): range(1, 13), n("v"): values}), table.name, False)

        state = dict(_state(engine, table))
        assert [state[i] for i in range(1, 14)] == ["u", "u", "v"] + ["u"] * 7 + ["v", "u", "v"]
        assert _rejected_rows(tmp_path / "r.csv") == [("UPDATE", 2), ("UPDATE", 10)]
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
def test_isolate_value_too_long_is_not_isolated(engine: Engine, tmp_path: Any) -> None:  # noqa: F811
    """R-1: el valor demasiado largo no llega como ``DataError`` y la operación falla entera, como sin aislamiento.

    pyodbc con ``fast_executemany``: ``ProgrammingError`` en el cliente (``String data, right truncation``); pymssql:
    2628 como ``OperationalError``. Oracle lo aísla con batcherrors desde la sesión 2026-10-01s.
    """
    n = lambda logical: _name(logical, engine)  # noqa: E731
    table = _isolate_table(engine)
    try:
        crud = BulkCrud(engine, chunk_size=4, on_error="isolate", rejects_csv_path=tmp_path / "r.csv")
        with pytest.raises(DatabaseError) as info:
            crud.bulk_update_from_df(pd.DataFrame({n("id"): [1, 2], n("v"): ["u", "demasiado"]}), table.name, False)
        assert not isinstance(info.value, IntegrityError | DataError)
        assert [row[1] for row in _state(engine, table)][:2] == ["v", "v"]
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(exclude=frozenset({"sqlite"})), indirect=True)
def test_isolate_delete_rejects_rows_still_referenced(engine: Engine, tmp_path: Any) -> None:  # noqa: F811
    n = lambda logical: _name(logical, engine)  # noqa: E731
    parent = _isolate_table(engine)
    child = Table(
        n(_table_name()),
        MetaData(),
        Column(n("id"), Integer, primary_key=True, autoincrement=False),
        Column(n("parent_id"), Integer, ForeignKey(parent.c[n("id")])),
    )
    child.create(engine)
    try:
        with engine.begin() as conn:
            conn.execute(child.insert(), [{n("id"): 1, n("parent_id"): 4}, {n("id"): 2, n("parent_id"): 9}])
        crud = BulkCrud(engine, chunk_size=4, on_error="isolate", rejects_csv_path=tmp_path / "r.csv")
        with crud.bulk_session():
            crud.bulk_delete_from_df(pd.DataFrame({n("id"): range(1, 11)}), parent.name, False)

        assert [row[0] for row in _state(engine, parent)] == [4, 9, *range(11, 21)]
        assert _rejected_rows(tmp_path / "r.csv") == [("DELETE", 3), ("DELETE", 8)]
    finally:
        child.drop(engine, checkfirst=True)
        parent.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"mssql"})), indirect=True)
def test_isolate_mssql_xact_abort_raises_the_data_error(engine: Engine, tmp_path: Any) -> None:  # noqa: F811
    """B-1: con XACT_ABORT ON el servidor deshace la transacción con el primer error; llega el error de datos con nota."""

    @event.listens_for(engine, "connect")
    def _xact_abort(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET XACT_ABORT ON")
        cursor.close()

    engine.dispose()  # conexiones nuevas, con el evento
    n = lambda logical: _name(logical, engine)  # noqa: E731
    table = _isolate_table(engine)
    try:
        crud = BulkCrud(engine, chunk_size=4, on_error="isolate", rejects_csv_path=tmp_path / "r.csv")
        with pytest.raises(IntegrityError) as info:
            crud.bulk_insert_from_df(pd.DataFrame({n("id"): range(19, 25), n("v"): ["i"] * 6}), table.name, False)

        assert any("XACT_ABORT ON" in note for note in info.value.__notes__)
        assert info.value.__cause__ is not None
        assert [row[0] for row in _state(engine, table)] == list(range(1, 21))  # nada aplicado
        assert crud.rows_rejected == 0
    finally:
        event.remove(engine, "connect", _xact_abort)
        engine.dispose()
        table.drop(engine, checkfirst=True)


# ------------------------------------------------------------------- S-5: batcherrors de Oracle (sesión 2026-10-01s)


def _oracle_errors_table(db: Engine) -> Table:
    table = Table(
        _table_name(),
        MetaData(),
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("s", String(5)),
        Column("n", Numeric(5, 2)),
        Column("req", String(5), nullable=False),
        Column("doc", Text),
    )
    table.create(db)
    return table


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"oracle"})), indirect=True)
def test_oracle_batch_errors_isolate_errors_the_bisection_could_not(engine: Engine, tmp_path: Any) -> None:  # noqa: F811
    """ORA-00001, ORA-12899, ORA-01438 y ORA-01400 se aíslan en un envío por lote (antes, solo la PK duplicada)."""
    table = _oracle_errors_table(engine)
    try:
        rows = [{"id": i, "s": "ok", "n": decimal.Decimal("1.25"), "req": "r", "doc": "x" * 9000} for i in range(12)]
        rows[2] = {**rows[2], "id": 1}  # ORA-00001
        rows[5] = {**rows[5], "s": "demasiado"}  # ORA-12899
        rows[7] = {**rows[7], "n": decimal.Decimal("1234.5")}  # ORA-01438
        rows[10] = {**rows[10], "req": None}  # ORA-01400
        crud = BulkCrud(engine, chunk_size=6, on_error="isolate", rejects_csv_path=tmp_path / "r.csv")
        with crud.bulk_session():
            crud.bulk_insert_from_df(pd.DataFrame(rows), table.name, False)

        assert [row[0] for row in _state(engine, table)] == [0, 1, 3, 4, 6, 8, 9, 11]
        frame = pd.read_csv(tmp_path / "r.csv", sep="	")
        assert frame["fila"].tolist() == [2, 5, 7, 10]
        assert [error.split(":")[1].strip() for error in frame["error"]] == [
            "ORA-00001",
            "ORA-12899",
            "ORA-01438",
            "ORA-01400",
        ]
        assert crud.rows_rejected == 4
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"oracle"})), indirect=True)
def test_oracle_update_with_lob_columns_uses_the_bisection(engine: Engine, tmp_path: Any) -> None:  # noqa: F811
    """Con columnas LOB en el UPDATE no se usa batcherrors (ORA-03106 del driver, S-5): el demasiado largo no se aísla."""
    table = _oracle_errors_table(engine)
    try:
        seed = pd.DataFrame({"id": [1, 2, 3], "s": ["a"] * 3, "n": [1] * 3, "req": ["r"] * 3, "doc": ["d"] * 3})
        BulkCrud(engine).bulk_insert_from_df(seed, table.name, False)
        crud = BulkCrud(engine, chunk_size=4, on_error="isolate", rejects_csv_path=tmp_path / "r.csv")
        update = pd.DataFrame({"id": [1, 2, 3], "s": ["b", "demasiado", "b"], "doc": ["x" * 9000] * 3})
        with pytest.raises(DatabaseError) as info:
            crud.bulk_update_from_df(update, table.name, False)
        assert "ORA-12899" in str(info.value)
        assert [row[1] for row in _state(engine, table)] == ["a", "a", "a"]  # nada aplicado

        crud.bulk_update_from_df(update.assign(s=["b", "b", "b"]).iloc[[0, 2]], table.name, False)
        dup = pd.DataFrame({"id": [1, 1, 3], "s": ["c"] * 3})
        crud.bulk_update_from_df(dup, table.name, False)  # sin LOB: batcherrors (sin errores aquí)
        assert [row[1] for row in _state(engine, table)] == ["c", "a", "c"]
    finally:
        table.drop(engine, checkfirst=True)


@pytest.mark.parametrize("engine", _engine_params(only=frozenset({"oracle"})), indirect=True)
def test_oracle_batch_errors_over_max_rejects(engine: Engine, tmp_path: Any) -> None:  # noqa: F811
    table = _oracle_errors_table(engine)
    try:
        rows = pd.DataFrame({"id": range(6), "s": ["ok", "demasiado", "ok", "demasiado", "ok", "ok"], "req": ["r"] * 6})
        crud = BulkCrud(engine, chunk_size=10, on_error="isolate", rejects_csv_path=tmp_path / "r.csv", max_rejects=1)
        with pytest.raises(DatabaseError) as info:
            crud.bulk_insert_from_df(rows, table.name, False)
        assert "ORA-12899" in str(info.value)
        assert any("max_rejects=1" in note for note in info.value.__notes__)
        assert _state(engine, table) == []
        assert pd.read_csv(tmp_path / "r.csv", sep="	")["fila"].tolist() == [1]
    finally:
        table.drop(engine, checkfirst=True)
