"""``BulkCrud(on_error="isolate", rejects_csv_path=...)`` (S-2 de bulk, sesión 2026-10-01n).

Cada lote va en un SAVEPOINT; si falla con un error de datos, se reenvía por mitades hasta aislar las filas que fallan,
que se escriben en el CSV de rechazos. El resto se aplica. Otros errores se propagan como sin aislamiento.
"""

from __future__ import annotations

import csv
import json

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, ForeignKey, Integer, MetaData, String, Table, create_engine, event, text
from sqlalchemy.exc import IntegrityError, OperationalError

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._execution.insert_strategies import InsertStrategyResolver, MySQLDriverExecutemanyStrategy
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
    assert list(rows[0]) == ["timestamp", "tabla", "operacion", "fila", "error", "valores"]


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
