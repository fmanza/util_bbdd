import logging, pathlib, sqlite3, tempfile
import pandas as pd
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
import util_bbdd.bulk._support.rejects as rj
from util_bbdd.bulk import BulkCrud
logging.disable(logging.CRITICAL)

def patched(connection):
    if getattr(getattr(connection, "dialect", None), "name", None) == "sqlite":
        driver = connection.connection.driver_connection
        legacy = getattr(driver, "autocommit", sqlite3.LEGACY_TRANSACTION_CONTROL) == sqlite3.LEGACY_TRANSACTION_CONTROL
        if legacy and driver.isolation_level is not None and not driver.in_transaction:
            driver.execute("BEGIN")
    return connection.begin_nested()
rj._savepoint = patched

for bad in (False, True):
    d = pathlib.Path(tempfile.mkdtemp())
    eng = create_engine(f"sqlite:///{d/'a.db'}", connect_args={"autocommit": True})
    Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(5), nullable=False)).create(eng)
    crud = BulkCrud(eng, chunk_size=4, on_error="isolate", rejects_csv_path=d/"r.csv", warn_if_audit_disabled=False)
    crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2, 3, 4], "v": ["a", None if bad else "b", "c", "d"]}), "items", False)
    other = sqlite3.connect(d/"a.db", timeout=1)
    try:
        n = other.execute("select count(*) from items").fetchone()[0]
        other.execute("create table zz (x int)"); other.commit(); lock = "sin bloqueo"
    except Exception as exc:
        lock = f"BLOQUEO ({exc})"
    print(f"autocommit=True con arreglo, fila_mala={bad}: otra conexión ve {n} filas; {lock}")
    other.close(); eng.dispose()
