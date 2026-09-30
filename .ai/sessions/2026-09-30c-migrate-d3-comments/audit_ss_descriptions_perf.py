"""Auditoría 0.21.0: coste del extractor de SQL Server con MS_Description en todas las tablas y columnas."""

import logging
import os
import time

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from util_bbdd import SyncDatabaseManager
from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor

logging.disable(logging.CRITICAL)
NS = "zz_util_bbdd_audit"
N = 200
url = make_url(os.environ["UTIL_BBDD_TEST_MSSQL_URL"])


def run(target_url: object, statements: list[str]) -> None:
    engine = create_engine(target_url, isolation_level="AUTOCOMMIT")  # type: ignore[call-overload]
    with engine.connect() as conn:
        cur = conn.connection.dbapi_connection.cursor()
        for statement in statements:
            cur.execute(statement)
    engine.dispose()


drop = (
    f"IF DB_ID('{NS}') IS NOT NULL BEGIN ALTER DATABASE {NS} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
    f"DROP DATABASE {NS}; END"
)
run(url.set(database="master"), [drop, f"CREATE DATABASE {NS}"])
statements: list[str] = []
for k in range(N):
    statements.append(f"CREATE TABLE t{k:03d} (id INT PRIMARY KEY, a INT, b VARCHAR(20), c DATE, d INT, e INT)")
    prop = f"EXEC sys.sp_addextendedproperty N'MS_Description', N'{{v}}', N'SCHEMA', N'dbo', N'TABLE', N't{k:03d}'"
    statements.append(prop.format(v=f"tabla {k}"))
    statements += [prop.format(v=f"col {c}") + f", N'COLUMN', N'{c}'" for c in ("id", "a", "b", "c", "d", "e")]
run(url.set(database=NS), statements)
manager = SyncDatabaseManager(
    "sqlserver",
    {"host": url.host, "port": url.port, "user": url.username, "password": url.password, "database": NS},
    use_pool=False,
)
try:
    times = []
    for _ in range(3):
        start = time.perf_counter()
        tables = SQLServerSchemaExtractor(manager).extract("dbo")
        times.append(time.perf_counter() - start)
    commented = sum(1 for t in tables for c in t.columns if c.comment)
    print(f"tablas={len(tables)} columnas con comentario={commented} tablas con comentario="
          f"{sum(1 for t in tables if t.comment)} extract()={min(times):.3f}s")
finally:
    manager.close()
    run(url.set(database="master"), [drop])
