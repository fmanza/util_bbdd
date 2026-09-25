import cProfile, pstats, tempfile, logging, io
from pathlib import Path
from time import perf_counter
from util_bbdd.bulk import AuditManager
logging.basicConfig(level=logging.WARNING)
p = Path(tempfile.mkdtemp()) / "a.csv"
m = AuditManager(p)
for _ in range(200): m.registrar_operacion("t","SQLITE","INSERT",5000,0.1)
pr = cProfile.Profile(); pr.enable()
for _ in range(3000): m.registrar_operacion("t","SQLITE","INSERT",5000,0.1)
pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(12); print(s.getvalue()[:3500])
# alternativas: handle abierto persistente
import csv
N=3000
t0=perf_counter()
with open(p.with_name("b.csv"),"a",newline="",encoding="utf-8") as fh:
    w=csv.writer(fh,delimiter="\t")
    for _ in range(N): w.writerow(["2026-09-25 10:00:00","t","SQLITE","INSERT",5000,"0,100","No"]); fh.flush()
print(f"handle persistente + flush por fila: {(perf_counter()-t0)/N*1e6:.1f} us")
t0=perf_counter()
for _ in range(N):
    with open(p.with_name("c.csv"),"a",newline="",encoding="utf-8") as fh:
        csv.writer(fh,delimiter="\t").writerow(["2026-09-25 10:00:00","t","SQLITE","INSERT",5000,"0,100","No"])
print(f"solo open/append/close: {(perf_counter()-t0)/N*1e6:.1f} us")
t0=perf_counter()
for _ in range(N): p.resolve()
print(f"Path.resolve(): {(perf_counter()-t0)/N*1e6:.1f} us")
t0=perf_counter()
for _ in range(N): p.parent.mkdir(parents=True, exist_ok=True)
print(f"mkdir exist_ok: {(perf_counter()-t0)/N*1e6:.1f} us")
t0=perf_counter()
for _ in range(N): p.exists()
print(f"exists(): {(perf_counter()-t0)/N*1e6:.1f} us")
