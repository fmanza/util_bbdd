"""A8: ¿dos columnas (o tablas) que solo difieren en mayúsculas rompen el DDL hacia Oracle?

Origen PostgreSQL real (schema zz_util_bbdd_audit) → MigrationPlanner → OracleDDLEmitter → Oracle del banco.
"""

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from util_bbdd import SyncDatabaseManager
from util_bbdd.migrate import MigrationPlanner

logging.disable(logging.CRITICAL)
NS = "zz_util_bbdd_audit"


def raw(url: object, statements: list[str]) -> list[str]:
    engine = create_engine(url, isolation_level="AUTOCOMMIT")  # type: ignore[call-overload]
    errors: list[str] = []
    with engine.connect() as conn:
        cur = conn.connection.dbapi_connection.cursor()
        for statement in statements:
            try:
                cur.execute(statement)
            except Exception as err:  # noqa: BLE001
                errors.append(f"{statement[:50]!r} -> {str(err).splitlines()[0][:80]}")
    engine.dispose()
    return errors


pg = make_url(os.environ["UTIL_BBDD_TEST_POSTGRESQL_URL"])
ora = make_url(os.environ["UTIL_BBDD_TEST_ORACLE_URL"])
raw(pg, [f"DROP SCHEMA IF EXISTS {NS} CASCADE", f"CREATE SCHEMA {NS}"])
raw(
    pg,
    [
        f'CREATE TABLE {NS}.zzaud_cols (id INT PRIMARY KEY, "Nombre" VARCHAR(20), nombre VARCHAR(20))',
        f'CREATE TABLE {NS}."ZZAUD_T" (id INT PRIMARY KEY)',
        f"CREATE TABLE {NS}.zzaud_t (id INT PRIMARY KEY)",
    ],
)
manager = SyncDatabaseManager(
    "postgresql",
    {"host": pg.host, "port": pg.port, "user": pg.username, "password": pg.password, "database": pg.database},
    use_pool=False,
)
try:
    plan = MigrationPlanner(source_engine="postgresql", target_engine="oracle").plan(manager, NS)
finally:
    manager.close()
print("errores del plan:", plan.error_count)
for warning in plan.warnings:
    if "CASE" in warning.oracle_type:
        print("  aviso:", warning.severity, warning.message[:110])
statements = plan.emit_statements()
cleanup = ['DROP TABLE "ZZAUD_COLS"', 'DROP TABLE "ZZAUD_T"']
raw(ora, cleanup)
for error in raw(ora, statements):
    print("  ORACLE:", error)
raw(ora, cleanup)
raw(pg, [f"DROP SCHEMA IF EXISTS {NS} CASCADE"])
print("limpieza hecha")
