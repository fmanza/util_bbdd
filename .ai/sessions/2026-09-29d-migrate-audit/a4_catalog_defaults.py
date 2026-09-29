"""A4: cómo devuelven MariaDB y MySQL un DEFAULT/COMMENT con barra invertida, salto de línea, tabulador y comilla."""

import os

from sqlalchemy import create_engine

NS = "zz_util_bbdd_audit"
# Literal MySQL-family: \\ = barra, \n = salto, \t = tabulador, '' = comilla
LITERAL = r"'C:\\datos\\x\nsegunda\tfin''q'"
for env in ("UTIL_BBDD_TEST_MARIADB_URL", "UTIL_BBDD_TEST_MYSQL_URL"):
    engine = create_engine(os.environ[env], isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        cur = conn.connection.dbapi_connection.cursor()
        cur.execute(f"DROP DATABASE IF EXISTS {NS}")
        cur.execute(f"CREATE DATABASE {NS}")
        cur.execute(f"CREATE TABLE {NS}.t (id INT PRIMARY KEY, ruta VARCHAR(80) DEFAULT {LITERAL} COMMENT {LITERAL})")
        cur.execute(f"INSERT INTO {NS}.t (id) VALUES (1)")
        cur.execute(f"SELECT ruta FROM {NS}.t")
        value = cur.fetchone()[0]
        cur.execute(
            f"SELECT COLUMN_DEFAULT, COLUMN_COMMENT FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA = '{NS}' AND COLUMN_NAME = 'ruta'"
        )
        default, comment = cur.fetchone()
        print(env.split("_")[3], "valor:", repr(value))
        print("   COLUMN_DEFAULT:", repr(default))
        print("   COLUMN_COMMENT:", repr(comment))
        cur.execute(f"DROP DATABASE IF EXISTS {NS}")
    engine.dispose()
