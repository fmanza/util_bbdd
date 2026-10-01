import csv, logging, pathlib, tempfile
import pandas as pd
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from util_bbdd.bulk import ParallelBulkLoader
logging.disable(logging.CRITICAL)
for disable in (False, True):
    for max_rejects in (None, 1):
        d = pathlib.Path(tempfile.mkdtemp())
        eng = create_engine(f"sqlite:///{d/'x.db'}")
        Table("items", MetaData(), Column("id", Integer, primary_key=True), Column("v", String(10), nullable=False)).create(eng)
        reader = lambda: iter([pd.DataFrame({"id": [1, 2, 3], "v": ["a", None, "c"]}), pd.DataFrame({"id": [4, 5, 6], "v": ["d", None, "f"]})])
        r = ParallelBulkLoader(eng, max_workers=1, chunk_size=10, disable_constraints=disable, on_error="isolate",
                               rejects_csv_path=d/"r.csv", max_rejects=max_rejects).load("items", [reader])
        rows = [int(x["fila"]) for x in csv.DictReader((d/"r.csv").open(encoding="utf-8"), delimiter="\t")] if (d/"r.csv").exists() else []
        print(f"disable_constraints={disable} max_rejects={max_rejects}: filas={rows} errores={len(r.partition_errors)} rejected={r.rows_rejected}")
