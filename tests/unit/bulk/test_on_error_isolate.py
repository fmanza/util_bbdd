"""``BulkCrud(on_error="isolate", rejects_csv_path=...)`` (S-2 de bulk, sesión 2026-10-01n).

Cada lote va en un SAVEPOINT; si falla con un error de datos, se reenvía por mitades hasta aislar las filas que fallan,
que se escriben en el CSV de rechazos. El resto se aplica. Otros errores se propagan como sin aislamiento.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import threading

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, ForeignKey, Integer, MetaData, String, Table, Text, create_engine, event, text
from sqlalchemy.exc import IntegrityError, OperationalError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.insert_strategies import InsertStrategyResolver, MySQLDriverExecutemanyStrategy
from util_bbdd.bulk._support import oracle_batch_errors
from util_bbdd.bulk._support.rejects import Isolator, RejectsWriter

pytestmark = pytest.mark.unit


def _engine(tmp_path: Path, *, foreign_keys: bool = False) -> Engine:
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    if foreign_keys:

        @event.listens_for(eng, "connect")
        def _fk_on(dbapi_connection: Any, _record: Any) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    metadata = MetaData()
    Table("items", metadata, Column("id", Integer, primary_key=True), Column("v", String(10), nullable=False))
    Table("child", metadata, Column("id", Integer, primary_key=True), Column("item_id", ForeignKey("items.id")))
    metadata.create_all(eng)
    return eng


def _frame(ids: list[int], v: str = "v", none_at: tuple[int, ...] = ()) -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [None if i in none_at else f"{v}{i}" for i in ids]})


def _rows(engine: Engine) -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text("SELECT id, v FROM items ORDER BY id"))]


def _seed(engine: Engine, ids: list[int]) -> None:
    BulkCrud(engine, warn_if_audit_disabled=False).bulk_insert_from_df(_frame(ids), "items", False)


def _rejects(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _crud(engine: Engine, tmp_path: Path, **kwargs: Any) -> BulkCrud:
    kwargs.setdefault("chunk_size", 3)
    return BulkCrud(
        engine,
        on_error="isolate",
        rejects_csv_path=tmp_path / "rejects.csv",
        warn_if_audit_disabled=False,
        **kwargs,
    )


@pytest.mark.parametrize("columns", [False, True], ids=["registros", "columnas"])
def test_insert_applies_good_rows_and_rejects_bad_ones(tmp_path: Path, columns: bool) -> None:
    engine = _engine(tmp_path)
    _seed(engine, [5])  # la fila 4 de la entrada (id 5) choca con la PK
    resolver = InsertStrategyResolver(default_strategy=MySQLDriverExecutemanyStrategy()) if columns else None
    crud = _crud(engine, tmp_path, insert_resolver=resolver)

    crud.bulk_insert_from_df(_frame(list(range(1, 11)), none_at=(1, 10)), "items", False)

    assert [r[0] for r in _rows(engine)] == [2, 3, 4, 5, 6, 7, 8, 9]
    rejects = _rejects(tmp_path / "rejects.csv")
    assert [int(r["fila"]) for r in rejects] == [0, 4, 9]
    assert {r["operacion"] for r in rejects} == {"INSERT"}
    assert all(r["error"].startswith("IntegrityError: ") for r in rejects)
    assert json.loads(rejects[1]["valores"]) == {"id": 5, "v": "v5"}
    assert crud.rows_rejected == 3


def test_update_rejects_rows_and_csv_has_no_pk_aliases(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _seed(engine, list(range(1, 8)))
    crud = _crud(engine, tmp_path)

    crud.bulk_update_from_df(_frame(list(range(1, 8)), "u", none_at=(3, 7)), "items", False)

    assert _rows(engine) == [(1, "u1"), (2, "u2"), (3, "v3"), (4, "u4"), (5, "u5"), (6, "u6"), (7, "v7")]
    rejects = _rejects(tmp_path / "rejects.csv")
    assert [(r["operacion"], int(r["fila"])) for r in rejects] == [("UPDATE", 2), ("UPDATE", 6)]
    assert set(json.loads(rejects[0]["valores"])) == {"id", "v"}


def test_delete_rejects_rows_still_referenced(tmp_path: Path) -> None:
    engine = _engine(tmp_path, foreign_keys=True)
    _seed(engine, list(range(1, 8)))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO child (id, item_id) VALUES (1, 2), (2, 6)"))
    crud = _crud(engine, tmp_path)

    crud.bulk_delete_from_df(pd.DataFrame({"id": list(range(1, 8))}), "items", False)

    assert [r[0] for r in _rows(engine)] == [2, 6]
    rejects = _rejects(tmp_path / "rejects.csv")
    assert [(r["operacion"], int(r["fila"]), json.loads(r["valores"])) for r in rejects] == [
        ("DELETE", 1, {"id": 2}),
        ("DELETE", 5, {"id": 6}),
    ]


def test_from_chunks_positions_are_in_the_sequence(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    crud = _crud(engine, tmp_path, max_rejects=3)

    chunks = [_frame([1, 2, 3, 4], none_at=(2,)), _frame([]), _frame([5, 6, 7, 8, 9], none_at=(8,))]
    assert crud.bulk_insert_from_chunks(iter(chunks), "items") == 9
    crud.bulk_update_from_chunks(iter([_frame([1, 3]), _frame([4, 5], "u", none_at=(5,))]), "items")

    assert _rows(engine) == [(1, "v1"), (3, "v3"), (4, "u4"), (5, "v5"), (6, "v6"), (7, "v7"), (9, "v9")]
    rejects = _rejects(tmp_path / "rejects.csv")
    assert [(r["operacion"], int(r["fila"])) for r in rejects] == [("INSERT", 1), ("INSERT", 7), ("UPDATE", 3)]
    assert crud.rows_rejected == 3


def test_max_rejects_exceeded_fails_the_whole_operation(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    crud = _crud(engine, tmp_path, max_rejects=1)

    with pytest.raises(IntegrityError) as info:
        crud.bulk_insert_from_df(_frame(list(range(1, 8)), none_at=(2, 6)), "items", False)

    assert _rows(engine) == []  # atómica: nada aplicado
    assert any("max_rejects=1" in note for note in info.value.__notes__)
    assert [int(r["fila"]) for r in _rejects(tmp_path / "rejects.csv")] == [1]  # R-6: lo escrito se queda
    assert crud.rows_rejected == 1


def test_max_rejects_zero_behaves_like_raise(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    crud = _crud(engine, tmp_path, max_rejects=0)

    with pytest.raises(IntegrityError):
        crud.bulk_insert_from_df(_frame([1, 2], none_at=(2,)), "items", False)

    assert _rows(engine) == []
    assert not (tmp_path / "rejects.csv").exists()


def test_non_data_errors_propagate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine(tmp_path)
    crud = _crud(engine, tmp_path)
    executor = crud._batch_statement_executor

    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError("INSERT", {}, Exception("no such column"))

    monkeypatch.setattr(executor, "_send", broken)
    with pytest.raises(OperationalError):
        crud.bulk_insert_from_df(_frame([1, 2, 3]), "items", False)

    assert not (tmp_path / "rejects.csv").exists()
    assert executor.isolator is None  # el aislador no sobrevive a la operación


def test_raise_is_unchanged(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    crud = BulkCrud(engine, chunk_size=3, warn_if_audit_disabled=False)

    with pytest.raises(IntegrityError):
        crud.bulk_insert_from_df(_frame([1, 2, 3, 4], none_at=(4,)), "items", False)

    assert _rows(engine) == []
    assert crud.rows_rejected == 0


@pytest.mark.parametrize("none_at", [(), (2,)], ids=["limpio", "con-rechazo"])
def test_isolation_keeps_the_session_atomic(tmp_path: Path, none_at: tuple[int, ...]) -> None:
    """Los SAVEPOINT no confirman nada por su cuenta: si la sesión se deshace, se deshace todo.

    En SQLite (pysqlite), si el SAVEPOINT abría la transacción, su RELEASE la confirmaba y el lote limpio sobrevivía.
    """
    engine = _engine(tmp_path)
    _seed(engine, [10, 11])
    crud = _crud(engine, tmp_path)

    with pytest.raises(RuntimeError), crud.bulk_session():
        crud.bulk_insert_from_df(_frame([1, 2, 3, 4], none_at=none_at), "items", False)
        crud.bulk_delete_from_df(pd.DataFrame({"id": [10]}), "items", False)
        raise RuntimeError("fallo posterior")

    assert _rows(engine) == [(10, "v10"), (11, "v11")]


def test_with_commit_cadence_rejected_rows_count_as_positions(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    crud = _crud(engine, tmp_path, commit_every_n_chunks=1)

    crud.bulk_insert_from_df(_frame(list(range(1, 8)), none_at=(2, 5)), "items", False)

    assert [r[0] for r in _rows(engine)] == [1, 3, 4, 6, 7]
    assert crud.last_operation_rows_committed == 7  # R-4: posiciones de la entrada, para reanudar
    assert crud.rows_rejected == 2


def test_audit_counts_applied_rows(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    audit = tmp_path / "audit.csv"
    crud = _crud(engine, tmp_path, audit_csv_path=audit)

    crud.bulk_insert_from_df(_frame(list(range(1, 6)), none_at=(3,)), "items", False)
    crud.bulk_insert_from_chunks(iter([_frame([6, 7], none_at=(7,)), _frame([8])]), "items")

    assert pd.read_csv(audit, sep="\t")["total_filas"].tolist() == [4, 1, 1]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"on_error": "skip"}, "on_error"),
        ({"on_error": "isolate"}, "rejects_csv_path"),
        ({"rejects_csv_path": Path("r.csv")}, "solo se usan"),
        ({"max_rejects": 3}, "solo se usan"),
        ({"on_error": "isolate", "rejects_csv_path": Path("r.csv"), "max_rejects": -1}, "max_rejects"),
        ({"on_error": "isolate", "rejects_csv_path": Path("r.csv"), "max_rejects": True}, "max_rejects"),
    ],
)
def test_invalid_parameters(tmp_path: Path, kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        BulkCrud(_engine(tmp_path), **kwargs)


def test_rejects_writer_neutralizes_formulas(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "rejects.csv"
    writer = RejectsWriter(path)
    error = IntegrityError("INSERT ...", {"a": 1}, Exception("=cmd|' /C calc'!A0\nsegunda línea"))

    writer.write(table="@tabla", operation="INSERT", position=0, error=error, values={"v": "=1+1"})
    writer.write(table="t", operation="INSERT", position=1, error=error, values={"v": "ñ"})

    rows = _rejects(path)
    assert rows[0]["tabla"] == "'@tabla"
    assert rows[0]["error"] == "IntegrityError: =cmd|' /C calc'!A0"  # empieza por la clase: no es una fórmula
    assert json.loads(rows[1]["valores"]) == {"v": "ñ"}
    assert list(rows[0]) == ["timestamp", "tabla", "operacion", "particion", "fila", "error", "valores"]
    assert rows[0]["particion"] == ""  # fuera de ParallelBulkLoader


def test_isolator_bisects_down_to_single_rows() -> None:
    sent: list[list[int]] = []

    class _Savepoint:
        def commit(self) -> None: ...

        def rollback(self) -> None: ...

    class _Connection:
        def begin_nested(self) -> _Savepoint:
            return _Savepoint()

    def send(items: list[dict[str, int]]) -> None:
        sent.append([item["id"] for item in items])
        if any(item["id"] in (2, 7) for item in items):
            raise IntegrityError("x", {}, Exception("dup"))

    rejected: list[int] = []
    isolator = Isolator(on_reject=lambda position, _values, _error: rejected.append(position))
    isolator.run_records(_Connection(), [{"id": i} for i in range(8)], send, first_row=100)

    assert rejected == [102, 107]
    assert sent[0] == list(range(8))
    assert isolator.rejected == 2


def test_unwritable_rejects_csv_fails_with_its_own_message(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """M-1 (audit-code 2026-10-01): la ruta no escribible (un directorio, como un CSV abierto en Excel en Windows)."""
    engine = _engine(tmp_path)
    (tmp_path / "rejects.csv").mkdir()
    crud = _crud(engine, tmp_path)

    with pytest.raises(OSError) as info:
        crud.bulk_insert_from_df(_frame([1, 2, 3, 4], none_at=(2,)), "items", False)

    assert any(note.startswith("bulk: no se pudo escribir el CSV de rechazos") for note in info.value.__notes__)
    assert "No se pudo escribir el CSV de rechazos" in caplog.text
    assert "auditoría" not in caplog.text
    assert crud.rows_rejected == 0  # la fila no llegó al CSV
    assert _rows(engine) == []


def test_rejected_rows_are_logged_per_row_only_in_debug(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    engine = _engine(tmp_path)
    crud = _crud(engine, tmp_path)

    with caplog.at_level("WARNING", logger="util_bbdd.bulk.crud"):
        crud.bulk_insert_from_df(_frame(list(range(1, 7)), none_at=(2, 5)), "items", False)

    warnings = [r.getMessage() for r in caplog.records if r.name == "util_bbdd.bulk.crud"]
    assert not any("rechazada (" in message for message in warnings)  # el mensaje por fila va en DEBUG
    assert any("2 filas rechazadas" in message for message in warnings)


def test_isolate_with_prefetch_blocks(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    crud = _crud(engine, tmp_path, prefetch_blocks=True)

    crud.bulk_insert_from_df(_frame(list(range(1, 11)), none_at=(4, 9)), "items", False)

    assert [r[0] for r in _rows(engine)] == [1, 2, 3, 5, 6, 7, 8, 10]
    assert [int(r["fila"]) for r in _rejects(tmp_path / "rejects.csv")] == [3, 8]


def test_delete_from_chunks_positions_are_in_the_sequence(tmp_path: Path) -> None:
    engine = _engine(tmp_path, foreign_keys=True)
    _seed(engine, list(range(1, 9)))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO child (id, item_id) VALUES (1, 6)"))
    crud = _crud(engine, tmp_path)

    chunks = [pd.DataFrame({"id": [1, 2, 3]}), pd.DataFrame({"id": [4, 5, 6, 7]})]
    crud.bulk_delete_from_chunks(iter(chunks), "items")

    assert [r[0] for r in _rows(engine)] == [6, 8]
    assert [(r["operacion"], int(r["fila"])) for r in _rejects(tmp_path / "rejects.csv")] == [("DELETE", 5)]


def test_sqlite_cadence_then_session_failure(tmp_path: Path) -> None:
    """Tras un commit periódico, el BEGIN de ``_savepoint`` vuelve a abrir una transacción real: lo no confirmado se deshace."""
    engine = _engine(tmp_path)
    crud = _crud(engine, tmp_path, chunk_size=2, commit_every_n_chunks=2)

    with pytest.raises(RuntimeError), crud.bulk_session():
        crud.bulk_insert_from_df(_frame([1, 2, 3, 4, 5], none_at=(2,)), "items", False)
        raise RuntimeError("fallo posterior")

    assert [r[0] for r in _rows(engine)] == [1, 3, 4]  # los 2 primeros lotes (confirmados); el 5 se deshace


# ------------------------------------------------------------ B-1, B-3 y B-4 (audit-code 2026-10-01, sesión 2026-10-01o)


def test_failed_savepoint_rollback_raises_the_data_error_with_a_note() -> None:
    """B-1: con XACT_ABORT ON el SAVEPOINT ya no existe; llega el error de datos, no el del rollback."""
    rollback_error = RuntimeError(
        "Cannot roll back sa_savepoint_1. No transaction or savepoint of that name was found."
    )

    class _Savepoint:
        def commit(self) -> None: ...

        def rollback(self) -> None:
            raise rollback_error

    class _Connection:
        def begin_nested(self) -> _Savepoint:
            return _Savepoint()

    def send(_items: Any) -> None:
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    isolator = Isolator(on_reject=lambda *_args: None)
    with pytest.raises(IntegrityError) as info:
        isolator.run_records(_Connection(), [{"id": 1}, {"id": 2}], send, first_row=0)

    assert info.value.__cause__ is rollback_error
    assert any("XACT_ABORT ON" in note and "Cannot roll back" in note for note in info.value.__notes__)
    assert isolator.rejected == 0


def _sqlite_items(path: Path, **engine_kwargs: Any) -> Engine:
    eng = create_engine(f"sqlite:///{path}", **engine_kwargs)
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10), nullable=False)).create(
        eng
    )
    return eng


def _other_connection_state(path: Path) -> tuple[int, bool]:
    """Filas que ve otra conexión y si puede escribir (sin una transacción colgada en la del engine)."""
    other = sqlite3.connect(path, timeout=0.5)
    try:
        count = other.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        try:
            other.execute("CREATE TABLE zz_lock_probe (x INTEGER)")
            other.commit()
            return count, True
        except sqlite3.OperationalError:
            return count, False
    finally:
        other.close()


def test_sqlite3_autocommit_true_is_rejected_before_sending(tmp_path: Path) -> None:
    """B-3: con sqlite3 autocommit=True las filas no se confirmaban y la BD quedaba bloqueada."""
    db = tmp_path / "auto.db"
    engine = _sqlite_items(db, connect_args={"autocommit": True})
    crud = _crud(engine, tmp_path)

    with pytest.raises(ValueError, match="autocommit=True"):
        crud.bulk_insert_from_df(_frame([1, 2, 3], none_at=(2,)), "items", False)
    engine.dispose()

    assert _other_connection_state(db) == (0, True)
    assert not (tmp_path / "rejects.csv").exists()


@pytest.mark.parametrize("none_at", [(), (2,)], ids=["limpio", "con-rechazo"])
def test_sqlalchemy_autocommit_still_works(tmp_path: Path, none_at: tuple[int, ...]) -> None:
    db = tmp_path / "sa_auto.db"
    engine = _sqlite_items(db, isolation_level="AUTOCOMMIT")
    crud = _crud(engine, tmp_path)

    crud.bulk_insert_from_df(_frame([1, 2, 3, 4], none_at=none_at), "items", False)

    assert _other_connection_state(db) == (4 - len(none_at), True)
    engine.dispose()


def test_rejects_csv_with_another_header_is_set_aside(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """B-4: no se añaden filas a un fichero con otra cabecera (p. ej. re-guardado en Excel con comas)."""
    path = tmp_path / "rejects.csv"
    path.write_text('"timestamp,tabla,operacion"\n"x,y,z"\n', encoding="utf-8")
    writer = RejectsWriter(path)
    error = IntegrityError("x", {}, Exception("dup"))

    writer.write(table="t", operation="INSERT", position=0, error=error, values={"id": 1})
    writer.write(table="t", operation="INSERT", position=1, error=error, values={"id": 2})

    assert [int(r["fila"]) for r in _rejects(path)] == [0, 1]
    aside = list(tmp_path.glob("rejects.invalid-*.csv"))
    assert len(aside) == 1 and aside[0].read_text(encoding="utf-8").startswith('"timestamp,tabla')
    assert "otra cabecera" in caplog.text


def test_rejects_writers_on_the_same_path_do_not_interleave(tmp_path: Path) -> None:
    """B-4: dos instancias (p. ej. en hilos) sobre la misma ruta: una cabecera y todas las filas completas."""
    path = tmp_path / "rejects.csv"
    error = IntegrityError("x", {}, Exception("dup"))

    def work(writer: RejectsWriter, base: int) -> None:
        for i in range(200):
            writer.write(table="t", operation="INSERT", position=base + i, error=error, values={"v": "x" * 500})

    threads = [threading.Thread(target=work, args=(RejectsWriter(path), base)) for base in (0, 1000, 2000, 3000)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    rows = _rejects(path)
    assert sorted(int(r["fila"]) for r in rows) == [b + i for b in (0, 1000, 2000, 3000) for i in range(200)]
    assert path.read_text(encoding="utf-8").count("timestamp\ttabla") == 1


# ----------------------------------------------------------------- batcherrors de Oracle (S-5, sesión 2026-10-01s)


class _BatchError:
    """Como los errores de ``cursor.getbatcherrors()`` de oracledb: ``offset``, ``full_code`` y el mensaje."""

    def __init__(self, offset: int, code: str = "ORA-00001") -> None:
        self.offset = offset
        self.full_code = code

    def __str__(self) -> str:
        return f"{self.full_code}: unique constraint violated"


class _Savepoints:
    def __init__(self) -> None:
        self.log: list[str] = []

    def begin_nested(self) -> Any:
        log = self.log

        class _Savepoint:
            def commit(self) -> None:
                log.append("commit")

            def rollback(self) -> None:
                log.append("rollback")

        log.append("savepoint")
        return _Savepoint()


def _batch_errors_send(bad: set[int], calls: list[int]) -> Any:
    """``send`` falso: con colector activo devuelve los errores de fila; sin él lanza, como el driver."""

    def send(items: Any) -> None:
        calls.append(len(items))
        sink = oracle_batch_errors._SINK.get()
        if sink is None:
            raise IntegrityError("INSERT", {}, Exception("ORA-00001: unique constraint violated"))
        sink.extend(_BatchError(offset) for offset in sorted(bad, reverse=True))

    return send


def test_batch_errors_rejects_rows_with_one_send() -> None:
    rejected: list[tuple[int, Any, str]] = []
    isolator = Isolator(
        on_reject=lambda position, values, error: rejected.append((position, dict(values), str(error))),
        batch_errors=True,
    )
    calls: list[int] = []
    connection = _Savepoints()

    isolator.run_records(connection, [{"id": i} for i in range(8)], _batch_errors_send({1, 6}, calls), first_row=100)

    assert calls == [8]  # un envío, sin bisección
    assert [(p, v) for p, v, _ in rejected] == [(101, {"id": 1}), (106, {"id": 6})]
    assert rejected[0][2].startswith("ORA-00001")
    assert connection.log == ["savepoint", "commit"]
    assert isolator.rejected == 2


def test_batch_errors_with_frames() -> None:
    rejected: list[tuple[int, Any]] = []
    isolator = Isolator(on_reject=lambda p, v, _e: rejected.append((p, v)), batch_errors=True)

    isolator.run_frame(_Savepoints(), pd.DataFrame({"id": [10, 11, 12]}), _batch_errors_send({2}, []), first_row=0)

    assert rejected == [(2, {"id": 12})]


def test_batch_errors_over_max_rejects_resends_to_raise_the_driver_error() -> None:
    rejected: list[int] = []
    isolator = Isolator(on_reject=lambda p, _v, _e: rejected.append(p), max_rejects=1, batch_errors=True)
    calls: list[int] = []
    connection = _Savepoints()

    with pytest.raises(IntegrityError) as info:
        isolator.run_records(connection, [{"id": i} for i in range(5)], _batch_errors_send({0, 3}, calls), first_row=0)

    assert rejected == [0]  # las que caben en max_rejects se escriben (como con bisección)
    assert calls == [5, 5]  # el reenvío sin batcherrors da el error real del driver
    assert any("max_rejects=1" in note for note in info.value.__notes__)
    assert connection.log == ["savepoint", "rollback", "savepoint", "rollback"]


def test_batch_errors_statement_errors_propagate() -> None:
    connection = _Savepoints()

    def broken(_items: Any) -> None:
        raise OperationalError("INSERT", {}, Exception("ORA-00942: table or view does not exist"))

    with pytest.raises(OperationalError):
        Isolator(on_reject=lambda *_a: None, batch_errors=True).run_records(
            connection, [{"id": 1}], broken, first_row=0
        )

    assert connection.log == ["savepoint", "rollback"]


def test_batch_errors_support_and_install(tmp_path: Path) -> None:
    sqlite_engine = create_engine(f"sqlite:///{tmp_path / 'x.db'}")

    class _Oracle:
        class dialect:  # noqa: N801
            name = "oracle"
            driver = "oracledb"

    assert oracle_batch_errors.supports(_Oracle())
    assert not oracle_batch_errors.supports(sqlite_engine)

    oracle_batch_errors.install(sqlite_engine)
    oracle_batch_errors.install(sqlite_engine)  # idempotente: un solo listener
    with sqlite_engine.begin() as conn:  # sin colector activo, SQLAlchemy ejecuta como siempre
        conn.execute(text("CREATE TABLE t (x INTEGER)"))
        conn.execute(text("INSERT INTO t VALUES (:x)"), [{"x": 1}, {"x": 2}])
        assert conn.execute(text("SELECT COUNT(*) FROM t")).scalar() == 2
    listeners = sqlite_engine.dialect.dispatch.do_executemany
    assert len(list(listeners)) == 1


@pytest.mark.parametrize(
    ("column", "expected"),
    [("v", True), ("doc", False), ("v4000", True), ("v5000", False)],
    ids=["sin-lob", "con-lob", "string-4000", "string-5000"],
)
def test_update_uses_batch_errors_only_without_lob_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, column: str, expected: bool
) -> None:
    """S-5: con un bind LOB grande y una fila mala, batcherrors da ORA-03106 en el UPDATE: entonces, bisección."""
    engine = create_engine(f"sqlite:///{tmp_path / 'lob.db'}")
    Table(
        "items",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("v", String(10)),
        Column("doc", Text),
        Column("v4000", String(4000)),
        Column("v5000", String(5000)),  # B-2: VARCHAR2 > 4000 (MAX_STRING_SIZE=EXTENDED) como LOB
    ).create(engine)
    _seed_lob = pd.DataFrame({"id": [1, 2], "v": ["a", "b"], "doc": ["x", "y"]})
    BulkCrud(engine, warn_if_audit_disabled=False).bulk_insert_from_df(_seed_lob, "items", False)
    monkeypatch.setattr(oracle_batch_errors, "supports", lambda _engine: True)
    monkeypatch.setattr(oracle_batch_errors, "install", lambda _engine: None)
    seen: list[bool] = []
    original = Isolator.run_records

    def spy(self: Isolator, *args: Any, **kwargs: Any) -> None:
        seen.append(self.batch_errors)
        self.batch_errors = False  # SQLite no tiene batcherrors: se ejecuta por bisección
        original(self, *args, **kwargs)

    monkeypatch.setattr(Isolator, "run_records", spy)
    crud = _crud(engine, tmp_path)

    crud.bulk_update_from_df(pd.DataFrame({"id": [1, 2], column: ["c", "d"]}), "items", False)

    assert seen == [expected]
