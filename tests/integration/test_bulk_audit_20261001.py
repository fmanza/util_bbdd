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
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Table,
    Unicode,
    Uuid,
    event,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

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
