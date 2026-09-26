"""Coste de BulkCrud.reflect_table en SQL Server con 200 tablas: total y parte de FK (FK anuladas por parche)."""
import sys
from time import perf_counter
from unittest.mock import patch
from sqlalchemy import text
sys.path.insert(0, "scripts")
import bench_dump as b
from util_bbdd.bulk import BulkCrud

eng = b.make_engine("mssql")
S = "zz_rf_dst"
N = 200
def drop(c):
    for t, fk in c.execute(text("SELECT OBJECT_NAME(parent_object_id), name FROM sys.foreign_keys WHERE schema_id = SCHEMA_ID(:s)"), {"s": S}).all():
        c.execute(text(f"ALTER TABLE {S}.{t} DROP CONSTRAINT {fk}"))
    for (t,) in c.execute(text("SELECT name FROM sys.tables WHERE schema_id = SCHEMA_ID(:s)"), {"s": S}).all():
        c.execute(text(f"DROP TABLE {S}.{t}"))
    c.execute(text(f"IF SCHEMA_ID('{S}') IS NOT NULL EXEC('DROP SCHEMA {S}')"))
try:
    with eng.begin() as c:
        drop(c)
        c.execute(text(f"EXEC('CREATE SCHEMA {S}')"))
        c.execute(text(f"CREATE TABLE {S}.t000 (id INT IDENTITY PRIMARY KEY, v VARCHAR(20))"))
        for i in range(1, N):
            c.execute(text(f"CREATE TABLE {S}.t{i:03d} (id INT IDENTITY PRIMARY KEY, parent_id INT REFERENCES {S}.t000 (id), v VARCHAR(20))"))
    names = [f"{S}.t{i:03d}" for i in range(N)]
    def run(label, ctx=None):
        crud = BulkCrud(eng, warn_if_audit_disabled=False)
        t = perf_counter()
        if ctx:
            with ctx:
                for n in names: crud.reflect_table(n)
        else:
            for n in names: crud.reflect_table(n)
        el = perf_counter() - t
        print(f"{label:28} {el:6.2f}s  {el / N * 1000:5.1f} ms/tabla", flush=True)
    run("calentamiento")
    for _ in range(2):
        run("reflect_table actual")
        run("sin FK (get_foreign_keys=[])", patch.object(type(eng.dialect), "get_foreign_keys", lambda *a, **k: []))
finally:
    with eng.begin() as c:
        drop(c)
    eng.dispose()
