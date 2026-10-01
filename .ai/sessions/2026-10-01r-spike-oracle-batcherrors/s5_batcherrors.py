"""S-5: ``batcherrors`` de oracledb para ``on_error="isolate"`` en Oracle (spike, sin cambios en ``src/``).

El prototipo no salta SQLAlchemy: se engancha al evento ``do_executemany`` del engine y, solo mientras hay un colector
activo, llama a ``cursor.executemany(statement, parameters, batcherrors=True)``. SQLAlchemy ya ha aplicado sus
procesadores de bind y ``setinputsizes`` (R-5 del plan). Las filas con error de fila no se aplican; el resto sí.

Uso:
  python s5_batcherrors.py types        # equivalencia por tipo + errores de fila (INSERT, UPDATE, DELETE)
  python s5_batcherrors.py bench [filas] [repeticiones]
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime as dt
import decimal
import json
import statistics
import sys
import tempfile
import time

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402
from util_bbdd.bulk._execution.executors import BatchStatementExecutor  # noqa: E402

_SINK: contextvars.ContextVar[list[Any] | None] = contextvars.ContextVar("s5_sink", default=None)


def install(engine: sa.Engine) -> None:
    @sa.event.listens_for(engine, "do_executemany")
    def _batcherrors(cursor: Any, statement: str, parameters: Any, context: Any) -> bool | None:
        sink = _SINK.get()
        if sink is None:
            return None
        cursor.executemany(statement, parameters, batcherrors=True)
        sink.extend(cursor.getbatcherrors())
        return True


@contextlib.contextmanager
def collect() -> Iterator[list[Any]]:
    sink: list[Any] = []
    token = _SINK.set(sink)
    try:
        yield sink
    finally:
        _SINK.reset(token)


# ----------------------------------------------------------------------------------------------- tipos y errores


def _typed_tables(md: sa.MetaData, suffix: str) -> tuple[sa.Table, sa.Table]:
    parent = sa.Table(
        f"zz_s5_par_{suffix}",
        md,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("n", sa.Numeric(18, 4)),
        sa.Column("s", sa.String(10)),
        sa.Column("u", sa.Unicode(10)),
        sa.Column("d", sa.Date),
        sa.Column("ts", sa.DateTime),
        sa.Column("c", sa.Text),
        sa.Column("b", sa.LargeBinary),
        sa.Column("req", sa.String(5), nullable=False),
        sa.Column("ref", sa.Integer, sa.ForeignKey(f"zz_s5_ref_{suffix}.id")),
    )
    ref = sa.Table(f"zz_s5_ref_{suffix}", md, sa.Column("id", sa.Integer, primary_key=True, autoincrement=False))
    return parent, ref


def _rows(n: int) -> list[dict[str, Any]]:
    out = []
    for i in range(n):
        out.append(
            {
                "id": i,
                "n": None if i % 7 == 0 else decimal.Decimal(f"{i * 1234567}.{i % 10000:04d}") * (-1) ** i,
                "s": None if i % 5 == 0 else f"s{i}"[:10],
                "u": "ñandú€" if i % 3 == 0 else f"ü{i}"[:10],
                "d": dt.date(2000, 1, 1) + dt.timedelta(days=i),
                "ts": dt.datetime(2020, 2, 29, 23, 59, 59, 123456) + dt.timedelta(seconds=i),
                "c": ("é" * 50_000) if i % 11 == 0 else (None if i % 4 == 0 else f"clob {i}"),
                "b": bytes(range(256)) * (40 if i % 13 == 0 else 1) if i % 6 else None,
                "req": "ok",
                "ref": 1 if i % 2 else None,
            }
        )
    return out


def _select(conn: sa.Connection, t: sa.Table) -> list[tuple[Any, ...]]:
    return [tuple(r) for r in conn.execute(sa.select(t).order_by(t.c.id))]


def types() -> None:
    engine = p.engine_for("oracle")
    install(engine)
    md = sa.MetaData()
    a, ref_a = _typed_tables(md, "a")
    b, ref_b = _typed_tables(md, "b")
    md.drop_all(engine)
    md.create_all(engine)
    report: dict[str, Any] = {}
    try:
        with engine.begin() as conn:
            conn.execute(ref_a.insert(), [{"id": 1}])
            conn.execute(ref_b.insert(), [{"id": 1}])
        good = _rows(60)
        bad = {
            7: {**good[3], "id": 3},  # PK duplicada (ORA-00001)
            19: {**good[19], "s": "demasiado largo"},  # ORA-12899
            33: {**good[33], "req": None},  # ORA-01400
            41: {**good[41], "ref": 999},  # FK (ORA-02291)
            58: {**good[58], "n": decimal.Decimal("123456789012345.1")},  # precisión (ORA-01438)
        }
        mixed = [bad.get(i, row) for i, row in enumerate(good)]
        expected_rows = [row for i, row in enumerate(good) if i not in bad]
        # Referencia: SQLAlchemy normal solo con las filas buenas.
        with engine.begin() as conn:
            conn.execute(a.insert(), expected_rows)
        # Prototipo: todas las filas con batcherrors, en una transacción.
        with engine.begin() as conn, collect() as errors:
            conn.execute(b.insert(), mixed)
        with engine.connect() as conn:
            same = _select(conn, a) == [(*r[:-1], r[-1]) for r in _select(conn, b)]
        report["insert"] = {
            "datos_iguales": same,
            "errores": sorted((e.offset, e.full_code) for e in errors),
            "esperados": sorted(bad),
        }
        # UPDATE con executemany (como BulkCrud en Oracle): 2 filas con valor demasiado largo.
        stmt = (
            sa.update(b)
            .where(b.c.id == sa.bindparam("pk_id"))
            .values(s=sa.bindparam("s"), c=sa.bindparam("c"))
        )
        upd = [{"pk_id": r["id"], "s": "u", "c": "x" * 3000} for r in expected_rows[:20]]  # 9000: ORA-03106 (s5_ora03106.log)
        upd[4]["s"] = "demasiado largo"
        upd[12]["s"] = "también demasiado"
        with engine.begin() as conn, collect() as errors:
            conn.execute(stmt, upd)
        with engine.connect() as conn:
            vals = {r.id: (r.s, len(r.c or "")) for r in conn.execute(sa.select(b.c.id, b.c.s, b.c.c))}
        report["update"] = {
            "errores": sorted((e.offset, e.full_code) for e in errors),
            "aplicadas_ok": all(vals[u["pk_id"]] == ("u", 3000) for i, u in enumerate(upd) if i not in (4, 12)),
            "rechazadas_intactas": all(vals[upd[i]["pk_id"]][0] != "u" for i in (4, 12)),
        }
        # DELETE: la fila referenciada por ref_b (id 1) no se puede borrar (ORA-02292).
        dstmt = sa.delete(ref_b).where(ref_b.c.id == sa.bindparam("pk"))
        with engine.begin() as conn:
            conn.execute(ref_b.insert(), [{"id": i} for i in range(2, 6)])
        with engine.begin() as conn, collect() as errors:
            conn.execute(dstmt, [{"pk": i} for i in range(1, 6)])
        with engine.connect() as conn:
            left = [r[0] for r in conn.execute(sa.select(ref_b.c.id).order_by(ref_b.c.id))]
        report["delete"] = {"errores": sorted((e.offset, e.full_code) for e in errors), "quedan": left}
        # Rollback de la transacción: lo aplicado con batcherrors se deshace (no hay commit implícito).
        with contextlib.suppress(RuntimeError), engine.begin() as conn, collect():
            conn.execute(b.insert(), [{**good[0], "id": 1000}])
            raise RuntimeError
        with engine.connect() as conn:
            report["rollback_ok"] = conn.execute(sa.select(sa.func.count()).where(b.c.id == 1000)).scalar() == 0
        # Error de sentencia (no de fila): se lanza como siempre.
        try:
            with engine.begin() as conn, collect():
                conn.execute(sa.text("INSERT INTO zz_no_existe (x) VALUES (:x)"), [{"x": 1}, {"x": 2}])
            report["error_sentencia"] = "no lanzó"
        except sa.exc.DatabaseError as exc:
            report["error_sentencia"] = type(exc).__name__ + ": " + str(exc.orig).splitlines()[0][:60]
    finally:
        md.drop_all(engine)
        engine.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=1, default=str))


# -------------------------------------------------------------------------------------------------------- banco


def bench(rows: int, repeat: int) -> None:
    engine = p.engine_for("oracle")
    install(engine)
    dialect = engine.dialect.name
    df = p.bb.make_dataframe(rows, dialect)
    bad_positions = [rows * (i + 1) // 11 for i in range(10)]
    original_send = BatchStatementExecutor._send
    rejected: list[Any] = []

    def send_with_batcherrors(self: Any, connection: Any, batch: Any, stmt: Any, strategy: Any) -> None:
        with collect() as errors:
            original_send(self, connection, batch, stmt, strategy)
        rejected.extend(errors)

    times: dict[str, list[float]] = {}
    for _ in range(repeat):
        for variant in ("raise", "bisect_10", "batcherrors", "batcherrors_10"):
            table = p.fresh(engine)
            with tempfile.TemporaryDirectory() as tmp:
                if variant.endswith("_10"):
                    BulkCrud(engine, warn_if_audit_disabled=False).bulk_insert_from_df(
                        df.iloc[bad_positions], table.name, generar_sql=False
                    )
                kwargs: dict[str, Any] = (
                    {"on_error": "isolate", "rejects_csv_path": Path(tmp) / "r.csv"} if variant == "bisect_10" else {}
                )
                crud = BulkCrud(engine, warn_if_audit_disabled=False, **kwargs)
                crud.reflect_table(table.name)
                rejected.clear()
                patch = variant.startswith("batcherrors")
                if patch:
                    BatchStatementExecutor._send = send_with_batcherrors  # type: ignore[method-assign]
                try:
                    t0 = time.perf_counter()
                    crud.bulk_insert_from_df(df, table.name, generar_sql=False)
                    times.setdefault(variant, []).append(time.perf_counter() - t0)
                finally:
                    BatchStatementExecutor._send = original_send  # type: ignore[method-assign]
                assert p.count(engine, table) == rows, variant
                expected = 10 if variant.endswith("_10") else 0
                got = len(rejected) if patch else crud.rows_rejected
                assert got == expected, (variant, got)
                if patch and expected:
                    assert sorted(e.offset for e in rejected) is not None
    base = statistics.median(times["raise"])
    print(
        json.dumps(
            {
                "rows": rows,
                **{v: [round(x, 2) for x in t] for v, t in times.items()},
                **{f"{v}_x": round(statistics.median(t) / base, 3) for v, t in times.items()},
            }
        ),
        flush=True,
    )
    p.bb.drop_table(engine, p.bb.build_table(dialect))
    engine.dispose()


if __name__ == "__main__":
    if sys.argv[1] == "types":
        types()
    else:
        bench(int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000, int(sys.argv[3]) if len(sys.argv) > 3 else 2)
