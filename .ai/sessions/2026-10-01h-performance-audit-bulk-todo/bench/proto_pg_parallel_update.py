"""E7b: UPDATE paralelo en PostgreSQL. ¿Convoy del GIL? switchinterval 5 ms vs 0,2 ms, executemany vs staging."""

from __future__ import annotations

import sys
import threading
import time

from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import proto_bulk_todo as p  # noqa: E402

import util_bbdd.bulk.crud as crud_mod  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402

ROWS, WORKERS = 1_000_000, 4


def run(variant: str, switch: float) -> None:
    engine = p.engine_for("postgresql")
    df = p.bb.make_dataframe(ROWS, "postgresql")
    df_upd = df.copy()
    df_upd["a"] = df_upd["a"] + 1
    table = p.fresh(engine)
    BulkCrud(engine, warn_if_audit_disabled=False).bulk_insert_from_df(df, table.name, generar_sql=False)
    bounds = [round(i * ROWS / WORKERS) for i in range(WORKERS + 1)]
    original = crud_mod.MySQLStagingUpdateStrategy

    def work(part):  # noqa: ANN001
        crud = BulkCrud(engine, chunk_size=5000, warn_if_audit_disabled=False)
        crud.reflect_table(table.name)
        if variant == "staging":
            p._update_with_strategy(crud, lambda t, pk, upd: p._SqlStaging(t, pk, upd, mssql=False))
        crud.bulk_update_from_df(part, table.name, generar_sql=False)

    old = sys.getswitchinterval()
    sys.setswitchinterval(switch)
    try:
        threads = [threading.Thread(target=work, args=(df_upd.iloc[bounds[i] : bounds[i + 1]],)) for i in range(WORKERS)]
        t0 = time.perf_counter()
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        t = time.perf_counter() - t0
    finally:
        sys.setswitchinterval(old)
        crud_mod.MySQLStagingUpdateStrategy = original  # type: ignore[misc]
    p.record("pg_parallel_update", "postgresql", f"{variant}_w{WORKERS}_switch{switch * 1000:g}ms", ROWS, t,
             p.sum_a(engine, table) == int(df["a"].sum()) + ROWS)
    p.bb.drop_table(engine, table)
    engine.dispose()


if __name__ == "__main__":
    for v, s in (("executemany", 0.005), ("executemany", 0.0002), ("staging", 0.005)):
        run(v, s)
