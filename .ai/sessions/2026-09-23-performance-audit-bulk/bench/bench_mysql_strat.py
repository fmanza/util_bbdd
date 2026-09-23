import cProfile, pstats, io
from time import perf_counter
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, insert
from util_bbdd.bulk._execution.batch import MySQLMultiRowInsertStrategy, DefaultInsertStrategy
eng = create_engine("sqlite://")
md = MetaData(); cols = [f"c{i}" for i in range(9)]
tab = Table("t", md, Column("id", Integer, primary_key=True), *[Column(c, String(50)) for c in cols]); md.create_all(eng)
N = 100_000
recs = [{"id": i, **{c: f"v{i}" for c in cols}} for i in range(N)]
for name, strat in (("default_executemany", DefaultInsertStrategy()), ("mysql_multirow", MySQLMultiRowInsertStrategy())):
    with eng.begin() as c:
        c.execute(tab.delete())
    with eng.begin() as c:
        s = perf_counter()
        for i in range(0, N, 5000):
            strat.execute(connection=c, stmt=insert(tab), records=recs[i:i+5000])
        print(f"{name}: {perf_counter()-s:.2f}s / 100K filas")
pr = cProfile.Profile()
with eng.begin() as c:
    c.execute(tab.delete())
    pr.enable(); MySQLMultiRowInsertStrategy().execute(connection=c, stmt=insert(tab), records=recs[:20000]); pr.disable()
st = io.StringIO(); pstats.Stats(pr, stream=st).sort_stats("cumulative").print_stats(12); print(st.getvalue()[:2500])
