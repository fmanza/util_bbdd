"""Auditoría 0.21.0: ¿qué hace cada destino con un comentario de columna de 5000 caracteres (posible desde PostgreSQL)?"""

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
from util_bbdd.migrate.emitters.mysql import MySQLDDLEmitter
from util_bbdd.migrate.emitters.oracle import OracleDDLEmitter
from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.emitters.sqlserver import SQLServerDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable

logging.disable(logging.CRITICAL)
NS = "zz_util_bbdd_audit"
LONG = "x" * 5000


def table(target_type: str) -> CanonicalTable:
    col = CanonicalColumn(
        name="c", original_name="c", source_type="text", target_type=target_type, nullable=True, default=None,
        comment=LONG, ordinal=1,
    )
    return CanonicalTable("zzaud_long", "zzaud_long", "s", [col], [], [], [], "", [])


CASES = {
    "mysql": ("UTIL_BBDD_TEST_MYSQL_URL", MySQLDDLEmitter("utf8mb4", "utf8mb4_0900_ai_ci"), "VARCHAR(10)"),
    "mariadb": ("UTIL_BBDD_TEST_MARIADB_URL", MariaDBDDLEmitter("utf8mb4", "utf8mb4_bin"), "VARCHAR(10)"),
    "oracle": ("UTIL_BBDD_TEST_ORACLE_URL", OracleDDLEmitter(), "VARCHAR2(10)"),
    "sqlserver": ("UTIL_BBDD_TEST_MSSQL_URL", SQLServerDDLEmitter(), "NVARCHAR(10)"),
    "postgresql": ("UTIL_BBDD_TEST_POSTGRESQL_URL", PostgreSQLDDLEmitter(pg_schema=NS), "VARCHAR(10)"),
}
for engine_name, (env, emitter, target_type) in CASES.items():
    url = make_url(os.environ[env])
    admin = create_engine(url.set(database="master") if engine_name == "sqlserver" else url, isolation_level="AUTOCOMMIT")
    setup = {
        "mysql": [f"DROP DATABASE IF EXISTS {NS}", f"CREATE DATABASE {NS}"],
        "mariadb": [f"DROP DATABASE IF EXISTS {NS}", f"CREATE DATABASE {NS}"],
        "sqlserver": [f"IF DB_ID('{NS}') IS NOT NULL DROP DATABASE {NS}", f"CREATE DATABASE {NS}"],
        "postgresql": [f"DROP SCHEMA IF EXISTS {NS} CASCADE", f"CREATE SCHEMA {NS}"],
        "oracle": ['BEGIN EXECUTE IMMEDIATE \'DROP TABLE "ZZAUD_LONG"\'; EXCEPTION WHEN OTHERS THEN NULL; END;'],
    }[engine_name]
    with admin.connect() as conn:
        cur = conn.connection.dbapi_connection.cursor()
        for statement in setup:
            cur.execute(statement)
    admin.dispose()
    work_url = url.set(database=NS) if engine_name in ("mysql", "mariadb", "sqlserver") else url
    engine = create_engine(work_url, isolation_level="AUTOCOMMIT")
    result = "OK"
    with engine.connect() as conn:
        cur = conn.connection.dbapi_connection.cursor()
        for statement in emitter.emit_statements([table(target_type)]):
            try:
                cur.execute(statement)
            except Exception as err:  # noqa: BLE001
                result = f"ERROR en {statement.split()[0]} {statement.split()[1]}: {str(err).splitlines()[0][:110]}"
                break
    engine.dispose()
    print(f"{engine_name:10s} {result}")
    cleanup = {
        "mysql": [f"DROP DATABASE IF EXISTS {NS}"],
        "mariadb": [f"DROP DATABASE IF EXISTS {NS}"],
        "sqlserver": [
            f"IF DB_ID('{NS}') IS NOT NULL BEGIN ALTER DATABASE {NS} SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"DROP DATABASE {NS}; END"
        ],
        "postgresql": [f"DROP SCHEMA IF EXISTS {NS} CASCADE"],
        "oracle": ['BEGIN EXECUTE IMMEDIATE \'DROP TABLE "ZZAUD_LONG"\'; EXCEPTION WHEN OTHERS THEN NULL; END;'],
    }[engine_name]
    admin = create_engine(url.set(database="master") if engine_name == "sqlserver" else url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        cur = conn.connection.dbapi_connection.cursor()
        for statement in cleanup:
            cur.execute(statement)
    admin.dispose()
