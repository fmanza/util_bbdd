"""Prototipos A/B del performance-audit de bulk (2026-10-01h). Solo lectura sobre ``src/``: nada de aquí se importa
desde la librería; los cambios se simulan con subclases, parches de instancia o SQL propio.

Uso (con las URLs del banco cargadas, ver .ai/runtime.md):

    python proto_bulk_todo.py <experimento> [--engines ...] [--rows N] [--out DIR]

Experimentos:
    prep        E1/E2  CPU de preparación: registros dict vs columnas→tuplas (sin BD)
    share       E1     fracción de la preparación en el INSERT real por motor
    pipeline    E3     prefetch de bloques preparados en un hilo (cola acotada) vs secuencial
    pgupdate    E4     UPDATE PostgreSQL por staging (COPY + UPDATE FROM) vs executemany
    msupdate    E4b    UPDATE SQL Server por staging (#temp + fast_executemany + UPDATE FROM) vs executemany
    msdelete    E5     DELETE SQL Server: IN de 2000 parámetros vs OPENJSON (1 parámetro)
    parallel    E7     ParallelBulkLoader INSERT con 1/2/4/8 workers + UPDATE paralelo por rangos
    cadence     E8     coste de commit_every_n_chunks, coste del rollback y reanudación por rows_committed
    audit       E9     auditoría CSV activa vs desactivada
    oracleupd   E4c    UPDATE Oracle por tabla temporal privada + MERGE vs executemany
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import threading
import time
import uuid

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pandas as pd
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import bench_bulk as bb  # noqa: E402

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader  # noqa: E402
from util_bbdd.bulk._execution.insert_strategies import DefaultInsertStrategy, PostgresCopyStrategy  # noqa: E402

from util_bbdd.bulk.normalize import dataframe_to_sql_columns, dataframe_to_sql_records  # noqa: E402
from util_bbdd.dump._source_reader import _prefetch  # noqa: E402

RESULTS: list[dict[str, Any]] = []


def record(exp: str, engine: str, variant: str, rows: int, seconds: float, ok: bool = True, **extra: Any) -> None:
    row = {"exp": exp, "engine": engine, "variant": variant, "rows": rows, "seconds": round(seconds, 3),
           "rows_s": round(rows / seconds) if seconds > 0 else None, "ok": ok, **extra}
    RESULTS.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)


def engine_for(key: str, pool_size: int = 10) -> sa.Engine:
    if key == "sqlite":
        path = Path(os.environ.get("TEMP", ".")) / f"proto_bulk_{uuid.uuid4().hex[:6]}.db"
        return sa.create_engine(f"sqlite:///{path}")
    url = bb.resolve_engine_url(key)
    if url is None:
        raise SystemExit(f"sin URL para {key}")
    return sa.create_engine(url, pool_size=pool_size, max_overflow=0)


def fresh(engine: sa.Engine) -> sa.Table:
    table = bb.build_table(engine.dialect.name)
    bb.reset_table(engine, table)
    return table


def timed(fn: Callable[[], Any]) -> tuple[float, Any]:
    t0 = time.perf_counter()
    out = fn()
    return time.perf_counter() - t0, out


def count(engine: sa.Engine, table: sa.Table) -> int:
    with engine.connect() as c:
        return int(c.execute(sa.select(sa.func.count()).select_from(table)).scalar_one())


def sum_a(engine: sa.Engine, table: sa.Table) -> int:
    return bb._sum_a(engine, table)


# ---------------------------------------------------------------------------- E1/E2 CPU de preparación


def exp_prep(args: argparse.Namespace) -> None:
    df = bb.make_dataframe(args.rows, "postgresql")
    cols = list(df.columns)
    chunk = 5000

    def via_records() -> int:
        n = 0
        for s in range(0, len(df), chunk):
            recs = dataframe_to_sql_records(df.iloc[s : s + chunk])
            n += len([tuple(r[c] for c in cols) for r in recs])  # lo que hacen COPY / PyMySQL / execute_values
        return n

    def records_only() -> int:
        n = 0
        for s in range(0, len(df), chunk):
            n += len(dataframe_to_sql_records(df.iloc[s : s + chunk]))
        return n

    def via_columns() -> int:
        n = 0
        for s in range(0, len(df), chunk):
            _keys, columns = dataframe_to_sql_columns(df.iloc[s : s + chunk])
            n += len(list(zip(*columns, strict=True)))
        return n

    for name, fn in (("records_dict(+tuplas)", via_records), ("records_dict", records_only), ("columnas→tuplas", via_columns)):
        times = [timed(fn)[0] for _ in range(3)]
        record("prep", "cpu", name, args.rows, statistics.median(times))


# ---------------------------------------------------------------------------- E1 fracción de preparación


def exp_share(args: argparse.Namespace) -> None:
    for key in args.engines:
        engine = engine_for(key)
        df = bb.make_dataframe(args.rows, engine.dialect.name)
        prep = statistics.median(
            timed(lambda: [dataframe_to_sql_records(df.iloc[s : s + 5000]) for s in range(0, len(df), 5000)])[0]
            for _ in range(3)
        )
        table = fresh(engine)
        crud = BulkCrud(engine, chunk_size=5000, warn_if_audit_disabled=False)
        crud.reflect_table(table.name)
        total, _ = timed(lambda: crud.bulk_insert_from_df(df, table.name, generar_sql=False))
        record("share", key, "insert_total", args.rows, total, count(engine, table) == args.rows,
               prep_s=round(prep, 3), prep_pct=round(100 * prep / total, 1))
        bb.drop_table(engine, table)
        engine.dispose()


# ---------------------------------------------------------------------------- E3 pipeline (prefetch de bloques)


def _with_prefetch(crud: BulkCrud, depth: int) -> None:
    original = crud._BulkCrud__record_blocks  # type: ignore[attr-defined]

    def blocks(df: pd.DataFrame, tabla: sa.Table) -> Iterator[list[dict[str, Any]]]:
        return _prefetch(original(df, tabla), depth=depth)

    crud._BulkCrud__record_blocks = blocks  # type: ignore[attr-defined]


def exp_pipeline(args: argparse.Namespace) -> None:
    for key in args.engines:
        engine = engine_for(key)
        df = bb.make_dataframe(args.rows, engine.dialect.name)
        df_upd = df.copy()
        col_a = bb.physical_column("a", engine.dialect.name)
        df_upd[col_a] = df_upd[col_a] + 1
        for variant in ("secuencial", "prefetch2"):
            for rep in range(args.repeat):
                table = fresh(engine)
                crud = BulkCrud(engine, chunk_size=5000, warn_if_audit_disabled=False)
                crud.reflect_table(table.name)
                if variant == "prefetch2":
                    _with_prefetch(crud, 2)
                t_ins, _ = timed(lambda: crud.bulk_insert_from_df(df, table.name, generar_sql=False))
                ok_i = count(engine, table) == args.rows
                t_upd, _ = timed(lambda: crud.bulk_update_from_df(df_upd, table.name, generar_sql=False))
                ok_u = sum_a(engine, table) == int(df[col_a].sum()) + args.rows
                record("pipeline", key, f"{variant}/insert", args.rows, t_ins, ok_i, rep=rep)
                record("pipeline", key, f"{variant}/update", args.rows, t_upd, ok_u, rep=rep)
        bb.drop_table(engine, bb.build_table(engine.dialect.name))
        engine.dispose()


# ---------------------------------------------------------------------------- E4 UPDATE por staging (PG / MSSQL)


class _SqlStaging:
    """Tabla temporal + carga con la estrategia INSERT del motor + UPDATE t SET ... FROM tmp (SQLAlchemy).

    PostgreSQL: ``CREATE TEMPORARY TABLE`` + COPY. SQL Server: ``#temp`` + executemany con fast_executemany.
    """

    def __init__(self, table: sa.Table, pk_cols: list[str], update_cols: list[str], *, mssql: bool) -> None:
        self.table, self.pk_cols, self.update_cols, self.mssql = table, pk_cols, update_cols, mssql
        self.loader = DefaultInsertStrategy() if mssql else PostgresCopyStrategy()

    def execute(self, *, connection: Any, stmt: Any, records: Any) -> None:
        cols = [*self.pk_cols, *self.update_cols]
        rows = {tuple(r[c] for c in self.pk_cols): {c: r[c] for c in cols} for r in records}
        name = f"{'#' if self.mssql else ''}tmp_bulkupd_{uuid.uuid4().hex[:10]}"
        tmp = sa.Table(name, sa.MetaData(), *(sa.Column(c, self.table.c[c].type) for c in cols),
                       prefixes=[] if self.mssql else ["TEMPORARY"])
        tmp.create(connection)
        try:
            self.loader.execute(connection=connection, stmt=sa.insert(tmp), records=list(rows.values()))
            connection.execute(
                sa.update(self.table)
                .values({self.table.c[c]: tmp.c[c] for c in self.update_cols})
                .where(sa.and_(*(self.table.c[c] == tmp.c[c] for c in self.pk_cols)))
            )
        finally:
            connection.exec_driver_sql(f"DROP TABLE {connection.dialect.identifier_preparer.format_table(tmp)}")


def _update_with_strategy(crud: BulkCrud, factory: Callable[[sa.Table, list[str], list[str]], Any]) -> None:
    """Fuerza ``crud`` a usar una estrategia de staging en el UPDATE (como hace con MySQL)."""
    crud._update_via_staging = True  # type: ignore[attr-defined]
    import util_bbdd.bulk.crud as crud_mod

    class _Factory:
        def __init__(self, *, table: sa.Table, pk_cols: list[str], update_cols: list[str], loader: Any) -> None:
            self._inner = factory(table, list(pk_cols), list(update_cols))
            self.staging_denied = False

        def execute(self, **kw: Any) -> None:
            self._inner.execute(**kw)

    crud_mod.MySQLStagingUpdateStrategy = _Factory  # type: ignore[misc]


def _exp_update_staging(args: argparse.Namespace, key: str, factory: Callable[..., Any]) -> None:
    import util_bbdd.bulk.crud as crud_mod

    original = crud_mod.MySQLStagingUpdateStrategy
    engine = engine_for(key)
    df = bb.make_dataframe(args.rows, engine.dialect.name)
    col_a = bb.physical_column("a", engine.dialect.name)
    df_upd = df.copy()
    df_upd[col_a] = df_upd[col_a] + 1
    expected = int(df[col_a].sum()) + args.rows
    try:
        for variant in ("executemany", "staging"):
            for rep in range(args.repeat):
                table = fresh(engine)
                loader = BulkCrud(engine, chunk_size=5000, warn_if_audit_disabled=False)
                loader.bulk_insert_from_df(df, table.name, generar_sql=False)
                crud = BulkCrud(engine, chunk_size=args.chunk, warn_if_audit_disabled=False)
                crud.reflect_table(table.name)
                crud_mod.MySQLStagingUpdateStrategy = original  # type: ignore[misc]
                if variant == "staging":
                    _update_with_strategy(crud, factory)
                t, _ = timed(lambda: crud.bulk_update_from_df(df_upd, table.name, generar_sql=False))
                record("update_staging", key, variant, args.rows, t, sum_a(engine, table) == expected,
                       rep=rep, chunk=args.chunk)
    finally:
        crud_mod.MySQLStagingUpdateStrategy = original  # type: ignore[misc]
        bb.drop_table(engine, bb.build_table(engine.dialect.name))
        engine.dispose()


def exp_pgupdate(args: argparse.Namespace) -> None:
    _exp_update_staging(args, "postgresql", lambda t, pk, upd: _SqlStaging(t, pk, upd, mssql=False))


def exp_msupdate(args: argparse.Namespace) -> None:
    _exp_update_staging(args, "mssql", lambda t, pk, upd: _SqlStaging(t, pk, upd, mssql=True))


class _OracleStaging:
    """Tabla temporal privada (ORA$PTT_, 18c+) + executemany + MERGE. Se comprueba que el CREATE no confirma."""

    def __init__(self, table: sa.Table, pk_cols: list[str], update_cols: list[str]) -> None:
        self.table, self.pk_cols, self.update_cols = table, pk_cols, update_cols

    def execute(self, *, connection: Any, stmt: Any, records: Any) -> None:
        cols = [*self.pk_cols, *self.update_cols]
        prep = connection.dialect.identifier_preparer
        name = f"ORA$PTT_U{uuid.uuid4().hex[:10].upper()}"
        coldefs = ", ".join(f"{prep.quote(c)} {self.table.c[c].type.compile(dialect=connection.dialect)}" for c in cols)
        connection.exec_driver_sql(f"CREATE PRIVATE TEMPORARY TABLE {name} ({coldefs}) ON COMMIT PRESERVE DEFINITION")
        try:
            rows = {tuple(r[c] for c in self.pk_cols): tuple(r[c] for c in cols) for r in records}
            binds = ", ".join(f":{i + 1}" for i in range(len(cols)))
            connection.exec_driver_sql(f"INSERT INTO {name} ({', '.join(prep.quote(c) for c in cols)}) VALUES ({binds})",
                                       list(rows.values()))
            on = " AND ".join(f"t.{prep.quote(c)} = s.{prep.quote(c)}" for c in self.pk_cols)
            sets = ", ".join(f"t.{prep.quote(c)} = s.{prep.quote(c)}" for c in self.update_cols)
            connection.exec_driver_sql(
                f"MERGE INTO {prep.format_table(self.table)} t USING {name} s ON ({on}) WHEN MATCHED THEN UPDATE SET {sets}"
            )
        finally:
            connection.exec_driver_sql(f"DROP TABLE {name}")


def exp_oracleupd(args: argparse.Namespace) -> None:
    # ¿CREATE PRIVATE TEMPORARY TABLE confirma la transacción en curso?
    engine = engine_for("oracle")
    table = fresh(engine)
    with engine.connect() as c:
        c.execute(sa.insert(table), [{bb.physical_column("id", "oracle"): 1}])
        c.exec_driver_sql("CREATE PRIVATE TEMPORARY TABLE ORA$PTT_PROBE (x NUMBER) ON COMMIT PRESERVE DEFINITION")
        c.exec_driver_sql("DROP TABLE ORA$PTT_PROBE")
        c.rollback()
    record("oracle_ptt_probe", "oracle", "filas_tras_rollback", 1, 0.0, True, persisted=count(engine, table))
    engine.dispose()
    _exp_update_staging(args, "oracle", lambda t, pk, upd: _OracleStaging(t, pk, upd))


# ---------------------------------------------------------------------------- E5 DELETE SQL Server


def exp_msdelete(args: argparse.Namespace) -> None:
    engine = engine_for("mssql")
    BulkCrud(engine, warn_if_audit_disabled=False)  # activa fast_executemany como la librería
    for rows in args.sizes:
        df = bb.make_dataframe(rows, "mssql")
        for variant in ("in_2000", "openjson"):
            for rep in range(args.repeat):
                table = fresh(engine)
                crud = BulkCrud(engine, chunk_size=5000, warn_if_audit_disabled=False)
                crud.bulk_insert_from_df(df, table.name, generar_sql=False)
                if variant == "in_2000":
                    t, _ = timed(lambda: crud.bulk_delete_from_df(df[["id"]], table.name, generar_sql=False))
                else:
                    quoted = engine.dialect.identifier_preparer.format_table(table)

                    def run() -> None:
                        with engine.begin() as c:
                            for s in range(0, rows, 5000):
                                ids = json.dumps(df["id"].iloc[s : s + 5000].tolist())
                                c.exec_driver_sql(
                                    f"DELETE FROM {quoted} WHERE id IN (SELECT CAST(value AS INT) FROM OPENJSON(?))",
                                    (ids,),
                                )

                    t, _ = timed(run)
                record("mssql_delete", "mssql", variant, rows, t, count(engine, table) == 0, rep=rep)
    bb.drop_table(engine, bb.build_table("mssql"))
    engine.dispose()


# ---------------------------------------------------------------------------- E7 paralelismo


def exp_parallel(args: argparse.Namespace) -> None:
    for key in args.engines:
        engine = engine_for(key, pool_size=10)
        dialect = engine.dialect.name
        df = bb.make_dataframe(args.rows, dialect)
        col_a = bb.physical_column("a", dialect)
        for workers in args.workers:
            table = fresh(engine)
            bounds = [round(i * len(df) / workers) for i in range(workers + 1)]
            parts = [df.iloc[bounds[i] : bounds[i + 1]] for i in range(workers)]
            readers = [(lambda p=p: (p.iloc[s : s + 5000] for s in range(0, len(p), 5000))) for p in parts]
            loader = ParallelBulkLoader(engine, chunk_size=5000, max_workers=workers)
            t, res = timed(lambda: loader.load(table.name, readers))
            record("parallel", key, f"insert_w{workers}", args.rows, t,
                   count(engine, table) == args.rows and not res.partition_errors, errors=len(res.partition_errors))
            # UPDATE paralelo por rangos disjuntos (no existe en la API: una BulkCrud por hilo)
            df_upd = df.copy()
            df_upd[col_a] = df_upd[col_a] + 1
            upd_parts = [df_upd.iloc[bounds[i] : bounds[i + 1]] for i in range(workers)]
            errors: list[str] = []

            def upd(part: pd.DataFrame) -> None:
                try:
                    BulkCrud(engine, chunk_size=5000, warn_if_audit_disabled=False).bulk_update_from_df(
                        part, table.name, generar_sql=False)
                except Exception as exc:  # noqa: BLE001
                    errors.append(str(exc)[:120])

            def run_upd() -> None:
                threads = [threading.Thread(target=upd, args=(p,)) for p in upd_parts]
                for th in threads:
                    th.start()
                for th in threads:
                    th.join()

            t, _ = timed(run_upd)
            record("parallel", key, f"update_w{workers}", args.rows, t,
                   not errors and sum_a(engine, table) == int(df[col_a].sum()) + args.rows, errors=len(errors),
                   first_error=errors[0] if errors else "")
        bb.drop_table(engine, bb.build_table(dialect))
        engine.dispose()


# ---------------------------------------------------------------------------- E8 cadencia, rollback y reanudación


class _Boom(Exception):
    pass


def exp_cadence(args: argparse.Namespace) -> None:
    for key in args.engines:
        engine = engine_for(key)
        df = bb.make_dataframe(args.rows, engine.dialect.name)
        # (a) coste de la cadencia
        for every in (None, 20, 5):
            table = fresh(engine)
            crud = BulkCrud(engine, chunk_size=5000, commit_every_n_chunks=every, warn_if_audit_disabled=False)
            crud.reflect_table(table.name)
            t, _ = timed(lambda: crud.bulk_insert_from_df(df, table.name, generar_sql=False))
            record("cadence", key, f"insert_every_{every}", args.rows, t, count(engine, table) == args.rows)
        # (b) coste del fallo atómico al final: INSERT completo + rollback
        table = fresh(engine)
        crud = BulkCrud(engine, chunk_size=5000, warn_if_audit_disabled=False)
        crud.reflect_table(table.name)
        t0 = time.perf_counter()
        t_rb = 0.0
        try:
            with crud.bulk_session():
                crud.bulk_insert_from_df(df, table.name, generar_sql=False)
                t_rb = time.perf_counter()
                raise _Boom
        except _Boom:
            pass
        t_end = time.perf_counter()
        record("rollback", key, "insert_then_rollback", args.rows, t_end - t0, count(engine, table) == 0,
               rollback_s=round(t_end - t_rb, 3))
        # (c) fallo al 60 % con cadencia y reanudación desde rows_committed (checkpoint implícito)
        table = fresh(engine)
        crud = BulkCrud(engine, chunk_size=5000, commit_every_n_chunks=20, warn_if_audit_disabled=False)
        crud.reflect_table(table.name)
        cut = int(args.rows * 0.6)
        bad = df.copy()
        sentinel = bb.physical_column("id", engine.dialect.name)
        bad.loc[cut, sentinel] = bad.loc[0, sentinel]  # PK duplicada → IntegrityError al 60 %
        t1, _ = timed(lambda: _swallow(lambda: crud.bulk_insert_from_df(bad, table.name, generar_sql=False)))
        done = crud.rows_committed
        t2, _ = timed(lambda: crud.bulk_insert_from_df(df.iloc[done:], table.name, generar_sql=False))
        record("resume", key, "fail60_resume", args.rows, t1 + t2, count(engine, table) == args.rows,
               committed_before_fail=done, first_attempt_s=round(t1, 3), resume_s=round(t2, 3))
        bb.drop_table(engine, bb.build_table(engine.dialect.name))
        engine.dispose()


def _swallow(fn: Callable[[], Any]) -> None:
    try:
        fn()
    except sa.exc.SQLAlchemyError:
        pass


# ---------------------------------------------------------------------------- E9 auditoría


def exp_audit(args: argparse.Namespace) -> None:
    out = Path(args.out)
    for key in args.engines:
        engine = engine_for(key)
        df = bb.make_dataframe(args.rows, engine.dialect.name)
        for variant in ("sin_auditoria", "con_auditoria", "sin_auditoria", "con_auditoria"):
            table = fresh(engine)
            path = out / f"audit_{key}.csv" if variant == "con_auditoria" else None
            crud = BulkCrud(engine, chunk_size=5000, audit_csv_path=path, warn_if_audit_disabled=False)
            crud.reflect_table(table.name)
            t, _ = timed(lambda: crud.bulk_insert_from_df(df, table.name, generar_sql=False))
            record("audit", key, variant, args.rows, t, count(engine, table) == args.rows)
        bb.drop_table(engine, bb.build_table(engine.dialect.name))
        engine.dispose()


EXPERIMENTS: dict[str, Callable[[argparse.Namespace], None]] = {
    "prep": exp_prep, "share": exp_share, "pipeline": exp_pipeline, "pgupdate": exp_pgupdate,
    "msupdate": exp_msupdate, "msdelete": exp_msdelete, "parallel": exp_parallel, "cadence": exp_cadence,
    "audit": exp_audit, "oracleupd": exp_oracleupd,
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("exp", choices=sorted(EXPERIMENTS))
    p.add_argument("--engines", default="sqlite,postgresql,mysql,mariadb,mssql,oracle")
    p.add_argument("--rows", type=int, default=1_000_000)
    p.add_argument("--sizes", default="1000,10000,100000,1000000")
    p.add_argument("--workers", default="1,2,4,8")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--chunk", type=int, default=5000)
    p.add_argument("--out", default=str(Path(__file__).resolve().parent / "results"))
    args = p.parse_args()
    args.engines = args.engines.split(",")
    args.sizes = [int(x) for x in args.sizes.split(",")]
    args.workers = [int(x) for x in args.workers.split(",")]
    Path(args.out).mkdir(parents=True, exist_ok=True)
    EXPERIMENTS[args.exp](args)
    path = Path(args.out) / f"{args.exp}.csv"
    with path.open("a", newline="", encoding="utf-8") as fh:
        keys = sorted({k for r in RESULTS for k in r})
        w = csv.DictWriter(fh, fieldnames=keys)
        if fh.tell() == 0:
            w.writeheader()
        w.writerows(RESULTS)


if __name__ == "__main__":
    main()
