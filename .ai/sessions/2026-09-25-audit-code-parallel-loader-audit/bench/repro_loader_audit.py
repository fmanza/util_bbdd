"""Reproductores de los hallazgos de la auditoría de ``ParallelBulkLoader`` (FASE 3).

Ejecutar desde la raíz del repo:  PYTHONPATH=src PYTHONIOENCODING=utf-8 python <este fichero>
"""

from __future__ import annotations

import logging
import tempfile

from pathlib import Path

import pandas as pd
import sqlalchemy as sa

from sqlalchemy.exc import OperationalError

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader

TMP = Path(tempfile.mkdtemp(prefix="repro_loader_audit_"))


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _engine(name: str) -> sa.Engine:
    engine = sa.create_engine(f"sqlite:///{TMP / name}.sqlite")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE t (id INTEGER PRIMARY KEY, a INTEGER)"))
    return engine


def _df(lo: int, hi: int) -> pd.DataFrame:
    return pd.DataFrame({"id": range(lo, hi), "a": range(lo, hi)})


def _csv_rows(path: Path) -> list[int]:
    if not path.exists():
        return []
    df = pd.read_csv(path, delimiter="\t")
    return df["total_filas"].tolist()


def _count(engine: sa.Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(sa.text("SELECT COUNT(*) FROM t")).scalar_one())


def r1_commit_every_partial_operation() -> None:
    """commit_every_n_chunks: una operación a medio confirmar se descarta del CSV con un aviso inexacto."""
    engine = _engine("r1")
    csv = TMP / "r1.csv"
    cap = _Capture()
    logging.getLogger("util_bbdd").addHandler(cap)
    loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1, commit_every_n_chunks=3, audit_csv_path=csv)

    def reader():  # 20 + 20 filas (2 lotes cada chunk); el 3.er chunk repite la PK 0 -> IntegrityError en el lote 5
        yield _df(0, 20)
        yield _df(20, 40)
        yield _df(0, 10)

    res = loader.load("t", [reader])
    logging.getLogger("util_bbdd").removeHandler(cap)
    pr = res.partition_results[0]
    warn = [r.getMessage() for r in cap.records if "se descartan" in r.getMessage()]
    print("R1 commit_every_n_chunks=3, chunk_size=10, chunks del lector 20/20/10 (el 3.º falla)")
    print(f"   BD: {_count(engine)} filas | PartitionResult.rows={pr.rows} | total_rows={res.total_rows}")
    print(f"   CSV: {_csv_rows(csv)} -> suma {sum(_csv_rows(csv))}")
    print(f"   aviso: {warn}")
    print(f"   error: {pr.error}")


def r2_strict_retry_commit_failure() -> None:
    """audit_strict + max_retries: si el COMMIT falla con OperationalError tras escribir el CSV, el reintento duplica."""
    for strict in (True, False):
        engine = _engine(f"r2_{strict}")
        csv = TMP / f"r2_{strict}.csv"
        state = {"fail": True}

        @sa.event.listens_for(engine, "commit")
        def _fail_once(conn, state=state):  # type: ignore[no-untyped-def]
            if state["fail"]:
                state["fail"] = False
                raise OperationalError("COMMIT", {}, Exception("conexión perdida en el commit (simulado)"))

        loader = ParallelBulkLoader(
            engine, chunk_size=10, max_workers=1, max_retries=1, audit_csv_path=csv, audit_strict=strict
        )

        def reader():
            yield _df(0, 20)
            yield _df(20, 40)

        res = loader.load("t", [reader])
        pr = res.partition_results[0]
        print(f"R2 audit_strict={strict}, max_retries=1, 1.er COMMIT falla con OperationalError")
        print(f"   BD: {_count(engine)} filas | retries={pr.retries} | error={pr.error}")
        print(f"   CSV: {_csv_rows(csv)} -> suma {sum(_csv_rows(csv))}")


def r3_fast_executemany_leak() -> None:
    """_resolve_table crea una BulkCrud con enable_fast_executemany=True aunque el loader se configurase con False."""
    try:
        engine = sa.create_engine("mssql+pyodbc://u:p@dsn_inexistente")
    except Exception as exc:  # noqa: BLE001
        print(f"R3 omitido: {exc}")
        return
    loader = ParallelBulkLoader(engine, max_workers=1, enable_fast_executemany=False, disable_constraints=True)
    before = engine.dialect.fast_executemany
    fake = sa.Table("t", sa.MetaData(), sa.Column("id", sa.Integer, primary_key=True))
    orig = BulkCrud.reflect_table
    BulkCrud.reflect_table = lambda self, name: fake  # type: ignore[method-assign,assignment]  # sin conexión
    try:
        loader._resolve_table("t")
    finally:
        BulkCrud.reflect_table = orig  # type: ignore[method-assign]
    print("R3 mssql+pyodbc, ParallelBulkLoader(enable_fast_executemany=False, disable_constraints=True)")
    print(f"   dialect.fast_executemany antes={before} después de _resolve_table={engine.dialect.fast_executemany}")


def r4_disabled_audit_warnings() -> None:
    """Con audit_csv_path=None (default) cada partición emite su WARNING de auditoría deshabilitada."""
    engine = _engine("r4")
    cap = _Capture()
    logging.getLogger("util_bbdd").addHandler(cap)
    loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=1)
    readers = [(lambda i=i: iter([_df(i * 10, i * 10 + 10)])) for i in range(8)]
    loader.load("t", readers)
    loader.load("t", [(lambda: iter([_df(1000, 1010)]))])
    logging.getLogger("util_bbdd").removeHandler(cap)
    n = sum(1 for r in cap.records if r.levelno == logging.WARNING and "deshabilitada" in r.getMessage())
    print(f"R4 audit_csv_path=None, 2 cargas (8 + 1 particiones): {n} WARNING 'Auditoría deshabilitada'")


def r5_invalid_audit_path_fails_late() -> None:
    """Una ruta de auditoría inválida no se valida en __init__: falla cada partición, ya dentro del pool."""
    engine = _engine("r5")
    blocker = TMP / "no_soy_directorio"
    blocker.write_text("x")
    cap = _Capture()
    logging.getLogger("util_bbdd").addHandler(cap)
    try:
        loader = ParallelBulkLoader(engine, chunk_size=10, max_workers=2, audit_csv_path=blocker / "audit.csv")
        created = True
    except Exception as exc:  # noqa: BLE001
        created = False
        print(f"R5 __init__ lanza {type(exc).__name__}")
    if created:
        res = loader.load("t", [(lambda i=i: iter([_df(i * 10, i * 10 + 10)])) for i in range(4)])
        tb = sum(1 for r in cap.records if r.exc_info)
        print(
            f"R5 __init__ acepta la ruta; load(): {len(res.partition_errors)} particiones en error, "
            f"{tb} WARNING con traza; 1.er error: {res.partition_errors[0][:90]}"
        )
    logging.getLogger("util_bbdd").removeHandler(cap)


if __name__ == "__main__":
    logging.getLogger("util_bbdd").setLevel(logging.DEBUG)
    logging.getLogger("util_bbdd").propagate = False
    r1_commit_every_partial_operation()
    r2_strict_retry_commit_failure()
    r3_fast_executemany_leak()
    r4_disabled_audit_warnings()
    r5_invalid_audit_path_fails_late()
