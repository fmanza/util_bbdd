"""Q9: coste fijo por tabla del volcado con muchas tablas pequeñas (esquemas zz_q9_src/zz_q9_dst, se borran)."""
import json, sys, tempfile
from pathlib import Path
from time import perf_counter
from sqlalchemy import text
sys.path.insert(0, "scripts")
import bench_dump as b
engine_key, n = sys.argv[1], int(sys.argv[2])
SRC, DST = "zz_q9_src", "zz_q9_dst"
eng = b.make_engine(engine_key)
def drop(c):
    for s in (SRC, DST):
        if engine_key == "postgresql":
            c.execute(text(f"DROP SCHEMA IF EXISTS {s} CASCADE"))
        elif engine_key == "mysql":
            c.execute(text(f"DROP DATABASE IF EXISTS {s}"))
        else:
            for t, fk in c.execute(text("SELECT OBJECT_NAME(parent_object_id), name FROM sys.foreign_keys WHERE schema_id = SCHEMA_ID(:s)"), {"s": s}).all():
                c.execute(text(f"ALTER TABLE {s}.{t} DROP CONSTRAINT {fk}"))
            for (t,) in c.execute(text("SELECT name FROM sys.tables WHERE schema_id = SCHEMA_ID(:s)"), {"s": s}).all():
                c.execute(text(f"DROP TABLE {s}.{t}"))
            c.execute(text(f"IF SCHEMA_ID('{s}') IS NOT NULL EXEC('DROP SCHEMA {s}')"))
def create(c, s):
    if engine_key == "postgresql": c.execute(text(f"CREATE SCHEMA {s}"))
    elif engine_key == "mysql": c.execute(text(f"CREATE DATABASE {s}"))
    else: c.execute(text(f"EXEC('CREATE SCHEMA {s}')"))
    c.execute(text(f"CREATE TABLE {s}.t000 (id INT PRIMARY KEY, v VARCHAR(20))"))
    c.execute(text(f"INSERT INTO {s}.t000 VALUES " + ",".join(f"({i},'x')" for i in range(1, 101))))
    for i in range(1, n):
        c.execute(text(f"CREATE TABLE {s}.t{i:03d} (id INT PRIMARY KEY, parent_id INT REFERENCES {s}.t000 (id), v VARCHAR(20))"))
        if s == SRC:
            c.execute(text(f"INSERT INTO {s}.t{i:03d} VALUES " + ",".join(f"({j},{j},'x')" for j in range(1, 101))))
try:
    with eng.begin() as c:
        drop(c)
    with eng.begin() as c:
        create(c, SRC); create(c, DST)
    b.install_instrumentation()
    import collections, re
    from sqlalchemy import event
    from sqlalchemy.engine import reflection
    SQLT = collections.defaultdict(lambda: [0, 0.0])
    INSP = collections.defaultdict(lambda: [0, 0.0])
    def _key(stmt):
        st = " ".join(stmt.split())
        m = re.match(r"(TRUNCATE TABLE|DELETE FROM|INSERT INTO|SELECT COUNT|ALTER TABLE \S+ (?:NO)?CHECK|ALTER TABLE|UPDATE|DBCC|SET)", st, re.I)
        return m.group(1).upper() if m else "SQL:" + st[:70]
    @event.listens_for(eng, "before_cursor_execute")
    def _b(conn, cur, stmt, params, ctx, many):
        conn.info["_t0"] = perf_counter()
    @event.listens_for(eng, "after_cursor_execute")
    def _a(conn, cur, stmt, params, ctx, many):
        k = _key(stmt); SQLT[k][0] += 1; SQLT[k][1] += perf_counter() - conn.info.pop("_t0", perf_counter())
    for name in ("get_table_names", "get_foreign_keys", "get_columns", "get_pk_constraint", "get_indexes", "get_unique_constraints", "has_table"):
        orig = getattr(reflection.Inspector, name)
        def wrap(*a, _o=orig, _n=name, **k):
            t0 = perf_counter()
            try:
                return _o(*a, **k)
            finally:
                INSP[_n][0] += 1; INSP[_n][1] += perf_counter() - t0
        setattr(reflection.Inspector, name, wrap)
    from util_bbdd.dump import DumpConfig, DumpOrchestrator
    t = perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        r = DumpOrchestrator(DumpConfig(source_engine=eng, target_engine=eng, source_schema=SRC, target_schema=DST, output_dir=Path(tmp))).run()
    total = perf_counter() - t
    ok = sum(1 for x in r.table_results if x.status == "success")
    ph = {k: round(v, 2) for k, v in b.STATS.items()}
    print("INSPECTOR:", {k: (v[0], round(v[1], 2)) for k, v in INSP.items()})
    for k, v in sorted(SQLT.items(), key=lambda kv: -kv[1][1])[:25]:
        print(f"  {v[1]:7.2f}s {v[0]:5d}x  {k}")
    print(json.dumps({"engine": engine_key, "tables": n, "success": ok, "total_s": round(total, 1), "ms_por_tabla": round(total / n * 1000), "phases": ph}))
finally:
    with eng.begin() as c:
        drop(c)
    eng.dispose()
