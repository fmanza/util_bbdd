from time import perf_counter
from sqlalchemy import text, MetaData, Table, Column, Integer, String, insert
from sqlalchemy.dialects import mysql, mssql
from sqlalchemy.dialects.mysql import pymysql as pm
cols = [f"c{i}" for i in range(10)]
rows = 1000
vals = ", ".join("(" + ", ".join(f":p{r}_{c}" for c in range(10)) + ")" for r in range(rows))
sql = f"INSERT INTO t ({', '.join(cols)}) VALUES {vals}"
params = {f"p{r}_{c}": r for r in range(rows) for c in range(10)}
d = pm.dialect()
N = 20
s = perf_counter()
for _ in range(N):
    tc = text(sql)
t_text = (perf_counter() - s) / N
s = perf_counter()
for _ in range(N):
    tc = text(sql); comp = tc.compile(dialect=d); p = comp.construct_params(params)
t_comp = (perf_counter() - s) / N
print(f"MySQL multi-row 1000x10: text()={t_text*1e3:.1f}ms  text+compile+params={t_comp*1e3:.1f}ms por sub-lote -> por 1M filas: {t_comp*1000:.1f}s")
# DELETE IN 5000
ph = ", ".join(f":pk_{i}_0" for i in range(5000))
dsql = f"DELETE FROM t WHERE id IN ({ph})"
dp = {f"pk_{i}_0": i for i in range(5000)}
s = perf_counter()
for _ in range(N):
    tc = text(dsql); comp = tc.compile(dialect=d); comp.construct_params(dp)
td = (perf_counter() - s) / N
print(f"DELETE IN 5000: {td*1e3:.1f}ms por lote -> por 1M filas: {td*200:.1f}s")
# generar_sql: template literal vs per-row compile
md = MetaData(); tab = Table("t", md, Column("id", Integer, primary_key=True), *[Column(c, String(50)) for c in cols])
from util_bbdd.bulk._support.sql_helpers import generate_insert_sql
recs = [{"id": i, **{c: f"v'{i}" for c in cols}} for i in range(2000)]
md2 = mssql.dialect()
s = perf_counter(); generate_insert_sql(insert(tab), recs, md2); tg = perf_counter() - s
# prototipo: literal processors
procs = {c.name: c.type.literal_processor(md2) for c in tab.columns}
prep = md2.identifier_preparer
head = f"INSERT INTO {prep.format_table(tab)} ({', '.join(prep.quote(k) for k in recs[0])}) VALUES "
def lit(k, v):
    return "NULL" if v is None else procs[k](v) if procs[k] else str(v)
s = perf_counter(); out = [head + "(" + ", ".join(lit(k, v) for k, v in r.items()) + ");" for r in recs]; tp = perf_counter() - s
ref = generate_insert_sql(insert(tab), recs[:1], md2)[0]
print(f"generar_sql 2000 filas: actual={tg:.2f}s ({tg/2000*1e6:.0f}us/fila) prototipo={tp*1e3:.1f}ms ({tg/tp:.0f}x)")
print("ref :", ref[:140]); print("prot:", out[0][:140])
