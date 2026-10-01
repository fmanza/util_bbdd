import logging, pathlib, sqlite3, tempfile
import pandas as pd
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text
from util_bbdd.bulk import BulkCrud
logging.disable(logging.CRITICAL)
for label, kwargs in (("SA AUTOCOMMIT", {"isolation_level": "AUTOCOMMIT"}), ("sqlite3 autocommit=True", {"connect_args": {"autocommit": True}})):
    for bad in (False, True):
        d = pathlib.Path(tempfile.mkdtemp())
        eng = create_engine(f"sqlite:///{d/'a.db'}", **kwargs)
        Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(5), nullable=False)).create(eng)
        crud = BulkCrud(eng, chunk_size=4, on_error="isolate", rejects_csv_path=d/"r.csv", warn_if_audit_disabled=False)
        try:
            crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2, 3, 4], "v": ["a", None if bad else "b", "c", "d"]}), "items", False)
            out = "ok"
        except Exception as exc:
            out = type(exc).__name__
        other = sqlite3.connect(d/"a.db", timeout=1)
        try:
            n = other.execute("select count(*) from items").fetchone()[0]
            other.execute("create table zz (x int)"); other.commit(); lock = "sin bloqueo"
        except Exception as exc:
            lock = f"BLOQUEO ({exc})"
        print(f"{label} fila_mala={bad}: {out}; otra conexión ve {n} filas; {lock}")
        other.close(); eng.dispose()
