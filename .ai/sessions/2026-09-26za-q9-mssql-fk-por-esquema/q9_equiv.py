"""Q9: _referred_tables por schema (sys.foreign_keys) == get_foreign_keys tabla a tabla, con pyodbc y pymssql."""
import os, sys
from sqlalchemy import create_engine, inspect
sys.path.insert(0, "scripts")
import bench_dump as b
from util_bbdd.dump.orchestrator import DumpOrchestrator as D

url = next(v for k, v in os.environ.items() if k.endswith("_MSSQL_URL"))
engines = {"pyodbc": b.make_engine("mssql"), "pymssql": create_engine(url)}
for drv, eng in engines.items():
    for schema in ("dump_src", "dump_dst", None):
        insp = inspect(eng)
        tables = insp.get_table_names(schema=schema)
        fast = D._referred_tables(tables, insp, schema)
        slow = {t: [fk.get("referred_table") or "" for fk in insp.get_foreign_keys(t, schema=schema)] for t in tables}
        same = {t: sorted(v) for t, v in fast.items()} == {t: sorted(v) for t, v in slow.items()}
        print(f"{drv:8} schema={schema!s:9} tablas={len(tables):3} fk={sum(map(len, slow.values())):3} iguales={same}")
    upper = [t.upper() for t in inspect(eng).get_table_names(schema="dump_src")]
    print(f"{drv:8} nombres en mayúsculas:", D._referred_tables(upper, inspect(eng), "dump_src"))
    print(f"{drv:8} orden:", D._topological_sort(inspect(eng).get_table_names(schema="dump_src"), inspect(eng), "dump_src"))
    eng.dispose()
