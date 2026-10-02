import csv, logging, pathlib, tempfile
import numpy as np, pandas as pd
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.exc import IntegrityError
from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk._support import oracle_batch_errors
from util_bbdd.bulk._support.rejects import Isolator
logging.disable(logging.CRITICAL)
d = pathlib.Path(tempfile.mkdtemp())
eng = create_engine(f"sqlite:///{d/'x.db'}")
Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10), nullable=False)).create(eng)
crud = BulkCrud(eng, on_error="isolate", rejects_csv_path=d/"r.csv", warn_if_audit_disabled=False)
# H1: partition con prefijo de fórmula
with crud.rejects_scope(partition="=HYPERLINK(\"x\")"):
    crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2], "v": ["a", None]}), "items", False)
print("H1 particion:", [r["particion"] for r in csv.DictReader((d/"r.csv").open(encoding="utf-8"), delimiter="\t")])
# H2: row_offset numpy
try:
    with crud.rejects_scope(row_offset=np.int64(5)):
        pass
    print("H2 numpy: aceptado")
except ValueError as e:
    print("H2 numpy: ValueError")
# H4: presupuesto común en modo batcherrors
class E:
    def __init__(s, o): s.offset, s.full_code = o, "ORA-00001"
    def __str__(s): return "ORA-00001: x"
class SP:
    def commit(s): pass
    def rollback(s): pass
class C:
    def begin_nested(s): return SP()
def send(items):
    sink = oracle_batch_errors._SINK.get()
    if sink is None: raise IntegrityError("x", {}, Exception("ORA-00001"))
    sink.extend([E(0), E(2)])
iso = Isolator(on_reject=lambda *a: None, max_rejects=2, batch_errors=True, already_rejected=1)
try:
    iso.run_records(C(), [{"id": i} for i in range(4)], send, first_row=0); print("H4: sin error, rejected", iso.rejected)
except IntegrityError:
    print("H4: falla al superar el presupuesto común; rejected =", iso.rejected)
