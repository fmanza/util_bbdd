"""D1 paso 0: coste por consulta agrupada en PostgreSQL (¿qué consulta domina los 1,5 s?)."""

import importlib.util
import statistics
import sys
import time

from pathlib import Path

spec = importlib.util.spec_from_file_location("d1", Path(__file__).with_name("d1_baseline.py"))
assert spec and spec.loader
d1 = importlib.util.module_from_spec(spec)
sys.argv = ["d1", "200", "20"]
spec.loader.exec_module(d1)

engine = "postgresql"
params, schema = d1._setup(engine)
manager = d1.SyncDatabaseManager(engine, params, use_pool=False)
try:
    counting = d1.CountingManager(manager)
    d1.MigrationPlanner(source_engine=engine, target_engine="oracle", view_strategy="passthrough").plan(counting, schema)
    for sql, sample in counting.samples.items():
        stripped = d1._WHERE_FILTER.sub("WHERE ", d1._AND_FILTER.sub("", sql))
        remaining = {k: v for k, v in sample.items() if k not in d1._OBJECT_PARAMS}
        times = []
        for _ in range(3):
            start = time.perf_counter()
            rows = manager.execute_custom_many(stripped, remaining)
            times.append(time.perf_counter() - start)
        print(f"{1000 * statistics.median(times):8.1f} ms  {len(rows):6d} filas  {' '.join(sql.split())[:110]}")
finally:
    manager.close()
    d1._teardown(engine)
